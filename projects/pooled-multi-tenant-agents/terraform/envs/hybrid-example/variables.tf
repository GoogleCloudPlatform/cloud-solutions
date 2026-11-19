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

variable "tenant_project_id" {
  description = "Tenant-controlled data project."
  type        = string
}

variable "tenant_id" {
  description = "Tenant ID (config/tenants/<env>/<tenant>.yaml)."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for the tenant's data-plane resources."
  type        = string
}

variable "region" {
  description = "Region (same for the data plane and the PSC endpoint)."
  type        = string
  default     = "us-central1"
}

variable "pooled_project_id" {
  description = "Pooled platform project (the PSC consumer)."
  type        = string
}

variable "pooled_network" {
  description = "Pooled VPC self link or ID for the PSC endpoint."
  type        = string
}

variable "pooled_subnetwork" {
  description = "Pooled subnetwork self link or ID for the PSC endpoint address."
  type        = string
}
