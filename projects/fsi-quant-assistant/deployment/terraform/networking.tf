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

resource "google_compute_network" "agent_cluster_vpc_network" {
  name                    = "agent-demo-cluster-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.servicenetworking_googleapis_com]
}

resource "google_compute_subnetwork" "agent_cluster_subnet" {
  name                     = "adk-demo-cluster-subnet"
  ip_cidr_range            = "10.0.0.0/24" # A /24 subnet for the nodes.
  region                   = var.region
  network                  = google_compute_network.agent_cluster_vpc_network.self_link
  private_ip_google_access = true
}

resource "google_compute_router" "router" {
  name    = "nat-router"
  region  = var.region
  network = google_compute_network.agent_cluster_vpc_network.self_link
}

resource "google_compute_router_nat" "nat" {
  name                               = "my-cloud-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  nat_ip_allocate_option             = "AUTO_ONLY"
}

resource "google_compute_global_address" "worker_range" {
  name          = "worker-pool-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.agent_cluster_vpc_network.id
}

resource "google_service_networking_connection" "worker_pool_conn" {
  network                 = google_compute_network.agent_cluster_vpc_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.worker_range.name]
  depends_on              = [google_project_service.servicenetworking_googleapis_com]
}
