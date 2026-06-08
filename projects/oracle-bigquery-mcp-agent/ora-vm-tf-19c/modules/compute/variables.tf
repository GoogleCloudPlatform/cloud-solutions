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
  type        = string
  description = "The Google Cloud Project ID where the database VM will be hosted"
}

variable "region" {
  type        = string
  description = "The Google Cloud Region for compute resource deployments"
}

variable "zone" {
  type        = string
  description = "The Google Cloud Zone where the GCE virtual machine hypervisor will be allocated"
}

variable "subnetwork_name" {
  type        = string
  description = "The name identifier of the VPC subnetwork to bind the VM network interface"
}

variable "ssh_user" {
  type        = string
  description = "The POSIX username assigned to administer OS login and SSH tunnels on the GCE instance"
}

variable "gcs_bucket_name" {
  type        = string
  description = "The GCS staging bucket containing Oracle 19c database installation scripts"
}

variable "rpm_name" {
  type        = string
  description = "The exact file name of the Oracle 19c Database Enterprise Edition RPM package"
}

variable "ssh_key_path" {
  type        = string
  description = "The local filesystem path to the private SSH key used to negotiate handshake authentication"
}

variable "os_image_family" {
  type        = string
  default     = "oracle-linux-8"
  description = "The GCE image family used for the database VM"
}

variable "os_image_project" {
  type        = string
  default     = "oracle-linux-cloud"
  description = "The Google Cloud project hosting the target database VM image"
}

variable "machine_type" {
  type        = string
  default     = "n2-standard-4"
  description = "The GCE virtual machine hardware profile type (e.g., 'n2-standard-4')"
}

variable "service_account_email" {
  type        = string
  description = "The custom dedicated service account email assigned to the GCE VM to adhere to SRE least privilege security guidelines"
}
