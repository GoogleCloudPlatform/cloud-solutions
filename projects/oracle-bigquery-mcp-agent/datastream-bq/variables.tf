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

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "The Google Cloud Zone where the GCE Oracle VM is hosted"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Google Cloud Region"
}

variable "vpc_name" {
  type        = string
  default     = "oracle-vpc"
  description = "The VPC name where Oracle is deployed"
}



variable "datastream_private_ip_range" {
  type        = string
  default     = "10.0.2.0/29"
  description = "Non-overlapping CIDR range for Datastream private connectivity subnet"
}



variable "oracle_db_user" {
  type        = string
  default     = "c##datastream"
  description = "Datastream database username in Oracle"
}



variable "oracle_vm_name" {
  type        = string
  default     = "oracle-db-19c"
  description = "The GCE VM instance name of the source Oracle Database"
}

variable "oracle_schema" {
  type        = string
  default     = "RB_INTEL_LEDGER_19C"
  description = "The target Oracle schema to replicate CDC transactions from"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Datastream database password in Oracle"
}
