/**
 * Copyright 2026 Google LLC
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

module "cli" {
  source  = "terraform-google-modules/gcloud/google"
  version = "~> 4.0"

  platform              = "linux"
  additional_components = ["kubectl", "beta"]

  create_cmd_entrypoint = "chmod +x ${path.module}/scripts/qwiklab.sh;${path.module}/scripts/qwiklab.sh"
  create_cmd_body       = "${var.gcp_project_id} ${var.gcp_region} ${var.gcp_zone}"
  skip_download         = false
  upgrade               = false
  gcloud_sdk_version    = "420.0.0"
}

terraform {
  required_version = "1.12.1"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

resource "google_project_service" "apis" {
  for_each = toset([
    "alloydb.googleapis.com",
    "compute.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "aiplatform.googleapis.com",
  ])

  service = each.key

  // This prevents Terraform from disabling the APIs when the resources are destroyed.
  // Set to 'true' if you want to disable the APIs on 'terraform destroy'.
  disable_on_destroy = false
}

resource "google_compute_network" "vpc_1" {
  name                    = "vpc-1"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "vpc_1_subnet" {
  name          = "vpc-1-subnet"
  ip_cidr_range = "10.10.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.vpc_1.self_link
}

resource "google_compute_network" "vpc_2" {
  name                    = "vpc-2"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "vpc_2_subnet" {
  name          = "vpc-2-subnet"
  ip_cidr_range = "10.20.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.vpc_2.self_link
}

data "google_compute_image" "debian_image" {
  family  = "debian-12"
  project = "debian-cloud"
}

resource "google_compute_instance" "self_managed_postgres_vm" {
  name         = "self-managed-postgres-vm"
  machine_type = "e2-standard-4"
  zone         = var.gcp_zone

  boot_disk {
    initialize_params {
      image = data.google_compute_image.debian_image.self_link
      size  = 100
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.vpc_1_subnet.self_link
    access_config {
      // Ephemeral public IP
    }
  }

  metadata_startup_script = file("${path.module}/scripts/self-managed-postgres-vm.sh")

  service_account {
    scopes = ["cloud-platform"]
  }
}

resource "google_compute_firewall" "vpc_1_allow_ssh" {
  name    = "vpc-1-allow-ssh"
  network = google_compute_network.vpc_1.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_firewall" "vpc_1_allow_postgres_internal" {
  name    = "vpc-1-allow-postgres-internal"
  network = google_compute_network.vpc_1.name

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }

  source_ranges = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
}

resource "google_compute_firewall" "vpc_2_allow_ssh" {
  name    = "vpc-2-allow-ssh"
  network = google_compute_network.vpc_2.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_firewall" "vpc_1_allow_icmp_internal" {
  name    = "vpc-1-allow-icmp-internal"
  network = google_compute_network.vpc_1.name

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
}

resource "google_compute_firewall" "vpc_2_allow_icmp_internal" {
  name    = "vpc-2-allow-icmp-internal"
  network = google_compute_network.vpc_2.name

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
}
