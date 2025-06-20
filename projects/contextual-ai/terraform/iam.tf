# Copyright 2025 Google LLC
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

data "google_project" "project" {
}

locals {
  default_compute_service_account_roles = [
    "roles/storage.objectAdmin",
    "roles/storage.admin",
    "roles/storage.objectViewer",
    "roles/artifactregistry.admin",
    "roles/logging.logWriter",
  ]

  cloud_run_sa_roles = [
    "roles/aiplatform.user",
    "roles/bigquery.jobUser",
    "roles/bigquery.dataOwner",
    "roles/storage.objectAdmin",
    "roles/storage.admin",
    "roles/storage.objectViewer",
    "roles/discoveryengine.user",
    "roles/artifactregistry.admin",
    "roles/logging.logWriter",
    "roles/aiplatform.expressUser"
  ]
}

resource "google_project_iam_member" "default_compute_service_account" {
  for_each = toset(local.default_compute_service_account_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_service_account" "cloudbuild_service_account" {
  account_id = "cloud-sa"
}

resource "google_project_iam_member" "cloud_sa_service_account" {
  for_each = toset(local.cloud_run_sa_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:cloud-sa@${var.project_id}.iam.gserviceaccount.com"
  depends_on = [
    google_service_account.cloudbuild_service_account
  ]
}

resource "google_project_iam_member" "act_as" {
  project = data.google_project.project.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_project_iam_member" "logs_writer" {
  project = data.google_project.project.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}
