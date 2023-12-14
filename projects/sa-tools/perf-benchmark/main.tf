# Copyright 2023 Google LLC
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

provider "google" {
  project = var.project_id
  region  = var.region
}

## Compute Project number from Project Id
data "google_project" "gcp_project_info" {
  project_id = var.project_id
}

// Enable requires APIs
resource "google_project_service" "enable_required_services" {
  project            = var.project_id
  disable_on_destroy = false
  for_each           = toset([
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "datastore.googleapis.com",
    "iamcredentials.googleapis.com",
    "iam.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
  ])
  service = each.key
}


### Create Service Account for the tool and assign roles/permissions

resource "google_service_account" "runner_sa" {
  account_id  = "${var.cloud_run_service_name}-runner"
  project     = var.project_id
  description = "SA for PerfkitBenchmark App"
  depends_on  = [google_project_service.enable_required_services]
}


resource "google_project_iam_member" "assign_sa_roles" {
  for_each = toset([
    //App and PKB Runner Roles
    "roles/bigquery.user",

    // App Only Roles
    "roles/datastore.user",
    "roles/cloudbuild.builds.viewer",
    "roles/storage.objectCreator",

    // PKB Roles
    "roles/compute.admin",
    "roles/logging.logWriter",
    "roles/storage.objectViewer",
  ])
  role    = each.key
  member = "serviceAccount:${google_service_account.runner_sa.email}"
  project = var.project_id
}

resource "google_service_account_iam_member" "add_runner_sa_as_gce_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${data.google_project.gcp_project_info.number}-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.runner_sa.email}"
}

## Grant user-group Service Account impersonation role
resource "google_service_account_iam_member" "add_user_group_as_sa_impersonator" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${google_service_account.runner_sa.email}"
  member             = "${var.tool_user_group_email_type}:${var.tool_user_group_email}"

  for_each = toset([
    "roles/iam.serviceAccountUser",
    "roles/iam.serviceAccountTokenCreator",
  ])
  role = each.key
}
## Grant user-group Cloud Build Role
resource "google_project_iam_member" "add_user_group_as_build_editor" {
  role    = "roles/cloudbuild.builds.editor"
  project = var.project_id
  member  = "${var.tool_user_group_email_type}:${var.tool_user_group_email}"
}

### Create Artifact Registry and build images
resource "google_artifact_registry_repository" "perfkit_images" {
  depends_on    = [google_project_service.enable_required_services]
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_name
  format        = "DOCKER"
  description   = "Perfkit Benchmarking images"
}

locals {
  artifact_registry_base_uri  = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.perfkit_images.name}"
  job_gcs_bucket_name         = "perfkit_benchmark_jobs_${var.project_id}"
  bq_project                  = coalesce(var.results_bq_project, var.project_id)
  pkb_runner_full_image_name  = "${local.artifact_registry_base_uri}/pkb-base-runner:${random_id.images_tag.hex}"
  perfkit_app_full_image_name = "${local.artifact_registry_base_uri}/${var.cloud_run_service_name}:${random_id.images_tag.hex}"
}

resource "random_id" "images_tag" {
  byte_length = 8
  keepers     = {
    project_id   = var.project_id
    region       = var.region
    service_name = var.cloud_run_service_name
  }
}


## Provide Cloud Build Service Account GCS Access
resource "google_project_iam_member" "set_cloud_build_sa_permissions" {
  member   = "serviceAccount:${data.google_project.gcp_project_info.number}@cloudbuild.gserviceaccount.com"
  project  = var.project_id
  role     = each.key
  for_each = toset([
    "roles/artifactregistry.writer"
  ])
}


resource "null_resource" "build_pkb_base_runner_image" {

  triggers = {
    full_image_path = local.pkb_runner_full_image_name
  }

  provisioner "local-exec" {
    when    = create
    command = <<-EOT
gcloud builds submit . \
--config=benchmarkrunnerbase-cloudbuild.yaml \
--project=${var.project_id} \
--substitutions=_CONTAINER_IMAGE_TAG=${self.triggers.full_image_path} \
--ignore-file=../.gcloudignore
EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
gcloud artifacts docker images delete \
${self.triggers.full_image_path} \
--quiet
EOT
  }
}

resource "null_resource" "build_perfkit_app_image" {
  triggers = {
    full_image_path = local.perfkit_app_full_image_name
  }

  provisioner "local-exec" {
    when    = create
    command = <<-EOT
gcloud builds submit ../ \
--config=perfkitbenchmark-cloudbuild.yaml \
--substitutions=_CONTAINER_IMAGE_TAG=${local.perfkit_app_full_image_name} \
--ignore-file=../.gcloudignore
EOT
  }
  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
gcloud artifacts docker images delete \
${self.triggers.full_image_path} \
--quiet
EOT
  }
}

#### Create storage Resources

resource "google_bigquery_dataset" "results_dataset" {
  project    = local.bq_project
  location   = var.region
  dataset_id = var.results_bq_dataset

  depends_on = [google_project_service.enable_required_services]
}

resource "google_bigquery_table" "results_table" {
  project    = local.bq_project
  dataset_id = google_bigquery_dataset.results_dataset.dataset_id
  table_id   = var.results_bq_table
}

resource "google_storage_bucket" "jobs_config_gcs_bucket" {
  name = local.job_gcs_bucket_name

  project  = var.project_id
  location = var.region

  force_destroy               = true
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  depends_on = [google_project_service.enable_required_services]
}

## Deploy Perfkit App on Cloud Run

resource "google_cloud_run_v2_service" "perfkit_benchmark_app" {
  depends_on = [
    null_resource.build_perfkit_app_image,
    null_resource.build_pkb_base_runner_image,
  ]

  name     = "perfkit-benchmark"
  project  = var.project_id
  location = var.region

  template {
    service_account       = google_service_account.runner_sa.email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    containers {
      image = local.perfkit_app_full_image_name

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "JOB_CONFIG_GCS_BUCKET"
        value = google_storage_bucket.jobs_config_gcs_bucket.name
      }
      env {
        name  = "PERFKIT_RUNNER_BASE_IMAGE"
        value = local.pkb_runner_full_image_name
      }
      env {
        name  = "RESULTS_BQ_PROJECT"
        value = local.bq_project
      }
      env {
        name  = "RESULTS_BQ_DATASET"
        value = var.results_bq_dataset
      }
      env {
        name  = "RESULTS_BQ_TABLE"
        value = var.results_bq_table
      }
      env {
        name  = "GSI_CLIENT_ID"
        value = var.client_id
      }
    }
  }
}

## Make the Cloud Run Unauthenticated

data "google_iam_policy" "noauth_policy" {
  binding {
    role    = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

resource "google_cloud_run_v2_service_iam_policy" "noauth_policy_for_app" {
  project     = var.project_id
  location    = var.region
  name        = google_cloud_run_v2_service.perfkit_benchmark_app.name
  policy_data = data.google_iam_policy.noauth_policy.policy_data
}

### Create PubSub Topic for receiving build event on App

resource "google_pubsub_topic" "cloud_builds_events" {
  depends_on = [ google_project_service.enable_required_services ]
  project = var.project_id
  name    = "cloud-builds"
}

resource "google_pubsub_subscription" "build_events_subscription_for_perfkit_app" {
  name    = "build-events-subscription-for-perfkit_app"
  topic   = google_pubsub_topic.cloud_builds_events.name
  project = var.project_id
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.perfkit_benchmark_app.uri}/buildstatus"
  }
  ack_deadline_seconds = 60
}
