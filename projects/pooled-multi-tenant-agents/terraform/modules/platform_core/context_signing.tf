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
# Context-token signing key (ADR-0014 B2)
#
# Non-exportable Cloud KMS asymmetric key that signs ES256 context tokens. Only the serving
# identity may sign (signerVerifier on THIS key only); the credential broker may only read public
# keys. Created in the sandbox with gcloud on 2026-11-03 and adopted into Terraform on
# 2026-11-06. Never destroyed by Terraform.
# After ADR-0014 B5 the signer moves to the gateway's own identity.
# ============================================================================

resource "google_kms_key_ring" "platform" {
  project    = var.project_id
  name       = "cymbal-platform-kr"
  location   = var.region
  depends_on = [google_project_service.enabled_apis]
}

resource "google_kms_crypto_key" "context_signing" {
  name     = "ws2-context-signing"
  key_ring = google_kms_key_ring.platform.id
  purpose  = "ASYMMETRIC_SIGN"
  labels   = { purpose = "context-token", workstream = "ws2" }

  version_template {
    algorithm        = "EC_SIGN_P256_SHA256"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "runtime_context_signer" {
  crypto_key_id = google_kms_crypto_key.context_signing.id
  role          = "roles/cloudkms.signerVerifier"
  member        = "serviceAccount:${google_service_account.pooled_agent_runtime.email}"
}

resource "google_kms_crypto_key_iam_member" "operator_context_signer" {
  for_each      = toset(var.operator_impersonation.members)
  crypto_key_id = google_kms_crypto_key.context_signing.id
  role          = "roles/cloudkms.signerVerifier"
  member        = each.value
  condition {
    title      = "operator-impersonation-until-${var.operator_impersonation.expires}"
    expression = "request.time < timestamp(\"${var.operator_impersonation.expires}\")"
  }
}
