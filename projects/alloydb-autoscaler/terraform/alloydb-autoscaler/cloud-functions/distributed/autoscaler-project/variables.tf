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
  type        = string
  description = "Project ID where the Autoscaler and resources will be deployed"
}

variable "region" {
  type        = string
  description = "Region where the Autoscaler and resources will be deployed"
}

variable "app_project_id" {
  description = "The project where the AlloyDB Cluster(s) live. If specified and different than project_id => centralized deployment"
  type        = string
  default     = ""
}

variable "terraform_spanner_state" {
  description = "If set to true, Terraform will create a Spanner instance for autoscaler state."
  type        = bool
  default     = false
}

variable "spanner_state_name" {
  type    = string
  default = "alloydb-autoscaler-state"
}

variable "spanner_state_database" {
  type    = string
  default = "alloydb-autoscaler-state"
}

variable "forwarder_sa_emails" {
  type = list(string)
  // Example ["serviceAccount:forwarder_sa@app-project.iam.gserviceaccount.com"]
  default = []
}

locals {
  # By default, these config files produce a per-project deployment
  # If you want a centralized deployment instead, then specify
  # an app_project_id that is different from project_id
  app_project_id = var.app_project_id == "" ? var.project_id : var.app_project_id
}
