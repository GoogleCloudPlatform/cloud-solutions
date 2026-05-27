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
