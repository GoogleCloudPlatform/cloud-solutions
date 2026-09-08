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

variable "project_id" {
  type        = string
  description = "Google Cloud project ID for provisioning resources."
}

variable "environment" {
  type        = string
  description = "Deployment environment stage (dev, staging, prod)."
}

variable "bigquery_dataset_id" {
  type        = string
  description = "Target BigQuery dataset for direct Pub/Sub writing."
}

variable "telemetry_table_id" {
  type        = string
  description = "Target BigQuery table ID for raw telemetry."
  default     = "telemetry_events"
}
