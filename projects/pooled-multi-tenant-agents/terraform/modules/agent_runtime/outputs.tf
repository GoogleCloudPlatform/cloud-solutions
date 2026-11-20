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

output "service_name" {
  description = "Cloud Run v2 service name for this agent runtime."
  value       = google_cloud_run_v2_service.agent_runtime.name
}

output "service_url" {
  description = "Deterministic Cloud Run URL for this agent runtime (used for AGENT_RUNTIME_URLS and RUNTIME_EXPECTED_AUDIENCE)."
  value       = local.service_url
}

output "service_uri" {
  description = "Cloud Run v2 service URI reported by the API."
  value       = google_cloud_run_v2_service.agent_runtime.uri
}

output "agent_principal" {
  description = "IAM principal (`principal://agents.global.org-...`) for this agent runtime's Cloud Run Agent Identity."
  value       = local.agent_principal
}

output "agent_spiffe_id" {
  description = "SPIFFE ID (`spiffe://agents.global.org-...`) in the `sub` claim of this agent's ID tokens."
  value       = local.agent_spiffe_id
}
