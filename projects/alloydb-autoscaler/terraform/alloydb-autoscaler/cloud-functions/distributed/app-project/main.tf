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
    module_name = "cloud-solutions/alloydb-autoscaler-deploy-cf-distributed-1.0.0"
  }
}

locals {
  autoscaler_library_name            = "alloydb-autoscaler"
  autoscaler_forwarder_function_name = "forwarderHandlePubSubRequest"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "terraform_remote_state" "autoscaler" {
  backend = "local"

  config = {
    path = "../autoscaler-project/terraform.tfstate"
  }
}

module "autoscaler-network" {
  source = "../../../../autoscaler-core/modules/autoscaler-network"
  count  = var.terraform_alloydb_instance ? 1 : 0

  autoscaler_library_name = local.autoscaler_library_name
  region                  = var.region
  project_id              = var.project_id
  ip_range                = var.ip_range
}

module "alloydb-cluster" {
  source = "../../../modules/alloydb-cluster"
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

  poller_sa_email = data.terraform_remote_state.autoscaler.outputs.poller_sa_email
  scaler_sa_email = data.terraform_remote_state.autoscaler.outputs.scaler_sa_email

  depends_on = [module.autoscaler-network]
}

# TODO: add autoscaler-monitoring.

module "autoscaler-scheduler" {
  source = "../../../../autoscaler-core/modules/autoscaler-scheduler"

  project_id   = var.project_id
  location     = var.region
  pubsub_topic = module.autoscaler-forwarder.forwarder_topic

  # TODO: fully generate from variables.
  json_config = jsonencode([{
    "projectId" : "${var.project_id}",
    "regionId" : "${var.region}",

    "clusterId" : "${var.alloydb_cluster_name}",
    "instanceId" : "${var.alloydb_read_pool_instance_name}",

    "scalerPubSubTopic" : "${data.terraform_remote_state.autoscaler.outputs.scaler_topic}",

    "scalingMethod" : "STEPWISE",
    "minSize" : 3,
    "maxSize" : 10,

    "stateProjectId" : "${var.state_project_id}",
    "stateDatabase" : {
      "name" : "firestore"
    }
  }])
}

module "autoscaler-forwarder" {
  source = "../../../../autoscaler-core/modules/autoscaler-forwarder"

  project_id = var.project_id
  region     = var.region

  target_pubsub_topic = data.terraform_remote_state.autoscaler.outputs.poller_topic

  autoscaler_forwarder_function_name = local.autoscaler_forwarder_function_name
}
