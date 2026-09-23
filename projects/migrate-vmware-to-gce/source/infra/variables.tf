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

variable "source_project_id" {
  description = "Pre-created Google Cloud project that hosts the GCVE mock source environment."
  type        = string
}

variable "region" {
  description = "Region for GCVE. Must be one where VMware Engine is available."
  type        = string
  default     = "us-west2"
}

variable "zone" {
  description = "Zone for the GCVE private cloud, for example us-west2-a."
  type        = string
  default     = "us-west2-a"
}

variable "private_cloud_name" {
  description = "Name of the GCVE private cloud. Use a new name if the old one is still purging."
  type        = string
  default     = "demo-pc-v2"
}

variable "vmware_engine_network_name" {
  description = "Name of the VMware Engine network. Use a new name if the old one is still purging."
  type        = string
  default     = "demo-ven-v2"
}

variable "private_cloud_type" {
  description = "Private cloud type. TIME_LIMITED provisions a single node that expires after 60 days at the lowest cost."
  type        = string
  default     = "TIME_LIMITED"
}

variable "node_type_id" {
  description = "GCVE node specification type ID."
  type        = string
  default     = "standard-72"
}

variable "node_count" {
  description = "Number of GCVE nodes to allocate in the initial cluster."
  type        = number
  default     = 1
}

variable "management_cidr" {
  description = "CIDR for the vCenter, NSX, and ESXi management appliances."
  type        = string
  default     = "192.168.0.0/24"
}

variable "edge_services_cidr" {
  description = "CIDR range (/26) for the internet gateway and external IP services that the network policy uses."
  type        = string
  default     = "192.168.30.0/26"
}

variable "web_app_internal_ip" {
  description = "Internal IP of the workload VM that receives the public external address."
  type        = string
  default     = "10.10.20.15"
}

variable "admin_ip_cidr" {
  description = "Public IPv4 CIDR (/32) of your local machine for direct vCenter and NSX-T web interface access."
  type        = string
  default     = ""
}

variable "dns_domain" {
  description = "Internal domain name for the demo application."
  type        = string
  default     = "vmware-demo.example.com."
}

variable "vmware_engine_network_type" {
  description = "VMware Engine network type: STANDARD (default) or LEGACY."
  type        = string
  default     = "STANDARD"
}

variable "deletion_delay_hours" {
  description = "Number of hours to delay private cloud deletion, such as 0 for immediate deletion."
  type        = number
  default     = 0
}

variable "bastion_network_name" {
  description = "Name of the VPC network hosting the bastion jump host and demo client."
  type        = string
  default     = "bastion-vpc"
}

variable "bastion_subnetwork_name" {
  description = "Name of the subnetwork hosting the bastion jump host and demo client."
  type        = string
  default     = "bastion-subnet"
}

variable "bastion_subnet_cidr" {
  description = "CIDR range for the bastion subnet."
  type        = string
  default     = "10.20.0.0/24"
}

variable "bastion_machine_type" {
  description = "Machine type for the Linux bastion jump host."
  type        = string
  default     = "e2-standard-4"
}

variable "bastion_disk_size_gb" {
  description = "Boot disk size in GB for the Linux bastion jump host."
  type        = number
  default     = 50
}

variable "bastion_image" {
  description = "OS boot image for the Linux bastion jump host."
  type        = string
  default     = "ubuntu-os-cloud/ubuntu-2204-lts"
}

variable "demo_client_machine_type" {
  description = "Machine type for the demo client instance."
  type        = string
  default     = "e2-micro"
}

variable "demo_client_image" {
  description = "OS boot image for the demo client instance."
  type        = string
  default     = "debian-cloud/debian-12"
}

variable "web_app_port" {
  description = "Destination port for the demo web application external access rule."
  type        = number
  default     = 80
}

variable "web_app_allowed_source_cidrs" {
  description = "Allowed source CIDR blocks for incoming HTTP traffic to the demo web application."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "dns_record_ttl" {
  description = "TTL in seconds for the demo application DNS record."
  type        = number
  default     = 10
}
