/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.12.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.33.0"
    }
  }

  provider_meta "google" {
    module_name = "cloud-solutions/alloydb-autoscaler-deploy-gke-1.0.0"
  }
}

locals {
  autoscaler_library_name = "alloydb-autoscaler"
  autoscaler_gke_name     = "alloydb-autoscaler"
  gke_ip_range            = "10.1.0.0/28"
  spanner_state_table     = "alloyDbAutoscaler"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_service_account" "autoscaler_sa" {
  account_id   = "scaler-sa"
  display_name = "AlloyDB Autoscaler - Autoscaler SA"
}

module "autoscaler-base" {
  source = "../../../autoscaler-core/modules/autoscaler-base"

  project_id               = var.project_id
  poller_sa_email          = google_service_account.autoscaler_sa.email
  scaler_sa_email          = google_service_account.autoscaler_sa.email
  path_to_downstream_proto = "src/alloydb-autoscaler/schema/downstream_event.proto"
}

module "autoscaler-gke" {
  source = "../../../autoscaler-core/modules/autoscaler-gke"

  region            = var.region
  project_id        = var.project_id
  name              = local.autoscaler_gke_name
  namespace         = local.autoscaler_gke_name
  network           = module.autoscaler-network.network_name
  subnetwork        = module.autoscaler-network.subnetwork_name
  ip_range_master   = local.gke_ip_range
  ip_range_pods     = ""
  ip_range_services = ""
  poller_sa_email   = google_service_account.autoscaler_sa.email
  scaler_sa_email   = google_service_account.autoscaler_sa.email

  autoscaler_repository_id = var.autoscaler_repository_id
}

module "autoscaler-firestore" {
  source = "../../../autoscaler-core/modules/autoscaler-firestore"

  project_id      = var.project_id
  poller_sa_email = google_service_account.autoscaler_sa.email
  scaler_sa_email = google_service_account.autoscaler_sa.email
}

module "autoscaler-spanner" {
  source = "../../../autoscaler-core/modules/autoscaler-spanner"

  region                  = var.region
  project_id              = var.project_id
  terraform_spanner_state = var.terraform_spanner_state
  spanner_state_name      = var.spanner_state_name
  spanner_state_database  = var.spanner_state_database
  spanner_state_table     = local.spanner_state_table

  poller_sa_email = google_service_account.autoscaler_sa.email
  scaler_sa_email = google_service_account.autoscaler_sa.email
}

module "autoscaler-network" {
  source = "../../../autoscaler-core/modules/autoscaler-network"

  autoscaler_library_name = local.autoscaler_library_name
  region                  = var.region
  project_id              = var.project_id
  ip_range                = var.ip_range
}

module "alloydb-cluster" {
  source = "../../modules/alloydb-cluster"
  count  = var.terraform_alloydb_instance ? 1 : 0

  region     = var.region
  project_id = var.project_id

  alloydb_cluster_name            = var.alloydb_cluster_name
  alloydb_primary_instance_name   = var.alloydb_primary_instance_name
  alloydb_read_pool_instance_name = var.alloydb_read_pool_instance_name
  alloydb_node_count              = var.alloydb_node_count
  alloydb_username                = var.alloydb_username
  alloydb_password                = var.alloydb_password

  network = module.autoscaler-network.network

  poller_sa_email = google_service_account.autoscaler_sa.email
  scaler_sa_email = google_service_account.autoscaler_sa.email

  depends_on = [module.autoscaler-network]
}

# TODO: add autoscaler-monitoring.
