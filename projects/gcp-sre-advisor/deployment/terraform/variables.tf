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
  description = "Runtime Google Cloud project ID hosting GCP SRE Advisor"
  type        = string

  validation {
    condition     = length(trimspace(var.project_id)) > 0
    error_message = "project_id must not be empty."
  }
}

variable "region" {
  description = "Primary Google Cloud region for Vertex AI Agent Engine and optional Cloud Run services"
  type        = string
  default     = "us-central1"
}

variable "name_prefix" {
  description = "Resource naming prefix for staging storage and optional services"
  type        = string
  default     = "gcp-sre-advisor"
}

variable "service_account_id" {
  description = "Account ID for the read-only GCP SRE Advisor runtime service account"
  type        = string
  default     = "sa-sre-advisor-reader"
}

variable "staging_bucket_name" {
  description = "Optional explicit Cloud Storage bucket name for Agent Engine staging and profile catalog"
  type        = string
  default     = ""
}

variable "target_project_ids" {
  description = "Additional Google Cloud project IDs granted read-only inspection access"
  type        = set(string)
  default     = []
}

variable "labels" {
  description = "Resource labels applied to managed storage and optional Cloud Run resources"
  type        = map(string)
  default     = {}
}

variable "database_toolbox" {
  description = "Optional Cloud Run deployment settings for Google MCP Toolbox for Databases"
  type = object({
    enabled              = bool
    vpc_network          = optional(string, "")
    vpc_subnetwork       = optional(string, "")
    tools_yaml_secret_id = optional(string, "")
    image                = optional(string, "us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest")
    min_instances        = optional(number, 0)
    max_instances        = optional(number, 3)
  })
  default = {
    enabled = false
  }

  validation {
    condition     = !var.database_toolbox.enabled || length(trimspace(var.database_toolbox.tools_yaml_secret_id)) > 0
    error_message = "database_toolbox.tools_yaml_secret_id must be provided when database_toolbox.enabled is true."
  }

  validation {
    condition     = (length(trimspace(var.database_toolbox.vpc_network)) == 0) == (length(trimspace(var.database_toolbox.vpc_subnetwork)) == 0)
    error_message = "database_toolbox.vpc_network and database_toolbox.vpc_subnetwork must either both be set or both be empty."
  }
}

variable "catalog_toolbox" {
  description = "Optional Cloud Run deployment settings for a SQL CMDB Catalog MCP Gateway via Google MCP Toolbox"
  type = object({
    enabled              = bool
    vpc_network          = optional(string, "")
    vpc_subnetwork       = optional(string, "")
    tools_yaml_secret_id = optional(string, "")
    image                = optional(string, "us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest")
    min_instances        = optional(number, 0)
    max_instances        = optional(number, 3)
  })
  default = {
    enabled = false
  }

  validation {
    condition     = !var.catalog_toolbox.enabled || length(trimspace(var.catalog_toolbox.tools_yaml_secret_id)) > 0
    error_message = "catalog_toolbox.tools_yaml_secret_id must be provided when catalog_toolbox.enabled is true."
  }

  validation {
    condition     = (length(trimspace(var.catalog_toolbox.vpc_network)) == 0) == (length(trimspace(var.catalog_toolbox.vpc_subnetwork)) == 0)
    error_message = "catalog_toolbox.vpc_network and catalog_toolbox.vpc_subnetwork must either both be set or both be empty."
  }
}
