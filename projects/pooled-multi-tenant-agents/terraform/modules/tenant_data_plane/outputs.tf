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

output "cmek_key_id" {
  description = "Tenant-held CMEK key that encrypts the data plane."
  value       = google_kms_crypto_key.data_plane.id
}

output "alloydb_cluster_id" {
  description = "AlloyDB cluster ID."
  value       = google_alloydb_cluster.data_plane.id
}

output "psc_service_attachment" {
  description = "PSC service attachment of the primary instance; the consumer's PSC endpoint targets it."
  value       = google_alloydb_instance.primary.psc_instance_config[0].service_attachment_link
}

output "psc_dns_name" {
  description = "DNS name clients use through the PSC endpoint."
  value       = google_alloydb_instance.primary.psc_instance_config[0].psc_dns_name
}
