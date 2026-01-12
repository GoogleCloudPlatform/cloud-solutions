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

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "7.0.1"

  identifier = "${var.aws_prefix}-cymbalbankdb"

  engine            = "postgres"
  engine_version    = "16"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  db_name           = "cymbalbank"
  username          = "postgres"
  port              = 5432

  manage_master_user_password = false
  password_wo                 = var.rds_password
  password_wo_version         = 1
  vpc_security_group_ids      = [module.db_sg.security_group_id]
  subnet_ids                  = module.vpc.public_subnets

  # DB subnet group
  create_db_subnet_group = true

  maintenance_window              = "Mon:00:00-Mon:03:00"
  backup_window                   = "03:00-06:00"
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  publicly_accessible             = true
  skip_final_snapshot             = true

  # DB parameter group
  family = "postgres16"
  parameters = [
    {
      name         = "rds.force_ssl"
      value        = "0"
      apply_method = "pending-reboot"
    },
    {
      name         = "rds.logical_replication"
      value        = "1"
      apply_method = "pending-reboot"
    },
    {
      name         = "shared_preload_libraries"
      value        = "pg_stat_statements,pg_tle,pglogical"
      apply_method = "pending-reboot"
    },
    {
      name         = "wal_sender_timeout"
      value        = "0"
      apply_method = "immediate"
    },
    {
      name         = "max_replication_slots"
      value        = "20"
      apply_method = "pending-reboot"
    },
    {
      name         = "max_wal_senders"
      value        = "20"
      apply_method = "pending-reboot"
    },
    {
      name         = "max_worker_processes"
      value        = "16"
      apply_method = "pending-reboot"
    }
  ]

  tags = {
    Project = var.aws_project_tag
    Env     = var.aws_environment_tag
  }
}
