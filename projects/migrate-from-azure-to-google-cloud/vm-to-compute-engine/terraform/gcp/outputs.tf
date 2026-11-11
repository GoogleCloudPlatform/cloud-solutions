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

output "lb_ip" {
  description = "Global static IP address of the load balancer. The self-signed certificate names this address."
  value       = module.lb_address.global_addresses[local.lb_address_name].address
}

output "ha_vpn_interface_ips" {
  description = "Public IP addresses of the HA VPN gateway, in tunnel order: element 0 is interface 0 for tunnel 0, element 1 is interface 1 for tunnel 1. The Azure configuration takes them under the same name."
  value = [
    for id in [0, 1] : one([
      for interface in module.vpn.gateway.vpn_interfaces : interface.ip_address if interface.id == id
    ])
  ]
}

output "router_name" {
  description = "Cloud Router that holds the BGP sessions with Azure."
  value       = module.vpn.router_name
}

output "vpn_tunnel_names" {
  description = "HA VPN tunnel names in tunnel order: element 0 is tunnel 0, element 1 is tunnel 1. Empty before you set ssl_certificate_name."
  value       = values(module.vpn.tunnel_names)
}

output "backend_service_names" {
  description = "Load balancer backend services, keyed by azure and gce. Null before you set ssl_certificate_name."
  value       = try(module.load_balancer[0].backend_service_names, null)
}
