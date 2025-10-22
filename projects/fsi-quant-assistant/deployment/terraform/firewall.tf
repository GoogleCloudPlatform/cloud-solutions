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

resource "google_compute_firewall" "network_allow_ssh" {
  project     = var.project_id
  name        = "agent-vpc-network-allow-ssh"
  network     = google_compute_network.agent_cluster_vpc_network.id
  description = "Creates firewall rule to allow ssh to the vm"
  direction   = "INGRESS"
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  priority      = 65534
}
