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

resource "google_storage_bucket_iam_member" "cloudbuild_reader" {
  bucket = google_storage_bucket.cloudbuild_logs.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

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

resource "google_artifact_registry_repository_iam_member" "cloudbuild_sa_cloud_run_artifact_writer" {
  repository = google_artifact_registry_repository.cloud_run_source_repo.id
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_sa_cloud_run_artifact_reader" {
  repository = google_artifact_registry_repository.cloud_run_source_repo.id
  location   = var.region
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_artifact_registry_repository_iam_member" "compute_cloud_run_deploy_artifact_writer" {
  project    = var.project_id
  repository = google_artifact_registry_repository.cloud_run_source_repo.id
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_sa_finance_bundle_artifact_writer" {
  repository = google_artifact_registry_repository.finance_bundle.id
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_sa_finance_bundle_artifact_reader" {
  repository = google_artifact_registry_repository.finance_bundle.id
  location   = var.region
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_artifact_registry_repository_iam_member" "compute_finance_bundle_artifact_writer" {
  project    = var.project_id
  repository = google_artifact_registry_repository.finance_bundle.id
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

resource "google_storage_bucket_iam_member" "adk_cloud_build_bucket" {
  bucket = google_storage_bucket.adk_cloudrun_deploy.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

resource "google_storage_bucket_iam_member" "iceberg_connection_access" {
  bucket = google_storage_bucket.iceberg_warehouse.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_bigquery_connection.iceberg.cloud_resource[0].service_account_id}"
}

resource "google_bigquery_connection_iam_member" "alloydb_connection_user" {
  location      = var.region
  connection_id = null_resource.alloydb_connection.triggers.conn_id
  role          = "roles/bigquery.connectionUser"
  member        = "serviceAccount:${google_service_account.reporting_service_account.email}"
}

resource "google_bigquery_dataset_iam_binding" "reporting_data_viewer" {
  role       = "roles/bigquery.dataEditor"
  dataset_id = google_bigquery_dataset.iceberg_catalog.dataset_id
  members    = ["serviceAccount:${google_service_account.reporting_service_account.email}"]
}
