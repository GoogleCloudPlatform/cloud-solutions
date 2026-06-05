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

resource "google_dataproc_cluster" "managed_spark" {
  name   = "managed-spark-cluster"
  region = var.region

  cluster_config {
    # Staging bucket for Dataproc cluster data
    staging_bucket = google_storage_bucket.detox_bucket.name

    master_config {
      num_instances = 1
      machine_type  = "n1-standard-2"
      disk_config {
        boot_disk_size_gb = 50
      }
    }

    worker_config {
      num_instances = 2
      machine_type  = "n1-standard-2"
      disk_config {
        boot_disk_size_gb = 50
      }
    }

    # Software settings
    software_config {
      image_version = "2.3-debian12"
    }

    # Network configuration
    gce_cluster_config {
      subnetwork      = google_compute_subnetwork.dataproc_subnet.id
      service_account = google_service_account.dataproc_sa.email
      service_account_scopes = [
        "https://www.googleapis.com/auth/cloud-platform"
      ]

      # Internal traffic is allowed via firewall rules in network.tf
      internal_ip_only = "true"
    }
  }

  # Prevent unnecessary cluster recreations due to API-computed defaults
  lifecycle {
    ignore_changes = [
      cluster_config[0].gce_cluster_config[0].service_account_scopes,
      cluster_config[0].software_config[0].image_version,
    ]
  }
  timeouts {
    # Creation sometimes can take a long time - usually around 20m, but can be longer.
    create = "60m"
  }
}
