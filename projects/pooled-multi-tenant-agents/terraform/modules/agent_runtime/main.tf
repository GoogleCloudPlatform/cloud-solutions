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
# Per-agent Cloud Run runtime service (ADR-0014 B5 / ADR-0016 Layer 3)
#
# Each catalog agent runs in its own Cloud Run service deployed with Cloud Run
# Agent Identity (`--identity-type=agent-identity --functional-type=agent
# --identity-certificate` on the gcloud beta track, which is immutable at
# creation time; see docs/runbooks/b5_agent_runtime_rollout.md).
#
# Least privilege:
# - Inbound (`roles/run.invoker`): ONLY the gateway SA (`var.gateway_service_account_email`).
#   Never grant public or unauthenticated invoker bindings.
# - Outbound (granted to the SPIFFE Agent Identity `principal://...`):
#   * `roles/cloudkms.publicKeyViewer` on `ws2-context-signing` (verify only, never sign).
#   * `roles/run.invoker` on `cymbal-credential-broker`.
#   * `roles/aiplatform.user` on the project (only when `var.enable_live_mode = true`).
#   * ZERO signing keys, ZERO tenant SA impersonation (`ct-*`), ZERO direct tenant data-plane access.
# ============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.50"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.50"
    }
  }
}

locals {
  agent_principal            = "principal://agents.global.org-${var.organization_id}.system.id.goog/resources/run/projects/${var.project_number}/locations/${var.region}/services/${var.service_name}"
  agent_spiffe_id            = "spiffe://agents.global.org-${var.organization_id}.system.id.goog/resources/run/projects/${var.project_number}/locations/${var.region}/services/${var.service_name}"
  service_url                = "https://${var.service_name}-${var.project_number}.${var.region}.run.app"
  expected_audience          = var.expected_audience != "" ? var.expected_audience : local.service_url
  context_signing_version_id = "${var.context_signing_key_id}/cryptoKeyVersions/${var.context_signing_key_version}"
}

resource "google_cloud_run_v2_service" "agent_runtime" {
  provider            = google-beta
  project             = var.project_id
  name                = var.service_name
  location            = var.region
  launch_stage        = "BETA"
  ingress             = "INGRESS_TRAFFIC_ALL" # IAM-only (gateway SA is the sole invoker)
  deletion_protection = var.deletion_protection
  labels              = var.labels

  template {
    service_account                  = null
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 1 # in-process per-tenant rate-limit state until shared Redis store
    }

    dynamic "vpc_access" {
      for_each = (var.enable_live_mode && var.enable_vpc_access) ? [1] : []
      content {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = var.vpc_network_name
          subnetwork = var.vpc_network_name
        }
      }
    }

    containers {
      image   = var.runtime_image
      command = ["uvicorn"]
      args = [
        "runtime_service.main:create_app",
        "--factory",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
      ]

      resources {
        limits            = { cpu = "1000m", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "CYMBAL_ENV"
        value = var.environment
      }
      env {
        name  = "CYMBAL_LIVE_GCP"
        value = var.enable_live_mode ? "1" : "0"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_REGION"
        value = var.region
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "RUNTIME_AGENT_ID"
        value = var.agent_id
      }
      env {
        name  = "RUNTIME_ALLOWED_CALLERS"
        value = var.gateway_service_account_email
      }
      env {
        name  = "RUNTIME_EXPECTED_AUDIENCE"
        value = local.expected_audience
      }
      env {
        name  = "CREDENTIAL_BROKER_URL"
        value = var.credential_broker_url
      }
      env {
        name  = "CONTEXT_SIGNING_KMS_KEY"
        value = local.context_signing_version_id
      }
      env {
        name  = "CONTEXT_TOKEN_KMS_KEY_VERSION"
        value = local.context_signing_version_id
      }
      env {
        name  = "CONTEXT_TOKEN_REQUIRE_KMS"
        value = "1"
      }
      env {
        name  = "CONTEXT_TOKEN_REQUIRE_AGENT_ID"
        value = var.require_agent_binding ? "1" : "0"
      }

      dynamic "env" {
        for_each = merge(
          var.agent_sandbox_reasoning_engine_name != "" ? {
            AGENT_SANDBOX_REASONING_ENGINE_NAME = var.agent_sandbox_reasoning_engine_name
            MEMORY_BANK_REASONING_ENGINE        = var.agent_sandbox_reasoning_engine_name
          } : {},
          var.agent_sandbox_code_template != "" ? { AGENT_SANDBOX_CODE_TEMPLATE = var.agent_sandbox_code_template } : {},
          var.agent_sandbox_shell_template != "" ? { AGENT_SANDBOX_SHELL_TEMPLATE = var.agent_sandbox_shell_template } : {},
          var.enable_platform_live_resources ? {
            MODEL_ARMOR_TEMPLATE_ID = var.model_armor_template_id
            DLP_INSPECT_TEMPLATE    = var.dlp_inspect_template_id
            DLP_DEIDENTIFY_TEMPLATE = var.dlp_deidentify_template_id
            KMS_KEYRING_NAME        = var.kms_keyring_name
            RUNBOOK_BUCKET_NAME     = var.runbook_bucket_name
            BIGQUERY_DATASET        = var.analytics_dataset_id
            FIRESTORE_DATABASE      = var.firestore_database_name
          } : {},
          var.enable_live_mode ? { FIRESTORE_REVOCATION_STORE = "1" } : {},
          (var.enable_live_mode && var.enable_redis_tls) ? { REDIS_TLS_SECRET_VERSION = var.redis_tls_secret_version } : ((var.enable_live_mode && var.enable_memorystore_redis && !var.enable_redis_tls) ? { REDIS_URL = var.redis_url } : {}),
          (var.enable_live_mode && var.enable_alloydb_primary_auth) ? {
            DATABASE_URL            = "postgresql://${var.alloydb_primary_ip}:5432/postgres"
            ALLOYDB_TENANT_IAM_AUTH = "1"
          } : {},
        )
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  lifecycle {
    # Created via `gcloud beta run deploy --identity-type=agent-identity --functional-type=agent
    # --identity-certificate` and imported into Terraform state. Because `google-beta` 6.50 does
    # not model `spec.functional_type`, any `UpdateService` RPC from Terraform would omit
    # `functional_type` and be rejected by Cloud Run (`400: spec.functional_type: Functional type
    # cannot be updated or unset once set`). Ignore gcloud source-build metadata, label state diffs
    # on imported services, beta agent-identity annotations, computed revision service_account,
    # image digest, and server-defaulted scaling so `terraform plan` stays clean after import.
    ignore_changes = [
      annotations,
      build_config,
      client,
      client_version,
      deletion_protection,
      labels,
      launch_stage,
      scaling,
      template[0].annotations,
      template[0].containers[0].env,
      template[0].containers[0].image,
      template[0].labels,
      template[0].service_account,
      template[0].vpc_access,
    ]
  }
}

# Inbound: ONLY the gateway SA may invoke this agent runtime service.
resource "google_cloud_run_v2_service_iam_member" "gateway_invokes_agent_runtime" {
  project  = var.project_id
  name     = google_cloud_run_v2_service.agent_runtime.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.gateway_service_account_email}"
}

# Outbound 1: Verify context tokens with public keys only (never signing).
resource "google_kms_crypto_key_iam_member" "agent_context_key_viewer" {
  crypto_key_id = var.context_signing_key_id
  role          = "roles/cloudkms.publicKeyViewer"
  member        = local.agent_principal
}

# Outbound 2: Invoke the credential broker with the agent's SPIFFE identity + gateway-minted broker token.
resource "google_cloud_run_v2_service_iam_member" "agent_invokes_broker" {
  project  = var.project_id
  name     = var.broker_service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = local.agent_principal
}

# Outbound 3: Call Gemini models in live mode only (matches platform_core).
resource "google_project_iam_member" "agent_aiplatform_user" {
  count   = var.enable_live_mode ? 1 : 0
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = local.agent_principal
}

resource "google_project_iam_member" "agent_live_data_plane_roles" {
  for_each = var.enable_live_mode ? toset([
    "roles/serviceusage.serviceUsageConsumer",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
    "roles/modelarmor.user",
    "roles/modelarmor.viewer",
    "roles/dlp.user",
    "roles/dlp.inspectTemplatesReader",
    "roles/dlp.deidentifyTemplatesReader",
    "roles/datastore.user",
    "roles/bigquery.jobUser",
  ]) : toset([])
  project = var.project_id
  role    = each.value
  member  = local.agent_principal
}

# Table-scoped BigQuery span write permission for OpenTelemetry audit spans (insert-only via row policies).
resource "google_bigquery_table_iam_member" "agent_spans_writer" {
  count      = (var.enable_live_mode && var.enable_platform_live_resources) ? 1 : 0
  project    = var.project_id
  dataset_id = var.analytics_dataset_id
  table_id   = var.spans_table_id
  role       = "roles/bigquery.dataEditor"
  member     = local.agent_principal
}

resource "google_secret_manager_secret_iam_member" "agent_redis_tls_accessor" {
  count     = (var.enable_live_mode && var.enable_redis_tls) ? 1 : 0
  project   = var.project_id
  secret_id = var.redis_tls_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.agent_principal
}
