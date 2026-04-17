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

variable "aws_region" {
  type        = string
  description = "The AWS region to deploy resources into"
  default     = "us-west-1"
}

variable "node_instance_type" {
  type        = string
  description = "The instance type for EKS worker nodes"
  default     = "t3.medium"
}

variable "node_count" {
  type        = number
  description = "The number of worker nodes in the EKS cluster"
  default     = 1
}

variable "node_min_capacity" {
  type        = number
  description = "The minimum number of worker nodes in the EKS cluster"
  default     = 1
}

variable "node_max_capacity" {
  type        = number
  description = "The maximum number of worker nodes in the EKS cluster"
  default     = 4
}
