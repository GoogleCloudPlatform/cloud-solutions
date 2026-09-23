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

variable "target_project_id" {
  description = "Destination Google Cloud project where the workload lands."
  type        = string
}

variable "source_project_id" {
  description = "Source Google Cloud project hosting the simulated on-premises bastion VPC."
  type        = string
}

variable "region" {
  description = "Google Cloud region for the landing VPC and load balancer."
  type        = string
  default     = "us-west2"
}

variable "zone" {
  description = "Zone within the region for compute instances and instance groups."
  type        = string
  default     = "us-west2-a"
}

variable "subnet_cidr" {
  description = "CIDR for the landing subnet. This range intentionally matches the GCVE workload segment so that the migrated VM keeps its original IP address after cutover."
  type        = string
  default     = "10.10.20.0/24"
}

variable "migrated_instance_name" {
  description = "Name of the target Compute Engine instance created during cutover."
  type        = string
  default     = "web-app-01"
}

variable "app_port" {
  description = "TCP port on which the workload application serves traffic."
  type        = number
  default     = 80
}

variable "allowed_ingress_cidrs" {
  description = "CIDR blocks allowed to access the application port through the firewall. Defaults to 0.0.0.0/0 for demo convenience. Restrict to authorized corporate or client IP ranges for enterprise deployments."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "network_name" {
  description = "Name of the landing VPC network."
  type        = string
  default     = "landing-vpc"
}

variable "subnetwork_name" {
  description = "Name of the landing subnetwork."
  type        = string
  default     = "landing-subnet"
}

variable "source_network_name" {
  description = "Name of the VPC network in the source project to peer with."
  type        = string
  default     = "bastion-vpc"
}
