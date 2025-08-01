#
# Copyright 2025 Google LLC
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

#------------------------------------------------------------------------------
# Input variables.
#------------------------------------------------------------------------------

variable "project_id" {
  description = "Project to deploy to"
  type        = string
}

variable "region" {
  description = "Region to deploy resources in"
  type        = string
}

variable "repository" {
  description = "Name of the Artifact Registry repository"
  type        = string
  default     = "caims"
}

variable "image_tag" {
  description = "Docker image tag to deploy. If not specified, the image is built from source."
  type        = string
  default     = null
}

variable "debug_mode" {
  description = "Deploy Confidential Space instances in debug-mode."
  type        = bool
  default     = false
}

#------------------------------------------------------------------------------
# Provider.
#------------------------------------------------------------------------------

terraform {
  provider_meta "google" {
    module_name = "cloud-solutions/caims-confidential-space-v2.0"
  }
}

provider "google" {
  project = var.project_id
}

#------------------------------------------------------------------------------
# Local variables.
#------------------------------------------------------------------------------

locals {
  sources        = "${path.module}/../sources"
  broker_image   = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repository}/broker"
  workload_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repository}/workload"

  #
  # Effective image tag to use. We use the same tag for both images since they're
  # built from the same source tree.
  #
  image_tag = var.image_tag != null ? var.image_tag : data.external.git.result.sha
}

#
# Get current commit SHA.
#
data "external" "git" {
  program = [
    "sh", "-c", var.image_tag != null
    ? "echo {\\\"sha\\\": \\\"${var.image_tag}\\\"}"
    : "echo {\\\"sha\\\": \\\"$(git rev-parse HEAD)\\\"}"
  ]
  working_dir = local.sources
}

#------------------------------------------------------------------------------
# Required APIs
#------------------------------------------------------------------------------

resource "google_project_service" "iam" {
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iamcredentials" {
  service            = "iamcredentials.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "compute" {
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "confidentialcomputing" {
  service            = "confidentialcomputing.googleapis.com"
  disable_on_destroy = false
}

#------------------------------------------------------------------------------
# Project.
#------------------------------------------------------------------------------

data "google_project" "project" {
  project_id = var.project_id
}

#------------------------------------------------------------------------------
# Docker registry.
#------------------------------------------------------------------------------

#
# Create a Docker repository.
#
resource "google_artifact_registry_repository" "registry" {
  depends_on    = [google_project_service.artifactregistry]
  format        = "DOCKER"
  repository_id = var.repository
  location      = var.region
}

#------------------------------------------------------------------------------
# Broker.
#------------------------------------------------------------------------------

#
# Service account for the broker.
#
resource "google_service_account" "broker" {
  depends_on   = [google_project_service.iam]
  account_id   = "broker"
  display_name = "Broker service"
}

#
# Grant the service account the Token Creator role on itself so that it can sign JWTs.
#
resource "google_service_account_iam_member" "broker_token_creator" {
  service_account_id = google_service_account.broker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.broker.email}"
}

#
# Grant the service account the Compute Viewer role so that it can discover workload VMs.
#
resource "google_project_iam_member" "broker_compute_viewer" {
  project = var.project_id
  role    = "roles/compute.viewer"
  member  = "serviceAccount:${google_service_account.broker.email}"
}

#
# Build a Docker image unless a tag was provided.
#
resource "null_resource" "broker_docker_image" {
  depends_on = [google_artifact_registry_repository.registry]
  triggers = {
    always_rebuild = timestamp()
  }
  provisioner "local-exec" {
    command = var.image_tag == null ? join("&&", [
      "docker build --platform linux/amd64 -t ${local.broker_image}:${local.image_tag} -f ${local.sources}/broker.dockerfile ${local.sources}",
      "docker push ${local.broker_image}:${local.image_tag}"
    ]) : "echo Using predefined image tag, skipping Docker build"
    interpreter = ["sh", "-c"]
  }
}

#
# Deploy a Cloud Run service.
#
resource "google_cloud_run_v2_service" "broker" {
  depends_on = [null_resource.broker_docker_image, google_project_service.run]

  provider = google
  location = var.region
  name     = "broker"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account       = google_service_account.broker.email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    scaling {
      max_instance_count = 2
    }

    containers {
      image = "${local.broker_image}:${local.image_tag}"
    }

    vpc_access {
      network_interfaces {
        network    = "default"
        subnetwork = "default"
      }
    }
  }
}

#
# Allow anonymous access to the Cloud Run service.
#
resource "google_cloud_run_service_iam_binding" "default" {
  location = google_cloud_run_v2_service.broker.location
  service  = google_cloud_run_v2_service.broker.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}

#------------------------------------------------------------------------------
# Confidential Space VMs.
#------------------------------------------------------------------------------

#
# Service account for workloads.
#
resource "google_service_account" "workload" {
  depends_on   = [google_project_service.iam]
  account_id   = "workload"
  display_name = "Workload"
}

#
# Grant the service account access to Artifact Registry.
#
resource "google_project_iam_member" "workload_registry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.workload.email}"
}

#
# Grant the service account access to use Confidential Space.
#
resource "google_project_iam_member" "workload_confidentialspace" {
  project = var.project_id
  role    = "roles/confidentialcomputing.workloadUser"
  member  = "serviceAccount:${google_service_account.workload.email}"
}

#
# Build a Docker image unless a tag was provided.
#
resource "null_resource" "workload_docker_image" {
  depends_on = [google_artifact_registry_repository.registry]
  triggers = {
    always_rebuild = timestamp()
  }
  provisioner "local-exec" {
    command = var.image_tag == null ? join("&&", [
      "docker build --platform linux/amd64 -t ${local.workload_image}:${local.image_tag} -f ${local.sources}/workload.dockerfile ${local.sources}",
      "docker push ${local.workload_image}:${local.image_tag}"
    ]) : "echo Using predefined image tag, skipping Docker build"
    interpreter = ["sh", "-c"]
  }
}

#
# Create an instance template.
#
resource "google_compute_instance_template" "workload_template" {
  depends_on = [
    null_resource.workload_docker_image,
    google_project_service.compute,
    google_project_service.confidentialcomputing
  ]
  name_prefix  = "workload-template-"
  machine_type = "n2d-standard-2"

  disk {
    source_image = (var.debug_mode
      ? "projects/confidential-space-images/global/images/family/confidential-space-debug"
    : "projects/confidential-space-images/global/images/family/confidential-space")
  }

  network_interface {
    network = "default"

    # Add external IP, required for cloud-init.
    access_config {}
  }

  metadata = {
    "enable-guest-attributes" = "TRUE"
    "tee-image-reference"     = "${local.workload_image}:${local.image_tag}"
  }

  service_account {
    email  = google_service_account.workload.email
    scopes = ["cloud-platform"]
  }

  lifecycle {
    create_before_destroy = true
  }

  confidential_instance_config {
    enable_confidential_compute = true
    confidential_instance_type  = "SEV"
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_integrity_monitoring = true
    enable_vtpm                 = true
  }
}

#
# Create a managed instance group.
#
resource "google_compute_instance_group_manager" "workload" {
  depends_on         = [google_compute_instance_template.workload_template]
  name               = "workload"
  zone               = "${var.region}-a"
  base_instance_name = "workload"
  target_size        = 2
  wait_for_instances = true

  version {
    instance_template = google_compute_instance_template.workload_template.self_link
  }

  lifecycle {
    create_before_destroy = true
  }
}

#------------------------------------------------------------------------------
# Outputs.
#------------------------------------------------------------------------------

output "url" {
  description = "URL to application"
  value       = "https://${google_cloud_run_v2_service.broker.name}-${data.google_project.project.number}.${google_cloud_run_v2_service.broker.location}.run.app/"
}
