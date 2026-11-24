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
  description = "Platform GCP project ID hosting the agent runtime service."
  type        = string
}

variable "project_number" {
  description = "Platform GCP project number (used in deterministic Cloud Run URLs and Agent Identity principals)."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{1,20}$", var.project_number))
    error_message = "project_number must be 1-20 digits."
  }
}

variable "organization_id" {
  description = "GCP Organization ID that owns the Cloud Run Agent Identity STS pool (`agents.global.org-<org_id>.system.id.goog`)."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{1,20}$", var.organization_id))
    error_message = "organization_id must be 1-20 digits."
  }
}

variable "region" {
  description = "GCP region where the Cloud Run service is deployed."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Platform config environment loaded by the runtime (`CYMBAL_ENV`, e.g. `sandbox`)."
  type        = string
  default     = "sandbox"
}

variable "service_name" {
  description = "Cloud Run v2 service name for this agent runtime (e.g. `cymbal-agent-shared`)."
  type        = string

  validation {
    condition     = can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$", var.service_name))
    error_message = "service_name must be a valid Cloud Run service name (lowercase letters, digits, hyphens)."
  }
}

variable "agent_id" {
  description = "Catalog agent ID that this service exclusively executes (`RUNTIME_AGENT_ID`)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,63}$", var.agent_id))
    error_message = "agent_id must match ^[a-z][a-z0-9_]{0,63}$."
  }
}

variable "runtime_image" {
  description = "Container image URI for the agent runtime service (same image as the gateway, invoked with `runtime_service.main:create_app`)."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "gateway_service_account_email" {
  description = "Service account email of the gateway (`cymbal-pooled-runtime-sa@...`), the sole principal allowed to invoke this agent runtime."
  type        = string
}

variable "expected_audience" {
  description = "Optional explicit `RUNTIME_EXPECTED_AUDIENCE` override. When empty, defaults to the deterministic Cloud Run service URL (`https://<service_name>-<project_number>.<region>.run.app`)."
  type        = string
  default     = ""
}

variable "credential_broker_url" {
  description = "Credential broker service URL (`CREDENTIAL_BROKER_URL`)."
  type        = string
}

variable "broker_service_name" {
  description = "Cloud Run service name of the credential broker (for the agent principal's `roles/run.invoker` grant)."
  type        = string
  default     = "cymbal-credential-broker"
}

variable "context_signing_key_id" {
  description = "Full Cloud KMS crypto key resource ID for `ws2-context-signing` (the agent principal receives `roles/cloudkms.publicKeyViewer` only)."
  type        = string
}

variable "context_signing_key_version" {
  description = "Active KMS cryptoKeyVersion number for `ws2-context-signing`."
  type        = string
  default     = "1"

  validation {
    condition     = can(regex("^[1-9][0-9]{0,8}$", var.context_signing_key_version))
    error_message = "context_signing_key_version must be a positive integer string."
  }
}

variable "enable_live_mode" {
  description = "Whether the agent runtime calls live Google Cloud / Vertex AI APIs (`CYMBAL_LIVE_GCP=1`)."
  type        = bool
  default     = false
}

variable "require_agent_binding" {
  description = "Whether the agent runtime requires `agent_id` in verified context tokens (`CONTEXT_TOKEN_REQUIRE_AGENT_ID=1`, enabled at B5 S3.4)."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Enable Terraform deletion protection on the Cloud Run service."
  type        = bool
  default     = true
}

variable "labels" {
  description = "Common resource labels applied to the Cloud Run service."
  type        = map(string)
  default     = {}
}

variable "agent_sandbox_reasoning_engine_name" {
  description = "Parent agent runtime in Gemini resource name (`AGENT_SANDBOX_REASONING_ENGINE_NAME`) for per-session `sandboxEnvironments`."
  type        = string
  default     = ""

  validation {
    condition     = var.agent_sandbox_reasoning_engine_name == "" || can(regex("^projects/[a-z0-9-]+/locations/[a-z0-9-]+/reasoningEngines/[A-Za-z0-9_-]+$", var.agent_sandbox_reasoning_engine_name))
    error_message = "agent_sandbox_reasoning_engine_name must be empty or match 'projects/<project>/locations/<region>/reasoningEngines/<id>'."
  }
}

variable "agent_sandbox_code_template" {
  description = "Optional `SandboxEnvironmentTemplate` ID or resource name (`AGENT_SANDBOX_CODE_TEMPLATE`)."
  type        = string
  default     = ""

  validation {
    condition     = var.agent_sandbox_code_template == "" || can(regex("^([A-Za-z0-9_-]+|projects/[a-z0-9-]+/locations/[a-z0-9-]+/reasoningEngines/[A-Za-z0-9_-]+/sandboxEnvironmentTemplates/[A-Za-z0-9_-]+)$", var.agent_sandbox_code_template))
    error_message = "agent_sandbox_code_template must be empty, a template ID, or 'projects/<project>/locations/<region>/reasoningEngines/<id>/sandboxEnvironmentTemplates/<template_id>'."
  }
}

variable "agent_sandbox_shell_template" {
  description = "Optional `SandboxEnvironmentTemplate` ID or resource name (`AGENT_SANDBOX_SHELL_TEMPLATE`)."
  type        = string
  default     = ""

  validation {
    condition     = var.agent_sandbox_shell_template == "" || can(regex("^([A-Za-z0-9_-]+|projects/[a-z0-9-]+/locations/[a-z0-9-]+/reasoningEngines/[A-Za-z0-9_-]+/sandboxEnvironmentTemplates/[A-Za-z0-9_-]+)$", var.agent_sandbox_shell_template))
    error_message = "agent_sandbox_shell_template must be empty, a template ID, or 'projects/<project>/locations/<region>/reasoningEngines/<id>/sandboxEnvironmentTemplates/<template_id>'."
  }
}

variable "vpc_network_name" {
  description = "Optional VPC network/subnetwork name for Cloud Run Direct VPC Egress (`PRIVATE_RANGES_ONLY`) to Memorystore Redis and AlloyDB."
  type        = string
  default     = ""
}

variable "model_armor_template_id" {
  description = "Optional short template ID for Model Armor (`MODEL_ARMOR_TEMPLATE_ID`)."
  type        = string
  default     = ""
}

variable "dlp_inspect_template_id" {
  description = "Optional regional Cloud DLP Inspect Template resource ID (`DLP_INSPECT_TEMPLATE`)."
  type        = string
  default     = ""
}

variable "dlp_deidentify_template_id" {
  description = "Optional regional Cloud DLP De-identify Template resource ID (`DLP_DEIDENTIFY_TEMPLATE`)."
  type        = string
  default     = ""
}

variable "kms_keyring_name" {
  description = "Optional short Cloud KMS key ring name holding per-tenant CMEK keys (`KMS_KEYRING_NAME`)."
  type        = string
  default     = ""
}

variable "runbook_bucket_name" {
  description = "Optional pooled Cloud Storage runbook bucket name (`RUNBOOK_BUCKET_NAME`)."
  type        = string
  default     = ""
}

variable "analytics_dataset_id" {
  description = "Optional BigQuery telemetry dataset ID (`BIGQUERY_DATASET`)."
  type        = string
  default     = ""
}

variable "spans_table_id" {
  description = "Optional BigQuery OpenTelemetry spans table ID for table-scoped `roles/bigquery.dataEditor`."
  type        = string
  default     = ""
}

variable "firestore_database_name" {
  description = "Optional Cloud Firestore database name (`FIRESTORE_DATABASE`)."
  type        = string
  default     = ""
}

variable "redis_url" {
  description = "Optional Cloud Memorystore for Redis bulkhead connection URL (`REDIS_URL`)."
  type        = string
  default     = ""
}

variable "redis_tls_secret_id" {
  description = "Optional Secret Manager secret ID holding the Redis AUTH+TLS bundle (`roles/secretmanager.secretAccessor` granted per-secret to `local.agent_principal`)."
  type        = string
  default     = ""
}

variable "redis_tls_secret_version" {
  description = "Optional pinned Secret Manager version resource name (`REDIS_TLS_SECRET_VERSION`) for Redis AUTH+TLS."
  type        = string
  default     = ""
}

variable "alloydb_primary_ip" {
  description = "Optional private VPC IPv4 address of the AlloyDB primary instance (`DATABASE_URL` + `ALLOYDB_TENANT_IAM_AUTH=1`)."
  type        = string
  default     = ""
}

variable "enable_vpc_access" {
  description = "Attach Cloud Run Direct VPC Egress to `vpc_network_name` in live mode (static plan-time boolean)."
  type        = bool
  default     = false
}

variable "enable_platform_live_resources" {
  description = "Bind core `platform_core` resource env vars (`MODEL_ARMOR_TEMPLATE_ID`, DLP, KMS, Runbook GCS, BigQuery, Firestore) and grant BigQuery table writer access (static plan-time boolean)."
  type        = bool
  default     = false
}

variable "enable_memorystore_redis" {
  description = "Whether Memorystore for Redis bulkhead is provisioned in `platform_core` (static plan-time boolean)."
  type        = bool
  default     = false
}

variable "enable_redis_tls" {
  description = "Whether Redis AUTH+TLS Secret Manager bundle is enabled for `REDIS_TLS_SECRET_VERSION` and per-secret IAM access (static plan-time boolean)."
  type        = bool
  default     = false
}

variable "enable_alloydb_primary_auth" {
  description = "Whether AlloyDB primary IAM authentication (`DATABASE_URL` + `ALLOYDB_TENANT_IAM_AUTH=1`) is enabled (static plan-time boolean)."
  type        = bool
  default     = false
}
