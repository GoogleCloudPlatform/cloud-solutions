# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-c"
}

variable "tools_image_url" {
  type    = string
  default = "us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest"
}

variable "order_service_image_url" {
  type    = string
  default = null
}

variable "additional_tools_run_invoker_members" {
  description = "A list of IAM members to grant the Cloud Run Invoker role."
  type        = list(string)
  default     = []
}

variable "finnhub_api_key" {
  description = "Finnhub API key"
  type        = string
  sensitive   = true
  validation {
    condition     = var.finnhub_api_key != ""
    error_message = "The Finnhub API Key cannot be empty."
  }
}

variable "forecast_model_display_name" {
  type    = string
  default = "forecast-service-timesfm"
}

variable "alloydb_db_name" {
  type    = string
  default = "postgres"
}

variable "deploy_cloud_build_triggers" {
  type    = bool
  default = false
}

variable "deploy_order_service" {
  type    = bool
  default = false
}
