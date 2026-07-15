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

terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}
provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_client_openid_userinfo" "me" {}

locals {
  # Formats the active developer's email address to match the standard Google Cloud GCE OS Login username format (e.g., converting 'user@domain.com' to 'user_domain_com').
  # Permits absolute portability by enabling explicit developer overrides via var.ssh_user.
  oslogin_user = var.ssh_user != "" ? var.ssh_user : replace(replace(coalesce(data.google_client_openid_userinfo.me.email, "sa_deployer@google.com"), "@", "_"), ".", "_")
}

# 1. Read existing GCS bucket details if create_gcs_bucket is false
data "google_storage_bucket" "existing_bucket" {
  count = var.create_gcs_bucket ? 0 : 1
  name  = var.gcs_bucket_name
}

# 2. Provision new GCS staging bucket if create_gcs_bucket is true
resource "google_storage_bucket" "staging_bucket" {
  count                       = var.create_gcs_bucket ? 1 : 0
  name                        = var.gcs_bucket_name
  project                     = var.project_id
  location                    = var.region
  force_destroy               = true
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  depends_on = [
    google_project_service.storage_api
  ]
}

# 3. Consolidate GCS staging bucket pointers
locals {
  bucket_name = var.create_gcs_bucket ? google_storage_bucket.staging_bucket[0].name : data.google_storage_bucket.existing_bucket[0].name
}

# Upload scripts to GCS so the VM can pull them
resource "google_storage_bucket_object" "scripts" {
  for_each = toset(fileset("${path.module}/modules/oracle_config/scripts", "*"))

  name           = each.value
  source         = "${path.module}/modules/oracle_config/scripts/${each.value}"
  bucket         = local.bucket_name
  detect_md5hash = filemd5("${path.module}/modules/oracle_config/scripts/${each.value}")
}

module "networking" {
  source            = "./modules/networking"
  project_id        = var.project_id
  region            = var.region
  create_vpc        = var.create_vpc
  create_subnetwork = var.create_subnetwork
  vpc_name          = var.vpc_name
  subnetwork_name   = var.subnetwork_name

  depends_on = [
    google_project_service.compute_api
  ]
}

module "compute" {
  source                = "./modules/compute"
  project_id            = var.project_id
  region                = var.region
  zone                  = var.zone
  subnetwork_name       = module.networking.oracle_subnet_name
  ssh_user              = local.oslogin_user
  ssh_key_path          = var.ssh_key_path
  gcs_bucket_name       = local.bucket_name
  rpm_name              = var.rpm_name
  os_image_family       = var.os_image_family
  os_image_project      = var.os_image_project
  machine_type          = var.machine_type
  service_account_email = google_service_account.oracle_vm_sa.email

  depends_on = [google_storage_bucket_object.scripts]
}

# Dynamic Project details fetcher
data "google_project" "project" {
  project_id = var.project_id
}

# Declarative Secret Manager secret provisioning to secure database credentials
resource "google_secret_manager_secret" "db_password_secret" {
  secret_id = "oracle-db-password"
  project   = var.project_id
  replication {
    auto {}
  }

  depends_on = [
    google_project_service.secretmanager_api
  ]
}

resource "random_id" "sa_suffix" {
  byte_length = 4
}

# Declarative custom dedicated Service Account for the GCE VM to follow SRE least-privilege standards
resource "google_service_account" "oracle_vm_sa" {
  account_id   = "oracle-vm-sa-${random_id.sa_suffix.hex}"
  display_name = "Oracle Database VM Service Account"
  project      = var.project_id
}

# Grants Secret Manager Accessor permission on the database password secret to the custom GCE Service Account
resource "google_secret_manager_secret_iam_member" "sa_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.db_password_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.oracle_vm_sa.email}"
}

# Grants Secret Manager Version Adder permission to let the startup script dynamically register the password on boot
resource "google_secret_manager_secret_iam_member" "sa_secret_version_adder" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.db_password_secret.id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.oracle_vm_sa.email}"
}

# Grants full read/write object permissions on the GCS staging bucket strictly to the custom GCE Service Account
resource "google_storage_bucket_iam_member" "sa_bucket_object_user" {
  bucket = local.bucket_name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.oracle_vm_sa.email}"
}

