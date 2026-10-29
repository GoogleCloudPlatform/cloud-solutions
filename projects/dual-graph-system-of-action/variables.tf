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

variable "gcp_project_id" {
  type        = string
  default     = ""
  description = "Qwiklabs mandatory variable: Target Google Cloud project ID."
}

variable "gcp_region" {
  type        = string
  default     = "us-central1"
  description = "Qwiklabs mandatory variable: Target Google Cloud region (us-central1, us-west1, us-west4, us-east1, us-east4)."
}

variable "gcp_zone" {
  type        = string
  default     = "us-central1-a"
  description = "Qwiklabs mandatory variable: Target Google Cloud zone."
}

variable "service_account_key_file" {
  type        = string
  default     = ""
  description = "Qwiklabs mandatory variable: Path to the runner service account key file."
}

variable "spanner_instance_id" {
  type        = string
  default     = "soa-graph-instance"
  description = "Cloud Spanner Enterprise instance ID (100 processing units)."
}

variable "spanner_database_id" {
  type        = string
  default     = "thelook-soa-db"
  description = "Cloud Spanner database ID hosting thelook_ecommerce and OperationalContextGraph."
}

variable "bigquery_dataset_id" {
  type        = string
  default     = "soa_action_lineage"
  description = "BigQuery dataset ID hosting ActionLineageGraph."
}

variable "adk_model_name" {
  type        = string
  default     = "gemini-3-flash-preview"
  description = "Vertex AI Gemini model used by the ADK 2.0 IntentAgent and ResponseAgent."
}

variable "max_refunds_100d_limit" {
  type        = number
  default     = 10
  description = "Standard tier refund policy threshold: maximum allowed returned items within a 100-day rolling window."
}

variable "vip_max_refunds_100d_limit" {
  type        = number
  default     = 20
  description = "VIP tier refund policy threshold: maximum allowed returned items within a 100-day rolling window."
}

variable "argolis" {
  type        = bool
  default     = false
  description = "When true, enables Cloud Run built-in Identity-Aware Proxy (IAP) for internal Google Argolis environments where allUsers IAM bindings are restricted by organization policy."
}

variable "enable_iap" {
  type        = bool
  default     = false
  description = "When true (or when var.argolis is true), enables Cloud Run built-in Identity-Aware Proxy; when false (default for Qwiklabs student sessions and standalone deployments), grants roles/run.invoker to allUsers for 1-click browser access."
}
