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

variable "tenant_id" {
  description = "Tenant ID (e.g. tenant-finvault-alpha). Also the ct-* account seed and row filter."
  type        = string
  # Same rule as agents/platform_config.py (_TENANT_ID_RE). The ID is interpolated into the row
  # access policy's SQL filter, so nothing outside [a-z0-9-] may reach it.
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,62}$", var.tenant_id))
    error_message = "tenant_id must match ^[a-z][a-z0-9-]{2,62}$."
  }
}

variable "project_id" {
  description = "Project that holds the tenant's identity, secrets and skills bucket (the platform project when pooled, the tenant's own project when siloed)."
  type        = string
}

variable "region" {
  description = "Region for the tenant's skills bucket."
  type        = string
}

variable "labels" {
  description = "Base labels (the module adds tenant_id where resources are tenant-scoped)."
  type        = map(string)
  default     = {}
}

variable "cmek_key_name" {
  description = "Name of the tenant's CMEK key (config/tenants/<env>/<tenant>.yaml cmek_key)."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9_-]{0,62}$", var.cmek_key_name))
    error_message = "cmek_key_name must match ^[a-z][a-z0-9_-]{0,62}$."
  }
}

variable "key_ring_id" {
  description = "Key ring that holds the tenant's CMEK key."
  type        = string
}

variable "gcs_service_agent_email" {
  description = "Cloud Storage service agent of the project that holds the skills bucket."
  type        = string
}

variable "secret_ids" {
  description = "Secret Manager secret IDs only this tenant's SA may read. Empty = no 3LO connectors."
  type        = list(string)
  default     = []
  validation {
    condition     = alltrue([for s in var.secret_ids : can(regex("^[a-z][a-z0-9_-]{0,62}$", s))])
    error_message = "Each secret ID must match ^[a-z][a-z0-9_-]{0,62}$."
  }
}

variable "skills_bucket_name" {
  description = "Tenant skills bucket (encrypted with the tenant CMEK by default)."
  type        = string
}

variable "runbook_bucket_name" {
  description = "Pooled runbook bucket; the tenant gets the managed folder <tenant_id>/."
  type        = string
}

variable "telemetry_project_id" {
  description = "Project that holds the telemetry dataset (the platform project)."
  type        = string
}

variable "analytics_dataset_id" {
  description = "Telemetry dataset ID."
  type        = string
}

variable "spans_table_id" {
  description = "Telemetry spans table ID."
  type        = string
}

variable "row_policy_id" {
  description = "BigQuery row access policy ID for this tenant."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9_-]{0,62}$", var.row_policy_id))
    error_message = "row_policy_id must match ^[a-z][a-z0-9_-]{0,62}$."
  }
}

variable "bigquery_readers" {
  description = "Extra principals that may read this tenant's telemetry rows."
  type        = list(string)
  default     = []
}

variable "broker_enabled" {
  description = "Grant the credential broker TokenCreator on the tenant SA (ADR-0014 B4)."
  type        = bool
}

variable "broker_sa_email" {
  description = "Credential broker service account email (used when broker_enabled)."
  type        = string
  default     = ""
}

variable "runtime_keeps_token_creator" {
  description = "Keep TokenCreator for the runtime SA on the tenant SA (false after ADR-0014 B4 step 4)."
  type        = bool
  default     = false
}

variable "runtime_sa_email" {
  description = "Runtime service account email (used when runtime_keeps_token_creator)."
  type        = string
  default     = ""
}

variable "operator_impersonation" {
  description = "Operators allowed to impersonate the tenant SA, ALWAYS with an expiry (RFC 3339 UTC)."
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
  description = "When true, the skills bucket is not force-destroyed (Terraform-side guard)."
  type        = bool
  default     = true
}

variable "enable_tenant_wif_provider" {
  description = "Provision an issuer-bound Workload Identity Federation (WIF) pool and OIDC provider for this tenant's corporate IdP."
  type        = bool
  default     = false
}

variable "tenant_oidc_issuer_uri" {
  description = "Corporate OIDC IdP issuer URI locked to this tenant's WIF provider via attribute_condition."
  type        = string
  default     = "https://finvault.okta.com/oauth2/default"
  validation {
    condition     = can(regex("^https://[a-zA-Z0-9.-]+(/[a-zA-Z0-9._/-]*)?$", var.tenant_oidc_issuer_uri))
    error_message = "tenant_oidc_issuer_uri must be a valid https:// issuer URI."
  }
}

variable "enable_memory_bank_iam_cel" {
  description = "Bind roles/aiplatform.memoryUser to the tenant SA with a CEL condition locking aiplatform.googleapis.com/memoryScope['tenant_id'] (and optional ['agent_id']) to var.tenant_id."
  type        = bool
  default     = true
}

variable "allowed_memory_agent_ids" {
  description = "Optional catalog agent IDs locked into the Memory Bank IAM CEL condition (`aiplatform.googleapis.com/memoryScope['agent_id'] in [...]`). Empty keeps tenant_id-only CEL compatibility."
  type        = list(string)
  default     = []
  validation {
    condition     = alltrue([for aid in var.allowed_memory_agent_ids : can(regex("^[a-z][a-z0-9_-]{1,62}$", aid))])
    error_message = "Each entry in allowed_memory_agent_ids must match ^[a-z][a-z0-9_-]{1,62}$."
  }
}

variable "enable_identity_platform_tenant" {
  description = "Provision a Google Cloud Identity Platform tenant (`google_identity_platform_tenant`) and optional OIDC corporate SSO provider for Hop 0 brokered login."
  type        = bool
  default     = false
}

variable "identity_platform_oidc_client_id" {
  description = "Optional corporate OIDC client ID registered on this Identity Platform tenant when enable_identity_platform_tenant = true."
  type        = string
  default     = ""
}

variable "identity_platform_oidc_client_secret" {
  description = "Optional corporate OIDC client secret registered on this Identity Platform tenant when enable_identity_platform_tenant = true."
  type        = string
  default     = ""
  sensitive   = true
}

variable "alloydb_cluster_name" {
  description = "Optional AlloyDB cluster resource name (`projects/.../locations/.../clusters/...`). When non-empty alongside `enable_alloydb_iam = true`, registers this tenant's `ct-*` SA as an `ALLOYDB_IAM_USER` and grants AlloyDB IAM connection roles."
  type        = string
  default     = ""
}

variable "enable_alloydb_iam" {
  description = "Provision per-tenant AlloyDB IAM database identity and connection roles (kept separate from computed `alloydb_cluster_name` so `count` is known at plan time)."
  type        = bool
  default     = false
}
