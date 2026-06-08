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

data "google_compute_image" "os_image" {
  family  = var.os_image_family
  project = var.os_image_project
}

data "google_compute_subnetwork" "oracle_subnet" {
  name    = var.subnetwork_name
  project = var.project_id
  region  = var.region
}

resource "google_compute_instance" "oracle_vm" {
  name         = "oracle-db-19c"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id
  tags         = ["oracle-server"]

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  boot_disk {
    initialize_params {
      image = data.google_compute_image.os_image.self_link
      size  = 50
    }
  }

  network_interface {
    subnetwork = data.google_compute_subnetwork.oracle_subnet.self_link
  }

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }

  attached_disk {
    source      = google_compute_disk.data_disk.id
    device_name = "oracle-data"
  }

  metadata = {
    ssh-keys        = "${var.ssh_user}:${file(pathexpand("${var.ssh_key_path}.pub"))}"
    gcs_bucket_name = var.gcs_bucket_name
    rpm_name        = var.rpm_name
  }

  metadata_startup_script = file("${path.module}/scripts/startup.sh")
}

resource "google_compute_disk" "data_disk" {
  name    = "oracle-data-disk-${var.project_id}"
  type    = "pd-ssd"
  zone    = var.zone
  size    = 100
  project = var.project_id
}
