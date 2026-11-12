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
  description = "Google Cloud project ID where Terraform provisions the resources."
}

variable "region" {
  type        = string
  description = "Google Cloud region for Cloud Run, Artifact Registry, Cloud Build, and networking. BigQuery uses bigquery_location."
}

variable "image_tag" {
  type        = string
  description = "Container image tag for Cloud Run deployment."
  default     = "latest"
}

variable "container_image" {
  type        = string
  description = "Full container image URI for Cloud Run deployment. Defaults to the Artifact Registry image when empty."
  default     = ""
}

variable "mcp_toolbox_image" {
  type        = string
  description = "MCP Toolbox for Databases container image that the Oracle EBS MCP framework deploys, pinned by digest."
  default     = "us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:1.15.0@sha256:7e4f7bfd93ccec33c066563a4ca700572e4ce95a8d45ba18577df8ee50b9481a"
}

variable "create_vpc" {
  type        = bool
  description = "Set to true to create a new VPC network, or false to reuse an existing VPC network."
  default     = false
}

variable "vpc_network_name" {
  type        = string
  description = "Name of the new or existing VPC network where the Oracle EBS VM resides."
}

variable "create_subnet" {
  type        = bool
  description = "Set to true to create a new subnetwork, or false to reuse an existing subnetwork."
  default     = false
}

variable "subnet_name" {
  type        = string
  description = "Name of the new or existing subnetwork for the MCP Toolbox Direct VPC Egress."
}

variable "subnet_cidr" {
  type        = string
  description = "IPv4 CIDR range when creating a new subnetwork."
  default     = "10.10.0.0/24"
}

variable "oracle_host" {
  type        = string
  description = "Private IPv4 address of the Oracle E-Business Suite host (database listener and ISG web entry point)."

  validation {
    condition     = can(cidrhost("${var.oracle_host}/32", 0))
    error_message = "Use the private IPv4 address of the Oracle EBS host, for example 10.0.0.5."
  }
}

variable "oracle_port" {
  type        = number
  description = "Oracle E-Business Suite database listener port."
  default     = 1521
}

variable "oracle_service_name" {
  type        = string
  description = "Oracle E-Business Suite database service name."
  default     = "ebsdb"
}

variable "oracle_db_user" {
  type        = string
  description = "Read-only Oracle E-Business Suite database user for the MCP Toolbox (ebs-scripts/install_apps_ai_user.sql)."
  default     = "APPS_AI"
}

variable "oracle_db_password" {
  type        = string
  description = "Password of oracle_db_user. Set it in terraform.tfvars or TF_VAR_oracle_db_password, or let deploy_stack.sh read it from Secret Manager or prompt for it. Terraform writes it to Secret Manager as a write-only value."
  sensitive   = true
  ephemeral   = true
}

variable "oracle_db_password_version" {
  type        = number
  description = "Version of oracle_db_password. Increase it when you change the password, so Terraform writes the new secret version."
  default     = 1

  validation {
    condition     = var.oracle_db_password_version >= 1 && floor(var.oracle_db_password_version) == var.oracle_db_password_version
    error_message = "Use a whole number of at least 1."
  }
}

variable "ebs_isg_url" {
  type        = string
  description = "Base URL of the Oracle EBS web entry point that serves the Integrated SOA Gateway (ISG) REST services, for example https://ebs.example.internal:4443. Its host name must resolve to oracle_host. Defaults to https://<oracle_host>:4443."
  default     = null

  validation {
    condition     = var.ebs_isg_url == null || can(regex("^https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?$", var.ebs_isg_url))
    error_message = "Use a scheme, host, and optional port without a path, for example https://ebs.example.internal:4443."
  }
}

variable "ebs_writeback_user" {
  type        = string
  description = "Oracle EBS user name (FND_USER.USER_NAME) that calls the ISG REST service for the confirmed writebacks."
  default     = "VOLTGUARD_AGENT"

  validation {
    condition     = can(regex("^[A-Z0-9_.@-]+$", var.ebs_writeback_user))
    error_message = "Use an uppercase Oracle EBS user name, for example VOLTGUARD_AGENT."
  }
}

variable "ebs_writeback_password" {
  type        = string
  description = "Oracle EBS password of ebs_writeback_user. Set it in terraform.tfvars or TF_VAR_ebs_writeback_password, or let deploy_stack.sh read it from Secret Manager or prompt for it. Terraform writes it to Secret Manager as a write-only value."
  sensitive   = true
  ephemeral   = true
}

variable "ebs_writeback_password_version" {
  type        = number
  description = "Version of ebs_writeback_password. Increase it when you change the password, so Terraform writes the new secret version."
  default     = 1

  validation {
    condition     = var.ebs_writeback_password_version >= 1 && floor(var.ebs_writeback_password_version) == var.ebs_writeback_password_version
    error_message = "Use a whole number of at least 1."
  }
}

variable "ebs_inventory_responsibility" {
  type        = string
  description = "Oracle EBS responsibility key for transfers, safety stock updates, and notification closes."

  validation {
    condition     = can(regex("^[A-Z0-9_]+$", var.ebs_inventory_responsibility))
    error_message = "Use an Oracle EBS responsibility key, for example INVENTORY_VISION_OPERATIONS."
  }
}

variable "ebs_purchasing_responsibility" {
  type        = string
  description = "Oracle EBS responsibility key for purchase requisitions."

  validation {
    condition     = can(regex("^[A-Z0-9_]+$", var.ebs_purchasing_responsibility))
    error_message = "Use an Oracle EBS responsibility key, for example PURCHASING_OPERATIONS."
  }
}

variable "gemini_model" {
  type        = string
  description = "Primary Gemini model identifier on Vertex AI."
  default     = "gemini-3.8-flash"
}

variable "gemini_fallback_models" {
  type        = list(string)
  description = "Gemini models that take over, in order, when the primary model has no capacity or is unavailable."
  default     = ["gemini-3.7-flash", "gemini-3.5-flash-lite"]

  validation {
    condition     = length(var.gemini_fallback_models) > 0
    error_message = "List at least one fallback Gemini model."
  }
}

variable "gemini_location" {
  type        = string
  description = "Vertex AI location that serves the Gemini model."
  default     = "global"
}

variable "bigquery_location" {
  type        = string
  description = "BigQuery location of the signals dataset and the Gemini connection. The views read the Google Trends public dataset, which is in the US multi-region."
  default     = "US"
}

variable "mcp_timeout_seconds" {
  type        = number
  description = "Timeout in seconds for each MCP Toolbox request from the agent."
  default     = 120
}

variable "min_instance_count" {
  type        = number
  description = "Instances that the agent and the MCP Toolbox keep running. With 0, both scale to zero when idle, so an idle deployment adds no Cloud Run charges. Set 1 for a live demo to avoid cold starts and keep conversations through idle periods, and set 0 again afterwards."
  default     = 0

  validation {
    condition     = contains([0, 1], var.min_instance_count)
    error_message = "Use 0 or 1. The agent runs at most one instance, because sessions live in memory."
  }
}

variable "developer_user_email" {
  type        = string
  description = "Optional Google account email that gets the Cloud Run Invoker role on the agent and the MCP Toolbox for testing. That account can call the MCP Toolbox tools directly, without the agent's guardrails, so leave it empty outside testing."
  default     = ""
}
