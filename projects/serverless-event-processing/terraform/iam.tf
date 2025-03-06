# Copyright 2024 Google LLC
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

module "service_accounts" {
  source     = "terraform-google-modules/service-accounts/google"
  version    = "4.5.0"
  project_id = data.google_project.project.project_id

  grant_billing_role = false
  grant_xpn_roles    = false
  names              = local.service_account_names
}

# Get the project-wide Cloud Storage service account
data "google_storage_project_service_account" "project_cloud_storage_account" {
  project = data.google_project.project.project_id
}

# Grant the permission to invoke Cloud Run to the Eventarc service account
resource "google_cloud_run_service_iam_binding" "eventarc_cloud_run_invoker_iam_binding" {
  service  = local.cloud_run_event_processing_service_name
  location = var.region

  project = data.google_project.project.project_id
  role    = "roles/run.invoker"
  members = local.list_eventarc_service_account_iam_emails
}

# Grant the permission to receive Eventarc events to the Eventarc service account
resource "google_project_iam_binding" "eventarc_event_receiver_iam_binding" {
  project = data.google_project.project.project_id
  role    = "roles/eventarc.eventReceiver"
  members = local.list_eventarc_service_account_iam_emails
}

# Grant the project-wide Cloud Storage service account the permission to publish messages to Pub/Sub topics
resource "google_project_iam_member" "cloud_storage_eventarc_publisher_iam_member" {
  project = data.google_project.project.id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.project_cloud_storage_account.email_address}"
}
