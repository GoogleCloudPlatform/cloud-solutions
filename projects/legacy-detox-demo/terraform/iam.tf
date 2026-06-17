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

resource "google_service_account" "managed_spark_sa" {
  project      = data.google_project.legacy_detox_project.project_id
  account_id   = "managed-spark-serverless-sa"
  display_name = "Managed Spark Serverless Service Account"
}

resource "google_project_iam_member" "managed_spark_worker" {
  project = data.google_project.legacy_detox_project.project_id
  role    = "roles/dataproc.worker"
  member  = "serviceAccount:${google_service_account.managed_spark_sa.email}"
}

# --- Storage Permissions (Scoped to Bucket) ---

# Grant full control over objects ONLY in the detox bucket
# This allows reading scripts, writing staging data, and cleaning up (delete).
resource "google_storage_bucket_iam_member" "managed_spark_storage_admin" {
  bucket = google_storage_bucket.detox_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.managed_spark_sa.email}"
}

# --- BigQuery Permissions ---

# Project-level permissions required for the Storage Read API and running jobs
resource "google_project_iam_member" "bq_read_session" {
  project = data.google_project.legacy_detox_project.project_id
  role    = "roles/bigquery.readSessionUser"
  member  = "serviceAccount:${google_service_account.managed_spark_sa.email}"
}

resource "google_project_iam_member" "bq_job_user" {
  project = data.google_project.legacy_detox_project.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.managed_spark_sa.email}"
}

# Dataset-level permissions for the output (Least Privilege)
resource "google_bigquery_dataset_iam_member" "reengagement_editor" {
  dataset_id = google_bigquery_dataset.reengagement.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.managed_spark_sa.email}"
}

# Essential for Managed Spark: The service agent needs to be able to act as the custom SA
resource "google_service_account_iam_member" "managed_spark_sa_user" {
  service_account_id = google_service_account.managed_spark_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.legacy_detox_project.number}@dataproc-accounts.iam.gserviceaccount.com"
}

# --- Default Compute Engine Service Account Permissions ---
# Required for running 'gcloud builds submit' via local-exec when Terraform is
# executed from an environment using this identity (e.g., Cloud Shell or a GCE VM).

# Grant permission to submit build requests.
resource "google_project_iam_member" "default_compute_cloudbuild_editor" {
  project = data.google_project.legacy_detox_project.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${data.google_project.legacy_detox_project.number}-compute@developer.gserviceaccount.com"
}

# Grant permission to upload build source to the specific staging bucket (Least Privilege).
resource "google_storage_bucket_iam_member" "default_compute_storage_object_admin" {
  bucket = google_storage_bucket.detox_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_project.legacy_detox_project.number}-compute@developer.gserviceaccount.com"
}

# Grant permission to push images to the Artifact Registry (Least Privilege).
resource "google_artifact_registry_repository_iam_member" "default_compute_ar_writer" {
  project    = data.google_project.legacy_detox_project.project_id
  location   = google_artifact_registry_repository.legacy_detox_artifact_registry.location
  repository = google_artifact_registry_repository.legacy_detox_artifact_registry.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.legacy_detox_project.number}-compute@developer.gserviceaccount.com"
}
