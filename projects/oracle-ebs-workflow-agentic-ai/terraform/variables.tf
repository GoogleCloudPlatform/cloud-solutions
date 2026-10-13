# Copyright 2026 Google LLC
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
  type        = string
  description = "Google Cloud Project ID where resources will be provisioned."
}

variable "image_tag" {
  type        = string
  description = "Container image tag for Cloud Run deployment."
  default     = "latest"
}

variable "container_image" {
  type        = string
  description = "Full container image URI for Cloud Run deployment. Defaults to the Artifact Registry repository image with var.image_tag when empty."
  default     = ""
}

variable "region" {
  type        = string
  description = "Google Cloud Region for compute and network resources."
}

variable "environment" {
  type        = string
  description = "Deployment environment name (e.g. dev, staging, prod)."
  default     = "dev"
}

variable "create_vpc" {
  type        = bool
  description = "Set to true to create a new VPC network, or false to attach to an existing Oracle EBS VPC."
  default     = false
}

variable "vpc_network_name" {
  type        = string
  description = "Name of the VPC network where Oracle EBS VM resides."
  default     = "oracle-ebs-toolkit-network"
}

variable "subnet_name" {
  type        = string
  description = "Name of the subnetwork for Cloud Run Direct VPC Egress when create_vpc is false."
  default     = "oracle-ebs-toolkit-subnet-01"
}

variable "oracle_host" {
  type        = string
  description = "Oracle EBS Database Host IP or hostname."
  default     = "127.0.0.1"
}

variable "oracle_port" {
  type        = number
  description = "Oracle EBS Database Listener Port."
  default     = 1521
}

variable "oracle_service_name" {
  type        = string
  description = "Oracle EBS Database Service Name."
  default     = "ebsdb"
}

variable "oracle_db_user" {
  type        = string
  description = "Oracle EBS Database User."
  default     = "apps"
}


variable "developer_user_email" {
  type        = string
  description = "Optional developer Google account email to grant direct Cloud Run invoker permissions during development."
  default     = ""
}

variable "gemini_model" {
  type        = string
  description = "Primary Gemini foundation model identifier on Vertex AI."
  default     = "gemini-3.8-flash"
}

variable "gemini_fallback_model" {
  type        = string
  description = "Fallback Gemini foundation model identifier on Vertex AI."
  default     = "gemini-3.7-flash"
}

variable "gemini_flash_lite_model" {
  type        = string
  description = "Selected Gemini Flash Lite model for high-throughput gateway routing and response synthesis on Vertex AI."
  default     = "gemini-3.5-flash-lite"
}

variable "fnd_user_id" {
  type        = number
  description = "Default Oracle EBS FND User ID for session context initialization."
  default     = 0
}

variable "fnd_resp_id" {
  type        = number
  description = "Default Oracle EBS FND Responsibility ID for session context initialization."
  default     = 20420
}

variable "fnd_resp_appl_id" {
  type        = number
  description = "Default Oracle EBS FND Responsibility Application ID for session context initialization."
  default     = 1
}

variable "workflow_execution_path" {
  type        = string
  description = "Execution path for workflow actions: 'REST' (Path B primary) or 'PLSQL' (Path A secondary)."
  default     = "REST"
}

variable "isg_rest_base_url" {
  type        = string
  description = "Oracle EBS Integrated SOA Gateway REST base URL for Path B execution (defaults to http://<oracle_host>:8000 when empty)."
  default     = ""
}

variable "isg_username" {
  type        = string
  description = "Oracle EBS ISG REST Basic Auth username."
  default     = "ISGADMIN"
}
