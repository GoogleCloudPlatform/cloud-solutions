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

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

variable "obs_project_id" {
  type        = string
  description = "Central observability Google Cloud project ID"
}

variable "workload_project_id" {
  type        = string
  description = "Target workload Google Cloud project ID"
}

# Metrics Scope Configuration
resource "google_monitoring_monitored_project" "workload_project" {
  metrics_scope = "projects/${var.obs_project_id}"
  name          = "projects/${var.workload_project_id}"
}

# Log Bucket with Analytics
resource "google_logging_project_bucket_config" "custom_bucket" {
  project          = var.obs_project_id
  location         = "global"
  bucket_id        = "custom-telemetry-bucket"
  retention_days   = 30
  enable_analytics = true
}

# Log Router Sink
resource "google_logging_project_sink" "splunk_sink" {
  name        = "payments-to-splunk"
  destination = "pubsub.googleapis.com/projects/${var.obs_project_id}/topics/splunk-ingest"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"payments\""

  unique_writer_identity = true
}
