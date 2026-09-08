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

# =============================================================================
# Cloud BigQuery Analytical Data Warehouse
# =============================================================================

resource "google_bigquery_dataset" "analytics" {
  dataset_id                 = local.bigquery_dataset_id
  friendly_name              = "Aegis Analytics Dataset"
  description                = "Dataset storing Aegis real-time telemetry events and agent RCA logs"
  location                   = var.region
  project                    = var.project_id
  delete_contents_on_destroy = true

  depends_on = [google_project_service.enabled_apis]
}

resource "google_bigquery_table" "telemetry_events" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "telemetry_events"
  project             = var.project_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["asset_id"]

  schema = jsonencode([
    {
      name        = "asset_id"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Industrial asset identifier"
    },
    {
      name        = "timestamp"
      type        = "TIMESTAMP"
      mode        = "NULLABLE"
      description = "Event timestamp"
    },
    {
      name        = "cpu_utilization"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "CPU utilization percentage"
    },
    {
      name        = "temperature_c"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Temperature in Celsius"
    },
    {
      name        = "pressure_psi"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Pressure in PSI"
    },
    {
      name        = "memory_utilization_pct"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Memory utilization percentage"
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Asset operational status (OK, WARNING, CRITICAL)"
    },
    {
      name        = "is_anomaly"
      type        = "BOOLEAN"
      mode        = "NULLABLE"
      description = "Flag indicating telemetry anomaly"
    }
  ])
}

resource "google_bigquery_table" "rca_events" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "rca_events"
  project             = var.project_id
  deletion_protection = false

  schema = jsonencode([
    {
      name        = "event_id"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Unique RCA event UUID"
    },
    {
      name        = "asset_id"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Industrial asset ID"
    },
    {
      name        = "timestamp"
      type        = "TIMESTAMP"
      mode        = "NULLABLE"
      description = "RCA execution timestamp"
    },
    {
      name        = "root_cause"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Identified root cause summary"
    },
    {
      name        = "mitigation_plan"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Generated mitigation steps"
    },
    {
      name        = "tokens_used"
      type        = "INTEGER"
      mode        = "NULLABLE"
      description = "Total tokens used by LLM inference"
    },
    {
      name        = "cost_usd"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Estimated cost in USD"
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Mitigation execution status"
    }
  ])
}
