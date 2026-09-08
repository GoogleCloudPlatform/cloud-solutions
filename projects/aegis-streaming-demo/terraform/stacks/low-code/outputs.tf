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

output "project_id" {
  description = "The Google Cloud Project ID where infrastructure was deployed."
  value       = var.project_id
}

output "region" {
  description = "The Google Cloud region where regional resources were deployed."
  value       = var.region
}

output "hud_backend_url" {
  description = "URL of the deployed HUD Backend Service on Cloud Run."
  value       = module.base_platform.hud_backend_url
}

output "telemetry_simulator_url" {
  description = "URL of the standalone Telemetry Simulator Service on Cloud Run."
  value       = module.base_platform.telemetry_simulator_url
}

output "hud_frontend_url" {
  description = "URL of the deployed HUD Frontend Web Application on Cloud Run."
  value       = module.base_platform.hud_frontend_url
}

output "agent_service_url" {
  description = "Resource name of the deployed Agent on Gemini Enterprise Agent Platform (GEAP)."
  value       = module.base_platform.agent_service_url
}

output "geap_agent_id" {
  description = "The dynamically retrieved Resource ID of the deployed GEAP Reasoning Engine."
  value       = module.base_platform.geap_agent_id
}

output "bigtable_instance_id" {
  description = "The ID of the provisioned Cloud Bigtable instance."
  value       = module.base_platform.bigtable_instance_id
}

output "bigquery_dataset_id" {
  description = "The ID of the provisioned BigQuery Analytics dataset."
  value       = module.base_platform.bigquery_dataset_id
}

output "service_account_email" {
  description = "The email address of the provisioned Aegis Service Account."
  value       = module.base_platform.service_account_email
}

output "artifact_registry_repo" {
  description = "The name of the provisioned Artifact Registry Docker repository."
  value       = module.base_platform.artifact_registry_repo
}

output "pubsub_topic_id" {
  description = "The ID of the raw telemetry Pub/Sub topic."
  value       = module.stack_low_code.pubsub_topic_id
}

output "pubsub_topic_name" {
  description = "Full resource name of the raw telemetry Pub/Sub topic."
  value       = module.stack_low_code.pubsub_topic_name
}

output "pubsub_subscription_id" {
  description = "The ID of the BigQuery direct subscription."
  value       = module.stack_low_code.pubsub_subscription_id
}
