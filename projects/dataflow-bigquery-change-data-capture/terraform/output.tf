# Copyright 2024 Google LLC
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

output "region" {
  description = "Region where the resources are defined"
  value       = var.region
}

output "bq-project-id" {
  description = "Project id containing the BigQuery dataset"
  value       = google_bigquery_dataset.spanner_bigquery.project
}
output "bq-dataset" {
  description = "BigQuery dataset name"
  value       = google_bigquery_dataset.spanner_bigquery.dataset_id
}
output "dataflow-temp-bucket" {
  description = "Temporary bucket for Dataflow staging files"
  value       = google_storage_bucket.dataflow_temp.id
}
output "orders_change_stream" {
  description = "Spanner change stream"
  value       = local.orders_change_stream
}

output "spanner-project-id" {
  description = "Spanner project id"
  value       = google_spanner_instance.main.project
}
output "spanner-database" {
  description = "Spanner database"
  value       = google_spanner_database.fulfillment.name
}
output "spanner-instance" {
  description = "Spanner instance"
  value       = google_spanner_instance.main.name
}
output "dataflow-sa" {
  description = "Service Account to run Dataflow pipelines"
  value       = google_service_account.dataflow_sa.email
}
output "dataflow-project-id" {
  description = "Project ID where to launch Dataflow jobs"
  value       = var.project_id
}
