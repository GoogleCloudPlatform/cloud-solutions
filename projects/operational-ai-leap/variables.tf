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
  description = "The GCP project ID. If omitted, will be detected from gcloud config list."
  type        = string
  default     = ""
}

variable "gcp_region" {
  description = "The GCP region to apply this config to."
  type        = string
  default     = "us-central1"
}

# Qwiklab Mandantory Variable
variable "gcp_zone" {
  type    = string
  default = "us-central1-a"
}

# Qwiklab Mandantory Variable
variable "service_account_key_file" {
  type    = string
  default = ""
}

variable "alloydb_password" {
  description = "The password for the 'postgres' user in AlloyDB. If left blank, a secure random password will be generated automatically."
  type        = string
  default     = ""
  sensitive   = true
}

variable "alloydb_cluster_id" {
  description = "The ID of the AlloyDB cluster."
  type        = string
  default     = "stylesearch-cluster"
}

variable "alloydb_instance_id" {
  description = "The ID of the AlloyDB primary instance."
  type        = string
  default     = "stylesearch-instance"
}

variable "alloydb_database" {
  description = "The name of the database to create in AlloyDB."
  type        = string
  default     = "ecom"
}

variable "database_backup_uri" {
  description = "The GCS URI of the SQL backup file for import."
  type        = string
  default     = "gs://sample-data-and-media/ecomm-retail/ecom_generic_vectors.sql"
}

variable "demo_app_name" {
  description = "The name for the Cloud Run demo application service."
  type        = string
  default     = "cymbalshops"
}

variable "demo_app_repo_name" {
  description = "The name for the Artifact Registry repository."
  type        = string
  default     = "cymbalshops"
}

variable "demo_app_image_name" {
  description = "The name for the demo application Docker image."
  type        = string
  default     = "cymbalshops"
}

variable "argolis" {
  description = "Whether to override Argolis policies."
  type        = bool
  default     = false
}
