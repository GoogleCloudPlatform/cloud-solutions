# Copyright 2025 Google LLC
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

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-c"
}

variable "tools_images_url" {
  type    = string
  default = "us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest"
}

variable "additional_tools_run_invoker_members" {
  description = "A list of IAM members to grant the Cloud Run Invoker role."
  type        = list(string)
  default     = []
}

variable "k8s_namespace" {
  description = "The Kubernetes namespace for the service account."
  default     = "adk-agent-demo"
}

variable "deploy_mcp_toolbox_for_databases_to_cloud_run" {
  description = <<-EOT
    Boolean indicating if the MCP Toolbox for Databases should be deployed to Cloud Run.
    If set to false, it will not be deployed, and you can apply scripts and manifests directly in GKE.
  EOT
  type        = bool
  default     = false
}

variable "generate_kustomization_overlays" {
  description = "Boolean indicating if the kustomization overlays should be generated."
  type        = bool
  default     = true
}

variable "overlay_output_directory_name" {
  description = "The environment name of the directory for the overlay outputs"
  type        = string
  default     = "demo"
}

variable "hugging_face_api_token" {
  description = "Hugging face api token with read access"
  type        = string
  sensitive   = true
  validation {
    condition     = var.hugging_face_api_token != ""
    error_message = "The Hugging Face API token cannot be empty."
  }
}

variable "finnhub_api_key" {
  description = "Finnhub API key"
  type        = string
  sensitive   = true
  validation {
    condition     = var.finnhub_api_key != ""
    error_message = "The Finnhub API Key cannot be empty."
  }
}
