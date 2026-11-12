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

output "voltguard_a2a_url" {
  description = "Cloud Run URL of the VoltGuard agent, which the A2A agent card advertises to Gemini Enterprise."
  value       = local.agent_public_url
}

output "voltguard_service_account_email" {
  description = "Service account email attached to the VoltGuard Cloud Run service."
  value       = google_service_account.voltguard_agent_sa.email
}

output "mcp_toolbox_uri" {
  description = "HTTPS endpoint URL of the Oracle EBS MCP Toolbox Cloud Run service."
  value       = google_cloud_run_v2_service.ebs_mcp_toolbox.uri
}

output "mcp_toolbox_service_account_email" {
  description = "Service account email attached to the Oracle EBS MCP Toolbox Cloud Run service."
  value       = google_service_account.mcp_toolbox_sa.email
}

output "vpc_network_id" {
  description = "Target VPC network ID used for the MCP Toolbox Direct VPC Egress."
  value       = local.target_vpc_id
}

output "subnet_name" {
  description = "Target subnetwork name used for the MCP Toolbox Direct VPC Egress."
  value       = local.target_subnet_name
}

output "ebs_signals_dataset_id" {
  description = "BigQuery dataset ID for the search, forecast, hub market, and freight lane signals."
  value       = google_bigquery_dataset.ebs_scm_agentic_ai.dataset_id
}

output "bigquery_location" {
  description = "BigQuery location of the signals dataset."
  value       = google_bigquery_dataset.ebs_scm_agentic_ai.location
}
