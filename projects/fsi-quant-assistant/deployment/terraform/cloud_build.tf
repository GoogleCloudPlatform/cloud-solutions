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

resource "google_cloudbuild_worker_pool" "pool" {
  name     = "build-pool"
  location = var.region
  worker_config {
    disk_size_gb   = 100
    machine_type   = "n2d-standard-4"
    no_external_ip = false
  }
  network_config {
    peered_network          = google_compute_network.agent_cluster_vpc_network.id
    peered_network_ip_range = "/29"
  }
  depends_on = [google_service_networking_connection.vpc_connection]
}

resource "google_cloudbuildv2_connection" "gitlab_connection" {
  count    = var.deploy_cloud_build_triggers ? 1 : 0
  location = var.region
  name     = "google-cloud-ce"

  gitlab_config {
    # Required: Secret for the Webhook Secret (any secure string)
    webhook_secret_secret_version = data.google_secret_manager_regional_secret_version_access.gitlab_webhook_secret[0].name

    # Required: API Token (with 'api' scope) for connecting/disconnecting repos
    authorizer_credential {
      user_token_secret_version = data.google_secret_manager_regional_secret_version_access.gitlab_api_token_secret[0].name
    }

    # Required: Read-only API Token (with 'read_api' scope) for fetching code
    read_authorizer_credential {
      user_token_secret_version = data.google_secret_manager_regional_secret_version_access.gitlab_read_token_secret[0].name
    }
  }

  depends_on = [
    google_secret_manager_regional_secret_iam_member.gitlab_api_token_secret-secretAccessor,
    google_secret_manager_regional_secret_iam_member.gitlab_read_token_secret-secretAccessor,
    google_secret_manager_regional_secret_iam_member.gitlab_webhook_secret-secretAccessor,
  ]
}

resource "google_cloudbuildv2_repository" "fsi_bundle" {
  count             = var.deploy_cloud_build_triggers ? 1 : 0
  name              = "finance-bundle"
  location          = var.region
  parent_connection = google_cloudbuildv2_connection.gitlab_connection[0].name
  remote_uri        = "https://gitlab.com/google-cloud-ce/communities/data-cloud-sa/industry-bundles/finance-bundle.git"
}

resource "google_cloudbuild_trigger" "adk_deploy_trigger" {
  count    = var.deploy_cloud_build_triggers ? 1 : 0
  name     = "adk-deployment"
  location = var.region
  tags     = ["adk", "deploy"]

  repository_event_config {
    repository = google_cloudbuildv2_repository.fsi_bundle[0].id
    push {
      branch = "^main$"
    }
  }

  service_account = google_service_account.cloudbuild_service_account.id
  included_files  = ["adk-agent/**"]
  filename        = "adk-agent/cloudbuild-deploy.yaml"

  substitutions = {
    _REGION          = "us-central1"
    _DISPLAY_NAME    = "finance-bundle"
    _STAGING_BUCKET  = "gs://finance-bundle-1001_adk-deploy"
    _TRIGGER_CLEANUP = "true"
  }
}

resource "google_cloudbuild_trigger" "adk_clear_agents_trigger" {
  count    = var.deploy_cloud_build_triggers ? 1 : 0
  name     = "clear-old-adk-agents"
  location = var.region
  tags     = ["adk", "clean-up"]

  repository_event_config {
    repository = google_cloudbuildv2_repository.fsi_bundle[0].id
  }

  service_account = google_service_account.cloudbuild_service_account.id
  filename        = "adk-agent/cloudbuild-clear-agents.yaml"

  substitutions = {
    _REGION       = "us-central1"
    _DISPLAY_NAME = "finance-bundle"
  }
}

resource "google_cloudbuild_trigger" "order_service_deploy_trigger" {
  count    = var.deploy_cloud_build_triggers ? 1 : 0
  name     = "order-service-deployment"
  location = var.region
  tags     = ["order-service", "deploy"]

  repository_event_config {
    repository = google_cloudbuildv2_repository.fsi_bundle[0].id
    push {
      branch = "^main$"
    }
  }

  service_account = google_service_account.cloudbuild_service_account.id
  included_files  = ["order-service/**"]
  filename        = "order-service/cloudbuild-publish-deploy.yaml"

  substitutions = {
    _REGION         = "us-central1"
    _TRIGGER_DEPLOY = "true"
  }
}

resource "google_cloudbuild_trigger" "forecast_service_publish_trigger" {
  count    = var.deploy_cloud_build_triggers ? 1 : 0
  name     = "forecast-service-publish"
  location = var.region
  tags     = ["forecast-service", "publish"]

  repository_event_config {
    repository = google_cloudbuildv2_repository.fsi_bundle[0].id
    push {
      branch = "^main$"
    }
  }

  service_account = google_service_account.cloudbuild_service_account.id
  included_files  = ["forecast-service/**"]
  filename        = "forecast-service/cloudbuild-publish.yaml"

  substitutions = {
    _REGION             = "us-central1"
    _MODEL_DISPLAY_NAME = "forecast-service-timesfm"
    _ARTIFACT_NAME      = "forecast-service"
    _USE_JAX            = "false"
    _TRIGGER_DEPLOY     = "true"
  }
}

resource "google_cloudbuild_trigger" "forecast_service_deploy_trigger" {
  count    = var.deploy_cloud_build_triggers ? 1 : 0
  name     = "forecast-service-deploy"
  location = var.region
  tags     = ["forecast-service", "deploy"]

  repository_event_config {
    repository = google_cloudbuildv2_repository.fsi_bundle[0].id
  }

  service_account = google_service_account.cloudbuild_service_account.id
  included_files  = ["forecast-service/**"]
  filename        = "forecast-service/cloudbuild-deploy.yaml"

  substitutions = {
    _REGION             = "us-central1"
    _MODEL_DISPLAY_NAME = "forecast-service-timesfm"
    _IMAGE_URI          = "${var.region}-docker.pkg.dev/${var.project_id}/finance-bundle/forecast-service:latest"
    _MACHINE_TYPE       = "n1-standard-4"
    _USE_TPU            = "true"
    _TPU_MACHINE_TYPE   = "ct5lp-hightpu-1t"
    _ACCELERATOR_TYPE   = ""
    _ACCELERATOR_COUNT  = ""
    _TRIGGER_CLEANUP    = "true"
  }
}

resource "google_cloudbuild_trigger" "forecast_service_clear_models_trigger" {
  count    = var.deploy_cloud_build_triggers ? 1 : 0
  name     = "forecast-service-clear-old-models"
  location = var.region
  tags     = ["forecast-service", "cleanup"]

  repository_event_config {
    repository = google_cloudbuildv2_repository.fsi_bundle[0].id
  }

  service_account = google_service_account.cloudbuild_service_account.id
  included_files  = ["forecast-service/**"]
  filename        = "forecast-service/cloudbuild-clear-models.yaml"

  substitutions = {
    _REGION             = "us-central1"
    _MODEL_DISPLAY_NAME = "forecast-service-timesfm"
    _KEEP_COUNT         = "1"
  }
}
