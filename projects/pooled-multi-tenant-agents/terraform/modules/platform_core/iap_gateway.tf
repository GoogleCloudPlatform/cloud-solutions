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
# Hop 1, Hop 2 & Hop 5: Cloud Armor Edge Policy, Agent PEP Identities,
# Cloud Run Pooled Gateway (tenant 3LO secrets live in modules/tenant)
# ============================================================================

data "google_project" "current" {
  project_id = var.project_id
  depends_on = [google_project_service.enabled_apis]
}

# The legacy shared gateway identity `cymbal-ingress-pep-sa` (ADR-0010 "before") is retired: it
# runs nothing and is intentionally not defined here. Nothing may grant it roles. A future edge
# PEP gets a new, purpose-named identity when it exists (ADR-0014 B5).

resource "google_service_account" "pooled_agent_runtime" {
  account_id   = "cymbal-pooled-runtime-sa"
  display_name = "Cymbal Pooled ADK 2.0 Agent Runtime Fleet"
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_service_account" "stateless_mcp_server" {
  account_id   = "cymbal-stateless-mcp-sa"
  display_name = "Cymbal Stateless MCP Server (AlloyDB RLS Client)"
  depends_on   = [google_project_service.enabled_apis]
}

locals {
  # The ONE serving identity (Cloud Run gateway + agent runtime): cymbal-pooled-runtime-sa.
  # Least privilege (ADR-0010): no project-wide KMS / Secret Manager / Storage roles, no admin roles.
  # Tenant data access happens only through per-tenant service accounts it may impersonate
  # (modules/tenant). Guardrail templates and BigQuery row policies are owned by
  # Terraform, so the runtime needs only *user* roles to call and verify them.
  # Always: quota attribution and telemetry. Live mode only (CYMBAL_LIVE_GCP=1): the Google APIs
  # the runtime calls as itself. The sandbox gateway runs offline today, so it holds only the first.
  runtime_project_roles = setunion(
    toset([
      "roles/serviceusage.serviceUsageConsumer",
      "roles/logging.logWriter",
      "roles/monitoring.metricWriter",
      "roles/cloudtrace.agent",
    ]),
    var.enable_live_mode ? toset([
      "roles/aiplatform.user",
      "roles/modelarmor.user",
      "roles/modelarmor.viewer",
      "roles/dlp.user",
      "roles/dlp.inspectTemplatesReader",
      "roles/dlp.deidentifyTemplatesReader",
      "roles/datastore.user",
      "roles/bigquery.jobUser",
    ]) : toset([]),
    (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? toset([
      "roles/alloydb.client",
      "roles/alloydb.databaseUser",
    ]) : toset([]),
  )

  effective_agent_runtime_urls_json = var.agent_runtime_urls_json != "" ? var.agent_runtime_urls_json : (var.enable_agent_runtimes ? jsonencode({
    for agent_id, svc_name in var.agent_runtime_service_map :
    agent_id = > "https://${svc_name}-${data.google_project.current.number}.${var.region}.run.app"
  }) : "")

}

resource "google_project_iam_member" "runtime_bindings" {
  for_each = local.runtime_project_roles
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.pooled_agent_runtime.email}"
}

# Span writes (agents/gcp_live_bridge.py insert_rows_json) go only to the spans table, and only
# in live mode. Table scope, not dataset scope: the runtime can't touch other tables. It is not a
# row-policy grantee, so it reads zero rows. Narrowest predefined role (no insert-only role exists).
resource "google_bigquery_table_iam_member" "runtime_spans_writer" {
  count      = var.enable_live_mode ? 1 : 0
  dataset_id = google_bigquery_dataset.agent_analytics.dataset_id
  table_id   = google_bigquery_table.tenant_otel_spans.table_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pooled_agent_runtime.email}"
}

# Cloud Run v2 Pooled Agent Gateway (Protected via IAP & Edge Header Spoof Strip)
resource "google_cloud_run_v2_service" "cymbal_pooled_gateway" {
  provider            = google-beta # iap_enabled (Cloud Run built-in IAP)
  name                = "cymbal-pooled-gateway"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  iap_enabled         = true
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  template {
    service_account                  = google_service_account.pooled_agent_runtime.email
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = var.gateway_max_instance_count
    }

    dynamic "vpc_access" {
      for_each = ((var.enable_live_mode && var.enable_memorystore_redis) || (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance)) ? [1] : []
      content {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = google_compute_network.pooled_vpc[0].name
          subnetwork = google_compute_network.pooled_vpc[0].name
        }
      }
    }

    containers {
      image = var.gateway_container_image

      resources {
        limits            = { cpu = "1000m", memory = "512Mi" } # API's canonical form (no diff)
        cpu_idle          = true                                # CPU only during requests (context-key prewarm retries on requests)
        startup_cpu_boost = true
      }

      # Must match agents/runtime_env.py RUNTIME_ENV_CONTRACT (enforced by tests).
      dynamic "env" {
        for_each = {
          GOOGLE_CLOUD_PROJECT      = var.project_id
          GOOGLE_CLOUD_REGION       = var.region
          GOOGLE_CLOUD_LOCATION     = var.region
          GOOGLE_GENAI_USE_VERTEXAI = "true"
          CYMBAL_ENV                = var.platform_environment
          CYMBAL_LIVE_GCP           = var.enable_live_mode ? "1" : "0"
          MODEL_ARMOR_TEMPLATE_ID   = google_model_armor_template.inbound_pep.template_id
          DLP_INSPECT_TEMPLATE      = google_data_loss_prevention_inspect_template.tenant_pii_inspect.id
          DLP_DEIDENTIFY_TEMPLATE   = google_data_loss_prevention_deidentify_template.tenant_pii_deidentify.id
          KMS_KEYRING_NAME          = google_kms_key_ring.tenant_cmek_ring.name
          RUNBOOK_BUCKET_NAME       = google_storage_bucket.pooled_cmek_runbooks.name
          BIGQUERY_DATASET          = google_bigquery_dataset.agent_analytics.dataset_id
          FIRESTORE_DATABASE        = google_firestore_database.tenant_memory_bank.name
          CREDENTIAL_BROKER_URL     = local.effective_credential_broker_url
          # Live mode needs an explicit credential backend: direct impersonation only pre-B4.
          CYMBAL_DIRECT_IMPERSONATION = local.effective_credential_broker_url == "" ? "1" : "0"
          # Configurable token-expiry and autonomous call-ceiling policy (var.token_and_session_policy).
          GATEWAY_TOKEN_TTL_SECONDS             = tostring(var.token_and_session_policy.gateway_token_ttl_seconds)
          DPOP_PROOF_MAX_AGE_SECONDS            = tostring(var.token_and_session_policy.dpop_proof_max_age_seconds)
          TENANT_SA_TOKEN_TTL_SECONDS           = tostring(var.token_and_session_policy.tenant_sa_token_ttl_seconds)
          TENANT_SA_REFRESH_MARGIN_SECONDS      = tostring(var.token_and_session_policy.tenant_sa_refresh_margin_seconds)
          IDP_BROKER_MAX_TOKEN_LIFETIME_SECONDS = tostring(var.token_and_session_policy.idp_broker_max_token_lifetime_seconds)
          IDP_DIRECT_MAX_TOKEN_LIFETIME_SECONDS = tostring(var.token_and_session_policy.idp_direct_max_token_lifetime_seconds)
          STANDARD_MAX_TURNS_PER_SESSION        = tostring(var.token_and_session_policy.standard_max_turns_per_session)
          ENTERPRISE_MAX_TURNS_PER_SESSION      = tostring(var.token_and_session_policy.enterprise_max_turns_per_session)
        }
        content {
          name  = env.key
          value = env.value
        }
      }

      # ADR-0014 B5 / ADR-0016 S3 & ADR-0012 Agent Sandbox in Gemini cutover flags (omitted when false/empty so default plan has zero diff).
      dynamic "env" {
        for_each = merge(
          (var.agent_runtime_urls_json != "" || var.enable_agent_runtimes) ? { AGENT_RUNTIME_URLS = local.effective_agent_runtime_urls_json } : {},
          var.bind_agent_id ? { CONTEXT_TOKEN_BIND_AGENT_ID = "1" } : {},
          var.require_agent_binding ? { CONTEXT_TOKEN_REQUIRE_AGENT_ID = "1" } : {},
          var.agent_sandbox_reasoning_engine_name != "" ? {
            AGENT_SANDBOX_REASONING_ENGINE_NAME = var.agent_sandbox_reasoning_engine_name
            MEMORY_BANK_REASONING_ENGINE        = var.agent_sandbox_reasoning_engine_name
          } : {},
          var.agent_sandbox_code_template != "" ? { AGENT_SANDBOX_CODE_TEMPLATE = var.agent_sandbox_code_template } : {},
          var.agent_sandbox_shell_template != "" ? { AGENT_SANDBOX_SHELL_TEMPLATE = var.agent_sandbox_shell_template } : {},
          var.enable_live_mode ? { FIRESTORE_REVOCATION_STORE = "1" } : {},
          (var.enable_live_mode && var.enable_memorystore_redis && !var.enable_redis_auth_and_tls) ? {
            REDIS_URL = "redis://${google_redis_instance.token_bucket_bulkhead[0].host}:${google_redis_instance.token_bucket_bulkhead[0].port}/0"
          } : {},
          (var.enable_live_mode && var.enable_memorystore_redis && var.enable_redis_auth_and_tls) ? {
            REDIS_TLS_SECRET_VERSION = google_secret_manager_secret_version.redis_tls_bundle[0].name
          } : {},
          (var.enable_live_mode && var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? {
            DATABASE_URL     = "postgresql://${urlencode(trimsuffix(google_service_account.pooled_agent_runtime.email, ".gserviceaccount.com"))}@${google_alloydb_instance.pooled_rls_primary[0].ip_address}:5432/postgres"
            ALLOYDB_IAM_AUTH = "1"
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
    precondition {
      condition     = var.gateway_max_instance_count <= 1 || (var.enable_live_mode && var.enable_memorystore_redis)
      error_message = "gateway_max_instance_count > 1 requires enable_live_mode = true and enable_memorystore_redis = true for shared DPoP replay and rate-limit bulkheads (ADR-0012)."
    }

    ignore_changes = [
      build_config,
      template[0].containers[0].image,
      client,
      client_version,
      scaling, # service-level, server-defaulted; per-revision limits are in template.scaling
    ]
  }
}

# Only IAP may invoke the gateway service itself; users are authorized by IAP (below).
resource "google_cloud_run_v2_service_iam_member" "iap_invokes_gateway" {
  name     = google_cloud_run_v2_service.cymbal_pooled_gateway.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

resource "google_iap_web_cloud_run_service_iam_member" "gateway_accessors" {
  for_each               = toset(var.iap_accessors)
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.cymbal_pooled_gateway.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
}

# Reviewer access always expires (e.g. the 2026-11-20 demo window).
resource "google_iap_web_cloud_run_service_iam_member" "gateway_time_boxed_accessors" {
  for_each               = toset(var.iap_time_boxed_accessors.members)
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.cymbal_pooled_gateway.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
  condition {
    title      = var.iap_time_boxed_accessors.title
    expression = "request.time < timestamp(\"${var.iap_time_boxed_accessors.expires}\")"
  }
}

# Cloud Armor Edge WAF Policy: Blocks requests attempting header-spoofing attacks. Only effective
# behind an external HTTPS load balancer; the sandbox uses Cloud Run's built-in IAP instead.
resource "google_compute_security_policy" "cymbal_edge_waf" {
  count       = var.enable_edge_waf ? 1 : 0
  name        = "cymbal-multitenant-edge-waf"
  description = "Hop 1 Edge WAF: Rejects client-supplied X-Tenant-ID spoofing & enforces perimeter rules"
  depends_on  = [google_project_service.enabled_apis]

  rule {
    action   = "deny(403)"
    priority = 1000
    match {
      expr {
        expression = "has(request.headers['x-tenant-id']) || has(request.headers['x-subscription-tier'])"
      }
    }
    description = "Deny unverified client-supplied X-Tenant-ID or X-Subscription-Tier headers at Edge"
  }

  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default allow rule to IAP OIDC verification"
  }
}
