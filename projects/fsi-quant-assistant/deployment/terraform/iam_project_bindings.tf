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

resource "google_project_iam_member" "reporting_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.reporting_service_account.email}"
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

resource "google_project_iam_member" "cloudbuild_sa_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"

  depends_on = [google_project_service.run_googleapis_com]
}

resource "google_project_iam_member" "cloudbuild_sa_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"

  depends_on = [google_project_service.run_googleapis_com]
}

resource "google_project_iam_member" "adk_deploy_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${data.google_compute_default_service_account.default.email}"
}

resource "google_project_iam_member" "compute_sa_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${data.google_compute_default_service_account.default.email}"

  depends_on = [google_project_service.run_googleapis_com]
}

# https://googleapis.github.io/genai-toolbox/resources/sources/alloydb-pg/#iam-permissions
resource "google_project_iam_member" "toolbox_alloydb_client" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.toolbox-identity.email}"
}

resource "google_project_iam_member" "toolbox_alloydb_database_user" {
  project = var.project_id
  role    = "roles/alloydb.databaseUser"
  member  = "serviceAccount:${google_service_account.toolbox-identity.email}"
}

resource "google_project_iam_member" "order_service_alloydb_client" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.order-service.email}"
}

resource "google_project_iam_member" "order_service_alloydb_database_user" {
  project = var.project_id
  role    = "roles/alloydb.databaseUser"
  member  = "serviceAccount:${google_service_account.order-service.email}"
}

resource "google_project_iam_member" "reporting_alloydb_client" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.reporting_service_account.email}"
}

resource "google_project_iam_member" "reporting_alloydb_database_user" {
  project = var.project_id
  role    = "roles/alloydb.databaseUser"
  member  = "serviceAccount:${google_service_account.reporting_service_account.email}"
}

resource "google_project_iam_member" "toolbox_service_usage_consumer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.toolbox-identity.email}"
}

resource "google_project_iam_member" "order_service_service_usage_consumer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.order-service.email}"
}

resource "google_project_iam_member" "cloudbuild_sa_cloudbuild_invoker" {
  project = var.project_id
  role    = google_project_iam_custom_role.cloud_build_job_runner.id
  member  = "serviceAccount:${google_service_account.cloudbuild_service_account.email}"
}

resource "google_project_iam_member" "bq_alloydb_access" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${data.external.alloydb_sa.result.email}"
}
