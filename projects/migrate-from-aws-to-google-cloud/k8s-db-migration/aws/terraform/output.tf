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


output "aws_region" {
  description = "The AWS region."
  value       = var.aws_region
}

output "aws_prefix" {
  description = "Prefix for AWS resources"
  value       = var.aws_prefix
}

output "eks_cluster_name" {
  description = "The name of the EKS cluster."
  value       = module.eks.cluster_name
}

output "rds_db_identifier" {
  description = "RDS database ndentifier"
  value       = module.rds.db_instance_identifier
}

output "rds_endpoint" {
  description = "The endpoint of the RDS instance."
  value       = module.rds.db_instance_address
}

output "rds_username" {
  description = "The username for the RDS instance."
  value       = module.rds.db_instance_username
  sensitive   = true
}

output "ecr_registry_url" {
  description = "The base ECR registry URL."
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

output "db_security_group_id" {
  description = "DB security group ID"
  value       = module.db_sg.security_group_id
}

output "eks_cluster_security_group_id" {
  description = "EKS clustersecurity group ID"
  value       = module.eks.cluster_security_group_id
}

output "eks_node_security_group_id" {
  description = "EKS node security group ID"
  value       = module.eks.node_security_group_id
}

output "rds_access_policy_arn" {
  description = "The ARN of the IAM policy for the service account"
  value       = aws_iam_policy.rds_access.arn
}

output "aws_project_tag" {
  description = "Tag for AWS resources"
  value       = var.aws_project_tag
}

output "aws_environment_tag" {
  description = "Tag for AWS resources"
  value       = var.aws_environment_tag
}
