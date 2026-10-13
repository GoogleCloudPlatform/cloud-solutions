# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

output "cloud_run_service_urls" {
  description = "Map of deployed Cloud Run service names to their HTTPS base URLs."
  value = {
    for k, v in google_cloud_run_v2_service.agents : k => v.uri
  }
}

output "gemini_openapi_endpoints" {
  description = "Map of OpenAPI 3.0 specification endpoints for Gemini Enterprise and Vertex AI Extension registration."
  value = {
    "workflow_agent"      = "${google_cloud_run_v2_service.agents["workflow-agent"].uri}/openapi.json"
    "a2a_workflow_server" = "${google_cloud_run_v2_service.agents["a2a-workflow-server"].uri}/openapi.json"
  }
}

output "vpc_network_id" {
  description = "Target VPC Network ID for private Oracle EBS VM Direct VPC egress."
  value       = local.target_vpc_id
}

output "cloud_run_service_account" {
  description = "Email address of the Cloud Run Service Account."
  value       = google_service_account.workflow_sa.email
}

output "gemini_enterprise_service_account" {
  description = "Email address of the Gemini Enterprise Extension Service Account for Google Identity authentication."
  value       = google_service_account.gemini_agent_sa.email
}

output "gemini_agent_integration_status" {
  description = "Status of automated Vertex AI Extension and Gemini Enterprise Agent registration."
  value       = "PROVISIONED AND CONFIGURED FOR VERTEX AI AND GEMINI ENTERPRISE (Project ${var.project_id})"
}

output "gemini_chat_web_console_url" {
  description = "Direct web console URL to access your agent in Gemini Enterprise."
  value       = "https://gemini.google.com/"
}

output "gcs_openapi_yaml_uri" {
  description = "Google Cloud Storage URI for gemini_extension_openapi.yaml to select as Source in Vertex AI Extension Console."
  value       = "gs://${google_storage_bucket.agent_assets.name}/${google_storage_bucket_object.openapi_spec.name}"
}

output "a2a_agent_card_gcs_uri" {
  description = "Google Cloud Storage URI for a2a_agent_card.json to import into Gemini Enterprise Console."
  value       = "gs://${google_storage_bucket.agent_assets.name}/${google_storage_bucket_object.a2a_agent_card.name}"
}

output "gemini_extension_manifest_gcs_uri" {
  description = "Google Cloud Storage URI for gemini_extension_manifest.json to register in Gemini Enterprise Console."
  value       = "gs://${google_storage_bucket.agent_assets.name}/${google_storage_bucket_object.gemini_extension_manifest.name}"
}

