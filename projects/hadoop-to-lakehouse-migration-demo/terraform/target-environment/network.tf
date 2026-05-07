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

resource "google_compute_network" "target_network" {
  name                    = "lakehouse-net"
  auto_create_subnetworks = false
  project                 = data.google_project.target_project.project_id
}

resource "google_compute_subnetwork" "target_subnet" {
  name                     = "lakehouse-subnet"
  ip_cidr_range            = "10.1.0.0/24"
  region                   = var.region
  network                  = google_compute_network.target_network.id
  private_ip_google_access = true
  project                  = data.google_project.target_project.project_id
}

resource "google_compute_firewall" "target_allow_internal" {
  name    = "lakehouse-allow-internal"
  network = google_compute_network.target_network.id
  project = data.google_project.target_project.project_id

  allow {
    protocol = "icmp"
  }

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  source_ranges = ["10.1.0.0/24"]
}

resource "google_compute_router" "target_router" {
  name    = "lakehouse-net-router"
  region  = var.region
  network = google_compute_network.target_network.id
  project = data.google_project.target_project.project_id
}

resource "google_compute_router_nat" "target_nat" {
  project                            = data.google_project.target_project.project_id
  name                               = "lakehouse-net-nat"
  router                             = google_compute_router.target_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
