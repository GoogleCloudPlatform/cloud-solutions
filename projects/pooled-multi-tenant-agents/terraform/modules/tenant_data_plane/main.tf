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

# ============================================================================
# Tenant data plane (WS4 hybrid, Pattern C): the tenant's data stays in a project the tenant
# controls. The pooled platform reaches it only through Private Service Connect.
#
#   - CMEK key ring + key in the tenant project (the tenant can revoke the platform's access)
#   - AlloyDB cluster + primary instance, encrypted with that key, PSC-enabled (no VPC peering)
#   - The instance's PSC service attachment accepts only the listed consumer projects (the pooled
#     platform project); the consumer creates a PSC endpoint against `psc_service_attachment`.
#
# Code only: not instantiated in the sandbox. See terraform/envs/hybrid-example.
# ============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.50"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.50"
    }
  }
}

locals {
  labels = merge(var.labels, { tenant_id = var.tenant_id, data_plane = "tenant-hosted" })
  apis   = toset(["alloydb.googleapis.com", "cloudkms.googleapis.com", "compute.googleapis.com"])
}

resource "google_project_service" "apis" {
  for_each           = local.apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# The AlloyDB service agent must exist before it can be granted the CMEK key.
resource "google_project_service_identity" "alloydb" {
  provider   = google-beta
  project    = var.project_id
  service    = "alloydb.googleapis.com"
  depends_on = [google_project_service.apis]
}

resource "google_kms_key_ring" "data_plane" {
  project    = var.project_id
  name       = "${var.name_prefix}-kr"
  location   = var.region
  depends_on = [google_project_service.apis]
}

resource "google_kms_crypto_key" "data_plane" {
  name            = "${var.name_prefix}-cmek"
  key_ring        = google_kms_key_ring.data_plane.id
  rotation_period = "7776000s" # 90 days
  labels          = local.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "alloydb_agent" {
  crypto_key_id = google_kms_crypto_key.data_plane.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_project_service_identity.alloydb.email}"
}

resource "google_alloydb_cluster" "data_plane" {
  project    = var.project_id
  cluster_id = "${var.name_prefix}-db"
  location   = var.region
  labels     = local.labels

  encryption_config {
    kms_key_name = google_kms_crypto_key.data_plane.id
  }

  psc_config {
    psc_enabled = true
  }

  continuous_backup_config {
    enabled = true
    encryption_config {
      kms_key_name = google_kms_crypto_key.data_plane.id
    }
  }

  depends_on = [google_kms_crypto_key_iam_member.alloydb_agent]

  # Tenant data: Terraform never deletes the cluster (remove this block deliberately to tear down).
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_alloydb_instance" "primary" {
  cluster       = google_alloydb_cluster.data_plane.name
  instance_id   = "${var.name_prefix}-primary"
  instance_type = "PRIMARY"
  labels        = local.labels

  machine_config {
    cpu_count = var.cpu_count
  }

  psc_instance_config {
    allowed_consumer_projects = var.allowed_consumer_projects
  }
}
