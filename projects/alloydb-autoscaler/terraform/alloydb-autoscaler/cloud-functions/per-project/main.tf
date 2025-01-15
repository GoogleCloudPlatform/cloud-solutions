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
  }

  provider_meta "google" {
    module_name = "cloud-solutions/alloydb-autoscaler-deploy-cf-1.0.0"
  }
}

locals {
  autoscaler_library_name    = "alloydb-autoscaler"
  autoscaler_library_version = "1.0.0"
  nodejs_version             = "20"

  autoscaler_poller_function_name = "pollerHandlePubSubRequest"
  autoscaler_scaler_function_name = "scalerHandlePubSubRequest"
  spanner_state_table             = "alloyDbAutoscaler"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_service_account" "poller_sa" {
  account_id   = "poller-sa"
  display_name = "AlloyDB Autoscaler - Poller SA"
}

resource "google_service_account" "scaler_sa" {
  account_id   = "scaler-sa"
  display_name = "AlloyDB Autoscaler - Scaler SA"
}

module "autoscaler-base" {
  source = "../../../autoscaler-core/modules/autoscaler-base"

  project_id               = var.project_id
  poller_sa_email          = google_service_account.poller_sa.email
  scaler_sa_email          = google_service_account.scaler_sa.email
  path_to_downstream_proto = "src/alloydb-autoscaler/schema/downstream_event.proto"
}

module "autoscaler-functions" {
  source = "../../../autoscaler-core/modules/autoscaler-functions"

  nodejs_version                  = local.nodejs_version
  autoscaler_poller_function_name = local.autoscaler_poller_function_name
  autoscaler_scaler_function_name = local.autoscaler_scaler_function_name

  project_id      = var.project_id
  region          = var.region
  poller_sa_email = google_service_account.poller_sa.email
  scaler_sa_email = google_service_account.scaler_sa.email
  build_sa_id     = module.autoscaler-base.build_sa_id
}

module "autoscaler-firestore" {
  source = "../../../autoscaler-core/modules/autoscaler-firestore"

  project_id      = local.app_project_id
  poller_sa_email = google_service_account.poller_sa.email
  scaler_sa_email = google_service_account.scaler_sa.email
}

module "autoscaler-spanner" {
  source = "../../../autoscaler-core/modules/autoscaler-spanner"

  region                  = var.region
  project_id              = var.project_id
  terraform_spanner_state = var.terraform_spanner_state
  spanner_state_name      = var.spanner_state_name
  spanner_state_database  = var.spanner_state_database
  spanner_state_table     = local.spanner_state_table

  poller_sa_email = google_service_account.poller_sa.email
  scaler_sa_email = google_service_account.scaler_sa.email
}

module "autoscaler-network" {
  source = "../../../autoscaler-core/modules/autoscaler-network"
  count  = var.terraform_alloydb_instance ? 1 : 0

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

  network = var.terraform_alloydb_instance ? one(module.autoscaler-network).network : null

  poller_sa_email = google_service_account.poller_sa.email
  scaler_sa_email = google_service_account.scaler_sa.email

  depends_on = [module.autoscaler-network]
}

module "autoscaler-scheduler" {
  source = "../../../autoscaler-core/modules/autoscaler-scheduler"

  project_id   = var.project_id
  location     = var.region
  pubsub_topic = module.autoscaler-functions.poller_topic

  # TODO: fully generate from variables.
  json_config = jsonencode([{
    "projectId" : "${var.project_id}",
    "regionId" : "${var.region}",

    "clusterId" : "${var.alloydb_cluster_name}",
    "instanceId" : "${var.alloydb_read_pool_instance_name}",

    "scalerPubSubTopic" : "${module.autoscaler-functions.scaler_topic}",

    "scalingMethod" : "STEPWISE",
    "minSize" : 3,
    "maxSize" : 10,

    "stateProjectId" : "${var.project_id}",
    "stateDatabase" : {
      "name" : "firestore"
    }
  }])
}

# TODO: add autoscaler-monitoring.
