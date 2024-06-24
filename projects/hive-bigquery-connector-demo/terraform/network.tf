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


resource "google_compute_network" "default" {
  name                    = "hive-bq-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.gcp_services]
}

resource "google_compute_subnetwork" "vpc_subnetwork" {
  name          = "hive-bq-subnet"
  network       = google_compute_network.default.name
  region        = local.region
  ip_cidr_range = "10.128.0.0/20"
}

resource "google_compute_firewall" "default_allow_internal" {
  name    = "default-allow-internal"
  network = google_compute_network.default.name

  direction     = "INGRESS"
  priority      = 65534
  source_ranges = ["10.128.0.0/20"]
  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }
}

# This rule is to allow ssh for ssh tunneling in case you need to use a tunner in order to access the web interfaces.
# Use with care!!
resource "google_compute_firewall" "ssh-rule" {
  name    = "allow-ssh"
  network = google_compute_network.default.name
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  source_ranges = ["0.0.0.0/0"]
}
