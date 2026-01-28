# Copyright 2025 Google LLC
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

variable "aws_project_tag" {
  description = "Tag for AWS resources"
  type        = string
  default     = "VmMigrationDemo1529"
}

variable "aws_environment_tag" {
  description = "Tag for AWS resources"
  type        = string
  default     = "Dev"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}
variable "aws_user" {
  description = "AWS user"
  type        = string
}

# =============================================================================
# VPC Variables
# =============================================================================

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_1_cidr" {
  description = "CIDR block for public subnet 1"
  type        = string
  default     = "10.0.1.0/24"
}

variable "public_subnet_2_cidr" {
  description = "CIDR block for public subnet 2"
  type        = string
  default     = "10.0.2.0/24"
}

# =============================================================================
# EC2 Variables
# =============================================================================

variable "app_instance_type" {
  description = "EC2 instance type for app server"
  type        = string
  default     = "t3.small"
}

# =============================================================================
# RDS Variables
# =============================================================================

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "Name of the application database"
  type        = string
  default     = "appdb"
}

variable "db_master_user" {
  description = "RDS master username"
  type        = string
  default     = "postgres"
}

variable "db_master_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
  default     = "SecureAppPass123!"
}

variable "db_user" {
  description = "Application database user"
  type        = string
  default     = "appuser"
}

variable "db_password" {
  description = "Password for application database user"
  type        = string
  sensitive   = true
  default     = "SecureAppPass123!"
}

variable "dms_user" {
  description = "Database Migration Service user"
  type        = string
  default     = "dms_user"
}

variable "dms_password" {
  description = "Password for DMS user"
  type        = string
  sensitive   = true
  default     = "SecureDmsPass123!"
}

# =============================================================================
# Naming Variables
# =============================================================================

variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
  default     = "hero-demo-app"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}
