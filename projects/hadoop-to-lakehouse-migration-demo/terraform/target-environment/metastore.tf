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

# Dataproc Metastore
resource "google_dataproc_metastore_service" "default" {
  service_id = "lakehouse-metastore"
  project    = data.google_project.target_project.project_id
  location   = var.region
  port       = 9083
  tier       = "DEVELOPER"
  network    = google_compute_network.target_network.id

  maintenance_window {
    day_of_week = "MONDAY"
    hour_of_day = 2
  }

  hive_metastore_config {
    version = "3.1.2"
  }
}
