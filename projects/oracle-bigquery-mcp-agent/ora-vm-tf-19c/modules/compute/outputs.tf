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

# Removed public IP output as VM is private

output "oracle_db_private_ip" {
  value       = google_compute_instance.oracle_vm.network_interface[0].network_ip
  description = "Internal Private IP Address of the Oracle database VM"
}


output "vm_instance_id" {
  value       = google_compute_instance.oracle_vm.id
  description = "The unique Google Cloud resource ID identifier of the provisioned Google Compute Engine Oracle virtual machine instance"
}
