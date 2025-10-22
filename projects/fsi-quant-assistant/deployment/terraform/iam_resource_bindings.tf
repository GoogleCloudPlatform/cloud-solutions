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

resource "google_secret_manager_secret_iam_binding" "toolbox_identity_tools_access" {
  secret_id = google_secret_manager_secret.tools.secret_id
  role      = "roles/secretmanager.secretAccessor"
  members = [
    "serviceAccount:${google_service_account.toolbox-identity.email}",
  ]
}

resource "google_bigquery_dataset_iam_binding" "tools_analyst_demo_data_editor" {
  role       = "roles/bigquery.dataEditor"
  dataset_id = google_bigquery_dataset.analyst_demo.dataset_id
  members    = ["serviceAccount:${google_service_account.toolbox-identity.email}", ]
}

resource "google_storage_bucket_iam_member" "adk_builder_reader" {
  bucket = google_storage_bucket.cloudbuild_logs.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.adk-builder.email}"
}

resource "google_artifact_registry_repository_iam_member" "adk_agent_tools_artifact_reader" {
  project    = var.project_id
  repository = google_artifact_registry_repository.adk_repo.id
  location   = var.region
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.adk-agent.email}"
}

# Needed for demo environment due to policies restricting the default compute account.
resource "google_artifact_registry_repository_iam_member" "compute_tools_artifact_reader" {
  project    = var.project_id
  repository = google_artifact_registry_repository.adk_repo.id
  location   = var.region
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

resource "google_artifact_registry_repository_iam_member" "adk_builder_artifact_writer" {
  repository = google_artifact_registry_repository.adk_repo.id
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.adk-builder.email}"
}

resource "google_secret_manager_secret_iam_binding" "gemma_agent_hf_access" {
  secret_id = google_secret_manager_secret.hugging_face_api_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  members = [
    "serviceAccount:${google_service_account.gemma-agent.email}",
  ]
}
