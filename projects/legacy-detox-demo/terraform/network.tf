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

resource "google_compute_network" "dataproc_vpc" {
  name                    = "dataproc-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "dataproc_subnet" {
  name                     = "dataproc-subnet"
  ip_cidr_range            = "10.0.0.0/24"
  region                   = var.region
  network                  = google_compute_network.dataproc_vpc.id
  private_ip_google_access = true # Best practice for Dataproc Serverless
}

# Firewall rule to allow internal traffic within the VPC
# Dataproc Serverless requires internal connectivity between nodes
resource "google_compute_firewall" "dataproc_internal" {
  name    = "dataproc-internal-allow"
  network = google_compute_network.dataproc_vpc.name

  allow {
    protocol = "icmp"
  }

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  source_ranges = ["10.0.0.0/24"]
}
