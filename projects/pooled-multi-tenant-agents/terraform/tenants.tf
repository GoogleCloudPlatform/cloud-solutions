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

# Tenant config comes from config/tenants/<platform_environment>/*.yaml (the same files the
# gateway loads), so a new tenant needs no HCL edit: add its YAML file and run a plan.
locals {
  tenant_config_dir = "${path.module}/../config/tenants/${var.platform_environment}"
  tenant_files = {
    for f in fileset(local.tenant_config_dir, "*.yaml") :
    f = > yamldecode(file("${local.tenant_config_dir}/${f}"))
  }
  # Each file must be named <tenant_id>.yaml (as the gateway expects); the precondition on
  # output.tenant_service_accounts fails the plan otherwise.
  tenant_file_mismatches = [
    for f, cfg in local.tenant_files : f if "${try(cfg.tenant_id, "")}.yaml" != f
  ]
  tenant_configs = {
    for f, cfg in local.tenant_files : cfg.tenant_id => cfg
  }

  # Skills buckets created before the module layout keep their names; new tenants get
  # <project>-skills-<tenant_id>.
  legacy_skills_buckets = {
    "tenant-finvault-alpha"    = "cymbal-skills-finvault-${var.project_id}"
    "tenant-retailstream-beta" = "cymbal-skills-retail-${var.project_id}"
  }

  tenants = {
    for tenant_id, cfg in local.tenant_configs : tenant_id => {
      cmek_key = cfg.cmek_key
      # Same default as agents/platform_config.py (TenantConfig.row_policy_id).
      row_policy_id = try(cfg.bigquery_row_policy_id, null) != null ? cfg.bigquery_row_policy_id : "rap_${replace(tenant_id, "-", "_")}"
      secret_ids    = try(cfg.secret_ids, [])
      skills_bucket = lookup(local.legacy_skills_buckets, tenant_id, "${var.project_id}-skills-${tenant_id}")
      # Federated OIDC issuer URI for the tenant's Workload Identity Pool Provider.
      oidc_issuer_uri = lookup(
        var.tenant_wif_issuer_overrides,
        tenant_id,
        try(cfg.identity.issuer, "https://finvault.okta.com/oauth2/default"),
      )
    }
  }
}
