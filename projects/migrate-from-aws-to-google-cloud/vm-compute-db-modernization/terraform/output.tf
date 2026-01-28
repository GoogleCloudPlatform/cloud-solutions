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


output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "rds_endpoint" {
  description = "RDS endpoint (for GCP DMS)"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "RDS port"
  value       = aws_db_instance.postgres.port
}

output "db_security_group_id" {
  description = "Database Security Group ID"
  value       = aws_security_group.db_sg.id
}

output "app_instance_id" {
  description = "App Server EC2 Instance ID"
  value       = aws_instance.app.id
}

output "app_public_ip" {
  description = "App Server Public IP"
  value       = aws_instance.app.public_ip
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS Name"
  value       = aws_lb.app.dns_name
}

output "app_url" {
  description = "Application URL"
  value       = "http://${aws_lb.app.dns_name}"
}

output "summary" {
  description = "Deployment summary"
  value       = <<-EOT

    APPLICATION URL:
    http://${aws_lb.app.dns_name}

    RDS DATABASE INFO (for GCP DMS):
      Endpoint: ${aws_db_instance.postgres.address}
      Port:     ${aws_db_instance.postgres.port}
      Database: appdb
      DMS User: dms_user
      Password: SecureDmsPass123!

    APP SERVER INFO (for GCP M2VM):
      Instance ID: ${aws_instance.app.id}
      Public IP:   ${aws_instance.app.public_ip}

    SECURITY GROUP (to add DMS IPs):
      ${aws_security_group.db_sg.id}

    NEXT STEPS:
    1. Wait 3-5 minutes for initialization
    2. Test: curl http://${aws_lb.app.dns_name}/health

    ============================================================

  EOT
}
