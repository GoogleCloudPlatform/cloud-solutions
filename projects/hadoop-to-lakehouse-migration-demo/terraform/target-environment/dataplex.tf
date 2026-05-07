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

# Dataplex Lake
resource "google_dataplex_lake" "default" {
  name        = "lakehouse-lake"
  description = "Data Lakehouse Lake"
  location    = var.region
  project     = data.google_project.target_project.project_id
}

# Dataplex Zones
resource "google_dataplex_zone" "raw" {
  name     = "raw-zone"
  lake     = google_dataplex_lake.default.name
  location = var.region
  type     = "RAW"
  project  = data.google_project.target_project.project_id

  resource_spec {
    location_type = "SINGLE_REGION"
  }

  discovery_spec {
    enabled = true
  }
}

resource "google_dataplex_zone" "curated" {
  name     = "curated-zone"
  lake     = google_dataplex_lake.default.name
  location = var.region
  type     = "CURATED"
  project  = data.google_project.target_project.project_id

  resource_spec {
    location_type = "SINGLE_REGION"
  }

  discovery_spec {
    enabled = true
  }
}
