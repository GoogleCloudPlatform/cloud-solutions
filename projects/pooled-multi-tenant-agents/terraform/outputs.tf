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
  value       = module.platform_core.pooled_agent_runtime_sa_email
}

output "model_armor_template_id" {
  description = "Regional Model Armor template resource name."
  value       = module.platform_core.model_armor_template_id
}

output "finvault_cmek_key_id" {
  description = "KMS CMEK key ID for Tenant Alpha (FinVault Bank)."
  value       = try(module.tenant["tenant-finvault-alpha"].cmek_key_id, null)
}

output "retailstream_cmek_key_id" {
  description = "KMS CMEK key ID for Tenant Beta (RetailStream Corp)."
  value       = try(module.tenant["tenant-retailstream-beta"].cmek_key_id, null)
}

output "pooled_runbook_gcs_bucket" {
  description = "Pooled GCS bucket supporting per-object tenant CMEK encryption."
  value       = module.platform_core.pooled_runbook_gcs_bucket
}

output "dlp_inspect_template_id" {
  description = "Regional Cloud DLP Inspect Template resource name."
  value       = module.platform_core.dlp_inspect_template_id
}

output "dlp_deidentify_template_id" {
  description = "Regional Cloud DLP De-identify Template resource name."
  value       = module.platform_core.dlp_deidentify_template_id
}

output "bigquery_otel_table_id" {
  description = "BigQuery OpenTelemetry audit table ID for per-tenant COGS attribution."
  value       = module.platform_core.bigquery_otel_table_id
}

output "secret_manager_3lo_vault_ids" {
  description = "Secret Manager secret IDs for 3rd-party SaaS OAuth/API credentials, keyed by secret ID."
  value       = merge([for t in module.tenant : t.secret_ids]...)
}

output "pooled_gateway_uri" {
  description = "Canonical Cloud Run URI for the Cymbal Pooled Agent Gateway (WS2 Figure 4 output)."
  value       = module.platform_core.pooled_gateway_uri
}

output "redis_bulkhead_host" {
  description = "Memorystore for Redis token-bucket bulkhead host endpoint (WS2 Figure 4 output)."
  value       = module.platform_core.redis_bulkhead_host
}

output "redis_bulkhead_url" {
  description = "Plaintext Memorystore for Redis connection URL (`redis://host:port/0`) when Redis AUTH/TLS is disabled; empty otherwise."
  value       = module.platform_core.redis_bulkhead_url
}

output "alloydb_rls_cluster_id" {
  description = "AlloyDB Pooled RLS Cluster resource ID."
  value       = module.platform_core.alloydb_rls_cluster_id
}

output "alloydb_primary_instance_uri" {
  description = "AlloyDB primary instance resource name (`projects/.../instances/...`), or empty when disabled."
  value       = module.platform_core.alloydb_primary_instance_uri
}

output "alloydb_primary_ip_address" {
  description = "Private VPC IPv4 address of the AlloyDB primary instance, or empty when disabled."
  value       = module.platform_core.alloydb_primary_ip_address
}

output "pooled_vpc_name" {
  description = "Pooled VPC network/subnetwork name for Direct VPC Egress, or empty when disabled."
  value       = module.platform_core.pooled_vpc_name
}

output "model_armor_template_short_id" {
  description = "Short template ID of the Model Armor template (`MODEL_ARMOR_TEMPLATE_ID`)."
  value       = module.platform_core.model_armor_template_short_id
}

output "tenant_key_ring_name" {
  description = "Short Cloud KMS key ring name holding per-tenant CMEK keys (`KMS_KEYRING_NAME`)."
  value       = module.platform_core.tenant_key_ring_name
}

output "analytics_dataset_id" {
  description = "BigQuery telemetry dataset ID (`BIGQUERY_DATASET`)."
  value       = module.platform_core.analytics_dataset_id
}

output "firestore_database_name" {
  description = "Cloud Firestore database name (`FIRESTORE_DATABASE`)."
  value       = module.platform_core.firestore_database_name
}

output "credential_broker_url" {
  description = "Set var.credential_broker_url to exactly this at B4 step 3; empty until enabled."
  value       = module.platform_core.credential_broker_url
}

output "credential_broker_sa_email" {
  description = "Credential broker identity (ADR-0014 B4); empty until enabled."
  value       = module.platform_core.credential_broker_sa_email
}

output "agent_runtime_urls" {
  description = "Map of agent_id -> deterministic Cloud Run URL for AGENT_RUNTIME_URLS on the gateway (ADR-0014 B5); null until enable_agent_runtimes is true."
  value       = var.enable_agent_runtimes ? { for k, r in module.agent_runtime : local.agent_runtimes[k].agent_id => r.service_url } : null
}

output "agent_runtime_principals" {
  description = "Map of agent_id -> Cloud Run Agent Identity IAM principal (`principal://...`) for ADR-0016 bindings and BROKER_ALLOWED_CALLERS; null until enable_agent_runtimes is true."
  value       = var.enable_agent_runtimes ? { for k, r in module.agent_runtime : local.agent_runtimes[k].agent_id => r.agent_principal } : null
}

output "tenant_service_accounts" {
  description = "Per-tenant runtime identities (blast-radius containment, ADR-0010)."
  value       = { for tenant_id, t in module.tenant : tenant_id => t.service_account_email }

  precondition {
    condition     = length(local.tenant_file_mismatches) == 0
    error_message = "Tenant files must be named <tenant_id>.yaml: ${join(", ", local.tenant_file_mismatches)}"
  }
}
