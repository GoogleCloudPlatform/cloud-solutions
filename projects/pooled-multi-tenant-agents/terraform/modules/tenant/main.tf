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
# One tenant's blast-radius boundary (ADR-0010). Instantiate once per tenant (for_each over the
# tenant config). The tenant service account gets access to ONLY this tenant's:
#   - Cloud KMS CMEK key            (roles/cloudkms.cryptoKeyEncrypterDecrypter on the key)
#   - Secret Manager 3LO secrets    (roles/secretmanager.secretAccessor on each secret)
#   - Runbook managed folder        (roles/storage.objectViewer on "<tenant_id>/")
#   - Skills bucket                 (roles/storage.objectViewer on the bucket)
#   - Telemetry rows                (BigQuery row access policy on its tenant_id)
# Only the credential broker (and the runtime until ADR-0014 B4 step 4) may mint its tokens.
#
# The account ID formula must match agents/tenant_credentials.py:
#   tenant_service_account_id(t) = "ct-" + sha256(t)[:24]
# ============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.50"
    }
  }
}

locals {
  tenant_labels = merge(var.labels, { tenant_id = var.tenant_id })
}

resource "google_service_account" "tenant" {
  project      = var.project_id
  account_id   = "ct-${substr(sha256(var.tenant_id), 0, 24)}"
  display_name = "Cymbal tenant-scoped runtime identity (${var.tenant_id})"
  description  = "Can use only ${var.tenant_id}'s CMEK key, secrets and runbook folder (ADR-0010)."
}

# --- CMEK ------------------------------------------------------------------------------------------

# Destroying a KMS key makes its data unrecoverable: never destroyed by Terraform.
resource "google_kms_crypto_key" "tenant_cmek" {
  name            = var.cmek_key_name
  key_ring        = var.key_ring_id
  rotation_period = "7776000s" # 90 days
  labels          = local.tenant_labels

  lifecycle {
    prevent_destroy = true
  }
}

# The Cloud Storage service agent encrypts objects in the tenant's skills bucket (default key).
resource "google_kms_crypto_key_iam_member" "gcs_cmek_binding" {
  crypto_key_id = google_kms_crypto_key.tenant_cmek.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${var.gcs_service_agent_email}"
}

resource "google_kms_crypto_key_iam_member" "tenant_key_user" {
  crypto_key_id = google_kms_crypto_key.tenant_cmek.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.tenant.email}"
}

# --- Secret Manager (3LO vault shells; values are never in Terraform) ------------------------------

resource "google_secret_manager_secret" "tenant_3lo_vault" {
  for_each  = toset(var.secret_ids)
  project   = var.project_id
  secret_id = each.value
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "tenant_secret_accessor" {
  for_each  = toset(var.secret_ids)
  project   = var.project_id
  secret_id = google_secret_manager_secret.tenant_3lo_vault[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.tenant.email}"
}

# --- Cloud Storage ---------------------------------------------------------------------------------

resource "google_storage_managed_folder" "tenant_runbooks" {
  bucket = var.runbook_bucket_name
  name   = "${var.tenant_id}/"
}

resource "google_storage_managed_folder_iam_member" "tenant_runbooks_reader" {
  bucket         = google_storage_managed_folder.tenant_runbooks.bucket
  managed_folder = google_storage_managed_folder.tenant_runbooks.name
  role           = "roles/storage.objectViewer"
  member         = "serviceAccount:${google_service_account.tenant.email}"
}

resource "google_storage_bucket" "tenant_skills" {
  project                     = var.project_id
  name                        = var.skills_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = !var.deletion_protection
  labels                      = local.tenant_labels

  encryption {
    default_kms_key_name = google_kms_crypto_key.tenant_cmek.id
  }

  depends_on = [google_kms_crypto_key_iam_member.gcs_cmek_binding]
}

resource "google_storage_bucket_iam_member" "tenant_skills_reader" {
  bucket = google_storage_bucket.tenant_skills.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.tenant.email}"
}

# --- Who may mint this tenant's tokens ------------------------------------------------------------

# Removed at ADR-0014 B4 step 4 (runtime_keeps_token_creator = false): the broker SA then holds
# TokenCreator on tenant SAs instead.
resource "google_service_account_iam_member" "gateway_impersonates_tenant" {
  count              = var.runtime_keeps_token_creator ? 1 : 0
  service_account_id = google_service_account.tenant.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${var.runtime_sa_email}"
}

resource "google_service_account_iam_member" "broker_impersonates_tenant" {
  count              = var.broker_enabled ? 1 : 0
  service_account_id = google_service_account.tenant.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${var.broker_sa_email}"
}

# Time-boxed operator impersonation (live tests), never standing.
resource "google_service_account_iam_member" "operator_time_boxed_impersonation" {
  for_each           = toset(var.operator_impersonation.members)
  service_account_id = google_service_account.tenant.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = each.value
  condition {
    title      = "operator-impersonation-until-${var.operator_impersonation.expires}"
    expression = "request.time < timestamp(\"${var.operator_impersonation.expires}\")"
  }
}

# --- Telemetry -------------------------------------------------------------------------------------

# The tenant identity may read the shared spans table; its row access policy then restricts it to
# its own rows. jobUser only allows running query jobs (billing), not reading data.
resource "google_bigquery_table_iam_member" "tenant_spans_reader" {
  project    = var.telemetry_project_id
  dataset_id = var.analytics_dataset_id
  table_id   = var.spans_table_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.tenant.email}"
}

# BigQuery row-level security: readable only by this tenant's service account (+ optional
# tenant-side readers). Owned by Terraform; the runtime only verifies
# (LiveBigQueryOTelSink.verify_row_access_policies) and never issues DDL.
resource "google_bigquery_row_access_policy" "tenant" {
  project          = var.telemetry_project_id
  dataset_id       = var.analytics_dataset_id
  table_id         = var.spans_table_id
  policy_id        = var.row_policy_id
  filter_predicate = "tenant_id = '${var.tenant_id}'"
  grantees = concat(
    ["serviceAccount:${google_service_account.tenant.email}"],
    var.bigquery_readers,
  )
}

resource "google_project_iam_member" "tenant_bigquery_job_user" {
  project = var.telemetry_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.tenant.email}"
}

# --- Issuer-Bound Workload Identity Federation (WIF) Pool & Corporate OIDC IdP Provider -----------

resource "google_iam_workload_identity_pool" "tenant_idp_pool" {
  count                     = var.enable_tenant_wif_provider ? 1 : 0
  project                   = var.project_id
  workload_identity_pool_id = "wif-${substr(sha256(var.tenant_id), 0, 20)}"
  display_name              = substr("WIF ${var.tenant_id}", 0, 32)
  description               = "Issuer-bound Workload Identity Federation pool for ${var.tenant_id}."
}

resource "google_iam_workload_identity_pool_provider" "tenant_oidc_provider" {
  count                              = var.enable_tenant_wif_provider ? 1 : 0
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.tenant_idp_pool[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "oidc-${substr(sha256(var.tenant_id), 0, 19)}"
  display_name                       = substr("OIDC ${var.tenant_id}", 0, 32)

  attribute_mapping = {
    "google.subject"      = "assertion.sub"
    "attribute.tenant_id" = "'${var.tenant_id}'"
    "attribute.user_role" = "assertion.groups"
  }

  attribute_condition = "assertion.iss == '${var.tenant_oidc_issuer_uri}'"

  oidc {
    issuer_uri = var.tenant_oidc_issuer_uri
  }
}

# --- Memory Bank in Gemini Scope-Locked IAM Condition (Blog Section 4 / Figure 6) ------------------

resource "google_project_iam_member" "tenant_memory_bank_user" {
  count   = var.enable_memory_bank_iam_cel ? 1 : 0
  project = var.project_id
  role    = "roles/aiplatform.memoryUser"
  member  = "serviceAccount:${google_service_account.tenant.email}"

  # The condition text is a live IAM attribute: rewording it replaces the binding on every
  # deployed tenant, so keep title and description byte-stable.
  condition {
    title       = "memory-bank-tenant-scope-${var.tenant_id}"
    description = "Restricts Memory Bank in Gemini reads and writes to ${var.tenant_id} memoryScope."
    expression = (
      length(var.allowed_memory_agent_ids) == 0
      ? "api.getAttribute('aiplatform.googleapis.com/memoryScope', {})['tenant_id'] == '${var.tenant_id}'"
      : "api.getAttribute('aiplatform.googleapis.com/memoryScope', {})['tenant_id'] == '${var.tenant_id}' && api.getAttribute('aiplatform.googleapis.com/memoryScope', {})['agent_id'] in [${join(", ", [for aid in var.allowed_memory_agent_ids : "'${aid}'"])}]"
    )
  }
}

# --- Optional Google Cloud Identity Platform Multi-Tenant Brokered SSO (Hop 0) ---------------------

resource "google_identity_platform_tenant" "tenant" {
  count                    = var.enable_identity_platform_tenant ? 1 : 0
  project                  = var.project_id
  display_name             = var.tenant_id
  allow_password_signup    = false
  enable_email_link_signin = false
}

resource "google_identity_platform_tenant_oauth_idp_config" "corporate_sso" {
  count         = var.enable_identity_platform_tenant && var.tenant_oidc_issuer_uri != "" && var.identity_platform_oidc_client_id != "" ? 1 : 0
  project       = var.project_id
  tenant        = google_identity_platform_tenant.tenant[0].name
  name          = "oidc.${var.tenant_id}"
  display_name  = "${var.tenant_id} Corporate SSO"
  enabled       = true
  issuer        = var.tenant_oidc_issuer_uri
  client_id     = var.identity_platform_oidc_client_id
  client_secret = var.identity_platform_oidc_client_secret
}

# --- Per-Tenant Zero-Password AlloyDB IAM Database Identity ----------------------------------------

resource "google_project_iam_member" "tenant_alloydb_client" {
  count   = var.enable_alloydb_iam ? 1 : 0
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.tenant.email}"
}

resource "google_project_iam_member" "tenant_alloydb_db_user" {
  count   = var.enable_alloydb_iam ? 1 : 0
  project = var.project_id
  role    = "roles/alloydb.databaseUser"
  member  = "serviceAccount:${google_service_account.tenant.email}"
}

resource "google_alloydb_user" "tenant_iam_db_user" {
  count          = var.enable_alloydb_iam ? 1 : 0
  cluster        = var.alloydb_cluster_name
  user_id        = trimsuffix(google_service_account.tenant.email, ".gserviceaccount.com")
  user_type      = "ALLOYDB_IAM_USER"
  database_roles = ["alloydbiamuser"]

  lifecycle {
    # PostgreSQL RLS bootstrap grants the non-superuser `cymbal_mcp_app` role via SQL DDL.
    ignore_changes = [database_roles]
  }
}
