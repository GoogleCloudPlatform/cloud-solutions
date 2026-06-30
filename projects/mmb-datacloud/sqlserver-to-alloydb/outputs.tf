/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

output "gcp_project_id" {
  value       = var.gcp_project_id
  description = "The Google Cloud Project ID"
}

output "gcp_region" {
  value       = var.gcp_region
  description = "The Google Cloud Region"
}

output "gcp_zone" {
  value       = var.gcp_zone
  description = "The Google Cloud Zone"
}

output "sql_server_instance_name" {
  value       = google_sql_database_instance.mssql_source.name
  description = "The Cloud SQL SQL Server instance name"
}

output "sql_server_private_ip" {
  value       = google_sql_database_instance.mssql_source.private_ip_address
  description = "The private IP address of the source SQL Server instance"
}

output "sql_server_password" {
  value       = nonsensitive(random_password.sql_server_password.result)
  description = "The dynamically generated admin password for the SQL Server 'sqlserver' user"
}

output "loader_vm_name" {
  value       = google_compute_instance.mssql_loader_vm.name
  description = "The helper loader VM instance name"
}
