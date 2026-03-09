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
# Copyright 2026 Google LLC

terraform {
  required_version = ">= 1.11.1"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_client_config" "default" {}

data "google_project" "project" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "container.googleapis.com",
    "networkservices.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Wait for 60 seconds to ensure that the APIs are enabled and propagated
# before creating dependent resources.
resource "time_sleep" "wait_60_seconds" {
  depends_on      = [google_project_service.apis]
  create_duration = "60s"
}

locals {
  cluster_name    = "${var.prefix}-gke"
  gateway_ip_name = "${var.prefix}-gateway-ip"
  nat_ip_name     = "${var.prefix}-nat-ip"
  router_name     = "${var.prefix}-router"
  nat_name        = "${var.prefix}-nat"
  vpc_name        = "${var.prefix}-vpc"
}

resource "google_compute_network" "default" {
  name       = local.vpc_name
  project    = var.project_id
  depends_on = [time_sleep.wait_60_seconds]
}

resource "google_container_cluster" "main" {
  name             = local.cluster_name
  location         = var.region
  project          = var.project_id
  network          = google_compute_network.default.name
  enable_autopilot = true
  # Set to false for demo purposes. Production clusters should leave this
  # enabled to prevent accidental destruction.
  deletion_protection = false

  gateway_api_config {
    channel = "CHANNEL_STANDARD"
  }
}


resource "google_compute_global_address" "gateway" {
  name       = local.gateway_ip_name
  project    = var.project_id
  depends_on = [time_sleep.wait_60_seconds]
}

resource "google_compute_address" "nat" {
  name       = local.nat_ip_name
  region     = var.region
  project    = var.project_id
  depends_on = [time_sleep.wait_60_seconds]
}

resource "google_compute_router" "main" {
  name    = local.router_name
  region  = var.region
  project = var.project_id
  network = google_compute_network.default.name
}

resource "google_compute_router_nat" "main" {
  name                               = local.nat_name
  router                             = google_compute_router.main.name
  region                             = var.region
  project                            = var.project_id
  nat_ip_allocate_option             = "MANUAL_ONLY"
  nat_ips                            = [google_compute_address.nat.self_link]
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
