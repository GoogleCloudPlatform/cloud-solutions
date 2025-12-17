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

resource "google_service_account" "toolbox-identity" {
  account_id   = "toolbox-identity"
  display_name = "Toolbox Identity"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

resource "google_service_account" "order-service" {
  account_id   = "order-service"
  display_name = "Order Service"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

resource "google_service_account" "cloudbuild_service_account" {
  account_id   = "cloudbuild-sa"
  display_name = "Cloud Build Service Account"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

resource "google_service_account" "reporting_service_account" {
  account_id   = "reporting-sa"
  display_name = "Reporting Service Account"

  lifecycle {
    ignore_changes = [
      description,
      display_name
    ]
  }
}

resource "google_project_service_identity" "vertex_ai_sa" {
  provider = google-beta
  project  = var.project_id
  service  = "aiplatform.googleapis.com"
}

data "google_compute_default_service_account" "default" {
}

locals {
  cloudbuild_service_account = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}
