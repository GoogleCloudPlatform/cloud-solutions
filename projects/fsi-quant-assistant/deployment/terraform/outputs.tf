# Copyright 2025 Google LLC
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

output "mcp_tools_for_databases_uri" {
  value = var.deploy_mcp_toolbox_for_databases_to_cloud_run ? google_cloud_run_v2_service.toolbox[0].uri : "No instance created"
}

output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "adk_builder_service_account_id" {
  value = google_service_account.adk-builder.id
}

output "default_account" {
  value = data.google_compute_default_service_account.default.email
}
