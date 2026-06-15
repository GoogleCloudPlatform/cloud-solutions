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

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Primary Google Cloud Region"
}

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "Primary Google Cloud Zone"
}

variable "gcs_bucket_name" {
  type        = string
  description = "The GCS Bucket where Oracle RPMs and scripts are staged"
}

variable "rpm_name" {
  type        = string
  default     = "oracle-database-ee-19c-1.0-1.x86_64.rpm"
  description = "The exact filename of the Oracle 19c Enterprise Edition RPM"
}

variable "ssh_user" {
  type        = string
  default     = ""
  description = "Username override for VM SSH administration. If empty, dynamically falls back to email-to-POSIX formatting default."
}

variable "ssh_key_path" {
  type        = string
  default     = "~/.ssh/id_rsa"
  description = "Local path to your private SSH key"
}





variable "os_image_family" {
  type        = string
  default     = "oracle-linux-8"
  description = "The GCE image family used for the database VM"
}

variable "os_image_project" {
  type        = string
  default     = "oracle-linux-cloud"
  description = "The Google Cloud project hosting the target database VM image"
}

variable "machine_type" {
  type        = string
  default     = "n2-standard-4"
  description = "The GCE virtual machine hardware profile type (e.g., 'n2-standard-4')"
}

variable "create_vpc" {
  type        = bool
  default     = true
  description = "Toggle to dynamically create a new VPC network (set to false to use existing)"
}

variable "create_subnetwork" {
  type        = bool
  default     = true
  description = "Toggle to dynamically create a new Subnetwork (set to false to use existing)"
}

variable "create_gcs_bucket" {
  type        = bool
  default     = true
  description = "Toggle to dynamically create a new GCS Staging Bucket (set to false to use existing)"
}

variable "vpc_name" {
  type        = string
  default     = "oracle-vpc"
  description = "The VPC network name"
}

variable "subnetwork_name" {
  type        = string
  default     = "oracle-subnet"
  description = "The subnetwork name"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "The database master password"
}

