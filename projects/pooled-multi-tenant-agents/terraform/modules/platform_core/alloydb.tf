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
# Hop 3 & Hop 5: Tenant CMEK Key Ring, Pooled Per-Object CMEK GCS Vault & AlloyDB Pooled RLS
# Cluster (per-tenant keys and skills buckets: modules/tenant)
# ============================================================================

resource "google_kms_key_ring" "tenant_cmek_ring" {
  name       = "cymbal-tenant-kr-${var.environment}"
  location   = var.region
  depends_on = [google_project_service.enabled_apis]
}

# Tenant CMEK keys live in this ring but are owned by modules/tenant (one key per tenant).

data "google_storage_project_service_account" "gcs_account" {
  project    = var.project_id
  depends_on = [google_project_service.enabled_apis]
}

# Pooled GCS Runbook Bucket with per-object tenant CMEK.
# No bucket default key: a default would silently encrypt every tenant's objects with ONE tenant's
# key (previously FinVault's). Each object must be uploaded with its tenant's `kmsKeyName`, and
# LiveGCSCMEKRunbookVault rejects objects whose key does not match the reading tenant.
# Per-tenant read access is granted on managed folders in modules/tenant.
resource "google_storage_bucket" "pooled_cmek_runbooks" {
  name                        = "${var.project_id}-runbooks"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = !var.deletion_protection
  labels                      = local.common_labels
  depends_on                  = [google_project_service.enabled_apis]
}

# Per-tenant skills buckets: modules/tenant.

resource "google_compute_network" "pooled_vpc" {
  count                   = (var.enable_alloydb_cluster || var.enable_memorystore_redis) ? 1 : 0
  name                    = "cymbal-pooled-vpc-${var.environment}"
  auto_create_subnetworks = true
  depends_on              = [google_project_service.enabled_apis]
}

resource "google_alloydb_cluster" "pooled_rls_cluster" {
  count      = var.enable_alloydb_cluster ? 1 : 0
  cluster_id = "cymbal-pooled-rls-${var.environment}"
  location   = var.region
  network_config {
    network = google_compute_network.pooled_vpc[0].id
  }
  labels     = local.common_labels
  depends_on = [google_project_service.enabled_apis]
}

resource "google_compute_global_address" "alloydb_psa_range" {
  count         = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? 1 : 0
  name          = "cymbal-alloydb-psa-range-${var.environment}"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.pooled_vpc[0].id
  depends_on    = [google_project_service.enabled_apis]
}

resource "google_service_networking_connection" "alloydb_psa_connection" {
  count                   = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? 1 : 0
  network                 = google_compute_network.pooled_vpc[0].id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.alloydb_psa_range[0].name]
  depends_on              = [google_project_service.enabled_apis]
}

# Zonal 2-vCPU primary instance with IAM authentication (`alloydb.iam_authentication = on`, zero DB
# passwords). Private VPC address only by default. `var.alloydb_enable_public_ip = true` adds a
# public IP WITHOUT authorized_external_networks, so raw public TCP 5432 stays blocked while the
# AlloyDB Auth Proxy (mTLS + `roles/alloydb.client`) can reach it from an operator machine outside
# the VPC for schema bootstrap/tests. That is an internet-facing endpoint: opt in deliberately.
resource "google_alloydb_instance" "pooled_rls_primary" {
  count             = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? 1 : 0
  cluster           = google_alloydb_cluster.pooled_rls_cluster[0].name
  instance_id       = "cymbal-pooled-rls-primary-${var.environment}"
  instance_type     = "PRIMARY"
  availability_type = "ZONAL"
  labels            = local.common_labels

  machine_config {
    cpu_count = 2
  }

  database_flags = {
    "alloydb.iam_authentication"  = "on"
    "alloydb.enable_pgaudit"      = "on"
    "password.enforce_complexity" = "on"
  }

  network_config {
    enable_public_ip = var.alloydb_enable_public_ip
  }

  depends_on = [google_service_networking_connection.alloydb_psa_connection]
}

resource "google_alloydb_user" "runtime_iam_db_user" {
  count          = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? 1 : 0
  cluster        = google_alloydb_cluster.pooled_rls_cluster[0].name
  user_id        = trimsuffix(google_service_account.pooled_agent_runtime.email, ".gserviceaccount.com")
  user_type      = "ALLOYDB_IAM_USER"
  database_roles = ["alloydbiamuser"]
  depends_on     = [google_alloydb_instance.pooled_rls_primary]

  lifecycle {
    # PostgreSQL RLS bootstrap grants the non-superuser `cymbal_mcp_app` role via SQL DDL.
    ignore_changes = [database_roles]
  }
}

resource "google_alloydb_user" "operator_iam_admins" {
  for_each       = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? toset(var.alloydb_admin_iam_users) : toset([])
  cluster        = google_alloydb_cluster.pooled_rls_cluster[0].name
  user_id        = trimsuffix(each.value, ".gserviceaccount.com")
  user_type      = "ALLOYDB_IAM_USER"
  database_roles = ["alloydbiamuser", "alloydbsuperuser"]
  depends_on     = [google_alloydb_instance.pooled_rls_primary]

  lifecycle {
    ignore_changes = [database_roles]
  }
}

resource "google_project_iam_member" "operator_alloydb_client" {
  for_each = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? toset(var.alloydb_admin_iam_users) : toset([])
  project  = var.project_id
  role     = "roles/alloydb.client"
  member   = (startswith(each.value, "user:") || startswith(each.value, "serviceAccount:") || startswith(each.value, "group:")) ? each.value : (endswith(each.value, ".iam") ? "serviceAccount:${each.value}.gserviceaccount.com" : (endswith(each.value, ".gserviceaccount.com") ? "serviceAccount:${each.value}" : "user:${each.value}"))
}

resource "google_project_iam_member" "operator_alloydb_db_user" {
  for_each = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? toset(var.alloydb_admin_iam_users) : toset([])
  project  = var.project_id
  role     = "roles/alloydb.databaseUser"
  member   = (startswith(each.value, "user:") || startswith(each.value, "serviceAccount:") || startswith(each.value, "group:")) ? each.value : (endswith(each.value, ".iam") ? "serviceAccount:${each.value}.gserviceaccount.com" : (endswith(each.value, ".gserviceaccount.com") ? "serviceAccount:${each.value}" : "user:${each.value}"))
}
