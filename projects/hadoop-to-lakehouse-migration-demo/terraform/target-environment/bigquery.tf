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

# BigQuery Datasets
resource "google_bigquery_dataset" "bronze" {
  dataset_id    = "bronze"
  project       = data.google_project.target_project.project_id
  friendly_name = "Bronze Dataset"
  description   = "Raw data mirrored from source"
  location      = var.region
}

resource "google_bigquery_dataset" "silver" {
  dataset_id    = "silver"
  project       = data.google_project.target_project.project_id
  friendly_name = "Silver Dataset"
  description   = "Cleaned and transformed data (Iceberg)"
  location      = var.region
}

resource "google_bigquery_dataset" "gold" {
  dataset_id    = "gold"
  project       = data.google_project.target_project.project_id
  friendly_name = "Gold Dataset"
  description   = "Aggregated and business-ready data"
  location      = var.region
}
