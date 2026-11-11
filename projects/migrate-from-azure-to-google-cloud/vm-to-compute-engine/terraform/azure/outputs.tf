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

output "cross_cloud" {
  description = "Values that both configurations must agree on. Copy this object to the cross_cloud variable of the Google Cloud configuration. The VPN gateway IP addresses are in tunnel order: element 0 for tunnel 0 and element 1 for tunnel 1."
  value = {
    azure_vnet_cidr       = local.vnet_cidr
    azure_vm_private_ip   = azurerm_network_interface.source.private_ip_address
    azure_vpn_gateway_ips = azurerm_public_ip.vpn_gateway[*].ip_address
    azure_bgp_asn         = var.azure_bgp_asn
    azure_bgp_ips         = var.azure_bgp_ips
    cloud_router_asn      = var.cloud_router_asn
    cloud_router_bgp_ips  = var.cloud_router_bgp_ips
    lb_source_ranges      = local.lb_source_ranges
    app_port              = local.app_port
  }
}

output "discovery_client_id" {
  description = "Application (client) ID of the read-only app registration for the Migration Center discovery client."
  value       = azuread_application.migration["discovery"].client_id
}

output "m2vm_client_id" {
  description = "Application (client) ID of the app registration for Migrate to Virtual Machines."
  value       = azuread_application.migration["m2vm"].client_id
}
