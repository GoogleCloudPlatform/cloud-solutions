# Copyright 2025 Google LLC
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

locals {
  nat_gateway_name        = var.nat_gateway_name != null ? var.nat_gateway_name : var.unique_identifier_prefix
  network_name            = var.network_name != null ? var.network_name : var.unique_identifier_prefix
  networking_network_name = local.network_name
  router_name             = var.router_name != null ? var.router_name : var.unique_identifier_prefix
  subnetwork_name         = var.subnetwork_name != null ? var.subnetwork_name : var.unique_identifier_prefix
}

variable "project_id" {
  description = "The GCP project where to create resources"
  type        = string
}

variable "unique_identifier_prefix" {
  description = "Unique resource name prefix"
  type        = string
}

variable "dynamic_routing_mode" {
  default     = "GLOBAL"
  description = "VPC dynamic routing mode"
  type        = string
}

variable "nat_gateway_name" {
  default     = null
  description = "Name of the Cloud NAT Gateway"
  type        = string
}

variable "network_name" {
  default     = null
  description = "Name of the VPC network"
  type        = string
}

variable "region" {
  description = "Region where to create the network and the subnetwork"
  type        = string
}

variable "router_name" {
  default     = null
  description = "Name of the Cloud Router"
  type        = string
}

variable "subnet_cidr_range" {
  default     = "10.40.0.0/22"
  description = "CIDR range for the regional subnet"
  type        = string
}

variable "subnetwork_name" {
  default     = null
  description = "Name of the regional subnet"
  type        = string
}
