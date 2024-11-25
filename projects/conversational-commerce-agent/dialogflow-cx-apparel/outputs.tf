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

output "cloudfunction_uri" {
  description = "The uri of the cloudfunction"
  value       = google_cloudfunctions2_function.function.service_config[0].uri
}

output "dfcx_agent_id" {
  description = "The id of dialogflow cx agent"
  value       = google_dialogflow_cx_agent.cc_agent.id
}

output "agent_playbook_gs_uri" {
  description = "The gcs uri to agent_playbook"
  value       = "gs://${google_storage_bucket.dialogflowcx_assets_bucket.name}/${google_storage_bucket_object.agent_playbook_archive.name}"
}

output "application_integration_json" {
  description = "The file name of Application Integration manifest json"
  value       = local_file.app_integration.filename
}

output "ui_bucket_url" {
  description = "The gcs url to the bucket of ui static files"
  value       = "gs://${google_storage_bucket.ui_src_bucket.name}"
}

output "ui_cloudrun_url" {
  description = "The url to the cloud run service hosting the UI"
  value       = google_cloud_run_v2_service.ui_static.urls[0]
}
