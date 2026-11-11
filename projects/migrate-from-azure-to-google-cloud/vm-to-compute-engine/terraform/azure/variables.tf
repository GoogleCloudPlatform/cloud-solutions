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

variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "location" {
  description = "Azure location."
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

variable "vm_size" {
  description = "Azure VM size for the source VM."
  type        = string
  default     = "Standard_D2s_v5"
}

variable "data_disk_size_gb" {
  description = "Managed data disk size in GB."
  type        = number
  default     = 16
}

variable "admin_username" {
  description = "Administrator username on the source VM."
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key" {
  description = "SSH public key for the source VM."
  type        = string
}

# Azure VPN gateway connections require the IPsec pre-shared key in resource
# configuration, so Terraform persists it in state. Use an encrypted remote
# backend outside ephemeral demos.
variable "vpn_shared_key" {
  description = "Pre-shared key for both VPN connections."
  type        = string
  sensitive   = true
  nullable    = false
}

variable "ha_vpn_interface_ips" {
  description = "Google Cloud HA VPN interface IPs (set after deploying the Google Cloud foundation)."
  type        = list(string)
  default     = null

  validation {
    condition     = var.ha_vpn_interface_ips == null || length(var.ha_vpn_interface_ips) == 2
    error_message = "Provide both HA VPN interface IPs from the ha_vpn_interface_ips output of terraform/gcp."
  }
}

variable "azure_bgp_asn" {
  description = "BGP ASN of the Azure VPN gateway."
  type        = number
  default     = 65515
}

variable "azure_bgp_ips" {
  description = "Custom APIPA BGP addresses of the Azure VPN gateway instances."
  type        = list(string)
  default     = ["169.254.21.1", "169.254.22.1"]
}

variable "cloud_router_asn" {
  description = "Private BGP ASN of Cloud Router."
  type        = number
  default     = 64514
}

variable "cloud_router_bgp_ips" {
  description = "Cloud Router BGP interface CIDR ranges."
  type        = list(string)
  default     = ["169.254.21.2/30", "169.254.22.2/30"]
}
