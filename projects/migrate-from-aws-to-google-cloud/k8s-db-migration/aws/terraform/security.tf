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

module "db_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "5.3.1"

  name        = "${var.aws_prefix}-db-sg"
  description = "Allow inbound traffic to the database"
  vpc_id      = module.vpc.vpc_id

  ingress_with_cidr_blocks = length(var.dms_source_ip_cidrs) > 0 ? [
    {
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      description = "DMS Source Access"
      cidr_blocks = join(",", var.dms_source_ip_cidrs)
    }
  ] : []

  egress_with_cidr_blocks = [
    {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = "0.0.0.0/0"
    }
  ]

  tags = {
    Name    = "${var.aws_prefix}-db-sg"
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }
}

resource "aws_security_group_rule" "db_from_eks_cluster" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  description              = "PostgreSQL from Cluster"
  security_group_id        = module.db_sg.security_group_id
  source_security_group_id = module.eks.cluster_primary_security_group_id
}

resource "aws_iam_policy" "rds_access" {
  name        = "${var.aws_prefix}-cymbalbank-rds-access"
  description = "IAM policy for Cymbal Bank app to access RDS"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "rds-db:*"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:rds-db:${var.aws_region}:${data.aws_caller_identity.current.account_id}:dbuser:${module.rds.db_instance_resource_id}/*",
      },
    ],
  })

  tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }
}


