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

resource "google_project_service" "run_googleapis_com" {
  // Do not disable_on_destroy, as this deletes the
  // serverless-robot-prod.iam.gserviceaccount.com SA
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudbuild_googleapis_com" {
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry_googleapis_com" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam_googleapis_com" {
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "secretmanager_googleapis_com" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "container_googleapis_com" {
  service            = "container.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "aiplatform_googleapis_com" {
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

# resource "google_project_service" "beyondcorp_googleapis_com" {
#   service            = "beyondcorp.googleapis.com"
#   disable_on_destroy = false
# }

resource "google_project_service" "iap_googleapis_com" {
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudresourcemanager_googleapis_com" {
  service            = "cloudresourcemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "servicenetworking_googleapis_com" {
  service            = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}
