# Copyright 2026 Google LLC
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

variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Google Cloud region."
  type        = string
}

variable "zone" {
  description = "Google Cloud zone."
  type        = string
}

variable "prefix" {
  description = "Resource name prefix: 3 to 12 lowercase letters, digits, or hyphens, starting with a letter. Keep the default (vm-demo) when following README.md and scripts/cleanup.sh."
  type        = string
  default     = "vm-demo"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,11}$", var.prefix))
    error_message = "Use 3-12 lowercase letters, digits, or hyphens, starting with a letter."
  }
}

# Compute Engine HA VPN tunnels require the IPsec pre-shared key in resource
# configuration, so Terraform persists it in state. Use an encrypted remote
# backend outside ephemeral demos.
variable "vpn_shared_key" {
  description = "Pre-shared key for both HA VPN tunnels."
  type        = string
  sensitive   = true
  nullable    = false
}

variable "prod_subnet_cidr" {
  description = "IPv4 CIDR range for the prod subnet."
  type        = string
  default     = "10.10.0.0/24"
}

variable "test_subnet_cidr" {
  description = "IPv4 CIDR range for the isolated test subnet."
  type        = string
  default     = "10.10.1.0/24"
}

variable "network_tag" {
  description = "Network tag that the firewall rules target."
  type        = string
  default     = "migrated-app"
}

variable "health_check_path" {
  description = "HTTP health check path."
  type        = string
  default     = "/healthz"
}

variable "gce_weight" {
  description = "Load balancer weight (0-100) for the gce backend."
  type        = number
  default     = 0
  nullable    = false

  validation {
    condition     = var.gce_weight >= 0 && var.gce_weight <= 100 && floor(var.gce_weight) == var.gce_weight
    error_message = "Set gce_weight to a whole number from 0 to 100."
  }
}

variable "migrated_instance_name" {
  description = "Migrated Compute Engine instance name (empty before cut-over)."
  type        = string
  default     = ""
  nullable    = false
}

variable "operator_member" {
  description = "IAM principal that runs the migration, such as user:alice@example.com."
  type        = string
}

variable "vpn_peer_policy_enforced" {
  description = "Whether the org enforces compute.restrictVpnPeerIPs."
  type        = bool
}

variable "cross_cloud" {
  description = "Values that both configurations must agree on (from the cross_cloud output of terraform/azure)."
  type = object({
    azure_vnet_cidr       = string
    azure_vm_private_ip   = string
    azure_vpn_gateway_ips = list(string)
    azure_bgp_asn         = number
    azure_bgp_ips         = list(string)
    cloud_router_asn      = number
    cloud_router_bgp_ips  = list(string)
    lb_source_ranges      = list(string)
    app_port              = number
  })
}

variable "ssl_certificate_name" {
  description = "Uploaded self-managed SSL certificate name (enables the VPN tunnels and load balancer)."
  type        = string
  default     = null

  validation {
    condition     = var.ssl_certificate_name == null || can(regex("^[a-z]([-a-z0-9]{0,61}[a-z0-9])?$", var.ssl_certificate_name))
    error_message = "Set ssl_certificate_name to a valid Compute Engine SSL certificate name."
  }
}
