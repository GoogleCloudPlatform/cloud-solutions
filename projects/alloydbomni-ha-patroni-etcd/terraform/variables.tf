#
# Copyright 2024 Google LLC
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
#

## Define variables

variable "project_id" {
  description = "The project_id to deploy resources into"
  type        = string
}

variable "region" {
  description = "The region to deploy resources into"
  type        = string
  default     = "us-central1"
}

variable "zones" {
  description = "List of zones to deploy resources"
  type        = list(string)
  default     = ["us-central1-a", "us-central1-b", "us-central1-c"]
}

variable "download_folder" {
  description = "Local folder path to download files"
  default     = "alloydb"
}

variable "node_count" {
  description = "The number of nodes in the patroni cluster"
  type        = number
  default     = 3
}

variable "cluster_name" {
  description = "The name of the patroni cluster"
  type        = string
  default     = "my-patroni-cluster"
}

variable "replication_user_password" {
  description = "The replication user password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "postgres_super_user" {
  description = "The replication user password"
  type        = string
  default     = "postgres"
}

variable "postgres_super_user_password" {
  description = "The replication user password"
  type        = string
  sensitive   = true
  default     = ""
}
