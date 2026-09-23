/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

output "vm_name" {
  description = "Name of the deployed vSphere workload virtual machine."
  value       = vsphere_virtual_machine.web_app.name
}

output "vm_internal_ip" {
  description = "Internal IPv4 address of the deployed workload VM."
  value       = local.vm_ip
}

output "test_command" {
  description = "Command to verify HTTP service response from the deployed workload."
  value       = "curl http://${local.web_app_public_ip}"
}
