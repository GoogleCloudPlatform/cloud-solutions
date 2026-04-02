# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "project_id" {
  description = "The Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "The Google Cloud region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The Google Cloud zone"
  type        = string
  default     = "us-central1-a"
}

variable "cluster_name" {
  description = "The name of the GKE cluster"
  type        = string
  default     = "java-mod-demo"
}

variable "db_instance_name" {
  description = "The name of the Cloud SQL instance"
  type        = string
  default     = "java-mod-demo-dbi"
}

variable "db_names" {
  description = "The list of databases to create in the Cloud SQL instance"
  type        = list(string)
  default     = ["employee"]
}

variable "repo_name" {
  description = "The name of the Artifact Registry repository"
  type        = string
  default     = "app-repo"
}
