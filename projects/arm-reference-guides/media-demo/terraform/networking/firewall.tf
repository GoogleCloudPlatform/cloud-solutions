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

# All direct_connectivity to Google APIs from GCE
resource "google_compute_firewall" "gce_direct_connectivity_ipv4" {
  description        = "Some Google APIs and services support direct connectivity from Compute Engine virtual machine (VM) instances, bypassing Google Front Ends (GFEs), offering better performance."
  destination_ranges = ["34.126.0.0/18"] # Not available in a google_netblock_ip_ranges when checked 2025-05-30
  direction          = "EGRESS"
  name               = "gce-${var.unique_identifier_prefix}-direct-connectivity-ipv4"
  network            = data.google_compute_network.vpc.name
  project            = google_project_service.compute_googleapis_com.project

  allow {
    protocol = "all"
  }
}

resource "google_compute_firewall" "gce_direct_connectivity_ipv6" {
  description        = "Some Google APIs and services support direct connectivity from Compute Engine virtual machine (VM) instances, bypassing Google Front Ends (GFEs), offering better performance."
  destination_ranges = ["2001:4860:8040::/42"] # Not available in a google_netblock_ip_ranges when checked 2025-05-30
  direction          = "EGRESS"
  name               = "gce-${var.unique_identifier_prefix}-direct-connectivity-ipv6"
  network            = data.google_compute_network.vpc.name
  project            = google_project_service.compute_googleapis_com.project

  allow {
    protocol = "all"
  }
}
