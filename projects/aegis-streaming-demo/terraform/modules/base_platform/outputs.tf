# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

output "vpc_network_id" {
  description = "The ID of the provisioned Aegis VPC Network."
  value       = google_compute_network.aegis_vpc.id
}

output "subnet_id" {
  description = "The ID of the provisioned Aegis VPC Subnetwork."
  value       = google_compute_subnetwork.aegis_subnet.id
}

output "service_account_email" {
  description = "The email address of the Aegis Service Account."
  value       = google_service_account.aegis_sa.email
}

output "bigtable_instance_id" {
  description = "The ID of the provisioned Cloud Bigtable instance."
  value       = google_bigtable_instance.aegis_bigtable.name
}

output "bigquery_dataset_id" {
  description = "The ID of the provisioned BigQuery Analytics dataset."
  value       = google_bigquery_dataset.analytics.dataset_id
}

output "telemetry_table_id" {
  description = "The ID of the provisioned BigQuery telemetry events table."
  value       = google_bigquery_table.telemetry_events.table_id
}

output "artifact_registry_repo" {
  description = "The name of the provisioned Artifact Registry Docker repository."
  value       = google_artifact_registry_repository.aegis_containers.name
}

output "agent_service_url" {
  description = "Resource name of the deployed Agent on Gemini Enterprise Agent Platform (GEAP)."
  value       = data.external.geap_agent.result["resource_name"]
}

output "geap_agent_id" {
  description = "The dynamically retrieved Resource ID of the deployed GEAP Reasoning Engine."
  value       = data.external.geap_agent.result["agent_id"]
}

output "telemetry_simulator_url" {
  description = "URL of the standalone Telemetry Simulator Service on Cloud Run."
  value       = google_cloud_run_v2_service.telemetry_simulator.uri
}

output "hud_backend_url" {
  description = "URL of the deployed HUD Backend Service on Cloud Run."
  value       = google_cloud_run_v2_service.hud_backend.uri
}

output "hud_frontend_url" {
  description = "URL of the deployed HUD Frontend Web Application on Cloud Run."
  value       = google_cloud_run_v2_service.hud_frontend.uri
}
