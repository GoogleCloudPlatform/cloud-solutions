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
# Cloud Pub/Sub Telemetry Broker Layer (1st-Party Managed Streaming Stack)
# =============================================================================

resource "google_pubsub_topic" "telemetry_raw" {
  name    = "telemetry-raw"
  project = var.project_id

  labels = {
    environment = var.environment
    component   = "pubsub-telemetry-broker"
  }
}

resource "google_pubsub_subscription" "telemetry_dataflow" {
  name    = "telemetry-raw-dataflow-sub"
  topic   = google_pubsub_topic.telemetry_raw.name
  project = var.project_id

  ack_deadline_seconds       = 60
  retain_acked_messages      = false
  message_retention_duration = "86400s" # 24 Hours retention

  expiration_policy {
    ttl = "" # Never expire
  }

  labels = {
    environment = var.environment
    component   = "dataflow-subscription"
  }
}
