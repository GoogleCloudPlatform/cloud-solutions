# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

resource "google_container_cluster" "adk_cluster" {
  # The name for your GKE cluster
  name = "adk-demo-cluster"

  # This is the key setting that creates an Autopilot cluster.
  enable_autopilot = true

  network    = google_compute_network.agent_cluster_vpc_network.self_link
  subnetwork = google_compute_subnetwork.agent_cluster_subnet.self_link

  maintenance_policy {
    recurring_window {
      # Start Time: Saturday 12:00 AM UTC
      start_time = "2025-01-01T00:00:00Z"

      # End Time: 48 hours later (Sunday 12:00 AM UTC)
      end_time = "2025-01-03T00:00:00Z"

      # Recurrence: Weekly, anchored to the Saturday start_time
      recurrence = "FREQ=WEEKLY;BYDAY=SA"
    }
  }

  secret_manager_config {
    enabled = true
    rotation_config {
      enabled           = true
      rotation_interval = "300s"
    }
  }

  # This does not stick. On subsequent plans Terraform wants to destroy to add this
  # SA back.
  # node_config {
  #   # Google recommends custom service accounts that have cloud-platform scope and permissions granted via IAM Roles.
  #   service_account = google_service_account.adk-agent.email
  #   oauth_scopes = [
  #     "https://www.googleapis.com/auth/cloud-platform"
  #   ]
  # }

  # Add this block to disable the public endpoint
  private_cluster_config {
    # This is not for general public access, but rather for communication between your GKE cluster and other
    # GCP services (like Cloud Build, Cloud Run, etc.) that have external IP addresses.
    # If set to true, cloud build cannot reach without vpn.
    enable_private_endpoint = false # Set to false to access control plane via a public endpoint.
    enable_private_nodes    = true

    # IMPORTANT: Specifies a required /28 IP range for the control plane.
    master_ipv4_cidr_block = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    gcp_public_cidrs_access_enabled = true

    cidr_blocks {
      # Allow traffic from the VPC
      cidr_block   = google_compute_subnetwork.agent_cluster_subnet.ip_cidr_range # This is your subnet's CIDR range.
      display_name = "Agent Cluster Subnet"
    }

    # cidr_blocks {
    #   # Allows traffic from the Cloud Build Private Worker Pool
    #   cidr_block   = "${google_compute_global_address.worker_range.address}/${google_compute_global_address.worker_range.prefix_length}"
    #   display_name = "Cloud Build Worker Pool Range"
    # }
  }

  deletion_protection = false

  depends_on = [
    google_project_service.container_googleapis_com,
    google_service_account.adk-agent
  ]
}
