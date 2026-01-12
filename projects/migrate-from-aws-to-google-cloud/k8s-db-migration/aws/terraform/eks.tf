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

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = "${var.aws_prefix}-cymbalbank"
  kubernetes_version = var.kubernetes_version

  endpoint_public_access                   = true
  enable_cluster_creator_admin_permissions = true
  create_cloudwatch_log_group              = false

  compute_config = {
    enabled    = true
    node_pools = ["general-purpose"]
  }

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.public_subnets
  control_plane_subnet_ids = module.vpc.public_subnets

  enable_auto_mode_custom_tags = true

  enable_irsa = true

  addons = {
    vpc-cni = {
      most_recent = true
    }
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
  }

  iam_role_tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }

  tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }

  cluster_tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }

  node_security_group_tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }
}
