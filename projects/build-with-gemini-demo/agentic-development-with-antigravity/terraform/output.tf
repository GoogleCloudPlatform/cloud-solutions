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

output "project_id" {
  value       = data.google_project.project.project_id
  description = "The Google Cloud project ID"
}

output "region" {
  value       = var.region
  description = "The Google Cloud region"
}

output "gke_cluster_name" {
  value       = google_container_cluster.primary.name
  description = "The name of the GKE cluster"
}

output "sql_instance_name" {
  value       = google_sql_database_instance.postgres.name
  description = "The name of the Cloud SQL instance"
}

output "sql_instance_connection_name" {
  value       = google_sql_database_instance.postgres.connection_name
  description = "The connection name of the Cloud SQL instance"
}

output "db_password" {
  value     = random_password.db_password.result
  sensitive = true
}

output "artifact_registry_repo" {
  value       = google_artifact_registry_repository.repo.name
  description = "The name of the Artifact Registry repository"
}

output "load_balancer_ip" {
  value       = google_compute_global_address.lb_ip.address
  description = "The static IP for the Load Balancer"
}
