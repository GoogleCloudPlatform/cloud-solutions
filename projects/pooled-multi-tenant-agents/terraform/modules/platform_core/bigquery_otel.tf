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
# Subsystem 6 & FinOps: BigQuery OpenTelemetry Sink, Per-Tenant COGS View,
# and Row-Level Access Policies (ROW ACCESS POLICY)
# ============================================================================

resource "google_bigquery_dataset" "agent_analytics" {
  dataset_id  = "cymbal_agent_analytics"
  location    = var.region
  description = "Multi-Tenant OpenTelemetry Agent Spans & FinOps Tokenomics Attribution"
  labels      = local.common_labels
  depends_on  = [google_project_service.enabled_apis]
}

resource "google_bigquery_table" "tenant_otel_spans" {
  dataset_id          = google_bigquery_dataset.agent_analytics.dataset_id
  table_id            = "tenant_otel_spans"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = ["tenant_id", "agent_id", "model_id"]

  schema = jsonencode([
    { name = "event_timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "trace_id", type = "STRING", mode = "REQUIRED" },
    { name = "tenant_id", type = "STRING", mode = "REQUIRED" },
    { name = "subscription_tier", type = "STRING", mode = "REQUIRED" },
    { name = "agent_id", type = "STRING", mode = "REQUIRED" },
    { name = "model_id", type = "STRING", mode = "REQUIRED" },
    { name = "tool_name", type = "STRING", mode = "NULLABLE" },
    { name = "prompt_cache_hit", type = "BOOL", mode = "REQUIRED" },
    { name = "thinking_tokens_budget", type = "INT64", mode = "REQUIRED" },
    { name = "raw_input_tokens", type = "INT64", mode = "REQUIRED" },
    { name = "billable_tokens", type = "INT64", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" }
  ])
}

# Blog Part 2 Section 1 Control Plane Billing Schema (`tokenomics` partitioned by DATE(timestamp))
resource "google_bigquery_table" "control_plane_tokenomics" {
  dataset_id          = google_bigquery_dataset.agent_analytics.dataset_id
  table_id            = "tokenomics"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["tenant_id", "tier", "model_id"]

  schema = jsonencode([
    { name = "tenant_id", type = "STRING", mode = "REQUIRED" },
    { name = "tier", type = "STRING", mode = "REQUIRED" },
    { name = "model_id", type = "STRING", mode = "REQUIRED" },
    { name = "input_tokens", type = "INT64", mode = "REQUIRED" },
    { name = "output_tokens", type = "INT64", mode = "REQUIRED" },
    { name = "session_id", type = "STRING", mode = "REQUIRED" },
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" }
  ])

  lifecycle {
    ignore_changes = [schema]
  }
}

# Per-tenant row access policies (one per tenant, readable only by that tenant's SA): modules/tenant.

# Optional all-tenant operator view (FinOps). Off unless operator principals are listed.
resource "google_bigquery_row_access_policy" "operator_all_tenants" {
  count            = length(var.bigquery_operator_principals) > 0 ? 1 : 0
  dataset_id       = google_bigquery_dataset.agent_analytics.dataset_id
  table_id         = google_bigquery_table.tenant_otel_spans.table_id
  policy_id        = "cymbal_operator_all_tenants_rap"
  filter_predicate = "TRUE"
  grantees         = var.bigquery_operator_principals
}

resource "google_bigquery_table" "tenant_tokenomics_cogs_view" {
  dataset_id          = google_bigquery_dataset.agent_analytics.dataset_id
  table_id            = "v_tenant_tokenomics_cogs"
  deletion_protection = var.deletion_protection

  view {
    use_legacy_sql = false
    query          = <<-EOT
      SELECT
        tenant_id,
        subscription_tier,
        agent_id,
        model_id,
        COUNT(*) AS total_turns,
        SUM(raw_input_tokens) AS total_raw_tokens,
        SUM(billable_tokens) AS total_billable_tokens,
        ROUND(
          SAFE_DIVIDE(SUM(raw_input_tokens - billable_tokens), SUM(raw_input_tokens)) * 100,
          2
        ) AS prompt_cache_savings_pct
      FROM
        `${var.project_id}.${google_bigquery_dataset.agent_analytics.dataset_id}.${google_bigquery_table.tenant_otel_spans.table_id}`
      GROUP BY
        tenant_id, subscription_tier, agent_id, model_id
    EOT
  }
}
