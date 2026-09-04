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

output "agent_service_url" {
  description = "Resource name of the deployed Agent on Gemini Enterprise Agent Platform (GEAP)."
  value       = data.external.geap_agent.result["resource_name"]
}

output "geap_agent_id" {
  description = "The dynamically retrieved Resource ID of the deployed GEAP Reasoning Engine."
  value       = data.external.geap_agent.result["agent_id"]
}

output "hud_backend_url" {
  description = "URL of the deployed HUD Backend Service on Cloud Run."
  value       = google_cloud_run_v2_service.hud_backend.uri
}

output "telemetry_simulator_url" {
  description = "URL of the standalone Telemetry Simulator Service on Cloud Run."
  value       = google_cloud_run_v2_service.telemetry_simulator.uri
}

output "hud_frontend_url" {
  description = "URL of the deployed HUD Frontend Web Application on Cloud Run."
  value       = google_cloud_run_v2_service.hud_frontend.uri
}

output "bigtable_instance_id" {
  description = "The ID of the provisioned Cloud Bigtable instance."
  value       = google_bigtable_instance.aegis_bigtable.name
}

output "bigquery_dataset_id" {
  description = "The ID of the provisioned BigQuery Analytics dataset."
  value       = google_bigquery_dataset.analytics.dataset_id
}

output "kafka_cluster_id" {
  description = "The ID of the Managed Apache Kafka cluster for raw telemetry ingestion."
  value       = google_managed_kafka_cluster.aegis_kafka.cluster_id
}

output "kafka_topic_id" {
  description = "The ID of the Managed Apache Kafka topic for raw telemetry ingestion."
  value       = google_managed_kafka_topic.telemetry_raw.topic_id
}

output "service_account_email" {
  description = "The email address of the provisioned Aegis Service Account."
  value       = google_service_account.aegis_sa.email
}

output "artifact_registry_repo" {
  description = "The name of the provisioned Artifact Registry Docker repository."
  value       = google_artifact_registry_repository.aegis_containers.name
}

output "project_id" {
  description = "The GCP Project ID where infrastructure was deployed."
  value       = var.project_id
}

output "region" {
  description = "The GCP region where regional resources were deployed."
  value       = var.region
}
