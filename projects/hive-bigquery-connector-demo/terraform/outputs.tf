# Copyright 2023 Google LLC
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
  value = data.google_project.project.project_id
}

output "staging_bucket" {
  value = google_storage_bucket.hive_bq_cluster_staging.name
}

output "warehouse_bucket" {
  value = google_storage_bucket.warehouse.name
}

output "dataproc_region" {
  value = google_dataproc_cluster.hive_bq.region
}

output "jupyterlab_url" {
  value = google_dataproc_cluster.hive_bq.cluster_config[0].endpoint_config[0].http_ports.JupyterLab
}

output "jupyter_url" {
  value = google_dataproc_cluster.hive_bq.cluster_config[0].endpoint_config[0].http_ports.Jupyter
}

output "dataproc_name" {
  value = google_dataproc_cluster.hive_bq.name
}

output "bq_connection_location" {
  value = google_bigquery_connection.dwh.location
}

output "bq_connection_id" {
  value = google_bigquery_connection.dwh.connection_id
}
