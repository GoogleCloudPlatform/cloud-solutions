# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

data "google_compute_default_service_account" "default" {
}

# Cloud SQL Client role for the Kubernetes Service Account
resource "google_project_iam_member" "cloud_sql_client" {
  project = data.google_project.project.project_id
  role    = "roles/cloudsql.client"
  member  = "principal://iam.googleapis.com/projects/${data.google_project.project.number}/locations/global/workloadIdentityPools/${data.google_project.project.project_id}.svc.id.goog/subject/ns/java-modernization-demo/sa/java-backend-ksa"

  depends_on = [google_container_cluster.primary]
}

# Allow writing logs to Cloud Logging
resource "google_project_iam_member" "comput_engine_service_account_log_writer" {
  project = data.google_project.project.project_id
  role    = "roles/logging.logWriter"
  member  = data.google_compute_default_service_account.default.member

  depends_on = [google_project_service.gcp_services["compute.googleapis.com"]]
}

resource "google_artifact_registry_repository_iam_member" "comput_engine_service_account_artifact_registry_uploader" {
  project    = google_artifact_registry_repository.repo.project
  location   = google_artifact_registry_repository.repo.location
  repository = google_artifact_registry_repository.repo.name
  role       = "roles/artifactregistry.writer"
  member     = data.google_compute_default_service_account.default.member

  depends_on = [google_project_service.gcp_services["artifactregistry.googleapis.com"]]
}

# Grant the default Compute Engine service account (that Cloud Build uses)
# access to the Cloud Build bucket
resource "google_storage_bucket_iam_member" "compute_engine_service_account_cloud_build_bucket" {
  bucket = "${var.project_id}_cloudbuild"
  role   = "roles/storage.objectViewer"
  member = data.google_compute_default_service_account.default.member

  depends_on = [google_project_service.gcp_services["cloudbuild.googleapis.com"]]
}
