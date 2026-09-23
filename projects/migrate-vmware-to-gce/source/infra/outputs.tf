/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

output "project_id" {
  description = "Source Google Cloud project ID."
  value       = var.source_project_id
}

output "region" {
  description = "Source Google Cloud region."
  value       = var.region
}

output "zone" {
  description = "Source Google Cloud zone."
  value       = var.zone
}

output "private_cloud_name" {
  description = "GCVE private cloud name."
  value       = google_vmwareengine_private_cloud.this.name
}

output "cluster_name" {
  description = "GCVE management cluster name."
  value       = google_vmwareengine_private_cloud.this.management_cluster[0].cluster_id
}

output "vcenter_fqdn" {
  description = "vCenter fully qualified domain name (FQDN)."
  value       = google_vmwareengine_private_cloud.this.vcenter[0].fqdn
}

output "nsx_fqdn" {
  description = "NSX Manager fully qualified domain name (FQDN)."
  value       = google_vmwareengine_private_cloud.this.nsx[0].fqdn
}

output "nsx_public_ip" {
  description = "Public external IP for NSX-T Manager web interface access."
  value       = google_vmwareengine_external_address.nsx.external_ip
}

output "vcenter_public_ip" {
  description = "Public external IP for vCenter web interface access."
  value       = google_vmwareengine_external_address.vcenter.external_ip
}

output "web_app_internal_ip" {
  description = "Demo web app internal IP inside the GCVE workload segment."
  value       = var.web_app_internal_ip
}

output "web_app_public_ip" {
  description = "Public NAT IP for demo web app."
  value       = google_vmwareengine_external_address.web_app.external_ip
}

output "bastion_ssh_command" {
  description = "SSH into the Linux bastion jump host using Identity-Aware Proxy."
  value       = "gcloud compute ssh ${google_compute_instance.linux_bastion.name} --zone=${var.zone} --project=${var.source_project_id}"
}

output "vcenter_url" {
  description = "vCenter web interface URL."
  value       = "https://${google_vmwareengine_private_cloud.this.vcenter[0].fqdn}"
}

output "vcenter_password_command" {
  description = "Fetch vCenter admin credentials using gcloud."
  value       = "gcloud vmware private-clouds vcenter credentials describe --private-cloud=${google_vmwareengine_private_cloud.this.name} --location=${var.zone} --project=${var.source_project_id}"
}

output "cloud_dns_inbound_policy" {
  description = "Name of the Cloud DNS Inbound Server Policy for on-premises forwarding."
  value       = google_dns_policy.inbound.name
}

output "dns_server_ip" {
  description = "GCVE internal DNS server IP address for OVF deployment and resolution."
  value       = google_vmwareengine_private_cloud.this.network_config[0].dns_server_ip
}

output "vcenter_internal_ip" {
  description = "vCenter Server internal IP address for Migrate Connector registration."
  value       = google_vmwareengine_private_cloud.this.vcenter[0].internal_ip
}

output "watch_demo_client" {
  description = "Live view of DNS answer and app response from demo-client in the source environment."
  value       = "gcloud compute ssh demo-client --zone=${var.zone} --project=${var.source_project_id} --tunnel-through-iap -- tail -f /var/log/demo-watch.log"
}

output "dns_zone_name" {
  description = "Cloud DNS managed zone name for the demo application."
  value       = google_dns_managed_zone.demo_zone.name
}

output "dns_domain" {
  description = "Domain name for the demo application."
  value       = var.dns_domain
}
