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

# =============================================================================
# Service Account & IAM Role Bindings
# =============================================================================

resource "google_service_account" "aegis_sa" {
  account_id   = "aegis-sa"
  display_name = "Aegis Streaming Service Account"
  project      = var.project_id

  depends_on = [google_project_service.enabled_apis]
}

locals {
  sa_roles = [
    "roles/aiplatform.user",
    "roles/bigtable.user",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/run.invoker",
    "roles/dataproc.worker",
    "roles/dataproc.editor",
    "roles/storage.objectAdmin",
    "roles/managedkafka.client",
    "roles/managedkafka.topicEditor",
    "roles/managedkafka.consumerGroupEditor",
    "roles/iam.serviceAccountTokenCreator",
    "roles/iam.serviceAccountOpenIdTokenCreator",
    "roles/iam.serviceAccountUser"
  ]
}

resource "google_project_iam_member" "aegis_sa_roles" {
  for_each = toset(local.sa_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.aegis_sa.email}"
}

# =============================================================================
# Google Cloud Build & Compute Engine Service Account Permissions
# =============================================================================

data "google_project" "current" {
  project_id = var.project_id
}

locals {
  cloudbuild_builder_roles = [
    "roles/logging.logWriter",
    "roles/artifactregistry.writer",
    "roles/storage.admin"
  ]
  cloudbuild_builder_accounts = [
    "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com",
    "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
  ]
  cloudbuild_iam_bindings = distinct(flatten([
    for sa in local.cloudbuild_builder_accounts : [
      for r in local.cloudbuild_builder_roles : {
        key    = "${replace(replace(sa, "serviceAccount:", ""), "@", "-")}-${replace(r, "roles/", "")}"
        member = sa
        role   = r
      }
    ]
  ]))
}

resource "google_project_iam_member" "cloudbuild_builder_roles" {
  for_each = { for item in local.cloudbuild_iam_bindings : item.key => item }
  project  = var.project_id
  role     = each.value.role
  member   = each.value.member
}
