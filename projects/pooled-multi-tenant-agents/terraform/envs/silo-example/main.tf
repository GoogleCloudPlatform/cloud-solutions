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
# WS3 silo shape (Pattern B): one tenant gets its own project with its own platform stack
# (gateway, broker, keys, telemetry) and exactly one tenant module. Nothing is shared with the
# pooled sandbox. Example only: copy, fill in example.tfvars, and init with your own state bucket:
#
#   terraform init -backend-config="bucket=<silo-project>-tfstate" -backend-config="prefix=silo"
#   terraform plan -var-file=example.tfvars
# ============================================================================

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

  backend "gcs" {} # partial config: pass bucket/prefix with -backend-config
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
  source = "../../modules/platform_core"

  project_id               = var.project_id
  region                   = var.region
  environment              = var.environment
  platform_environment     = var.platform_environment
  gateway_container_image  = var.gateway_container_image
  broker_container_image   = var.gateway_container_image
  enable_live_mode         = true
  enable_credential_broker = true
  credential_broker_url    = "https://cymbal-credential-broker-${var.project_number}.${var.region}.run.app"
  enable_alloydb_cluster   = var.enable_alloydb_cluster
  enable_memorystore_redis = false
  iap_accessors            = var.iap_accessors
  # Optional Agent Sandbox in Gemini ("The Hands"): populate after `scripts/provision_gemini_agent_sandbox.py --live`
  agent_sandbox_reasoning_engine_name = ""
  agent_sandbox_code_template         = ""
  agent_sandbox_shell_template        = ""
  labels = {
    architecture_pattern = "pattern-b-silo"
    workstream           = "gemini-multitenancy-ws3"
    managed_by           = "terraform"
  }
}

module "tenant" {
  source = "../../modules/tenant"

  tenant_id               = var.tenant.tenant_id
  project_id              = var.project_id
  region                  = var.region
  labels                  = module.platform_core.labels
  cmek_key_name           = var.tenant.cmek_key
  key_ring_id             = module.platform_core.tenant_key_ring_id
  gcs_service_agent_email = module.platform_core.gcs_service_agent_email
  secret_ids              = var.tenant.secret_ids
  skills_bucket_name      = "${var.project_id}-skills"
  runbook_bucket_name     = module.platform_core.runbook_bucket_name
  telemetry_project_id    = var.project_id
  analytics_dataset_id    = module.platform_core.analytics_dataset_id
  spans_table_id          = module.platform_core.spans_table_id
  row_policy_id           = "rap_${replace(var.tenant.tenant_id, "-", "_")}"
  broker_enabled          = true
  broker_sa_email         = module.platform_core.credential_broker_sa_email
}
