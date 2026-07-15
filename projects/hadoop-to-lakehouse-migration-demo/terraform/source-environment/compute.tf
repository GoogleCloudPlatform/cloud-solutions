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

resource "google_dataproc_cluster" "legacy_hadoop" {
  name    = var.cluster_name
  region  = var.region
  project = data.google_project.source_project.project_id

  cluster_config {
    gce_cluster_config {
      subnetwork      = google_compute_subnetwork.source_subnet.id
      service_account = google_service_account.dataproc_sa.email
      zone            = var.zone
      service_account_scopes = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/cloud.useraccounts.readonly",
        "https://www.googleapis.com/auth/devstorage.read_write",
        "https://www.googleapis.com/auth/logging.write",
      ]
      internal_ip_only = "true"
    }

    master_config {
      num_instances = 1
      machine_type  = "n1-standard-4"
      disk_config {
        boot_disk_type    = "pd-standard"
        boot_disk_size_gb = 100
      }
    }

    worker_config {
      num_instances = 2
      machine_type  = "n2-standard-4"
      disk_config {
        boot_disk_size_gb = 1000
      }
    }

    software_config {
      image_version = "2.3-debian12"
    }
  }

  timeouts {
    create = "60m"
    delete = "60m"
  }
}
