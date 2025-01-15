/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

terraform {
  provider_meta "google" {
    module_name = "cloud-solutions/oss-autoscalers-deploy-network-1.0.0"
  }
}

resource "google_compute_network" "autoscaler_network" {
  name                    = "${var.autoscaler_library_name}-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "autoscaler_subnetwork" {
  name                     = "${var.autoscaler_library_name}-subnetwork"
  network                  = google_compute_network.autoscaler_network.id
  ip_cidr_range            = var.ip_range
  private_ip_google_access = true
}

resource "google_compute_router" "router" {
  name    = "app-router"
  region  = var.region
  network = google_compute_network.autoscaler_network.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.autoscaler_library_name}-nat"
  router                             = google_compute_router.router.name
  region                             = google_compute_router.router.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
