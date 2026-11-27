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

output "advisor_service_account_email" {
  description = "Read-only service account email for Vertex AI Agent Engine runtime"
  value       = google_service_account.advisor_reader.email
}

output "staging_bucket_uri" {
  description = "Cloud Storage URI used for Agent Engine staging artifacts"
  value       = "gs://${google_storage_bucket.staging.name}"
}

output "profiles_gcs_uri" {
  description = "Cloud Storage URI hosting declarative Workload Profiles"
  value       = "gs://${google_storage_bucket.staging.name}/profiles"
}

output "database_toolbox_url" {
  description = "Cloud Run URL of the optional MCP Toolbox for Databases service"
  value       = try(google_cloud_run_v2_service.database_toolbox["primary"].uri, "")
}

output "catalog_toolbox_url" {
  description = "Cloud Run URL of the optional SQL CMDB Catalog MCP service"
  value       = try(google_cloud_run_v2_service.database_toolbox["catalog"].uri, "")
}
