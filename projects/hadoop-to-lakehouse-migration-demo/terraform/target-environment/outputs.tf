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

output "bronze_bucket" {
  value = google_storage_bucket.bronze.name
}

output "silver_bucket" {
  value = google_storage_bucket.silver.name
}

output "gold_bucket" {
  value = google_storage_bucket.gold.name
}

output "metastore_id" {
  value = google_dataproc_metastore_service.default.id
}

output "bronze_dataset" {
  value = google_bigquery_dataset.bronze.dataset_id
}

output "silver_dataset" {
  value = google_bigquery_dataset.silver.dataset_id
}

output "gold_dataset" {
  value = google_bigquery_dataset.gold.dataset_id
}
output "project_id" {
  value = data.google_project.target_project.project_id
}
output "dataproc_service_account" {
  value = google_service_account.dataproc_sa.email
}

output "subnet_name" {
  value = google_compute_subnetwork.target_subnet.name
}

output "region" {
  value = var.region
}
