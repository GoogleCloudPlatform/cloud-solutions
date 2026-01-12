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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

locals {
  az_count = min(length(data.aws_availability_zones.available.names), 3)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.6.0"

  name = "${var.aws_prefix}-vpc"
  cidr = var.vpc_cidr_block

  azs = slice(data.aws_availability_zones.available.names, 0, local.az_count)

  private_subnets = [for k, v in slice(data.aws_availability_zones.available.names, 0, local.az_count) : cidrsubnet(var.vpc_cidr_block, 4, k)]
  public_subnets  = [for k, v in slice(data.aws_availability_zones.available.names, 0, local.az_count) : cidrsubnet(var.vpc_cidr_block, 4, k + local.az_count)]

  enable_nat_gateway      = true
  single_nat_gateway      = true
  enable_dns_hostnames    = true
  enable_dns_support      = true
  map_public_ip_on_launch = true

  public_subnet_tags = {
    "Project"                                            = var.aws_project_tag
    "Env"                                                = var.aws_environment_tag
    "kubernetes.io/role/elb"                             = "1"
    "kubernetes.io/cluster/${var.aws_prefix}-cymbalbank" = "shared"
  }
  private_subnet_tags = {
    "Project"                                            = var.aws_project_tag
    "Env"                                                = var.aws_environment_tag
    "kubernetes.io/role/internal-elb"                    = "1"
    "kubernetes.io/cluster/${var.aws_prefix}-cymbalbank" = "shared"
  }

  nat_gateway_tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }
  nat_eip_tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }

  tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }

  igw_tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }
}
