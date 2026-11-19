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
  description = "The tenant's dedicated (silo) project."
  type        = string
}

variable "project_number" {
  description = "Number of the silo project (used for the deterministic broker URL)."
  type        = string
}

variable "region" {
  description = "Region for the silo stack."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Resource-name suffix (e.g. prod)."
  type        = string
  default     = "prod"
}

variable "platform_environment" {
  description = "Platform config environment the gateway loads (config/environments/<name>.yaml)."
  type        = string
}

variable "gateway_container_image" {
  description = "Gateway image (the broker uses the same image with another entrypoint)."
  type        = string
}

variable "enable_alloydb_cluster" {
  description = "Create the tenant's AlloyDB cluster in the silo project."
  type        = bool
  default     = false
}

variable "iap_accessors" {
  description = "IAP accessors for the silo gateway (operators only)."
  type        = list(string)
  default     = []
}

variable "tenant" {
  description = "The one tenant in this silo (mirrors config/tenants/<env>/<tenant>.yaml)."
  type = object({
    tenant_id  = string
    cmek_key   = string
    secret_ids = optional(list(string), [])
  })
}
