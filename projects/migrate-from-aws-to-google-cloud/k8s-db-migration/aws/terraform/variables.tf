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

variable "aws_environment_tag" {
  description = "Tag for AWS resources"
  type        = string
  default     = "Dev"
}

variable "aws_prefix" {
  description = "A prefix to add to all created resources."
  type        = string
  default     = "mmb-demo"
}

variable "aws_project_tag" {
  description = "Tag for AWS resources"
  type        = string
  default     = "VmMigrationDemo1529"
}

variable "aws_region" {
  description = "The AWS region to deploy resources in."
  type        = string
  default     = "us-west-1"
}

variable "cymbal_services" {
  type        = set(string)
  description = "List of microservices to create ECR repos for"
  default = [
    "contacts",
    "loadgenerator",
    "frontend",
    "balancereader",
    "ledgerwriter",
    "transactionhistory",
    "userservice"
  ]
}

variable "dms_source_ip_cidrs" {
  description = "List of CIDR blocks for DMS IPs"
  type        = list(string)
  default     = []
}

variable "eks_node_desired_size" {
  description = "Desired number of EKS nodes"
  type        = number
  default     = 2
}

variable "eks_node_instance_types" {
  description = "Instance types for EKS nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "eks_node_max_size" {
  description = "Maximum number of EKS nodes"
  type        = number
  default     = 3
}

variable "eks_node_min_size" {
  description = "Minimum number of EKS nodes"
  type        = number
  default     = 1
}

variable "instance_type" {
  description = "The EC2 instance type."
  type        = string
  default     = "t2.micro"
}

variable "kubernetes_version" {
  description = "AWS EKS kubernetes version"
  type        = string
  default     = "1.34"
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "rds_password" {
  description = "The password for the RDS instance."
  type        = string
  default     = "Chiapet22!"
}

variable "vpc_cidr_block" {
  description = "The CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}
