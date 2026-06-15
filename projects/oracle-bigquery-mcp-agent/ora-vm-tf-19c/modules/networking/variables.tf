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
  description = "The Google Cloud Project ID where the VPC network will be provisioned"
}

variable "region" {
  type        = string
  description = "The target Google Cloud Region for allocating subnetworks and routers"
}

variable "create_vpc" {
  type        = bool
  default     = true
  description = "Toggle to dynamically create a new VPC network"
}

variable "create_subnetwork" {
  type        = bool
  default     = true
  description = "Toggle to dynamically create a new Subnetwork"
}

variable "vpc_name" {
  type        = string
  default     = "oracle-vpc"
  description = "The VPC network name"
}

variable "subnetwork_name" {
  type        = string
  default     = "oracle-subnet"
  description = "The subnetwork name"
}
