# Copyright 2025 Google LLC
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

resource "google_container_cluster" "gke_cluster" {
  provider = google-beta

  enable_autopilot    = true
  deletion_protection = false
  location            = var.region
  name                = var.unique_identifier_prefix
  network             = data.google_compute_network.vpc.name
  project             = google_project_service.container_googleapis_com.project
  subnetwork          = data.google_compute_subnetwork.subnetwork.name

  control_plane_endpoints_config {
    dns_endpoint_config {
      allow_external_traffic = true
    }
  }

  release_channel {
    channel = "RAPID"
  }

  secret_manager_config {
    enabled = true
  }
}
