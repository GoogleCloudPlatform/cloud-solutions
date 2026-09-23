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

variable "source_state_path" {
  description = "Path to the local terraform state file of the source/infra stage."
  type        = string
  default     = "../infra/terraform.tfstate"
}

variable "segment_name" {
  description = "Name of the NSX-T overlay segment for workloads."
  type        = string
  default     = "demo-workload"
}

variable "segment_gateway_cidr" {
  description = "NSX segment gateway in CIDR form. Terraform derives the VM gateway from this value."
  type        = string
  default     = "10.10.20.1/24"
}

variable "vm_name" {
  description = "Name of the sample workload virtual machine in vCenter."
  type        = string
  default     = "web-app-01"
}

variable "datacenter_name" {
  description = "GCVE default vSphere datacenter name."
  type        = string
  default     = "Datacenter"
}

variable "datastore_name" {
  description = "vSphere datastore that stores the VM disk."
  type        = string
  default     = "vsanDatastore"
}

variable "ubuntu_ova_url" {
  description = "Ubuntu cloud OVA that vCenter pulls into the content library."
  type        = string
  default     = "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-amd64.ova"
}

variable "vm_cpus" {
  description = "Number of vCPUs to allocate to the workload virtual machine."
  type        = number
  default     = 2
}

variable "vm_memory_mb" {
  description = "Memory in megabytes (MB) to allocate to the workload virtual machine."
  type        = number
  default     = 2048
}

variable "vm_disk_size_gb" {
  description = "Root disk size in gigabytes (GB) for the workload virtual machine."
  type        = number
  default     = 20
}

variable "vm_disk_thin_provisioned" {
  description = "Whether to thin-provision the workload virtual machine disk."
  type        = bool
  default     = true
}

variable "vsphere_folder" {
  description = "vSphere VM folder path that contains the workload VM."
  type        = string
  default     = "Workload VMs"
}

variable "vm_dns_servers" {
  description = "List of DNS nameserver IP addresses configured inside the workload VM."
  type        = list(string)
  default     = ["8.8.8.8", "8.8.4.4"]
}

variable "vm_guest_id" {
  description = "vSphere guest ID for the workload operating system."
  type        = string
  default     = "ubuntu64Guest"
}
