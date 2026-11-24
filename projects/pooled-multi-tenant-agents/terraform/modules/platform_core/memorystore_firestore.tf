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
# Subsystem 4 & 5: Firestore 5-Level Memory Bank & Memorystore Redis Bulkheads
# ============================================================================

resource "google_firestore_database" "tenant_memory_bank" {
  project                     = var.project_id
  name                        = "cymbal-memory-bank-${var.environment}"
  location_id                 = var.region
  type                        = "FIRESTORE_NATIVE"
  concurrency_mode            = "OPTIMISTIC"
  app_engine_integration_mode = "DISABLED"
  depends_on                  = [google_project_service.enabled_apis]
}

resource "google_redis_instance" "token_bucket_bulkhead" {
  count                   = var.enable_memorystore_redis ? 1 : 0
  name                    = "cymbal-token-bulkhead-${var.environment}"
  tier                    = "BASIC"
  memory_size_gb          = 1
  region                  = var.region
  redis_version           = "REDIS_7_0"
  auth_enabled            = var.enable_redis_auth_and_tls
  transit_encryption_mode = var.enable_redis_auth_and_tls ? "SERVER_AUTHENTICATION" : "DISABLED"
  authorized_network      = google_compute_network.pooled_vpc[0].id
  display_name            = "Cymbal Per-Tenant RPM/TPM Rate Limit Bulkhead"
  labels                  = local.common_labels
  depends_on              = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret" "redis_tls_bundle" {
  count      = (var.enable_memorystore_redis && var.enable_redis_auth_and_tls) ? 1 : 0
  project    = var.project_id
  secret_id  = "cymbal-redis-tls-auth-${var.environment}"
  labels     = local.common_labels
  depends_on = [google_project_service.enabled_apis]

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "redis_tls_bundle" {
  count  = (var.enable_memorystore_redis && var.enable_redis_auth_and_tls) ? 1 : 0
  secret = google_secret_manager_secret.redis_tls_bundle[0].id
  secret_data = jsonencode({
    url    = "rediss://:${google_redis_instance.token_bucket_bulkhead[0].auth_string}@${google_redis_instance.token_bucket_bulkhead[0].host}:${google_redis_instance.token_bucket_bulkhead[0].port}/0"
    ca_pem = try(google_redis_instance.token_bucket_bulkhead[0].server_ca_certs[0].cert, "")
  })
}

resource "google_secret_manager_secret_iam_member" "runtime_redis_tls_accessor" {
  count     = (var.enable_memorystore_redis && var.enable_redis_auth_and_tls) ? 1 : 0
  project   = var.project_id
  secret_id = google_secret_manager_secret.redis_tls_bundle[0].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pooled_agent_runtime.email}"
}
