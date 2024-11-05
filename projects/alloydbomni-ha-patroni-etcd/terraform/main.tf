#
# Copyright 2024 Google LLC
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
#

terraform {
  required_version = ">= 1.1.3"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.0.0"
    }
  }

  provider_meta "google" {
    module_name = "cloud-solutions/alloydbomni-patroni-ha-deploy-v0.1"
  }
}

data "google_project" "project" {
  project_id = var.project_id
}

provider "google" {
  billing_project = var.project_id
  project         = var.project_id
  region          = var.region
  zone            = var.zones[0]
}

locals {
  etcd_ip_count       = var.node_count
  patroni_ip_count    = var.node_count
  upload_scripts_path = "../src/"

  machine_type = "n2-highmem-4"
  image        = "ubuntu-os-cloud/ubuntu-2204-lts"

  etcd_ip_names    = [for idx in range(local.etcd_ip_count) : "alloydb-patroni-internal-etcd-ip-${idx + 1}"]
  patroni_ip_names = [for idx in range(local.patroni_ip_count) : "alloydb-patroni-internal-patroni-ip-${idx + 1}"]

  effective_replication_user_password    = var.replication_user_password != "" ? var.replication_user_password : random_password.replication_user_password[0].result
  effective_postgres_super_user_password = var.postgres_super_user_password != "" ? var.postgres_super_user_password : random_password.postgres_super_user_password[0].result
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "random_password" "postgres_super_user_password" {
  count   = var.postgres_super_user_password != "" ? 0 : 1
  length  = 16
  special = true
}

resource "random_password" "replication_user_password" {
  count   = var.replication_user_password != "" ? 0 : 1
  length  = 16
  special = true
}

resource "google_compute_network" "vpc" {
  name                    = "alloydb-patroni-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "alloydb-patroni-subnet"
  region        = var.region
  ip_cidr_range = "10.0.1.0/24"

  network = google_compute_network.vpc.id
}

resource "google_compute_address" "internal_ips" {
  for_each = toset(flatten([
    local.etcd_ip_names,
    local.patroni_ip_names
  ]))

  name         = each.key
  address_type = "INTERNAL"
  region       = var.region
  subnetwork   = google_compute_subnetwork.subnet.id
}

resource "google_compute_firewall" "firewalls" {
  for_each = tomap({
    allow_ssh = {
      name        = "alloydb-patroni-fw-allow-ssh"
      description = "Firewall rules to allow SSH"
      ports       = ["22"]
    }
    allow_postgres = {
      name        = "alloydb-patroni-fw-allow-postgres"
      description = "Firewall rules to allow Postgres"
      ports       = ["5432"]
    }
    allow_etcd = {
      name        = "alloydb-patroni-fw-allow-etcd"
      description = "Firewall rules to allow etcd"
      ports       = ["2379", "2380"]
    }
    allow_patroni = {
      name        = "alloydb-patroni-fw-allow-patroni"
      description = "Firewall rules to allow patroni"
      ports       = ["8008"]
    }
    allow_haproxy = {
      name        = "alloydb-patroni-fw-allow-haproxy"
      description = "Firewall rules to allow haproxy"
      ports       = ["5000", "5001", "7000"]
    }
  })

  name        = each.value.name
  network     = google_compute_network.vpc.id
  description = each.value.description

  allow {
    protocol = "tcp"
    ports    = each.value.ports
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_storage_bucket" "bucket" {
  name          = "alloydbomni-patroni-temporary-bucket-${random_id.bucket_suffix.hex}"
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket_object" "objects" {
  for_each = fileset(path.module, "${local.upload_scripts_path}**")

  name   = replace("${each.value}", "${local.upload_scripts_path}", "")
  bucket = google_storage_bucket.bucket.name
  source = each.value
}

resource "google_service_account" "service_accounts" {
  for_each = tomap({
    etcd_instance_sa = {
      account_id   = "etcd-instance-sa"
      display_name = "ETCD Instance Service Account"
    }
    alloydb_patroni_instance_sa = {
      account_id   = "alloydb-patroni-instance-sa"
      display_name = "AlloydbOmni with Patroni Instance Service Account"
    }
    haproxy_instance_sa = {
      account_id   = "haproxy-instance-sa"
      display_name = "HAProxy Instance Service Account"
    }
  })

  account_id   = each.value.account_id
  display_name = each.value.display_name
}

resource "google_storage_bucket_iam_member" "bucket_reader" {
  bucket = google_storage_bucket.bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.service_accounts["alloydb_patroni_instance_sa"].email}"
}

resource "local_file" "startup_scripts" {
  for_each = merge(
    {
      for idx in range(var.node_count) :
      "etcd_startup${idx + 1}" => {
        content = templatefile("${path.module}/scripts/etcd_startup.tftpl", {
          instance_index       = idx + 1,
          etcd_current_node_ip = google_compute_address.internal_ips[local.etcd_ip_names[idx]].address,
          etcd_nodes_ip_list   = [for idx in range(local.etcd_ip_count) : tostring(google_compute_address.internal_ips[local.etcd_ip_names[idx]].address)]
        })
        filename = "${path.module}/scripts/etcd_startup${idx + 1}.sh"
      }
    },
    {
      for idx in range(var.node_count) :
      "patroni_startup${idx + 1}" => {
        content = templatefile("${path.module}/scripts/patroni_startup.tftpl", {
          download_folder              = var.download_folder,
          bucket_name                  = google_storage_bucket.bucket.name,
          cluster_name                 = var.cluster_name,
          instance_index               = idx + 1,
          patroni_current_node_ip      = google_compute_address.internal_ips[local.patroni_ip_names[idx]].address,
          patroni_nodes_ip_list        = [for idx in range(local.patroni_ip_count) : tostring(google_compute_address.internal_ips[local.patroni_ip_names[idx]].address)]
          etcd_nodes_ip_list           = [for idx in range(local.etcd_ip_count) : tostring(google_compute_address.internal_ips[local.etcd_ip_names[idx]].address)]
          replication_user_password    = local.effective_replication_user_password,
          postgres_super_user          = var.postgres_super_user,
          postgres_super_user_password = local.effective_postgres_super_user_password
        })
        filename = "${path.module}/scripts/patroni_startup${idx + 1}.sh"
      }
    },
    {
      "haproxy" = {
        content = templatefile("${path.module}/scripts/haproxy_startup.tftpl", {
          patroni_nodes_ip_list = [for idx in range(local.patroni_ip_count) : tostring(google_compute_address.internal_ips[local.patroni_ip_names[idx]].address)]
        })
        filename = "${path.module}/scripts/haproxy_startup.sh"
      }
    }
  )

  content  = each.value.content
  filename = each.value.filename
}


resource "google_compute_instance" "instances" {
  for_each = merge(
    {
      for idx in range(var.node_count) :
      "etcd${idx + 1}" => {
        name           = "alloydb-patroni-etcd${idx + 1}"
        type           = "etcd"
        zone           = var.zones[idx % length(var.zones)]
        ip_name        = local.etcd_ip_names[idx]
        startup_script = local_file.startup_scripts["etcd_startup${idx + 1}"].content
        sa_email       = google_service_account.service_accounts["etcd_instance_sa"].email
      }
    },
    {
      for idx in range(var.node_count) :
      "patroni${idx + 1}" => {
        name           = "alloydb-patroni${idx + 1}"
        type           = "patroni"
        zone           = var.zones[idx % length(var.zones)]
        ip_name        = local.patroni_ip_names[idx]
        startup_script = local_file.startup_scripts["patroni_startup${idx + 1}"].content
        sa_email       = google_service_account.service_accounts["alloydb_patroni_instance_sa"].email
      }
    },
    {
      "haproxy" = {
        name           = "haproxy"
        type           = "haproxy"
        zone           = var.zones[0]
        ip_name        = null
        startup_script = local_file.startup_scripts["haproxy"].content
        sa_email       = google_service_account.service_accounts["haproxy_instance_sa"].email
      }
    }
  )

  name         = each.value.name
  machine_type = local.machine_type
  zone         = each.value.zone

  boot_disk {
    initialize_params {
      image = local.image
    }
  }

  network_interface {
    network    = google_compute_network.vpc.id
    subnetwork = google_compute_subnetwork.subnet.id
    network_ip = each.value.type == "haproxy" ? null : google_compute_address.internal_ips[each.value.ip_name].address
    access_config {}
  }

  service_account {
    email  = each.value.sa_email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata_startup_script = each.value.startup_script
  depends_on              = [google_storage_bucket.bucket]
}
