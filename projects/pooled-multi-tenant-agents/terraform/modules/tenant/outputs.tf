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

output "service_account_email" {
  description = "Tenant-scoped runtime identity (ct-*)."
  value       = google_service_account.tenant.email
}

output "cmek_key_id" {
  description = "Tenant CMEK key ID."
  value       = google_kms_crypto_key.tenant_cmek.id
}

output "skills_bucket_name" {
  description = "Tenant skills bucket."
  value       = google_storage_bucket.tenant_skills.name
}

output "secret_ids" {
  description = "Secret Manager secret resource IDs, keyed by secret ID."
  value       = { for k, v in google_secret_manager_secret.tenant_3lo_vault : k => v.id }
}
