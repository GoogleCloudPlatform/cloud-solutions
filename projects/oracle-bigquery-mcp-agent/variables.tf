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
  description = "The Google Cloud Project ID"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "The database master password (e.g. min 8 characters, capital, digit, _)"
}

variable "region" {
  type        = string
  description = "Primary Google Cloud Region"
  default     = "us-central1"
}

variable "zone" {
  type        = string
  description = "Primary Google Cloud Zone"
  default     = "us-central1-a"
}

variable "gcs_bucket_name" {
  type        = string
  description = "Globally unique GCS Staging Bucket (leave empty to auto-generate)"
  default     = ""
}

variable "ssh_user" {
  type        = string
  description = "SSH username override for GCE VM (leave empty for default)"
  default     = ""
}

variable "ssh_key_path" {
  type        = string
  description = "Local path to your private SSH key"
  default     = "~/.ssh/id_rsa"
}

variable "oauth_client_id" {
  type        = string
  description = "Google Cloud OAuth Web Client ID for Looker (leave empty to skip Looker)"
  default     = ""
}

variable "oauth_client_secret" {
  type        = string
  sensitive   = true
  description = "Google Cloud OAuth Web Client Secret for Looker (leave empty to skip Looker)"
  default     = ""
}

variable "edition" {
  type        = string
  description = "Looker Core Platform pricing tier (LOOKER_CORE_TRIAL, LOOKER_CORE_STANDARD)"
  default     = "LOOKER_CORE_STANDARD"
}

variable "create_vpc" {
  type        = bool
  description = "Create a new VPC network?"
  default     = true
}

variable "vpc_name" {
  type        = string
  description = "VPC network name"
  default     = "oracle-vpc"
}

variable "create_subnetwork" {
  type        = bool
  description = "Create a new Subnetwork?"
  default     = true
}

variable "subnetwork_name" {
  type        = string
  description = "Subnetwork name"
  default     = "oracle-subnet"
}

variable "create_gcs_bucket" {
  type        = bool
  description = "Create the staging GCS bucket?"
  default     = true
}

variable "rpm_name" {
  type        = string
  description = "Oracle 19c RPM filename"
  default     = "oracle-database-ee-19c-1.0-1.x86_64.rpm"
}
