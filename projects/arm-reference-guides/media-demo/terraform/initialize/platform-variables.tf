# Copyright 2025 Google LLC
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

locals {
  unique_identifier_prefix            = "${var.resource_name_prefix}-${var.platform_name}"
  unique_identifier_prefix_underscore = replace("${var.resource_name_prefix}-${var.platform_name}", "-", "_")
}

variable "platform_default_project_id" {
  description = "The default project ID to use if a specific project ID is not specified"
  type        = string

  validation {
    condition     = var.platform_default_project_id != ""
    error_message = "'platform_default_project_id' was not set, please set the value in 'shared_config/platform.auto.tfvars' file or via the TF_VAR_platform_default_project_id"
  }
}

variable "platform_name" {
  default     = "dev"
  description = "Name of the environment"
  type        = string
}

variable "resource_name_prefix" {
  default     = "axn"
  description = "The prefix to add before each resource's name"
  type        = string
}
