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

# ============================================================================
# Dedicated Cloud Build service account (drift finding S4)
#
# Replaces the over-privileged default Compute Engine SA (`<number>-compute@developer`,
# which holds `roles/storage.admin` and `roles/artifactregistry.admin`) for
# `gcloud run deploy --source=. --build-service-account=...` builds.
#
# Least privilege:
# - `roles/logging.logWriter` on the project (build logs).
# - `roles/artifactregistry.writer` on `cloud-run-source-deploy` only (never `admin`).
# - `roles/storage.objectViewer` + `roles/storage.objectCreator` on the Cloud Run
#   source staging bucket `run-sources-<project>-<region>` only (never `storage.admin`).
# - ZERO `roles/owner`, `roles/editor`, `roles/iam.*Admin`, or `roles/run.admin`.
# ============================================================================

resource "google_service_account" "cymbal_build" {
  count        = var.enable_build_sa ? 1 : 0
  account_id   = "cymbal-build-sa"
  display_name = "Cymbal dedicated Cloud Build service account (drift S4)"
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_project_iam_member" "build_log_writer" {
  count   = var.enable_build_sa ? 1 : 0
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cymbal_build[0].email}"
}

resource "google_artifact_registry_repository_iam_member" "build_ar_writer" {
  count      = var.enable_build_sa ? 1 : 0
  project    = var.project_id
  location   = var.region
  repository = "cloud-run-source-deploy"
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.cymbal_build[0].email}"
}

resource "google_storage_bucket_iam_member" "build_source_viewer" {
  count  = var.enable_build_sa ? 1 : 0
  bucket = "run-sources-${var.project_id}-${var.region}"
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.cymbal_build[0].email}"
}

resource "google_storage_bucket_iam_member" "build_source_creator" {
  count  = var.enable_build_sa ? 1 : 0
  bucket = "run-sources-${var.project_id}-${var.region}"
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.cymbal_build[0].email}"
}
