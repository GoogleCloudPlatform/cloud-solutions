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

resource "google_project_iam_member" "tools_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.toolbox-identity.email}"
}

resource "google_project_iam_member" "adk_agent_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.adk-agent.email}"
}

resource "google_project_iam_member" "adk_agent_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.adk-agent.email}"
}

resource "google_project_iam_member" "adk_builder_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.adk-builder.email}"
}

resource "google_project_iam_member" "terraform_project_admin" {
  project = var.project_id
  role    = "roles/owner"
  member  = "serviceAccount:${google_service_account.terraform-runner.email}"
}

resource "google_project_iam_member" "adk_builder_gke_admin" {
  project = var.project_id
  role    = "roles/container.admin"
  member  = "serviceAccount:${google_service_account.adk-builder.email}"
}

resource "google_project_iam_member" "adk_builder_service_account_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.adk-builder.email}"
}
