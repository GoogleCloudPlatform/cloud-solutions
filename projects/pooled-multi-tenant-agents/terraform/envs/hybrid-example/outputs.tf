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

output "psc_endpoint_ip" {
  description = "Internal IP the pooled runtime / MCP server uses for this tenant (topology.data_endpoint)."
  value       = google_compute_address.tenant_psc.address
}

output "tenant_cmek_key_id" {
  description = "Tenant-held CMEK key."
  value       = module.tenant_data_plane.cmek_key_id
}
