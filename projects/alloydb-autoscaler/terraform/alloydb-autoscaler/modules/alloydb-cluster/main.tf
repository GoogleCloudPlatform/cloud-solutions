/**
 * Copyright 2024 Google LLC
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

terraform {
  provider_meta "google" {
    module_name = "cloud-solutions/alloydb-autoscaler-deploy-alloydb-1.0.0"
  }
}

resource "google_compute_global_address" "alloydb_private_ip_alloc" {
  name          = var.alloydb_cluster_name
  address_type  = "INTERNAL"
  purpose       = "VPC_PEERING"
  prefix_length = 16
  network       = var.network
}

resource "google_service_networking_connection" "alloydb_vpc_connection" {
  network                 = var.network
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.alloydb_private_ip_alloc.name]
}

resource "google_alloydb_cluster" "alloydb_cluster" {
  cluster_id       = var.alloydb_cluster_name
  location         = var.region
  database_version = var.postgres_version

  network_config {
    network = var.network
  }

  initial_user {
    user     = var.alloydb_username
    password = var.alloydb_password
  }

  depends_on = [google_service_networking_connection.alloydb_vpc_connection]
}

resource "google_alloydb_instance" "alloydb_primary_instance" {
  cluster       = google_alloydb_cluster.alloydb_cluster.name
  instance_id   = var.alloydb_primary_instance_name
  instance_type = "PRIMARY"
}

resource "google_alloydb_instance" "alloydb_primary_read_pool" {
  cluster       = google_alloydb_cluster.alloydb_cluster.name
  instance_id   = var.alloydb_read_pool_instance_name
  instance_type = "READ_POOL"

  read_pool_config {
    node_count = var.alloydb_node_count
  }

  depends_on = [google_alloydb_instance.alloydb_primary_instance]
}

# Assign custom roles.
resource "random_id" "role_suffix" {
  byte_length = 4
}

resource "google_project_iam_custom_role" "metrics_viewer_iam_role" {
  project     = var.project_id
  role_id     = "alloyDbAutoscalerMetricsViewer_${random_id.role_suffix.hex}"
  title       = "AlloyDB Autoscaler Metrics Viewer Role"
  description = "Allows a principal to get AlloyDB instances and view time series metrics"
  permissions = [
    "alloydb.instances.get",
    "alloydb.instances.list",
    "monitoring.timeSeries.list"
  ]
}

resource "google_project_iam_member" "poller_metrics_viewer_iam" {
  role    = google_project_iam_custom_role.metrics_viewer_iam_role.name
  project = var.project_id
  member  = "serviceAccount:${var.poller_sa_email}"
}

resource "google_project_iam_custom_role" "capacity_manager_iam_role" {
  project     = var.project_id
  role_id     = "alloyDbAutoscalerCapacityManager_${random_id.role_suffix.hex}"
  title       = "AlloyDB Autoscaler Capacity Manager Role"
  description = "Allows a principal to scale AlloyDB instances"
  permissions = [
    "alloydb.instances.get",
    "alloydb.instances.update",
    "alloydb.operations.get"
  ]
}

resource "google_project_iam_member" "scaler_update_capacity_iam" {
  role    = google_project_iam_custom_role.capacity_manager_iam_role.name
  project = var.project_id
  member  = "serviceAccount:${var.scaler_sa_email}"
}
