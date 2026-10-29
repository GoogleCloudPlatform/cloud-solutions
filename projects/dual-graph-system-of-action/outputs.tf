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

output "shopping_mall_url" {
  description = "Cloud Run URL (/shop) for Customer A, Customer B, and Customer C refund requests."
  value       = "${google_cloud_run_v2_service.soa_app.uri}/shop"
}

output "data_engineer_console_url" {
  description = "Cloud Run URL (/console) for monitoring requests and querying Spanner and BigQuery graphs."
  value       = "${google_cloud_run_v2_service.soa_app.uri}/console"
}

output "spanner_instance_id" {
  description = "Provisioned Cloud Spanner instance identifier (soa-graph-instance)."
  value       = google_spanner_instance.soa_instance.name
}

output "spanner_database_id" {
  description = "Database containing thelook_ecommerce tables and OperationalContextGraph (thelook-soa-db)."
  value       = google_spanner_database.soa_database.name
}

output "bigquery_dataset_id" {
  description = "Dataset containing the ActionLineageGraph property graph (soa_action_lineage)."
  value       = google_bigquery_dataset.action_lineage.dataset_id
}

output "spanner_connection_id" {
  description = "BigQuery Cloud Spanner connection ID for EXTERNAL_QUERY."
  value       = local.spanner_connection_id
}

output "gcp_project_id" {
  description = "Active Google Cloud project ID."
  value       = local.gcp_project_id
}

output "gcp_region" {
  description = "Active deployment region selected from allowed_locations."
  value       = var.gcp_region
}
