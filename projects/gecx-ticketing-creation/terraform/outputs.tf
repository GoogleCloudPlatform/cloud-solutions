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

output "webhook_url" {
  description = "The URL of the private GECX webhook Cloud Run service"
  value       = google_cloud_run_v2_service.webhook.uri
}

output "web_portal_url" {
  description = "The secure web UI portals Cloud Run service URI"
  value       = google_cloud_run_v2_service.web.uri
}

output "artifact_registry_repo" {
  description = "The Artifact Registry Docker repository name"
  value       = google_artifact_registry_repository.repo.name
}

