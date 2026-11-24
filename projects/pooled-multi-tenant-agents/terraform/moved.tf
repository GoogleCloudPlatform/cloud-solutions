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
# Module layout refactor (2026-11-06): state addresses before -> after. These blocks make the
# refactor a no-op on the adopted sandbox state (plan: moves only). Keep them until every state
# that predates the module layout has been applied once; then they can be deleted.
#
# operator_time_boxed_impersonation moves to platform_core as a whole. Tenant-target instances
# ("<tenant>/<member>") would need per-member blocks; none existed in the sandbox state (the
# grants are time-boxed and recreated through var.operator_impersonation when needed).
# ============================================================================
# --- platform_core: same resource names, now inside module.platform_core
moved {
  from = google_project_service.enabled_apis
  to   = module.platform_core.google_project_service.enabled_apis
}
moved {
  from = google_service_account.pooled_agent_runtime
  to   = module.platform_core.google_service_account.pooled_agent_runtime
}
moved {
  from = google_service_account.stateless_mcp_server
  to   = module.platform_core.google_service_account.stateless_mcp_server
}
moved {
  from = google_project_iam_member.runtime_bindings
  to   = module.platform_core.google_project_iam_member.runtime_bindings
}
moved {
  from = google_bigquery_table_iam_member.runtime_spans_writer
  to   = module.platform_core.google_bigquery_table_iam_member.runtime_spans_writer
}
moved {
  from = google_cloud_run_v2_service.cymbal_pooled_gateway
  to   = module.platform_core.google_cloud_run_v2_service.cymbal_pooled_gateway
}
moved {
  from = google_cloud_run_v2_service_iam_member.iap_invokes_gateway
  to   = module.platform_core.google_cloud_run_v2_service_iam_member.iap_invokes_gateway
}
moved {
  from = google_iap_web_cloud_run_service_iam_member.gateway_accessors
  to   = module.platform_core.google_iap_web_cloud_run_service_iam_member.gateway_accessors
}
moved {
  from = google_iap_web_cloud_run_service_iam_member.gateway_time_boxed_accessors
  to   = module.platform_core.google_iap_web_cloud_run_service_iam_member.gateway_time_boxed_accessors
}
moved {
  from = google_compute_security_policy.cymbal_edge_waf
  to   = module.platform_core.google_compute_security_policy.cymbal_edge_waf
}
moved {
  from = google_service_account.credential_broker
  to   = module.platform_core.google_service_account.credential_broker
}
moved {
  from = google_kms_crypto_key_iam_member.broker_context_key_viewer
  to   = module.platform_core.google_kms_crypto_key_iam_member.broker_context_key_viewer
}
moved {
  from = google_project_iam_member.broker_log_writer
  to   = module.platform_core.google_project_iam_member.broker_log_writer
}
moved {
  from = google_cloud_run_v2_service.credential_broker
  to   = module.platform_core.google_cloud_run_v2_service.credential_broker
}
moved {
  from = google_cloud_run_v2_service_iam_member.runtime_invokes_broker
  to   = module.platform_core.google_cloud_run_v2_service_iam_member.runtime_invokes_broker
}
moved {
  from = google_kms_key_ring.platform
  to   = module.platform_core.google_kms_key_ring.platform
}
moved {
  from = google_kms_crypto_key.context_signing
  to   = module.platform_core.google_kms_crypto_key.context_signing
}
moved {
  from = google_kms_crypto_key_iam_member.runtime_context_signer
  to   = module.platform_core.google_kms_crypto_key_iam_member.runtime_context_signer
}
moved {
  from = google_model_armor_template.inbound_pep
  to   = module.platform_core.google_model_armor_template.inbound_pep
}
moved {
  from = google_data_loss_prevention_inspect_template.tenant_pii_inspect
  to   = module.platform_core.google_data_loss_prevention_inspect_template.tenant_pii_inspect
}
moved {
  from = google_data_loss_prevention_deidentify_template.tenant_pii_deidentify
  to   = module.platform_core.google_data_loss_prevention_deidentify_template.tenant_pii_deidentify
}
moved {
  from = google_bigquery_dataset.agent_analytics
  to   = module.platform_core.google_bigquery_dataset.agent_analytics
}
moved {
  from = google_bigquery_table.tenant_otel_spans
  to   = module.platform_core.google_bigquery_table.tenant_otel_spans
}
moved {
  from = google_bigquery_table.control_plane_tokenomics
  to   = module.platform_core.google_bigquery_table.control_plane_tokenomics
}
moved {
  from = google_bigquery_table.tenant_tokenomics_cogs_view
  to   = module.platform_core.google_bigquery_table.tenant_tokenomics_cogs_view
}
moved {
  from = google_bigquery_row_access_policy.operator_all_tenants
  to   = module.platform_core.google_bigquery_row_access_policy.operator_all_tenants
}
moved {
  from = google_kms_key_ring.tenant_cmek_ring
  to   = module.platform_core.google_kms_key_ring.tenant_cmek_ring
}
moved {
  from = google_storage_bucket.pooled_cmek_runbooks
  to   = module.platform_core.google_storage_bucket.pooled_cmek_runbooks
}
moved {
  from = google_compute_network.pooled_vpc
  to   = module.platform_core.google_compute_network.pooled_vpc
}
moved {
  from = google_alloydb_cluster.pooled_rls_cluster
  to   = module.platform_core.google_alloydb_cluster.pooled_rls_cluster
}
moved {
  from = google_firestore_database.tenant_memory_bank
  to   = module.platform_core.google_firestore_database.tenant_memory_bank
}
moved {
  from = google_redis_instance.token_bucket_bulkhead
  to   = module.platform_core.google_redis_instance.token_bucket_bulkhead
}
moved {
  from = google_kms_crypto_key.platform_global
  to   = module.platform_core.google_kms_crypto_key.platform_global
}
moved {
  from = google_kms_crypto_key_iam_member.runtime_platform_global
  to   = module.platform_core.google_kms_crypto_key_iam_member.runtime_platform_global
}
moved {
  from = google_kms_crypto_key_iam_member.curator_platform_global
  to   = module.platform_core.google_kms_crypto_key_iam_member.curator_platform_global
}
moved {
  from = google_service_account_iam_member.operator_time_boxed_impersonation
  to   = module.platform_core.google_service_account_iam_member.operator_time_boxed_impersonation
}

# --- tenant: per-tenant instances move into module.tenant["<tenant_id>"]

# tenant-finvault-alpha
moved {
  from = google_service_account.tenant["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_service_account.tenant
}
moved {
  from = google_kms_crypto_key_iam_member.tenant_key_user["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_kms_crypto_key_iam_member.tenant_key_user
}
moved {
  from = google_storage_managed_folder.tenant_runbooks["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_storage_managed_folder.tenant_runbooks
}
moved {
  from = google_storage_managed_folder_iam_member.tenant_runbooks_reader["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_storage_managed_folder_iam_member.tenant_runbooks_reader
}
moved {
  from = google_storage_bucket_iam_member.tenant_skills_reader["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_storage_bucket_iam_member.tenant_skills_reader
}
moved {
  from = google_service_account_iam_member.gateway_impersonates_tenant["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_service_account_iam_member.gateway_impersonates_tenant[0]
}
moved {
  from = google_service_account_iam_member.broker_impersonates_tenant["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_service_account_iam_member.broker_impersonates_tenant[0]
}
moved {
  from = google_bigquery_table_iam_member.tenant_spans_reader["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_bigquery_table_iam_member.tenant_spans_reader
}
moved {
  from = google_bigquery_row_access_policy.tenant["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_bigquery_row_access_policy.tenant
}
moved {
  from = google_project_iam_member.tenant_bigquery_job_user["tenant-finvault-alpha"]
  to   = module.tenant["tenant-finvault-alpha"].google_project_iam_member.tenant_bigquery_job_user
}

# tenant-retailstream-beta
moved {
  from = google_service_account.tenant["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_service_account.tenant
}
moved {
  from = google_kms_crypto_key_iam_member.tenant_key_user["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_kms_crypto_key_iam_member.tenant_key_user
}
moved {
  from = google_storage_managed_folder.tenant_runbooks["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_storage_managed_folder.tenant_runbooks
}
moved {
  from = google_storage_managed_folder_iam_member.tenant_runbooks_reader["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_storage_managed_folder_iam_member.tenant_runbooks_reader
}
moved {
  from = google_storage_bucket_iam_member.tenant_skills_reader["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_storage_bucket_iam_member.tenant_skills_reader
}
moved {
  from = google_service_account_iam_member.gateway_impersonates_tenant["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_service_account_iam_member.gateway_impersonates_tenant[0]
}
moved {
  from = google_service_account_iam_member.broker_impersonates_tenant["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_service_account_iam_member.broker_impersonates_tenant[0]
}
moved {
  from = google_bigquery_table_iam_member.tenant_spans_reader["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_bigquery_table_iam_member.tenant_spans_reader
}
moved {
  from = google_bigquery_row_access_policy.tenant["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_bigquery_row_access_policy.tenant
}
moved {
  from = google_project_iam_member.tenant_bigquery_job_user["tenant-retailstream-beta"]
  to   = module.tenant["tenant-retailstream-beta"].google_project_iam_member.tenant_bigquery_job_user
}

# tenant-finvault-alpha: previously hard-coded resources
moved {
  from = google_kms_crypto_key.finvault_alpha_cmek
  to   = module.tenant["tenant-finvault-alpha"].google_kms_crypto_key.tenant_cmek
}
moved {
  from = google_kms_crypto_key_iam_member.gcs_finvault_cmek_binding
  to   = module.tenant["tenant-finvault-alpha"].google_kms_crypto_key_iam_member.gcs_cmek_binding
}
moved {
  from = google_storage_bucket.finvault_skills_bucket
  to   = module.tenant["tenant-finvault-alpha"].google_storage_bucket.tenant_skills
}

# tenant-retailstream-beta: previously hard-coded resources
moved {
  from = google_kms_crypto_key.retailstream_beta_cmek
  to   = module.tenant["tenant-retailstream-beta"].google_kms_crypto_key.tenant_cmek
}
moved {
  from = google_kms_crypto_key_iam_member.gcs_retailstream_cmek_binding
  to   = module.tenant["tenant-retailstream-beta"].google_kms_crypto_key_iam_member.gcs_cmek_binding
}
moved {
  from = google_storage_bucket.retailstream_skills_bucket
  to   = module.tenant["tenant-retailstream-beta"].google_storage_bucket.tenant_skills
}

# Secrets: keyed by secret ID now (was a connector key)
moved {
  from = google_secret_manager_secret.tenant_3lo_vault["finvault_jira"]
  to   = module.tenant["tenant-finvault-alpha"].google_secret_manager_secret.tenant_3lo_vault["cymbal-finvault-jira-credentials"]
}
moved {
  from = google_secret_manager_secret_iam_member.tenant_secret_accessor["tenant-finvault-alpha/finvault_jira"]
  to   = module.tenant["tenant-finvault-alpha"].google_secret_manager_secret_iam_member.tenant_secret_accessor["cymbal-finvault-jira-credentials"]
}
moved {
  from = google_secret_manager_secret.tenant_3lo_vault["retailstream_servicenow"]
  to   = module.tenant["tenant-retailstream-beta"].google_secret_manager_secret.tenant_3lo_vault["cymbal-retailstream-servicenow-credentials"]
}
moved {
  from = google_secret_manager_secret_iam_member.tenant_secret_accessor["tenant-retailstream-beta/retailstream_servicenow"]
  to   = module.tenant["tenant-retailstream-beta"].google_secret_manager_secret_iam_member.tenant_secret_accessor["cymbal-retailstream-servicenow-credentials"]
}
moved {
  from = google_secret_manager_secret.tenant_3lo_vault["retailstream_entra"]
  to   = module.tenant["tenant-retailstream-beta"].google_secret_manager_secret.tenant_3lo_vault["cymbal-retailstream-entra-credentials"]
}
moved {
  from = google_secret_manager_secret_iam_member.tenant_secret_accessor["tenant-retailstream-beta/retailstream_entra"]
  to   = module.tenant["tenant-retailstream-beta"].google_secret_manager_secret_iam_member.tenant_secret_accessor["cymbal-retailstream-entra-credentials"]
}
