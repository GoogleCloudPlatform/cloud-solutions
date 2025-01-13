# Copyright 2024 Google LLC
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

resource "google_project_iam_binding" "default" {
  project = var.project_id
  for_each = toset([
    "roles/firebase.admin",
    "roles/storage.admin",
    "roles/storage.objectViewer",
    "roles/cloudbuild.builds.builder",
    "roles/retail.viewer",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/aiplatform.user",
    "roles/datastore.owner",
    "roles/secretmanager.viewer",
    "roles/connectors.admin",
    "roles/connectors.viewer",
    "roles/iam.serviceAccountTokenCreator"
  ])
  role    = each.key
  members = ["serviceAccount:${local.compute_service_account}"]
}

resource "google_project_iam_binding" "dialogflow_service_agent" {
  project = var.project_id
  role    = "roles/integrations.integrationInvoker"
  members = ["serviceAccount:service-${local.target_project_number}@gcp-sa-dialogflow.iam.gserviceaccount.com"]
  depends_on = [
    module.dialogflow_cx_demo_agent
  ]
}
