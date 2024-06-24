# Copyright 2023 Google LLC
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

resource "google_dataproc_cluster" "hive_bq" {
  depends_on = [
    google_project_service.gcp_services, google_storage_bucket.hive_bq_cluster_staging,
    google_project_iam_member.svc-access
  ]
  name                          = "hive-bq-cluster"
  region                        = local.region
  graceful_decommission_timeout = "120s"

  cluster_config {
    staging_bucket = google_storage_bucket.hive_bq_cluster_staging.name

    master_config {
      num_instances = 1
      machine_type  = "n2-standard-8"
    }

    worker_config {
      num_instances = 2
      machine_type  = "n2-standard-8"
    }

    preemptible_worker_config {
      num_instances = 0
    }

    # Override or set some custom properties
    software_config {
      image_version       = "2.1-debian11"
      optional_components = ["JUPYTER", "ZEPPELIN"]
    }

    endpoint_config {
      enable_http_port_access = true
    }

    gce_cluster_config {
      # Google recommends custom service accounts that have cloud-platform scope and permissions granted via IAM Roles.
      service_account = google_service_account.connector.email
      service_account_scopes = [
        "https://www.googleapis.com/auth/cloud.useraccounts.readonly",
        "https://www.googleapis.com/auth/devstorage.read_write",
        "https://www.googleapis.com/auth/logging.write",
        "cloud-platform"
      ]
      #network    = google_compute_network.vpc_network.name
      subnetwork = google_compute_subnetwork.vpc_subnetwork.name

      metadata = {
        "hive-bigquery-connector-version" = "2.0.3"
      }
    }

    # You can define multiple initialization_action blocks
    initialization_action {
      script      = "gs://goog-dataproc-initialization-actions-${local.region}/connectors/connectors.sh"
      timeout_sec = 500
    }

    initialization_action {
      script      = "gs://${google_storage_bucket.hive_bq_cluster_staging.name}/scripts/initialization-script.sh"
      timeout_sec = 500
    }
  }
}
