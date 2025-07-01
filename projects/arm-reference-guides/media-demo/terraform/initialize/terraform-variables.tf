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
  terraform_project_id  = var.terraform_project_id != null ? var.terraform_project_id : var.platform_default_project_id
  terraform_bucket_name = "${local.terraform_project_id}-${local.unique_identifier_prefix}-terraform"
}

variable "terraform_project_id" {
  default     = null
  description = "The GCP project where terraform will be run"
  type        = string
}

variable "terraform_write_tfvars" {
  default     = true
  description = "Write the configured values to the tfvars configuration files."
  type        = string
}

variable "terraform_bucket_location" {
  default     = "us-central1"
  description = "Location where to create the Cloud Storage bucket to save Terraform state."
  type        = string
}
