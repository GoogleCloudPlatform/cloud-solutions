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
# Cloud Pub/Sub Direct BigQuery Subscription (Low-Code Stack)
# =============================================================================

resource "google_project_service_identity" "pubsub_agent" {
  provider = google-beta
  project  = var.project_id
  service  = "pubsub.googleapis.com"
}

resource "google_project_iam_member" "pubsub_bq_data_editor" {
  project    = var.project_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_project_service_identity.pubsub_agent.email}"
  depends_on = [google_pubsub_topic.telemetry_raw]
}

resource "google_project_iam_member" "pubsub_bq_metadata_viewer" {
  project    = var.project_id
  role       = "roles/bigquery.metadataViewer"
  member     = "serviceAccount:${google_project_service_identity.pubsub_agent.email}"
  depends_on = [google_pubsub_topic.telemetry_raw]
}

resource "google_pubsub_topic" "telemetry_raw" {
  name    = "telemetry-raw"
  project = var.project_id

  labels = {
    environment = var.environment
    component   = "low-code-pubsub-broker"
  }
}

resource "google_pubsub_subscription" "telemetry_bigquery" {
  name    = "telemetry-raw-bq-sub"
  topic   = google_pubsub_topic.telemetry_raw.name
  project = var.project_id

  bigquery_config {
    table               = "${var.project_id}:${var.bigquery_dataset_id}.${var.telemetry_table_id}"
    use_table_schema    = true
    drop_unknown_fields = true
    write_metadata      = false
  }

  labels = {
    environment = var.environment
    component   = "low-code-bq-direct-subscription"
  }

  depends_on = [
    google_pubsub_topic.telemetry_raw,
    google_project_iam_member.pubsub_bq_data_editor,
    google_project_iam_member.pubsub_bq_metadata_viewer
  ]
}
