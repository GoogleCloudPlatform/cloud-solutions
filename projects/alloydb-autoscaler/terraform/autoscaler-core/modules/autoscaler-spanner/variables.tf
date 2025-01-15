/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "terraform_spanner_state" {
  description = "If set to true, Terraform will create a Cloud Spanner DB for state."
  type        = bool
}

variable "spanner_state_name" {
  description = "Name of the Spanner instance where the Autoscaler state is stored."
  type        = string
}

variable "spanner_state_database" {
  description = "Name of the Spanner database where the Autoscaler state is stored."
  type        = string
}

variable "spanner_state_table" {
  description = "Name of the Spanner table where the Autoscaler state is stored."
  type        = string
}

variable "spanner_state_processing_units" {
  description = "Default processing units for state Spanner, if created"
  default     = 100
}

variable "poller_sa_email" {
  type = string
}

variable "scaler_sa_email" {
  type = string
}
