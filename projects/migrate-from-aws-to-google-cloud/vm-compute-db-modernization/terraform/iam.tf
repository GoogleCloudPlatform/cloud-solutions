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

# =============================================================================
# IAM - Session Manager Access
# =============================================================================

resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}

resource "aws_iam_role_policy_attachment" "ssm_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

data "aws_iam_policy_document" "migration_center_discovery_document" {

  # Statement 1: Read-Only Discovery (EC2, RDS, ELB, S3, etc.)
  statement {
    sid    = "DiscoveryReadOnly"
    effect = "Allow"
    actions = [
      "ec2:Describe*",
      "ec2:DescribeInstances",
      "rds:DescribeDBEngineVersions",
      "elasticloadbalancing:DescribeTags",
      "ec2:DescribeRegions",
      "ebs:ListSnapshotBlocks",
      "ec2:DescribeNatGateways",
      "ec2:DescribeSnapshots",
      "ebs:ListChangedBlocks",
      "ec2:DescribeSecurityGroups",
      "elasticloadbalancing:DescribeLoadBalancers",
      "elasticloadbalancing:DescribeListeners",
      "ec2:DescribeVpcs",
      "ec2:DescribeVolumes",
      "elasticloadbalancing:DescribeTargetHealth",
      "rds:DescribeDBInstances",
      "ec2:DescribeInstanceTypes",
      "elasticloadbalancing:DescribeTargetGroups",
      "elasticloadbalancing:DescribeRules",
      "elasticloadbalancing:DescribeInstanceHealth",
      "ec2:DescribeSubnets",
      "ec2:DescribeNetworkAcls",
      "ebs:GetSnapshotBlock"
    ]
    resources = ["*"]
  }

  # =============================================================================
  # IAM - Policy Migration Center
  # =============================================================================
  statement {
    sid    = "MetricsCollection"
    effect = "Allow"
    actions = [
      "cloudwatch:ListMetrics",
      "cloudwatch:GetMetricData"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "migration_center_discovery_policy" {
  name        = "${var.project_name}-MigrationCenter-Discovery-Read-Only"
  description = "Minimal read-only policy for Google Cloud Migration Center AWS discovery."
  policy      = data.aws_iam_policy_document.migration_center_discovery_document.json


  tags = {
    Name        = "${var.project_name}-MigrationCenter-Discovery-Policy"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}
resource "aws_iam_user_policy_attachment" "migration_discovery_attach" {
  user       = var.aws_user
  policy_arn = aws_iam_policy.migration_center_discovery_policy.arn
}
