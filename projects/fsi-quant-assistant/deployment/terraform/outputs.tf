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
  value = google_cloud_run_v2_service.toolbox.uri
}

output "order_service_uri" {
  value = var.deploy_order_service ? google_cloud_run_v2_service.order_service[0].uri : "No instance created"
}

output "cloudbuild_service_account_id" {
  value = google_service_account.cloudbuild_service_account.id
}

output "current_user_email" {
  value = data.google_client_openid_userinfo.me.email
}

output "region" {
  value = var.region
}

output "adk_staging_bucket" {
  value = google_storage_bucket.adk_deploy.url
}

output "timesfm_endpoint_id" {
  value = google_vertex_ai_endpoint_with_model_garden_deployment.timesfm_deployment.id
}
