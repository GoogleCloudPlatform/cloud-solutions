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
  description = "Google Cloud hosting region for Cloud Run service deployment"
}

variable "service_name" {
  type        = string
  default     = "oracle-mcp-server"
  description = "Target Cloud Run service identifier"
}

variable "container_image" {
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello:latest"
  description = "Artifact Registry path to the built container image (e.g. us-central1-docker.pkg.dev/project/repo/image:tag)"
}

variable "oracle_db_user" {
  type        = string
  default     = "c##datastream"
  description = "Database connection username"
}

variable "agent_id" {
  type        = string
  description = "The provisioned Dialogflow CX Agent UUID"
  default     = ""
}

variable "looker_dashboard_url" {
  type        = string
  default     = ""
  description = "Optional Looker Dashboard URL to bind to the container"
}

variable "oracle_vm_name" {
  type        = string
  default     = "oracle-db-19c"
  description = "The GCE VM instance name of the source Oracle Database"
}

variable "subnetwork_name" {
  type        = string
  default     = "oracle-subnet"
  description = "The VPC subnetwork name where Oracle VM is located, used to peer the Cloud Run Serverless VPC Connector"
}

variable "db_password_secret_name" {
  type        = string
  default     = "oracle-db-password"
  description = "The Google Secret Manager secret identifier containing the Oracle master password"
}


