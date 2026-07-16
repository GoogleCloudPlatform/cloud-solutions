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

output "vpc_name" {
  description = "The name of the created VPC."
  value       = google_compute_network.demo_vpc.name
}

output "alloydb_cluster_name" {
  description = "The name of the AlloyDB cluster."
  value       = google_alloydb_cluster.default.name
}

output "alloydb_private_ip" {
  description = "The private IP address of the AlloyDB instance."
  value       = google_alloydb_instance.primary.ip_address
}

output "alloydb_public_ip" {
  description = "The public IP address of the AlloyDB instance."
  value       = google_alloydb_instance.primary.public_ip_address
}

output "demo_app_url" {
  description = "The URL of the deployed Cymbal Shops demo application."
  value       = google_cloud_run_v2_service.demo_app.uri
}

output "colab_runtime_template_id" {
  description = "The ID of the Colab Enterprise Runtime Template."
  value       = google_colab_runtime_template.colab_template.id
}

output "notebook_gcs_uri" {
  description = "The GCS URI of the uploaded Colab notebook."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebook_upload.name}"
}

output "notebook_gcs_uri_ko" {
  description = "The GCS URI of the uploaded Korean Colab notebook."
  value       = "gs://${google_storage_bucket.notebook_bucket.name}/${google_storage_bucket_object.notebook_upload_ko.name}"
}

output "alloydb_password" {
  description = "The password for the 'postgres' user in AlloyDB."
  value       = local.alloydb_password
  sensitive   = true
}

output "gcp_project_id" {
  description = "The GCP project ID being used."
  value       = local.gcp_project_id
}

output "gcp_region" {
  description = "The Google Cloud region where resources are deployed."
  value       = var.gcp_region
}

output "public_ip" {
  description = "The execution environment public IP address."
  value       = local.my_ip
}
