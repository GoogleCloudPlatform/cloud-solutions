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

variable "project_id" {
  description = "Target Google Cloud Project ID for Pattern A Pooled Multi-Tenant Architecture."
  type        = string
  default     = "your-gcp-project-id"
}

variable "region" {
  description = "Primary GCP region for pooled compute, AlloyDB, Memorystore, and Model Armor."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment label (dev, staging, prod)."
  type        = string
  default     = "prod"
}

variable "gateway_container_image" {
  description = "Container image URI for the Cymbal Pooled Agent Gateway on Cloud Run."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "platform_environment" {
  description = "Platform config environment the gateway loads (config/environments/<name>.yaml). No default: a defaulted 'sandbox' in a real project would enable sandbox-only behaviour."
  type        = string
}

variable "enable_live_mode" {
  description = "Gateway calls live Google Cloud / 3P APIs (true) or runs local simulation (false)."
  type        = bool
  default     = true
}

variable "model_armor_template_id" {
  description = "Model Armor template ID created by Terraform and verified by the runtime."
  type        = string
  default     = "cymbal-pooled-inbound-pep"
}

variable "tenant_bigquery_readers" {
  description = "Optional extra principals per tenant that may read that tenant's telemetry rows."
  type        = map(list(string))
  default     = {}
}

variable "bigquery_operator_principals" {
  description = "Principals for the all-tenant operator telemetry view. Empty = no all-tenant view."
  type        = list(string)
  default     = []
}

variable "enable_alloydb_cluster" {
  description = "Whether to provision the full AlloyDB cluster (set false for fast control-plane dry runs)."
  type        = bool
  default     = true
}

variable "enable_alloydb_primary_instance" {
  description = "Whether to provision the Private Services Access peering, Zonal 2-vCPU AlloyDB primary instance (`alloydb.iam_authentication = on`), IAM DB user, and Cloud Run Direct VPC Egress."
  type        = bool
  default     = false
}

variable "alloydb_enable_public_ip" {
  description = "Give the AlloyDB primary instance a public IP address (in addition to its private VPC address). Off by default. Even when on, no `authorized_external_networks` are configured, so raw public TCP 5432 is refused and the address is reachable only through the AlloyDB Auth Proxy / language connectors (mTLS + IAM `roles/alloydb.client` + IAM database auth). It is still an internet-facing endpoint: turn it on only when an operator machine outside the VPC must run `scripts/bootstrap_alloydb_rls.py` / `scripts/deploy.sh`, and prefer running the bootstrap from inside the VPC (bastion, Cloud Build private pool, Cloud Workstations)."
  type        = bool
  default     = false
}

variable "enable_memorystore_redis" {
  description = "Whether to provision Cloud Memorystore for Redis token-bucket bulkheads."
  type        = bool
  default     = true
}

variable "enable_redis_auth_and_tls" {
  description = "Enable Memorystore Redis AUTH (`auth_enabled = true`) and server-side TLS (`SERVER_AUTHENTICATION`), storing the connection URL + server CA PEM in Secret Manager (`REDIS_TLS_SECRET_VERSION`) instead of plaintext `REDIS_URL`."
  type        = bool
  default     = false
}

variable "alloydb_admin_iam_users" {
  description = "Optional Cloud IAM database users (`user@domain` or `<sa>@<project>.iam`) granted `alloydbiamuser` + `alloydbsuperuser` on the AlloyDB cluster for `scripts/bootstrap_alloydb_rls.py`."
  type        = list(string)
  default     = []
}

variable "gateway_max_instance_count" {
  description = "Maximum Cloud Run instances for `cymbal-pooled-gateway` (values > 1 require `enable_live_mode = true` and `enable_memorystore_redis = true` for shared DPoP replay and rate-limit bulkheads)."
  type        = number
  default     = 1

  validation {
    condition     = var.gateway_max_instance_count >= 1 && var.gateway_max_instance_count <= 100 && floor(var.gateway_max_instance_count) == var.gateway_max_instance_count
    error_message = "gateway_max_instance_count must be an integer between 1 and 100."
  }
}

variable "enable_platform_signing_secrets" {
  description = "Create Secret Manager secret shells for `cymbal-gateway-signing-key` and `cymbal-oauth-3lo-csrf-key` with per-secret `secretAccessor` for `cymbal-pooled-runtime-sa` (values are loaded out-of-band)."
  type        = bool
  default     = false
}

variable "enable_3p_connectors" {
  description = "Phase 1 (false = 100% Google-Only 1-variable deploy) vs Phase 2 (true = also provision Secret Manager vaults for Jira, ServiceNow & Azure Entra ID)."
  type        = bool
  default     = false
}

variable "global_memory_curators" {
  description = "IAM members allowed to seal GLOBAL memory with the platform key (e.g. an operator service account granted through Privileged Access Manager). Empty means nobody can write GLOBAL."
  type        = list(string)
  default     = []
}

# --- Credential broker (ADR-0014 B4) ---------------------------------------------------------------

variable "enable_credential_broker" {
  description = "Create the credential broker SA, its TokenCreator grants on tenant SAs and its Cloud Run service (ADR-0014 B4, staged rollout step 1-2)."
  type        = bool
  default     = false
}

variable "runtime_keeps_token_creator" {
  description = "Keep roles/iam.serviceAccountTokenCreator for the runtime SA on tenant SAs. Set false only at B4 step 4, after the runtime mints through the broker."
  type        = bool
  default     = true
}

variable "broker_container_image" {
  description = "Image for the credential broker service (the gateway image; separate entrypoint). The default placeholder (hello) has no broker_service, so the service crash-loops until this is set to the real image."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "credential_broker_url" {
  description = "Broker service URL given to the runtime (CREDENTIAL_BROKER_URL). Empty = runtime mints directly (pre-B4)."
  type        = string
  default     = ""
}

# --- Per-agent Cloud Run runtime services & dedicated build SA (ADR-0014 B5 / ADR-0016) ------------

variable "enable_agent_runtimes" {
  description = "Manage the per-agent Cloud Run runtime services (`cymbal-agent-shared`, `cymbal-agent-finvault-alpha`) and their least-privilege Agent Identity IAM bindings (ADR-0014 B5 / ADR-0016)."
  type        = bool
  default     = false
}

variable "organization_id" {
  description = "GCP Organization ID that owns the Cloud Run Agent Identity STS pool (`agents.global.org-<org_id>.system.id.goog`)."
  type        = string
  default     = "000000000000"

  validation {
    condition     = can(regex("^[0-9]{1,20}$", var.organization_id))
    error_message = "organization_id must be 1-20 digits."
  }
}

variable "require_agent_binding" {
  description = "Enable `BROKER_REQUIRE_AGENT_BINDING=1` on the broker and `CONTEXT_TOKEN_REQUIRE_AGENT_ID=1` on the gateway, broker, and agent runtime services (ADR-0016 B5 S3.4)."
  type        = bool
  default     = false
}

variable "bind_agent_id" {
  description = "Set `CONTEXT_TOKEN_BIND_AGENT_ID=1` on the gateway so signed context tokens carry `agent_id` (ADR-0016 B5 S3.4a)."
  type        = bool
  default     = false
}

variable "agent_runtime_urls_json" {
  description = "JSON map of `agent_id -> Cloud Run URL` (`AGENT_RUNTIME_URLS` on the gateway, ADR-0014 B5 S3.3). Empty = gateway runs turns in-process."
  type        = string
  default     = ""
}

variable "additional_broker_allowed_callers" {
  description = "Additional caller principals (e.g. Cloud Run Agent Identity `principal://...` URIs) allowed on the credential broker alongside or replacing the pooled runtime SA (ADR-0014 B5 / ADR-0016)."
  type        = list(string)
  default     = []
}

variable "broker_keep_runtime_caller" {
  description = "Keep `cymbal-pooled-runtime-sa` in `BROKER_ALLOWED_CALLERS` and `roles/run.invoker` on the broker. Set false at B5 S3.6 after all turns run on the dedicated agent runtime services."
  type        = bool
  default     = true
}

variable "enable_build_sa" {
  description = "Create the dedicated, least-privilege Cloud Build service account (`cymbal-build-sa`, drift finding S4)."
  type        = bool
  default     = false
}

# --- Access grants that must expire (no standing human access) -------------------------------------

variable "iap_accessors" {
  description = "Standing IAP accessors (roles/iap.httpsResourceAccessor) on the gateway: the project's own operators only. Keep this list minimal."
  type        = list(string)
  default     = []
}

variable "iap_time_boxed_accessors" {
  description = "Reviewers with IAP access that expires: members get roles/iap.httpsResourceAccessor with `request.time < expires`. Set in an untracked *.auto.tfvars, never in the repo."
  type = object({
    members = list(string)
    expires = string # RFC 3339, e.g. 2026-11-20T23:59:59Z
    title   = string
  })
  default = { members = [], expires = "", title = "" }
  validation {
    condition     = length(var.iap_time_boxed_accessors.members) == 0 || can(regex("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$", var.iap_time_boxed_accessors.expires))
    error_message = "iap_time_boxed_accessors.expires must be an RFC 3339 UTC timestamp when members are listed."
  }
}

variable "operator_impersonation" {
  description = "Operators allowed to impersonate the runtime, broker and tenant SAs (live tests), ALWAYS with an expiry: roles/iam.serviceAccountTokenCreator with `request.time < expires`. Empty = none."
  type = object({
    members = list(string)
    expires = string
  })
  default = { members = [], expires = "" }
  validation {
    condition     = length(var.operator_impersonation.members) == 0 || can(regex("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$", var.operator_impersonation.expires))
    error_message = "operator_impersonation.expires must be an RFC 3339 UTC timestamp when members are listed."
  }
}

variable "deletion_protection" {
  description = "Protect stateful/serving resources from Terraform deletion: deletion_protection on the Cloud Run services and BigQuery tables, and no force_destroy on the buckets (Terraform-side guards; nothing changes in the cloud). Set false only to tear down a throwaway environment."
  type        = bool
  default     = true
}

variable "enable_edge_waf" {
  description = "Create the Cloud Armor edge policy. It only takes effect behind an external HTTPS load balancer, which the sandbox does not use (Cloud Run with built-in IAP)."
  type        = bool
  default     = false
}

variable "enable_tenant_wif_provider" {
  description = "Provision per-tenant Google Cloud Workload Identity Pool & OIDC Provider mapping `google.subject`, `attribute.tenant_id`, and `attribute.user_role` with an issuer `attribute_condition`."
  type        = bool
  default     = false
}

variable "tenant_wif_issuer_overrides" {
  description = "Optional per-tenant override map (`tenant_id -> https://...`) for `google_iam_workload_identity_pool_provider` OIDC `issuer_uri` when synthetic sandbox YAML files use offline placeholder issuer IDs."
  type        = map(string)
  default     = {}
}

variable "enable_memory_bank_iam_cel" {
  description = "Grant each per-tenant service account `roles/aiplatform.memoryUser` constrained by an IAM CEL condition on `aiplatform.googleapis.com/memoryScope['tenant_id']`."
  type        = bool
  default     = true
}

# --- Configurable token expiry & autonomous session call ceilings ----------------------------------

variable "token_and_session_policy" {
  description = "Enterprise-tunable token lifetimes and autonomous agent call ceilings per gateway token. Defaults reflect the Balanced B2B SaaS profile: clients silently refresh 10-minute DPoP tokens against still-valid IdP tokens without user re-login while bounding runaway loops and IAM blast radius."
  type = object({
    gateway_token_ttl_seconds             = optional(number, 600)
    dpop_proof_max_age_seconds            = optional(number, 120)
    tenant_sa_token_ttl_seconds           = optional(number, 300)
    tenant_sa_refresh_margin_seconds      = optional(number, 60)
    idp_broker_max_token_lifetime_seconds = optional(number, 3600)
    idp_direct_max_token_lifetime_seconds = optional(number, 5400)
    standard_max_turns_per_session        = optional(number, 5)
    enterprise_max_turns_per_session      = optional(number, 12)
  })
  default = {}

  validation {
    condition = (
      var.token_and_session_policy.gateway_token_ttl_seconds >= 60 &&
      var.token_and_session_policy.gateway_token_ttl_seconds <= 3600 &&
      floor(var.token_and_session_policy.gateway_token_ttl_seconds) == var.token_and_session_policy.gateway_token_ttl_seconds
    )
    error_message = "token_and_session_policy.gateway_token_ttl_seconds must be an integer between 60 and 3600 seconds."
  }

  validation {
    condition = (
      var.token_and_session_policy.dpop_proof_max_age_seconds >= 30 &&
      var.token_and_session_policy.dpop_proof_max_age_seconds <= 300 &&
      var.token_and_session_policy.dpop_proof_max_age_seconds <= var.token_and_session_policy.gateway_token_ttl_seconds &&
      floor(var.token_and_session_policy.dpop_proof_max_age_seconds) == var.token_and_session_policy.dpop_proof_max_age_seconds
    )
    error_message = "token_and_session_policy.dpop_proof_max_age_seconds must be an integer between 30 and 300 seconds and <= gateway_token_ttl_seconds."
  }

  validation {
    condition = (
      var.token_and_session_policy.tenant_sa_token_ttl_seconds >= 60 &&
      var.token_and_session_policy.tenant_sa_token_ttl_seconds <= 300 &&
      var.token_and_session_policy.tenant_sa_refresh_margin_seconds >= 15 &&
      var.token_and_session_policy.tenant_sa_refresh_margin_seconds <= 270 &&
      (var.token_and_session_policy.tenant_sa_token_ttl_seconds - var.token_and_session_policy.tenant_sa_refresh_margin_seconds) >= 30 &&
      floor(var.token_and_session_policy.tenant_sa_token_ttl_seconds) == var.token_and_session_policy.tenant_sa_token_ttl_seconds &&
      floor(var.token_and_session_policy.tenant_sa_refresh_margin_seconds) == var.token_and_session_policy.tenant_sa_refresh_margin_seconds
    )
    error_message = "token_and_session_policy.tenant_sa_token_ttl_seconds (60-300s; may only lower the broker's 300s ceiling) must exceed tenant_sa_refresh_margin_seconds (15-270s) by at least 30 seconds."
  }

  validation {
    condition = (
      var.token_and_session_policy.idp_broker_max_token_lifetime_seconds >= 300 &&
      var.token_and_session_policy.idp_broker_max_token_lifetime_seconds <= 28800 &&
      var.token_and_session_policy.idp_direct_max_token_lifetime_seconds >= 300 &&
      var.token_and_session_policy.idp_direct_max_token_lifetime_seconds <= 28800 &&
      var.token_and_session_policy.gateway_token_ttl_seconds <= min(
        var.token_and_session_policy.idp_broker_max_token_lifetime_seconds,
        var.token_and_session_policy.idp_direct_max_token_lifetime_seconds,
      ) &&
      floor(var.token_and_session_policy.idp_broker_max_token_lifetime_seconds) == var.token_and_session_policy.idp_broker_max_token_lifetime_seconds &&
      floor(var.token_and_session_policy.idp_direct_max_token_lifetime_seconds) == var.token_and_session_policy.idp_direct_max_token_lifetime_seconds
    )
    error_message = "IdP max token lifetimes must be integers between 300 and 28800 seconds and >= gateway_token_ttl_seconds."
  }

  validation {
    condition = (
      var.token_and_session_policy.standard_max_turns_per_session >= 1 &&
      var.token_and_session_policy.standard_max_turns_per_session <= 500 &&
      var.token_and_session_policy.enterprise_max_turns_per_session >= 1 &&
      var.token_and_session_policy.enterprise_max_turns_per_session <= 500 &&
      floor(var.token_and_session_policy.standard_max_turns_per_session) == var.token_and_session_policy.standard_max_turns_per_session &&
      floor(var.token_and_session_policy.enterprise_max_turns_per_session) == var.token_and_session_policy.enterprise_max_turns_per_session
    )
    error_message = "standard_max_turns_per_session and enterprise_max_turns_per_session must be integers between 1 and 500."
  }
}

# --- Agent Sandbox in Gemini (ADR-0012 / PR-S2) ---------------------------------------------------------

variable "agent_sandbox_reasoning_engine_name" {
  description = "Parent agent runtime in Gemini resource name (`projects/<project>/locations/<region>/reasoningEngines/<id>`) hosting per-session `sandboxEnvironments`. Empty = omitted on Cloud Run until provisioned via `scripts/provision_gemini_agent_sandbox.py`."
  type        = string
  default     = ""

  validation {
    condition     = var.agent_sandbox_reasoning_engine_name == "" || can(regex("^projects/[a-z0-9-]+/locations/[a-z0-9-]+/reasoningEngines/[A-Za-z0-9_-]+$", var.agent_sandbox_reasoning_engine_name))
    error_message = "agent_sandbox_reasoning_engine_name must be empty or match 'projects/<project>/locations/<region>/reasoningEngines/<id>'."
  }
}

variable "agent_sandbox_code_template" {
  description = "Optional `SandboxEnvironmentTemplate` ID or resource name for Python/JavaScript sandboxes (`AGENT_SANDBOX_CODE_TEMPLATE`)."
  type        = string
  default     = ""

  validation {
    condition     = var.agent_sandbox_code_template == "" || can(regex("^([A-Za-z0-9_-]+|projects/[a-z0-9-]+/locations/[a-z0-9-]+/reasoningEngines/[A-Za-z0-9_-]+/sandboxEnvironmentTemplates/[A-Za-z0-9_-]+)$", var.agent_sandbox_code_template))
    error_message = "agent_sandbox_code_template must be empty, a template ID, or 'projects/<project>/locations/<region>/reasoningEngines/<id>/sandboxEnvironmentTemplates/<template_id>'."
  }
}

variable "agent_sandbox_shell_template" {
  description = "Optional `SandboxEnvironmentTemplate` ID or resource name for non-root Bash diagnostic sandboxes (`AGENT_SANDBOX_SHELL_TEMPLATE`)."
  type        = string
  default     = ""

  validation {
    condition     = var.agent_sandbox_shell_template == "" || can(regex("^([A-Za-z0-9_-]+|projects/[a-z0-9-]+/locations/[a-z0-9-]+/reasoningEngines/[A-Za-z0-9_-]+/sandboxEnvironmentTemplates/[A-Za-z0-9_-]+)$", var.agent_sandbox_shell_template))
    error_message = "agent_sandbox_shell_template must be empty, a template ID, or 'projects/<project>/locations/<region>/reasoningEngines/<id>/sandboxEnvironmentTemplates/<template_id>'."
  }
}
