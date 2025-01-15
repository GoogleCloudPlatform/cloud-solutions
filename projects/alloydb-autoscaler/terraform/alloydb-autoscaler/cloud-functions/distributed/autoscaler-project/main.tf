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
  nodejs_version                  = "20"
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
  source = "../../../../autoscaler-core/modules/autoscaler-base"

  project_id               = var.project_id
  poller_sa_email          = google_service_account.poller_sa.email
  scaler_sa_email          = google_service_account.scaler_sa.email
  path_to_downstream_proto = "src/alloydb-autoscaler/schema/downstream_event.proto"
}

module "autoscaler-functions" {
  source = "../../../../autoscaler-core/modules/autoscaler-functions"

  nodejs_version                  = local.nodejs_version
  autoscaler_poller_function_name = local.autoscaler_poller_function_name
  autoscaler_scaler_function_name = local.autoscaler_scaler_function_name

  project_id          = var.project_id
  region              = var.region
  poller_sa_email     = google_service_account.poller_sa.email
  scaler_sa_email     = google_service_account.scaler_sa.email
  forwarder_sa_emails = var.forwarder_sa_emails
  build_sa_id         = module.autoscaler-base.build_sa_id
}

module "autoscaler-firestore" {
  source = "../../../../autoscaler-core/modules/autoscaler-firestore"

  project_id      = local.app_project_id
  poller_sa_email = google_service_account.poller_sa.email
  scaler_sa_email = google_service_account.scaler_sa.email
}

module "autoscaler-spanner" {
  source = "../../../../autoscaler-core/modules/autoscaler-spanner"

  region                  = var.region
  project_id              = var.project_id
  terraform_spanner_state = var.terraform_spanner_state
  spanner_state_name      = var.spanner_state_name
  spanner_state_database  = var.spanner_state_database
  spanner_state_table     = local.spanner_state_table

  poller_sa_email = google_service_account.poller_sa.email
  scaler_sa_email = google_service_account.scaler_sa.email
}
