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

resource "google_alloydb_cluster" "default" {
  cluster_id       = "alloydb-cluster"
  location         = var.region
  database_version = "POSTGRES_16"

  network_config {
    network = google_compute_network.agent_cluster_vpc_network.id
  }

  initial_user {
    password = "alloydb-cluster"
  }

  deletion_protection = false

  depends_on = [google_project_service.alloydb_googleapis_com]
}

resource "google_alloydb_instance" "default" {
  cluster           = google_alloydb_cluster.default.name
  instance_id       = "alloydb-instance-2"
  instance_type     = "PRIMARY"
  availability_type = "ZONAL"

  machine_config {
    cpu_count    = 1
    machine_type = "c4a-highmem-1"
  }

  network_config {
    enable_public_ip = true
    authorized_external_networks {
      cidr_range = "68.129.133.69/32"
    }
  }

  database_flags = {
    "alloydb.iam_authentication"  = "on",
    "alloydb.enable_pg_cron"      = "on",
    "alloydb_ai_nl.enabled"       = "on",
    "parameterized_views.enabled" = "on"
    "password.enforce_complexity" = "on"
  }

  depends_on = [google_service_networking_connection.vpc_connection]
}

resource "google_alloydb_user" "bq_connector_user" {
  cluster   = google_alloydb_cluster.default.name
  user_id   = "bq_connector_user"
  user_type = "ALLOYDB_BUILT_IN"

  password       = "!bq_connector_user_secret@123"
  database_roles = ["alloydbsuperuser"]
  depends_on     = [google_alloydb_instance.default]
}

resource "google_alloydb_user" "toolbox_iam_user" {
  cluster   = google_alloydb_cluster.default.name
  user_id   = trimsuffix(google_service_account.toolbox-identity.email, ".gserviceaccount.com")
  user_type = "ALLOYDB_IAM_USER"

  database_roles = ["alloydbiamuser", "alloydbsuperuser"]
  depends_on     = [google_alloydb_instance.default]
}

resource "google_alloydb_user" "order_service_iam_user" {
  cluster   = google_alloydb_cluster.default.name
  user_id   = trimsuffix(google_service_account.order-service.email, ".gserviceaccount.com")
  user_type = "ALLOYDB_IAM_USER"

  database_roles = ["alloydbiamuser", "alloydbsuperuser"]
  depends_on     = [google_alloydb_instance.default]
}

resource "google_alloydb_user" "reporting_iam_user" {
  cluster   = google_alloydb_cluster.default.name
  user_id   = trimsuffix(google_service_account.reporting_service_account.email, ".gserviceaccount.com")
  user_type = "ALLOYDB_IAM_USER"

  database_roles = ["alloydbiamuser", "alloydbsuperuser"]
  depends_on     = [google_alloydb_instance.default]
}

resource "google_alloydb_user" "current_user" {
  cluster   = google_alloydb_cluster.default.name
  user_id   = trimsuffix(data.google_client_openid_userinfo.me.email, ".gserviceaccount.com")
  user_type = "ALLOYDB_IAM_USER"

  database_roles = ["alloydbiamuser", "alloydbsuperuser"]
  depends_on     = [google_alloydb_instance.default]
}
