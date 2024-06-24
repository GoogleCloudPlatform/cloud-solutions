# Copyright 2023 Google LLC
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

provider "google" {
  project = var.gcp_project
  region  = local.region
}

data "google_project" "project" {
}

# Enable services in newly created GCP Project.
resource "google_project_service" "gcp_services" {
  for_each = toset([
    "compute.googleapis.com",            # Compute (for networking)
    "dataproc.googleapis.com",           # Dataproc
    "bigquery.googleapis.com",           # BigQuery API
    "bigquerystorage.googleapis.com",    # BigQuery Storage API
    "bigqueryconnection.googleapis.com", # BigQuery Connection API
  ])
  project                    = data.google_project.project.project_id
  service                    = each.key
  disable_dependent_services = true
  disable_on_destroy         = true

  depends_on = [data.google_project.project]
}
