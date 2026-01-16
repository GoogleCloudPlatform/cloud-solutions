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
# RDS POSTGRESQL
# =============================================================================
resource "aws_db_parameter_group" "dms_pg16_logical_params" {
  name   = "${var.project_name}-${var.environment}-dms-pg16-logical-params"
  family = "postgres16"

  parameter {
    name         = "rds.logical_replication"
    value        = "1"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "wal_sender_timeout"
    value        = "0"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "max_replication_slots"
    value        = "10"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "max_wal_senders"
    value        = "10"
    apply_method = "pending-reboot"
  }

  tags = {
    Name        = "${var.project_name}-pg-16"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  tags = {
    Name        = "${var.project_name}-db-subnet-group"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16.9"
  instance_class = var.db_instance_class

  allocated_storage     = 40
  max_allocated_storage = 100
  storage_type          = "gp3"

  db_name  = var.db_name
  username = var.db_master_user
  password = var.db_master_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  parameter_group_name   = aws_db_parameter_group.dms_pg16_logical_params.name
  publicly_accessible    = true
  skip_final_snapshot    = true

  copy_tags_to_snapshot = true

  tags = {
    Name        = "${var.project_name}-db"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}

# =============================================================================
# APP SERVER EC2 INSTANCE
# =============================================================================

data "cloudinit_config" "app_config" {

  gzip          = true
  base64_encode = true

  part {
    content_type = "text/cloud-config"
    content = yamlencode({
      runcmd = [
        "mkdir -p /opt/flask-app"
      ]
      write_files = [
        {
          path        = "/opt/flask-app/requirements.txt"
          owner       = "root:root"
          permissions = "0644"
          content     = file("../scripts/requirements.txt")
        },
        {
          path        = "/opt/flask-app/app.py"
          owner       = "root:root"
          permissions = "0644"
          content     = file("../scripts/app.py")
        }
      ]
    })
  }

  part {
    content_type = "text/x-shellscript"
    content = templatefile("../scripts/app_setup.sh", {
      db_host            = aws_db_instance.postgres.address
      db_port            = "5432"
      db_name            = var.db_name
      db_user            = var.db_user
      db_password        = var.db_password
      db_master_user     = var.db_master_user
      db_master_password = var.db_master_password
      dms_user           = var.dms_user
      dms_password       = var.dms_password
    })
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.app_instance_type
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  subnet_id              = aws_subnet.public_1.id

  associate_public_ip_address = true

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data_base64 = data.cloudinit_config.app_config.rendered
  depends_on       = [aws_db_instance.postgres]

  tags = {
    Name        = "${var.project_name}-app"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }

  volume_tags = {
    Name        = "${var.project_name}-app-root-vol"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}

# =============================================================================
# APPLICATION LOAD BALANCER
# =============================================================================

resource "aws_lb" "app" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  tags = {
    Name        = "${var.project_name}-alb"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}

resource "aws_lb_target_group" "app" {
  name     = "${var.project_name}-tg"
  port     = 5000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Name        = "${var.project_name}-tg"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}

resource "aws_lb_listener" "app" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  tags = {
    Name        = "${var.project_name}-alb-listener"
    Project     = var.aws_project_tag
    Environment = var.aws_environment_tag
  }
}

resource "aws_lb_target_group_attachment" "app" {
  target_group_arn = aws_lb_target_group.app.arn
  target_id        = aws_instance.app.id
  port             = 5000
}
