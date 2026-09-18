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

output "gcp_project_id" {
  description = "The Google Cloud Project ID."
  value       = local.gcp_project_id
}

output "gcp_region" {
  description = "The Google Cloud Region."
  value       = var.gcp_region
}

output "colab_runtime_template_id" {
  description = "The ID of the Colab Enterprise Runtime Template."
  value       = google_colab_runtime_template.colab_template.id
}

output "notebooks_gcs_bucket" {
  description = "The Google Cloud Storage bucket containing the lab notebooks."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}"
}

output "notebook_01_gcs_uri" {
  description = "GCS URI for Notebook 01 - Data Profile & Quality (English)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["01_data_profile_quality.ipynb"].name}"
}

output "notebook_01_gcs_uri_ko" {
  description = "GCS URI for Notebook 01 - Data Profile & Quality (Korean)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["01_data_profile_quality_ko.ipynb"].name}"
}

output "notebook_02_gcs_uri" {
  description = "GCS URI for Notebook 02 - Data Insights (English)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["02_data_insight.ipynb"].name}"
}

output "notebook_02_gcs_uri_ko" {
  description = "GCS URI for Notebook 02 - Data Insights (Korean)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["02_data_insight_ko.ipynb"].name}"
}

output "notebook_03_gcs_uri" {
  description = "GCS URI for Notebook 03 - Dataset Insights (English)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["03_dataset_insights.ipynb"].name}"
}

output "notebook_03_gcs_uri_ko" {
  description = "GCS URI for Notebook 03 - Dataset Insights (Korean)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["03_dataset_insights_ko.ipynb"].name}"
}

output "notebook_04_gcs_uri" {
  description = "GCS URI for Notebook 04 - Glossary Setup (English)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["04_glossary_setup.ipynb"].name}"
}

output "notebook_04_gcs_uri_ko" {
  description = "GCS URI for Notebook 04 - Glossary Setup (Korean)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["04_glossary_setup_ko.ipynb"].name}"
}

output "notebook_05_gcs_uri" {
  description = "GCS URI for Notebook 05 - Graph Analysis (English)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["05_graph_analysis.ipynb"].name}"
}

output "notebook_05_gcs_uri_ko" {
  description = "GCS URI for Notebook 05 - Graph Analysis (Korean)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["05_graph_analysis_ko.ipynb"].name}"
}

output "notebook_06_gcs_uri" {
  description = "GCS URI for Notebook 06 - BigQuery AI/ML Demo (English)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["06_bigquery_ai_ml_demo.ipynb"].name}"
}

output "notebook_06_gcs_uri_ko" {
  description = "GCS URI for Notebook 06 - BigQuery AI/ML Demo (Korean)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["06_bigquery_ai_ml_demo_ko.ipynb"].name}"
}

output "notebook_07_gcs_uri" {
  description = "GCS URI for Notebook 07 - BigQuery AI Functions (English)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["07_bigquery_ai_functions.ipynb"].name}"
}

output "notebook_07_gcs_uri_ko" {
  description = "GCS URI for Notebook 07 - BigQuery AI Functions (Korean)."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebooks["07_bigquery_ai_functions_ko.ipynb"].name}"
}

output "bigquery_dataset_id" {
  description = "The BigQuery dataset ID."
  value       = google_bigquery_dataset.thelook.dataset_id
}

output "vpc_name" {
  description = "The name of the VPC network."
  value       = google_compute_network.vpc.name
}
