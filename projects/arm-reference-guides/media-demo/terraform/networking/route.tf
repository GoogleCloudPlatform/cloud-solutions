
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

# Direct connectivity to Google APIs
resource "google_compute_route" "gce_direct_connectivity_ipv4" {
  dest_range       = "34.126.0.0/18"
  name             = "gce-${var.unique_identifier_prefix}-direct-connectivity-ipv4"
  network          = data.google_compute_network.vpc.name
  next_hop_gateway = "default-internet-gateway"
  priority         = 1000
  project          = google_project_service.compute_googleapis_com.project
}

resource "google_compute_route" "gce_direct_connectivity_ipv6" {
  dest_range       = "2001:4860:8040::/42"
  name             = "gce-${var.unique_identifier_prefix}-direct-connectivity-ipv6"
  network          = data.google_compute_network.vpc.name
  next_hop_gateway = "default-internet-gateway"
  priority         = 1000
  project          = google_project_service.compute_googleapis_com.project
}
