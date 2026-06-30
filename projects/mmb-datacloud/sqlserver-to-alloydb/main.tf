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

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Generate a random password for SQL Server root/admin account
resource "random_password" "sql_server_password" {
  length           = 16
  special          = true
  override_special = "!#%*_-="
}

# Enable necessary Google Cloud APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "sqladmin.googleapis.com",
    "alloydb.googleapis.com",
    "compute.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com"
  ])

  service            = each.key
  disable_on_destroy = false
}

# Networks setup
resource "google_compute_network" "vpc_1" {
  name                    = "vpc-1"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
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
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "vpc_2_subnet" {
  name          = "vpc-2-subnet"
  ip_cidr_range = "10.20.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.vpc_2.self_link
}

# Private Service Access (PSA) configuration for vpc-1 (needed for Cloud SQL Private IP)
resource "google_compute_global_address" "private_ip_alloc" {
  name          = "private-ip-alloc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc_1.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_1.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
}

# Cloud SQL SQL Server instance (Source Database)
resource "google_sql_database_instance" "mssql_source" {
  name                = "mssql-source"
  database_version    = "SQLSERVER_2022_STANDARD"
  region              = var.gcp_region
  root_password       = random_password.sql_server_password.result
  deletion_protection = false

  settings {
    tier = "db-custom-2-13312" # 2 vCPU, 13GB RAM (13312 MiB is a multiple of 256 MiB)
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc_1.self_link
    }
  }

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

# Debian Image for helper VM
data "google_compute_image" "debian_image" {
  family  = "debian-12"
  project = "debian-cloud"
}

# Helper VM to load the BigQuery data into SQL Server
resource "google_compute_instance" "mssql_loader_vm" {
  name         = "mssql-loader-vm"
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
      // Ephemeral public IP to download packages and access BigQuery public data
    }
  }

  metadata_startup_script = file("${path.module}/scripts/load-data.sh")

  metadata = {
    SQL_SERVER_IP       = google_sql_database_instance.mssql_source.private_ip_address
    SQL_SERVER_PASSWORD = random_password.sql_server_password.result
  }

  service_account {
    scopes = ["cloud-platform"]
  }
}

# Firewall rules
resource "google_compute_firewall" "vpc_1_allow_ssh" {
  name    = "vpc-1-allow-ssh"
  network = google_compute_network.vpc_1.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_firewall" "vpc_1_allow_mssql_internal" {
  name    = "vpc-1-allow-mssql-internal"
  network = google_compute_network.vpc_1.name

  allow {
    protocol = "tcp"
    ports    = ["1433"]
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
