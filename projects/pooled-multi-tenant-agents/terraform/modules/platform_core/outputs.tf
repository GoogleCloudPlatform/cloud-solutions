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

output "pooled_agent_runtime_sa_email" {
  description = "The single serving identity (Cloud Run gateway + agent runtime)."
  value       = google_service_account.pooled_agent_runtime.email
}

output "model_armor_template_id" {
  description = "Regional Model Armor template resource name."
  value       = google_model_armor_template.inbound_pep.id
}

output "pooled_runbook_gcs_bucket" {
  description = "Pooled GCS bucket supporting per-object tenant CMEK encryption."
  value       = google_storage_bucket.pooled_cmek_runbooks.name
}

output "dlp_inspect_template_id" {
  description = "Regional Cloud DLP Inspect Template resource name."
  value       = google_data_loss_prevention_inspect_template.tenant_pii_inspect.id
}

output "dlp_deidentify_template_id" {
  description = "Regional Cloud DLP De-identify Template resource name."
  value       = google_data_loss_prevention_deidentify_template.tenant_pii_deidentify.id
}

output "bigquery_otel_table_id" {
  description = "BigQuery OpenTelemetry audit table ID for per-tenant COGS attribution."
  value       = google_bigquery_table.tenant_otel_spans.id
}

output "pooled_gateway_uri" {
  description = "Canonical Cloud Run URI for the Cymbal Pooled Agent Gateway (WS2 Figure 4 output)."
  value       = google_cloud_run_v2_service.cymbal_pooled_gateway.uri
}

output "redis_bulkhead_host" {
  description = "Memorystore for Redis token-bucket bulkhead host endpoint (WS2 Figure 4 output)."
  value       = var.enable_memorystore_redis ? google_redis_instance.token_bucket_bulkhead[0].host : "127.0.0.1"
}

output "redis_bulkhead_url" {
  description = "Plaintext Memorystore for Redis connection URL (`redis://host:port/0`) when Redis AUTH/TLS is disabled; empty otherwise."
  value       = (var.enable_memorystore_redis && !var.enable_redis_auth_and_tls) ? "redis://${google_redis_instance.token_bucket_bulkhead[0].host}:${google_redis_instance.token_bucket_bulkhead[0].port}/0" : ""
}

output "redis_tls_secret_id" {
  description = "Secret Manager secret ID holding the Redis AUTH+TLS connection bundle when `enable_redis_auth_and_tls` is true."
  value       = (var.enable_memorystore_redis && var.enable_redis_auth_and_tls) ? google_secret_manager_secret.redis_tls_bundle[0].secret_id : ""
}

output "redis_tls_secret_version" {
  description = "Pinned Secret Manager resource version name (`projects/.../secrets/.../versions/...`) for `REDIS_TLS_SECRET_VERSION`, or empty when disabled."
  value       = (var.enable_memorystore_redis && var.enable_redis_auth_and_tls) ? google_secret_manager_secret_version.redis_tls_bundle[0].name : ""
}

output "alloydb_rls_cluster_id" {
  description = "AlloyDB Pooled RLS Cluster resource ID."
  value       = var.enable_alloydb_cluster ? google_alloydb_cluster.pooled_rls_cluster[0].id : "disabled"
}

output "alloydb_primary_instance_uri" {
  description = "AlloyDB primary instance resource name (`projects/.../instances/...`), or empty when disabled."
  value       = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? google_alloydb_instance.pooled_rls_primary[0].name : ""
}

output "alloydb_primary_ip_address" {
  description = "Private VPC IPv4 address of the AlloyDB primary instance, or empty when disabled."
  value       = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? google_alloydb_instance.pooled_rls_primary[0].ip_address : ""
}

# --- Inputs for modules/tenant ------------------------------------------------------------------

output "project_number" {
  description = "Platform project number."
  value       = data.google_project.current.number
}

output "labels" {
  description = "Labels the platform applies (tenants reuse them)."
  value       = local.common_labels
}

output "tenant_key_ring_id" {
  description = "Key ring that holds the per-tenant CMEK keys."
  value       = google_kms_key_ring.tenant_cmek_ring.id
}

output "gcs_service_agent_email" {
  description = "Cloud Storage service agent (needs encrypt/decrypt on CMEK keys used as bucket defaults)."
  value       = data.google_storage_project_service_account.gcs_account.email_address
}

output "runbook_bucket_name" {
  description = "Pooled runbook bucket; each tenant gets a managed folder in it."
  value       = google_storage_bucket.pooled_cmek_runbooks.name
}

output "analytics_dataset_id" {
  description = "Telemetry dataset ID."
  value       = google_bigquery_dataset.agent_analytics.dataset_id
}

output "spans_table_id" {
  description = "Telemetry spans table ID (row access policies are per tenant)."
  value       = google_bigquery_table.tenant_otel_spans.table_id
}

output "credential_broker_enabled" {
  description = "Whether the broker exists (tenants then grant it TokenCreator)."
  value       = var.enable_credential_broker
}

output "credential_broker_service_name" {
  description = "Cloud Run service name of the credential broker."
  value       = var.enable_credential_broker ? google_cloud_run_v2_service.credential_broker[0].name : "cymbal-credential-broker"
}

output "context_signing_key_id" {
  description = "Full Cloud KMS crypto key ID for `ws2-context-signing` (agent runtimes get publicKeyViewer only)."
  value       = google_kms_crypto_key.context_signing.id
}

output "build_sa_email" {
  description = "Dedicated Cloud Build service account email (`cymbal-build-sa`), or empty when disabled."
  value       = var.enable_build_sa ? google_service_account.cymbal_build[0].email : ""
}

output "pooled_vpc_name" {
  description = "Pooled VPC network/subnetwork name for Direct VPC Egress, or empty when disabled."
  value       = (var.enable_alloydb_cluster || var.enable_memorystore_redis) ? google_compute_network.pooled_vpc[0].name : ""
}

output "tenant_key_ring_name" {
  description = "Short name of the KMS key ring holding per-tenant CMEK keys."
  value       = google_kms_key_ring.tenant_cmek_ring.name
}

output "firestore_database_name" {
  description = "Firestore database name for 5-level session state and control-plane revocations."
  value       = google_firestore_database.tenant_memory_bank.name
}

output "model_armor_template_short_id" {
  description = "Short template_id of the inbound/outbound Model Armor template."
  value       = google_model_armor_template.inbound_pep.template_id
}

output "alloydb_cluster_name" {
  description = "Full AlloyDB cluster resource name when cluster and primary instance are enabled."
  value       = (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance) ? google_alloydb_cluster.pooled_rls_cluster[0].name : ""
}
