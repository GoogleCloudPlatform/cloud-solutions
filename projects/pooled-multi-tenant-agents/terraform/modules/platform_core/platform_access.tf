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
# Platform key for GLOBAL memory and time-boxed operator access to the platform identities
# (per-tenant equivalents live in modules/tenant).
# ============================================================================

# Platform key for GLOBAL (non-tenant) memory (ADR-0011). Serving may only decrypt with it, curators
# may only encrypt, and tenant service accounts are never bound to it.
# Created in the sandbox with gcloud on 2026-10-27 and adopted into Terraform on 2026-11-06.
resource "google_kms_crypto_key" "platform_global" {
  name            = "cymbal-platform-global"
  key_ring        = google_kms_key_ring.tenant_cmek_ring.id
  rotation_period = "7776000s" # 90 days
  labels          = merge(local.common_labels, { purpose = "global-memory", data = "no-tenant-data" })

  lifecycle {
    prevent_destroy = true
  }
}

# Serving reads GLOBAL memory but must not be able to forge it: decrypt only.
resource "google_kms_crypto_key_iam_member" "runtime_platform_global" {
  crypto_key_id = google_kms_crypto_key.platform_global.id
  role          = "roles/cloudkms.cryptoKeyDecrypter"
  member        = "serviceAccount:${google_service_account.pooled_agent_runtime.email}"
}

# Only curators (operator SA or break-glass humans) can seal new GLOBAL entries.
resource "google_kms_crypto_key_iam_member" "curator_platform_global" {
  for_each      = toset(var.global_memory_curators)
  crypto_key_id = google_kms_crypto_key.platform_global.id
  role          = "roles/cloudkms.cryptoKeyEncrypter"
  member        = each.value
}

# Time-boxed operator impersonation (live tests) of the runtime and broker SAs, never standing.
# Tenant SAs get the same expiring grant from modules/tenant.
locals {
  operator_impersonation_targets = merge(
    { runtime = google_service_account.pooled_agent_runtime.name },
    var.enable_credential_broker ? { broker = google_service_account.credential_broker[0].name } : {},
  )
  # for_each keys must be known at plan time: build them from static names, never from resource
  # attributes (otherwise a fresh plan or `terraform import` fails with "Invalid for_each").
  operator_impersonation_target_keys = concat(
    ["runtime"],
    var.enable_credential_broker ? ["broker"] : [],
  )
  operator_impersonation_bindings = {
    for pair in setproduct(local.operator_impersonation_target_keys, var.operator_impersonation.members) :
    "${pair[0]}/${pair[1]}" = > { target = pair[0], member = pair[1] }
  }
}

resource "google_service_account_iam_member" "operator_time_boxed_impersonation" {
  for_each           = local.operator_impersonation_bindings
  service_account_id = local.operator_impersonation_targets[each.value.target]
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = each.value.member
  condition {
    title      = "operator-impersonation-until-${var.operator_impersonation.expires}"
    expression = "request.time < timestamp(\"${var.operator_impersonation.expires}\")"
  }
}

# Optional secret shells for multi-instance gateway JWT & 3LO OAuth CSRF signing keys
# (values are populated out-of-band; never stored in Terraform state).
locals {
  platform_signing_secret_ids = var.enable_platform_signing_secrets ? toset([
    "cymbal-gateway-signing-key",
    "cymbal-oauth-3lo-csrf-key",
  ]) : toset([])
}

resource "google_secret_manager_secret" "platform_signing_shells" {
  for_each   = local.platform_signing_secret_ids
  project    = var.project_id
  secret_id  = each.value
  labels     = local.common_labels
  depends_on = [google_project_service.enabled_apis]

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "runtime_platform_signing_accessor" {
  for_each  = local.platform_signing_secret_ids
  project   = var.project_id
  secret_id = google_secret_manager_secret.platform_signing_shells[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pooled_agent_runtime.email}"
}
