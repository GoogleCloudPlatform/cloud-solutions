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

output "cluster_name" {
  description = "The name of the provisioned GKE cluster"
  value       = google_container_cluster.main.name
}

output "gateway_ip" {
  description = "The global IP address allocated for the Gateway API"
  value       = google_compute_global_address.gateway.address
}

output "nat_ip" {
  description = "The external IP address allocated for Cloud NAT"
  value       = google_compute_address.nat.address
}

output "region" {
  description = "The Google Cloud region where resources are deployed"
  value       = var.region
}
