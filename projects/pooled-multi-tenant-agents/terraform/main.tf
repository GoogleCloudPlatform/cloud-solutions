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

# Sandbox composition (pooled, Pattern A): one platform_core + one tenant module per tenant in
# config/tenants/<platform_environment>/. Other shapes (silo, hybrid) are in terraform/envs/.
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

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

module "platform_core" {
  source = "./modules/platform_core"

  project_id                        = var.project_id
  region                            = var.region
  environment                       = var.environment
  platform_environment              = var.platform_environment
  gateway_container_image           = var.gateway_container_image
  enable_live_mode                  = var.enable_live_mode
  model_armor_template_id           = var.model_armor_template_id
  bigquery_operator_principals      = var.bigquery_operator_principals
  enable_alloydb_cluster            = var.enable_alloydb_cluster
  enable_alloydb_primary_instance   = var.enable_alloydb_primary_instance
  alloydb_enable_public_ip          = var.alloydb_enable_public_ip
  alloydb_admin_iam_users           = var.alloydb_admin_iam_users
  enable_memorystore_redis          = var.enable_memorystore_redis
  enable_redis_auth_and_tls         = var.enable_redis_auth_and_tls
  gateway_max_instance_count        = var.gateway_max_instance_count
  enable_platform_signing_secrets   = var.enable_platform_signing_secrets
  global_memory_curators            = var.global_memory_curators
  enable_credential_broker          = var.enable_credential_broker
  runtime_keeps_token_creator       = var.runtime_keeps_token_creator
  enable_agent_runtimes             = var.enable_agent_runtimes
  organization_id                   = var.organization_id
  agent_runtime_service_map         = var.enable_agent_runtimes ? { for k, v in local.agent_runtimes : v.agent_id => v.service_name } : {}
  broker_container_image            = var.broker_container_image
  credential_broker_url             = var.credential_broker_url
  additional_broker_allowed_callers = var.additional_broker_allowed_callers
  broker_keep_runtime_caller        = var.broker_keep_runtime_caller
  agent_runtime_urls_json           = var.agent_runtime_urls_json
  bind_agent_id                     = var.bind_agent_id
  require_agent_binding             = var.require_agent_binding
  enable_build_sa                   = var.enable_build_sa
  iap_accessors                     = var.iap_accessors
  iap_time_boxed_accessors          = var.iap_time_boxed_accessors
  operator_impersonation            = var.operator_impersonation
  deletion_protection               = var.deletion_protection
  enable_edge_waf                   = var.enable_edge_waf
  token_and_session_policy          = var.token_and_session_policy
  agent_sandbox_reasoning_engine_name        = var.agent_sandbox_reasoning_engine_name
  agent_sandbox_code_template        = var.agent_sandbox_code_template
  agent_sandbox_shell_template       = var.agent_sandbox_shell_template
}

locals {
  agent_runtimes = {
    shared = {
      service_name = "cymbal-agent-shared"
      agent_id     = "cymbal_shared_diagnostic_agent"
    }
    finvault-alpha = {
      service_name = "cymbal-agent-finvault-alpha"
      agent_id     = "finvault_regulatory_escalation_agent"
    }
  }
}

module "agent_runtime" {
  source   = "./modules/agent_runtime"
  for_each = var.enable_agent_runtimes ? local.agent_runtimes : {}

  project_id                     = var.project_id
  project_number                 = module.platform_core.project_number
  organization_id                = var.organization_id
  region                         = var.region
  environment                    = var.platform_environment
  service_name                   = each.value.service_name
  agent_id                       = each.value.agent_id
  runtime_image                  = var.gateway_container_image
  gateway_service_account_email  = module.platform_core.pooled_agent_runtime_sa_email
  credential_broker_url          = var.credential_broker_url != "" ? var.credential_broker_url : module.platform_core.credential_broker_url
  broker_service_name            = module.platform_core.credential_broker_service_name
  context_signing_key_id         = module.platform_core.context_signing_key_id
  enable_live_mode               = var.enable_live_mode
  require_agent_binding          = var.require_agent_binding
  agent_sandbox_reasoning_engine_name     = var.agent_sandbox_reasoning_engine_name
  agent_sandbox_code_template     = var.agent_sandbox_code_template
  agent_sandbox_shell_template    = var.agent_sandbox_shell_template
  vpc_network_name               = module.platform_core.pooled_vpc_name
  model_armor_template_id        = module.platform_core.model_armor_template_short_id
  dlp_inspect_template_id        = module.platform_core.dlp_inspect_template_id
  dlp_deidentify_template_id     = module.platform_core.dlp_deidentify_template_id
  kms_keyring_name               = module.platform_core.tenant_key_ring_name
  runbook_bucket_name            = module.platform_core.runbook_bucket_name
  analytics_dataset_id           = module.platform_core.analytics_dataset_id
  spans_table_id                 = module.platform_core.spans_table_id
  firestore_database_name        = module.platform_core.firestore_database_name
  redis_url                      = module.platform_core.redis_bulkhead_url
  redis_tls_secret_id            = module.platform_core.redis_tls_secret_id
  redis_tls_secret_version       = module.platform_core.redis_tls_secret_version
  alloydb_primary_ip             = module.platform_core.alloydb_primary_ip_address
  enable_vpc_access              = (var.enable_memorystore_redis || (var.enable_alloydb_cluster && var.enable_alloydb_primary_instance))
  enable_platform_live_resources = true
  enable_memorystore_redis       = var.enable_memorystore_redis
  enable_redis_tls               = var.enable_memorystore_redis && var.enable_redis_auth_and_tls
  enable_alloydb_primary_auth    = var.enable_alloydb_cluster && var.enable_alloydb_primary_instance
  deletion_protection            = var.deletion_protection
  labels                         = module.platform_core.labels
  depends_on                     = [module.platform_core]
}

module "tenant" {
  source   = "./modules/tenant"
  for_each = local.tenants

  tenant_id               = each.key
  project_id              = var.project_id
  region                  = var.region
  labels                  = module.platform_core.labels
  cmek_key_name           = each.value.cmek_key
  key_ring_id             = module.platform_core.tenant_key_ring_id
  gcs_service_agent_email = module.platform_core.gcs_service_agent_email
  secret_ids              = var.enable_3p_connectors ? each.value.secret_ids : []
  skills_bucket_name      = each.value.skills_bucket
  runbook_bucket_name     = module.platform_core.runbook_bucket_name
  telemetry_project_id    = var.project_id
  analytics_dataset_id    = module.platform_core.analytics_dataset_id
  spans_table_id          = module.platform_core.spans_table_id
  row_policy_id           = each.value.row_policy_id
  bigquery_readers        = lookup(var.tenant_bigquery_readers, each.key, [])

  broker_enabled              = var.enable_credential_broker
  broker_sa_email             = module.platform_core.credential_broker_sa_email
  runtime_keeps_token_creator = var.runtime_keeps_token_creator
  runtime_sa_email            = module.platform_core.pooled_agent_runtime_sa_email
  operator_impersonation      = var.operator_impersonation
  deletion_protection         = var.deletion_protection
  enable_tenant_wif_provider  = var.enable_tenant_wif_provider
  tenant_oidc_issuer_uri      = each.value.oidc_issuer_uri
  enable_memory_bank_iam_cel  = var.enable_memory_bank_iam_cel
  alloydb_cluster_name        = module.platform_core.alloydb_cluster_name
  enable_alloydb_iam          = var.enable_alloydb_cluster && var.enable_alloydb_primary_instance

  allowed_memory_agent_ids        = lookup(var.tenant_allowed_memory_agent_ids, each.key, [])
  enable_identity_platform_tenant = var.enable_identity_platform_tenant
  depends_on                      = [module.platform_core]
}
