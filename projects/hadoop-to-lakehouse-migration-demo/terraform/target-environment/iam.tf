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

resource "google_service_account" "dataproc_sa" {
  account_id   = "dataproc-serverless-sa"
  display_name = "Service Account for Managed Spark Serverless"
  project      = data.google_project.target_project.project_id
}

resource "google_project_iam_member" "dataproc_worker" {
  project = data.google_project.target_project.project_id
  role    = "roles/dataproc.worker"
  member  = "serviceAccount:${google_service_account.dataproc_sa.email}"
}

resource "google_project_iam_member" "dataproc_storage" {
  project = data.google_project.target_project.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.dataproc_sa.email}"
}

# Grant the source Managed Spark cluster's service account access to the target Bronze bucket.
# This is required for the data transfer step (HDFS to Cloud Storage) to work across projects.
# roles/storage.admin is used instead of objectAdmin to support Hadoop Cloud Storage connector metadata operations.
resource "google_project_iam_member" "source_sa_storage_admin" {
  project = data.google_project.target_project.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${var.source_service_account}"
}

# Grant the source Managed Spark cluster's service account permission to manage Storage Transfer in target project.
resource "google_project_iam_member" "source_sa_transfer_admin" {
  project = data.google_project.target_project.project_id
  role    = "roles/storagetransfer.admin"
  member  = "serviceAccount:${var.source_service_account}"
}
