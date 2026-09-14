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
    "bigquery.googleapis.com",
    "datamigration.googleapis.com"
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
  address       = "10.10.16.0"
  prefix_length = 20
  network       = google_compute_network.vpc_1.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_1.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
  deletion_policy         = "ABANDON"
}

# Cloud SQL SQL Server instance (Source Database)
resource "google_sql_database_instance" "sqlserver_source" {
  name                = "sqlserver-source"
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

# AlloyDB Cluster and Primary Instance with Private Service Connect (PSC) enabled
resource "google_alloydb_cluster" "alloydb_destination" {
  cluster_id = "alloydb-destination"
  location   = var.gcp_region
  project    = var.gcp_project_id

  psc_config {
    psc_enabled = true
  }

  initial_user {
    user     = "postgres"
    password = random_password.sql_server_password.result
  }

  deletion_policy = "FORCE"

  depends_on = [google_project_service.apis]
}

data "google_project" "current" {
  project_id = var.gcp_project_id
}

resource "google_alloydb_instance" "alloydb_destination_primary" {
  cluster       = google_alloydb_cluster.alloydb_destination.name
  instance_id   = "alloydb-destination-primary"
  instance_type = "PRIMARY"

  machine_config {
    cpu_count = 2
  }

  psc_instance_config {
    allowed_consumer_projects = [data.google_project.current.number]
  }
}

# Private Service Connect (PSC) Endpoint in vpc-2 pointing to AlloyDB Service Attachment
resource "google_compute_address" "alloydb_psc_endpoint_ip" {
  name         = "alloydb-psc-endpoint-ip"
  region       = var.gcp_region
  subnetwork   = google_compute_subnetwork.vpc_2_subnet.id
  address_type = "INTERNAL"
  address      = "10.20.0.100"
}

resource "google_compute_forwarding_rule" "alloydb_psc_endpoint" {
  name                  = "alloydb-psc-endpoint"
  region                = var.gcp_region
  network               = google_compute_network.vpc_2.id
  ip_address            = google_compute_address.alloydb_psc_endpoint_ip.self_link
  load_balancing_scheme = ""
  target                = google_alloydb_instance.alloydb_destination_primary.psc_instance_config[0].service_attachment_link
}

# Debian Image for helper VM
data "google_compute_image" "debian_image" {
  family  = "debian-12"
  project = "debian-cloud"
}

# Helper VM to load the BigQuery data into SQL Server
resource "google_compute_instance" "sqlserver_loader_vm" {
  name         = "sqlserver-loader-vm"
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
    SQL_SERVER_IP       = google_sql_database_instance.sqlserver_source.private_ip_address
    SQL_SERVER_PASSWORD = random_password.sql_server_password.result
  }

  service_account {
    scopes = ["cloud-platform"]
  }
}

# AlloyDB Proxy VM in vpc-2 to initialize thelook_ecommerce database over the PSC endpoint
resource "google_compute_instance" "alloydb_proxy_vm" {
  name         = "alloydb-proxy-vm"
  machine_type = "e2-micro"
  zone         = var.gcp_zone

  boot_disk {
    initialize_params {
      image = data.google_compute_image.debian_image.self_link
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.vpc_2_subnet.self_link
    access_config {
      // Ephemeral public IP for package installation and metadata setup
    }
  }

  metadata_startup_script = file("${path.module}/scripts/setup-alloydb-proxy.sh")

  metadata = {
    ALLOYDB_IP       = google_compute_address.alloydb_psc_endpoint_ip.address
    ALLOYDB_PASSWORD = random_password.sql_server_password.result
  }

  service_account {
    scopes = ["cloud-platform"]
  }

  depends_on = [google_compute_forwarding_rule.alloydb_psc_endpoint]
}

# TCP Proxy VM in vpc-1 to bridge DMS Private Connectivity to Cloud SQL (1433)
resource "google_compute_instance" "tcp_proxy_vm" {
  name           = "tcp-proxy-vm"
  machine_type   = "e2-micro"
  zone           = var.gcp_zone
  can_ip_forward = true

  boot_disk {
    initialize_params {
      image = data.google_compute_image.debian_image.self_link
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.vpc_1_subnet.self_link
    access_config {
      // Ephemeral public IP for package installation and metadata setup
    }
  }

  metadata_startup_script = file("${path.module}/scripts/setup-tcp-proxy.sh")

  metadata = {
    SQL_SERVER_IP = google_sql_database_instance.sqlserver_source.private_ip_address
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

resource "google_compute_firewall" "vpc_1_allow_sqlserver_internal" {
  name    = "vpc-1-allow-sqlserver-internal"
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
