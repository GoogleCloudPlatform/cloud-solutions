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
  description = "Tenant-controlled data project."
  type        = string
}

variable "region" {
  description = "Region for the key ring and the AlloyDB cluster."
  type        = string
}

variable "tenant_id" {
  description = "Tenant ID (label only)."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names (e.g. ct-acme)."
  type        = string
}

variable "allowed_consumer_projects" {
  description = "Projects (numbers or IDs) allowed to connect over PSC: the pooled platform project."
  type        = list(string)
  validation {
    condition     = length(var.allowed_consumer_projects) > 0
    error_message = "List at least the pooled platform project."
  }
}

variable "cpu_count" {
  description = "vCPUs for the primary instance."
  type        = number
  default     = 2
}

variable "labels" {
  description = "Base labels."
  type        = map(string)
  default     = {}
}
