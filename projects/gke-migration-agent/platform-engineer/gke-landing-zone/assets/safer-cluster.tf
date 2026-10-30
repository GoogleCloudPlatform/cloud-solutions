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

module "cluster" {
  source                  = "terraform-google-modules/kubernetes-engine/google//modules/safer-cluster"
  version                 = "~> 44.0"
  project_id              = var.project_id
  name                    = "${var.env}-${var.project_id}-primary"
  region                  = var.region
  network                 = module.vpc.network_name
  subnetwork              = "<subnet from the IP plan>"
  ip_range_pods           = "<pods range name from the IP plan>"
  ip_range_services       = "<services range name from the IP plan>"
  master_ipv4_cidr_block  = "<unique /28 from the IP plan>"
  release_channel         = "<confirmed channel>"
  enable_private_endpoint = true # Set per access decision
  gateway_api_channel     = "CHANNEL_STANDARD"
  deletion_protection     = true

  # Map node pools from EKS nodegroups in discovery
  node_pools = [
    {
      name               = "<mapped name>"
      machine_type       = "<mapped machine_type>"
      min_count          = 1   # Replace with mapped min_count
      max_count          = 10  # Replace with mapped max_count
      disk_size_gb       = 100 # Replace with mapped disk size
      disk_type          = "<mapped disk type such as pd-balanced>"
      enable_secure_boot = true
    }
  ]
}
