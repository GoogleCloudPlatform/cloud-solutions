# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ============================================================================
# Credential broker (ADR-0014 D2 / B4) - live in the sandbox since 2026-11-04 (Terraform-managed
# since the 2026-11-06 adoption)
#
# The broker service account becomes the only identity with
# roles/iam.serviceAccountTokenCreator on tenant service accounts (ct-*). The runtime keeps only
# roles/run.invoker on the broker. Staged (docs/runbooks/credential_broker_b4.md):
#   1. enable_credential_broker = true          -> broker SA + TokenCreator on ct-* + service
#   2. deploy the broker image                  -> invoker = runtime SA only, no allUsers
#   3. credential_broker_url = <broker URL>     -> runtime mints via RemoteBrokerBackend; verify
#   4. runtime_keeps_token_creator = false      -> runtime loses TokenCreator on ct-*
#   5. live 403 test (tests/breach_suite/test_live_credential_broker.py)
# ============================================================================

locals {
  # Deterministic Cloud Run URL. Use this exact string for BOTH the broker's
  # BROKER_EXPECTED_AUDIENCE and the runtime's CREDENTIAL_BROKER_URL (var.credential_broker_url):
  # the runtime requests its ID token for that audience and the broker requires it.
  credential_broker_url           = "https://cymbal-credential-broker-${data.google_project.current.number}.${var.region}.run.app"
  effective_credential_broker_url = var.credential_broker_url != "" ? var.credential_broker_url : ((var.enable_credential_broker && !var.runtime_keeps_token_creator) ? local.credential_broker_url : "")
  auto_agent_broker_callers = (var.enable_agent_runtimes && var.organization_id != "") ? [
    for svc_name in values(var.agent_runtime_service_map) :
    "principal://agents.global.org-${var.organization_id}.system.id.goog/resources/run/projects/${data.google_project.current.number}/locations/${var.region}/services/${svc_name}"
  ] : []
  broker_allowed_callers = join(",", distinct(concat(
    var.broker_keep_runtime_caller ? [google_service_account.pooled_agent_runtime.email] : [],
    var.additional_broker_allowed_callers,
    local.auto_agent_broker_callers,
  )))
}

resource "google_service_account" "credential_broker" {
  count        = var.enable_credential_broker ? 1 : 0
  account_id   = "cymbal-broker-sa"
  display_name = "Cymbal credential broker (ADR-0014 B4)" # matches the live sandbox SA
  # Only identity allowed to mint ct-* tokens; invoked only by the runtime SA.
  depends_on = [google_project_service.enabled_apis]
}

# TokenCreator on each tenant SA: modules/tenant (broker_impersonates_tenant).

# Verify broker-audience context tokens with the public key only.
resource "google_kms_crypto_key_iam_member" "broker_context_key_viewer" {
  count         = var.enable_credential_broker ? 1 : 0
  crypto_key_id = google_kms_crypto_key.context_signing.id
  role          = "roles/cloudkms.publicKeyViewer"
  member        = "serviceAccount:${google_service_account.credential_broker[0].email}"
}

resource "google_project_iam_member" "broker_log_writer" {
  count   = var.enable_credential_broker ? 1 : 0
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.credential_broker[0].email}"
}

resource "google_project_iam_member" "broker_firestore_user" {
  count   = (var.enable_credential_broker && var.enable_live_mode) ? 1 : 0
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.credential_broker[0].email}"
}

resource "google_cloud_run_v2_service" "credential_broker" {
  count               = var.enable_credential_broker ? 1 : 0
  name                = "cymbal-credential-broker"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL" # IAM-only (no allUsers); internal ingress needs VPC egress on the runtime
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  template {
    service_account = google_service_account.credential_broker[0].email
    scaling {
      max_instance_count = 1 # in-process replay store (single instance until a shared store)
    }
    timeout                          = "300s"
    max_instance_request_concurrency = 80
    containers {
      image   = var.broker_container_image
      command = ["uvicorn"]
      resources {
        limits            = { cpu = "1000m", memory = "512Mi" } # API's canonical form (no diff)
        cpu_idle          = true                                # CPU only during requests (live setting)
        startup_cpu_boost = true
      }
      args = ["broker_service.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
      env {
        name  = "BROKER_ALLOWED_CALLERS"
        value = local.broker_allowed_callers
      }
      env {
        name  = "BROKER_EXPECTED_AUDIENCE"
        value = local.credential_broker_url
      }
      env {
        name  = "CYMBAL_ENV"
        value = var.platform_environment
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "TENANT_SA_TOKEN_TTL_SECONDS"
        value = tostring(var.token_and_session_policy.tenant_sa_token_ttl_seconds)
      }
      dynamic "env" {
        for_each = merge(
          var.require_agent_binding ? {
            BROKER_REQUIRE_AGENT_BINDING   = "1"
            CONTEXT_TOKEN_REQUIRE_AGENT_ID = "1"
          } : {},
          var.enable_live_mode ? {
            FIRESTORE_REVOCATION_STORE = "1"
            FIRESTORE_DATABASE         = google_firestore_database.tenant_memory_bank.name
          } : {},
        )
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  depends_on = [google_project_service.enabled_apis]

  lifecycle {
    # `scaling` (service level) is server-defaulted (0 -> null diff on every plan); per-revision
    # limits live in template.scaling.
    ignore_changes = [template[0].containers[0].image, client, client_version, scaling]
  }
}

# The runtime SA is the only invoker until B5 S3.6 (when agent principals replace it).
# Never add allUsers / allAuthenticatedUsers.
resource "google_cloud_run_v2_service_iam_member" "runtime_invokes_broker" {
  count    = var.enable_credential_broker && var.broker_keep_runtime_caller ? 1 : 0
  name     = google_cloud_run_v2_service.credential_broker[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pooled_agent_runtime.email}"
}

output "credential_broker_url" {
  description = "Set var.credential_broker_url to exactly this at B4 step 3; empty until enabled."
  value       = var.enable_credential_broker ? local.credential_broker_url : ""
}

output "credential_broker_sa_email" {
  description = "Credential broker identity (ADR-0014 B4); empty until enabled."
  value       = var.enable_credential_broker ? google_service_account.credential_broker[0].email : ""
}
