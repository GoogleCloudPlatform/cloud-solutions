/**
 * Copyright 2022 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

variable "client_id" {
  type        = string
  description = "Client ID generated from OAuth Consent Screen"
}

variable "project_id" {
  type        = string
  description = "The project ID to host Performance Testing in (required)"
}

variable "region" {
  type        = string
  description = "The region to host Performance Testing in"
  default     = "asia-southeast1"
}

variable "deployers_os_platform" {
  type = string
  description = "The OS of the machine running the Terraform script one-of[linux, darwin]"
  default = "linux"
  validation {
    condition = contains(["linux", "darwin"], var.deployers_os_platform)
    error_message = "deployers_os_platform should be one-of [linux, darwin]"
  }
}

variable "cloud_run_service_name" {
  type        = string
  description = "The service account name to run Performance Testing in"
  default     = "perfkit-benchmark"
}

variable "artifact_registry_name" {
  type = string
  description = "The name of the DOCKER artifact registry to create"
  default = "images"
}

variable "tool_user_group_email" {
  type        = string
  description = "The group or user's email address that will be using the tool"
}

variable "tool_user_group_email_type" {
  type = string
  description = "the type of email provided that will be using the tool ('group' or 'user')"
  validation {
    condition = contains(["group", "user", "serviceAccount"], var.tool_user_group_email_type)
    error_message = "tool_user_group_email_type should be one-of [group, user, serviceAccount]"
  }
}

variable "results_bq_project" {
  type = string
  description = "The project to use for storing results in BigQuery"
  default = ""
}

variable "results_bq_dataset" {
  type = string
  description = "The dataset to be created for storing result BigQuery table"
  default = "perfkit"
}

variable "results_bq_table" {
  type = string
  description = "The table to be created for storing result in BigQuery"
  default = "results"
}



