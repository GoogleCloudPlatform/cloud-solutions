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
  description = "The Google Cloud Project ID. If omitted, it is detected dynamically from the environment."
  type        = string
  default     = ""
}

variable "gcp_region" {
  description = "The Google Cloud Region to apply this configuration to."
  type        = string
  default     = "us-central1"
}

# Qwiklabs Mandatory Variable
variable "gcp_zone" {
  description = "The Google Cloud Zone to apply this configuration to."
  type        = string
  default     = "us-central1-a"
}

# Qwiklabs Mandatory Variable
variable "service_account_key_file" {
  description = "Path to the service account key file in the Qwiklabs runner environment."
  type        = string
  default     = ""
}

variable "dataset_id" {
  description = "The ID of the target BigQuery dataset for the lab."
  type        = string
  default     = "thelook_ecommerce"
}

variable "colab_machine_type" {
  description = "The machine type for the Colab Enterprise runtime template."
  type        = string
  default     = "e2-standard-4"
}
