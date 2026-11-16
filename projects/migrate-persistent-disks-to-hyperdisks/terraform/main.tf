# Copyright 2026 Google LLC
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

resource "google_project_service" "required_apis" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])

  project                    = var.project_id
  service                    = each.key
  disable_dependent_services = false
  disable_on_destroy         = false
}

data "google_project" "target" {
  project_id = var.project_id

  depends_on = [google_project_service.required_apis]
}

resource "random_id" "suffix" {
  byte_length = 2
}

locals {
  name_prefix = "${var.resource_prefix}-${random_id.suffix.hex}"
  common_labels = {
    environment = "demo"
    workload    = "pd-to-hyperdisk-migration"
  }
}

resource "google_compute_network" "migration" {
  name                    = "${local.name_prefix}-net"
  project                 = data.google_project.target.project_id
  auto_create_subnetworks = false

  depends_on = [google_project_service.required_apis]
}

resource "google_compute_subnetwork" "migration" {
  name                     = "${local.name_prefix}-subnet"
  project                  = data.google_project.target.project_id
  region                   = var.region
  network                  = google_compute_network.migration.id
  ip_cidr_range            = "10.24.0.0/24"
  private_ip_google_access = true
}

resource "google_compute_firewall" "iap_ssh" {
  name          = "${local.name_prefix}-allow-iap-ssh"
  project       = data.google_project.target.project_id
  network       = google_compute_network.migration.id
  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["allow-iap-ssh"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_service_account" "vm" {
  account_id   = "${local.name_prefix}-vm-sa"
  display_name = "Persistent Disk to Hyperdisk migration demo VM service account"
  project      = data.google_project.target.project_id

  depends_on = [google_project_service.required_apis]
}

resource "google_project_iam_member" "vm_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])

  project = data.google_project.target.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.vm.email}"
}

# Creating a Hyperdisk from a snapshot does not copy the source Persistent
# Disk's resourcePolicies bindings. Attaching this regional snapshot schedule
# to the source data disk exercises policy transfer during migration and policy
# restoration during rollback: cutover attaches the existing regional policy to
# the target Hyperdisk and detaches it from the stopped source disk during the
# retention window, while KEEP_AUTO_SNAPSHOTS retains prior scheduled snapshots
# upon source disk deletion.
resource "google_compute_resource_policy" "daily_snapshots" {
  name    = "${local.name_prefix}-daily-snap"
  project = data.google_project.target.project_id
  region  = var.region

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        start_time    = "04:00"
      }
    }

    retention_policy {
      max_retention_days    = 7
      on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"
    }

    snapshot_properties {
      storage_locations = [var.region]
      labels            = local.common_labels
    }
  }

  depends_on = [google_project_service.required_apis]
}

# Remove out-of-band Gen4 instances, Hyperdisks, and migration snapshots created
# during the cutover walkthrough before Terraform destroys the subnetwork and
# snapshot schedule resource policy.
resource "terraform_data" "migration_cleanup" {
  input = {
    project_id  = data.google_project.target.project_id
    zone        = var.zone
    name_prefix = local.name_prefix
  }

  provisioner "local-exec" {
    when    = destroy
    command = "${path.module}/scripts/cleanup_migrated_resources.sh '${self.input.project_id}' '${self.input.zone}' '${self.input.name_prefix}'"
  }

  depends_on = [
    google_compute_resource_policy.daily_snapshots,
    google_compute_subnetwork.migration,
  ]
}

resource "google_compute_disk" "app_data" {
  name    = "${local.name_prefix}-data"
  project = data.google_project.target.project_id
  zone    = var.zone
  type    = "pd-ssd"
  size    = var.data_disk_size_gb
  labels  = merge(local.common_labels, { disk_role = "application-data" })

  depends_on = [
    google_project_service.required_apis,
    terraform_data.migration_cleanup,
  ]
}

resource "google_compute_disk_resource_policy_attachment" "app_data_schedule" {
  name    = google_compute_resource_policy.daily_snapshots.name
  project = data.google_project.target.project_id
  zone    = var.zone
  disk    = google_compute_disk.app_data.name
}

resource "google_compute_instance" "source" {
  name         = "${local.name_prefix}-gen2-vm"
  project      = data.google_project.target.project_id
  zone         = var.zone
  machine_type = var.source_machine_type
  tags         = ["allow-iap-ssh"]
  labels       = local.common_labels

  boot_disk {
    auto_delete = true
    device_name = "boot"

    initialize_params {
      image  = "debian-cloud/debian-12"
      size   = var.boot_disk_size_gb
      type   = "pd-balanced"
      labels = merge(local.common_labels, { disk_role = "boot" })
    }
  }

  attached_disk {
    source      = google_compute_disk.app_data.id
    device_name = "app-data"
    mode        = "READ_WRITE"
  }

  network_interface {
    subnetwork = google_compute_subnetwork.migration.id
  }

  service_account {
    email  = google_service_account.vm.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    enable-guest-attributes = "TRUE"
    enable-oslogin          = "TRUE"
    startup-script          = file("${path.module}/scripts/startup.sh")
  }

  depends_on = [
    google_compute_disk_resource_policy_attachment.app_data_schedule,
    google_project_iam_member.vm_roles,
  ]
}

resource "google_compute_disk" "multi_app_data" {
  name    = "${local.name_prefix}-multi-data"
  project = data.google_project.target.project_id
  zone    = var.zone
  type    = "pd-ssd"
  size    = var.data_disk_size_gb
  labels  = merge(local.common_labels, { disk_role = "application-data" })

  depends_on = [
    google_project_service.required_apis,
    terraform_data.migration_cleanup,
  ]
}

resource "google_compute_disk_resource_policy_attachment" "multi_app_data_schedule" {
  name    = google_compute_resource_policy.daily_snapshots.name
  project = data.google_project.target.project_id
  zone    = var.zone
  disk    = google_compute_disk.multi_app_data.name
}

resource "google_compute_disk" "db_wal" {
  name    = "${local.name_prefix}-wal"
  project = data.google_project.target.project_id
  zone    = var.zone
  type    = "pd-ssd"
  size    = var.wal_disk_size_gb
  labels  = merge(local.common_labels, { disk_role = "write-ahead-log" })

  depends_on = [
    google_project_service.required_apis,
    terraform_data.migration_cleanup,
  ]
}

resource "google_compute_disk" "analytics_spool" {
  name    = "${local.name_prefix}-spool"
  project = data.google_project.target.project_id
  zone    = var.zone
  type    = "pd-standard"
  size    = var.spool_disk_size_gb
  labels  = merge(local.common_labels, { disk_role = "throughput-spool" })

  depends_on = [
    google_project_service.required_apis,
    terraform_data.migration_cleanup,
  ]
}

resource "google_compute_instance" "multi_disk_source" {
  name         = "${local.name_prefix}-multi-disk-gen2-vm"
  project      = data.google_project.target.project_id
  zone         = var.zone
  machine_type = var.source_machine_type
  tags         = ["allow-iap-ssh"]
  labels       = local.common_labels

  boot_disk {
    auto_delete = true
    device_name = "boot"

    initialize_params {
      image  = "debian-cloud/debian-12"
      size   = var.boot_disk_size_gb
      type   = "pd-balanced"
      labels = merge(local.common_labels, { disk_role = "boot" })
    }
  }

  attached_disk {
    source      = google_compute_disk.multi_app_data.id
    device_name = "app-data"
    mode        = "READ_WRITE"
  }

  attached_disk {
    source      = google_compute_disk.db_wal.id
    device_name = "db-wal"
    mode        = "READ_WRITE"
  }

  attached_disk {
    source      = google_compute_disk.analytics_spool.id
    device_name = "analytics-spool"
    mode        = "READ_WRITE"
  }

  network_interface {
    subnetwork = google_compute_subnetwork.migration.id
  }

  service_account {
    email  = google_service_account.vm.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    enable-guest-attributes = "TRUE"
    enable-oslogin          = "TRUE"
    startup-script          = file("${path.module}/scripts/startup.sh")
  }

  depends_on = [
    google_compute_disk_resource_policy_attachment.multi_app_data_schedule,
    google_project_iam_member.vm_roles,
  ]
}
