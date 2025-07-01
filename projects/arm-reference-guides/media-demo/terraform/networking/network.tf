
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

resource "google_compute_network" "vpc" {
  count = var.network_name != null ? 0 : 1

  auto_create_subnetworks = false
  name                    = local.network_name
  project                 = google_project_service.compute_googleapis_com.project
  routing_mode            = var.dynamic_routing_mode
}

data "google_compute_network" "vpc" {
  depends_on = [google_compute_network.vpc]

  name    = local.network_name
  project = google_project_service.compute_googleapis_com.project
}

resource "google_compute_subnetwork" "region" {
  count = var.subnetwork_name != null ? 0 : 1

  ip_cidr_range            = var.subnet_cidr_range
  name                     = local.subnetwork_name
  network                  = data.google_compute_network.vpc.id
  private_ip_google_access = true
  project                  = google_project_service.compute_googleapis_com.project
  region                   = var.region
}

data "google_compute_subnetwork" "region" {
  depends_on = [google_compute_subnetwork.region]

  name    = local.subnetwork_name
  project = google_project_service.compute_googleapis_com.project
  region  = var.region
}

resource "google_compute_router" "router" {
  count = var.router_name != null ? 0 : 1

  name    = local.router_name
  network = data.google_compute_network.vpc.name
  project = google_project_service.compute_googleapis_com.project
  region  = var.region
}

data "google_compute_router" "router" {
  depends_on = [google_compute_router.router]

  name    = local.router_name
  network = data.google_compute_network.vpc.name
  project = google_project_service.compute_googleapis_com.project
  region  = var.region
}

resource "google_compute_router_nat" "nat_gateway" {
  count = var.nat_gateway_name != null ? 0 : 1

  name                               = local.nat_gateway_name
  nat_ip_allocate_option             = "AUTO_ONLY"
  project                            = google_project_service.compute_googleapis_com.project
  region                             = var.region
  router                             = data.google_compute_router.router.name
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

data "google_compute_router_nat" "nat_gateway" {
  depends_on = [google_compute_router_nat.nat_gateway]

  name    = local.nat_gateway_name
  project = google_project_service.compute_googleapis_com.project
  region  = var.region
  router  = data.google_compute_router.router.name
}
