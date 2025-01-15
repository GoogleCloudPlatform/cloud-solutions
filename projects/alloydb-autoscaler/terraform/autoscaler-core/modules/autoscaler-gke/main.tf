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
    module_name = "cloud-solutions/oss-autoscalers-deploy-gke-1.0.0"
  }
}

locals {
  poller_sa_name = element(split("@", var.poller_sa_email), 0)
  scaler_sa_name = element(split("@", var.scaler_sa_email), 0)
}

resource "google_service_account" "otel_collector_service_account" {
  project      = var.project_id
  account_id   = var.otel_collector_sa_name
  display_name = "Autoscaler - SA for OpenTelemetry Collector in ${var.name}"
}

resource "google_project_iam_member" "metrics_publisher_otel_collector" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.otel_collector_service_account.email}"
}

resource "google_service_account" "gke_cluster_service_account" {
  project      = var.project_id
  account_id   = "cluster-sa"
  display_name = "OSS Autoscaler - cluster SA for ${var.name}"
}

resource "google_project_iam_member" "cluster_iam_logginglogwriter" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gke_cluster_service_account.email}"
}

resource "google_project_iam_member" "cluster_iam_monitoringmetricwriter" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gke_cluster_service_account.email}"
}

resource "google_project_iam_member" "cluster_iam_monitoringviewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.gke_cluster_service_account.email}"
}

resource "google_project_iam_member" "cluster_iam_resourcemetadatawriter" {
  project = var.project_id
  role    = "roles/stackdriver.resourceMetadata.writer"
  member  = "serviceAccount:${google_service_account.gke_cluster_service_account.email}"
}

resource "google_project_iam_member" "cluster_iam_artifactregistryreader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.gke_cluster_service_account.email}"
}

resource "google_artifact_registry_repository" "autoscaler_artifact_repo" {
  location      = var.region
  repository_id = var.autoscaler_repository_id
  description   = "Image registry for the OSS Autoscaler"
  format        = "DOCKER"
}

data "google_client_config" "default" {}

provider "kubernetes" {
  host                   = "https://${module.autoscaler-gke.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(module.autoscaler-gke.ca_certificate)
}

resource "kubernetes_namespace" "autoscaler_namespace" {
  metadata {
    name = var.namespace
  }
}

module "workload_identity_poller" {
  count               = var.unified_components ? 0 : 1
  source              = "terraform-google-modules/kubernetes-engine/google//modules/workload-identity"
  version             = "34.0.0"
  project_id          = var.project_id
  namespace           = var.namespace
  use_existing_k8s_sa = false
  use_existing_gcp_sa = true
  name                = local.poller_sa_name
  depends_on          = [kubernetes_namespace.autoscaler_namespace, var.poller_sa_email]
}

module "workload_identity_scaler" {
  source              = "terraform-google-modules/kubernetes-engine/google//modules/workload-identity"
  version             = "34.0.0"
  project_id          = var.project_id
  namespace           = var.namespace
  use_existing_k8s_sa = false
  use_existing_gcp_sa = true
  name                = local.scaler_sa_name
  depends_on          = [kubernetes_namespace.autoscaler_namespace, var.scaler_sa_email]
}

module "workload_identity_otel_collector" {
  source              = "terraform-google-modules/kubernetes-engine/google//modules/workload-identity"
  version             = "34.0.0"
  project_id          = var.project_id
  namespace           = var.namespace
  use_existing_k8s_sa = false
  use_existing_gcp_sa = true
  name                = var.otel_collector_sa_name
  depends_on          = [kubernetes_namespace.autoscaler_namespace, google_service_account.otel_collector_service_account]
}

module "autoscaler-gke" {
  source  = "terraform-google-modules/kubernetes-engine/google//modules/private-cluster"
  version = "34.0.0"

  project_id             = var.project_id
  name                   = var.name
  region                 = var.region
  network                = var.network
  subnetwork             = var.subnetwork
  release_channel        = var.release_channel
  master_ipv4_cidr_block = var.ip_range_master
  ip_range_pods          = var.ip_range_pods
  ip_range_services      = var.ip_range_services
  enable_private_nodes   = true
  enable_shielded_nodes  = true
  network_policy         = true
  regional               = true

  create_service_account = false
  service_account        = google_service_account.gke_cluster_service_account.email
  node_metadata          = "GKE_METADATA"

  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = false

  master_authorized_networks = [
    {
      cidr_block   = "0.0.0.0/0"
      display_name = "Public"
    },
  ]

  node_pools = [
    {
      name               = "autoscaler-pool"
      machine_type       = var.machine_type
      min_count          = var.minimum_node_pool_instances
      max_count          = var.maximum_node_pool_instances
      auto_upgrade       = true
      auto_repair        = true
      enable_secure_boot = true
      service_account    = google_service_account.gke_cluster_service_account.email
    },
  ]

  node_pools_oauth_scopes = {
    all = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }
}
