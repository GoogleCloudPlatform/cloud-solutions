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

variable "target_project_id" {
  description = "The Google Cloud Target Project ID"
  type        = string
}

variable "region" {
  description = "The region to deploy to"
  type        = string
}

variable "zone" {
  description = "The zone to deploy to"
  type        = string
}

variable "source_service_account" {
  description = "The service account of the source Managed Spark cluster to grant access to the bronze bucket"
  type        = string
}

variable "source_project_id" {
  description = "The source Google Cloud Project ID (simulated Hadoop)"
  type        = string
}

variable "source_cluster_name" {
  description = "The name of the source Managed Spark cluster"
  type        = string
}
