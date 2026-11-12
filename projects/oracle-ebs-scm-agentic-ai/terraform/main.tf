# Copyright 2026 Google LLC
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

terraform {
  # Write-only arguments need Terraform 1.11 or later.
  required_version = ">= 1.11.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 8.6.0, < 9.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.9.0, < 4.0.0"
    }
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

locals {
  services = toset([
    "aiplatform.googleapis.com",
    "apikeys.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "bigquerydatatransfer.googleapis.com",
    "cloudaicompanion.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "discoveryengine.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "places.googleapis.com",
    "routes.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "static-maps-backend.googleapis.com",
    "storage.googleapis.com",
    "weather.googleapis.com",
  ])

  container_image_uri = coalesce(
    var.container_image != "" ? var.container_image : null,
    "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agent_repo.repository_id}/oracle-ebs-scm-agentic-ai:${var.image_tag}"
  )

  cloudbuild_builder_accounts = {
    compute    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
    cloudbuild = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
  }

  target_vpc_id      = var.create_vpc ? google_compute_network.vpc_network[0].id : "projects/${var.project_id}/global/networks/${var.vpc_network_name}"
  target_vpc_name    = var.create_vpc ? google_compute_network.vpc_network[0].name : var.vpc_network_name
  target_subnet_name = (var.create_vpc || var.create_subnet) ? google_compute_subnetwork.subnet[0].name : var.subnet_name

  agent_service_name = "voltguard-scm-agent"
  agent_public_url   = "https://${local.agent_service_name}-${data.google_project.project.number}.${var.region}.run.app"
  resolved_db_dsn    = "${var.oracle_host}:${var.oracle_port}/${var.oracle_service_name}"
  ebs_isg_url        = coalesce(var.ebs_isg_url, "https://${var.oracle_host}:4443")

  gemini_enterprise_agents = {
    discovery_engine   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
    cloud_ai_companion = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudaicompanion.iam.gserviceaccount.com"
  }
  developer_invoker = var.developer_user_email != "" ? { developer = "user:${var.developer_user_email}" } : {}
}

resource "google_project_service" "enabled_apis" {
  for_each                   = local.services
  project                    = var.project_id
  service                    = each.key
  disable_on_destroy         = false
  disable_dependent_services = false
}

data "google_project" "project" {
  project_id = var.project_id
  depends_on = [google_project_service.enabled_apis]
}

resource "google_compute_network" "vpc_network" {
  count                   = var.create_vpc ? 1 : 0
  name                    = var.vpc_network_name
  auto_create_subnetworks = false
  project                 = var.project_id
  depends_on              = [google_project_service.enabled_apis]
}

resource "google_compute_subnetwork" "subnet" {
  count                    = (var.create_vpc || var.create_subnet) ? 1 : 0
  name                     = var.subnet_name
  ip_cidr_range            = var.subnet_cidr
  region                   = var.region
  network                  = local.target_vpc_id
  private_ip_google_access = true
  project                  = var.project_id
  depends_on               = [google_project_service.enabled_apis]
}

resource "google_artifact_registry_repository" "agent_repo" {
  location      = var.region
  repository_id = "oracle-ebs-scm-repo"
  description   = "Docker repository for the VoltGuard supply chain resiliency agent images"
  format        = "DOCKER"
  project       = var.project_id
  depends_on    = [google_project_service.enabled_apis]
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_ar_writer" {
  for_each   = local.cloudbuild_builder_accounts
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.agent_repo.name
  role       = "roles/artifactregistry.writer"
  member     = each.value
  depends_on = [google_project_service.enabled_apis]
}

resource "google_project_iam_member" "cloudbuild_logging" {
  project    = var.project_id
  role       = "roles/logging.logWriter"
  member     = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.enabled_apis]
}

# deploy_stack.sh uploads the agent source here, and Cloud Build reads it
# back as the build service account. In organizations that turn off the
# automatic Editor grant, the Compute Engine default service account can't
# read the default Cloud Build bucket. A build needs the source only while it
# runs, so a lifecycle rule deletes it after a day.
resource "google_storage_bucket" "build_source" {
  name                        = "${var.project_id}-voltguard-build-source"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_storage_bucket_iam_member" "cloudbuild_source_reader" {
  for_each = local.cloudbuild_builder_accounts
  bucket   = google_storage_bucket.build_source.name
  role     = "roles/storage.objectViewer"
  member   = each.value
}

# -----------------------------------------------------------------------------
# Secrets: Oracle EBS read-only database password, ISG writeback credential,
# MCP Toolbox configuration, and Google Maps Platform credentials.
# -----------------------------------------------------------------------------

resource "google_secret_manager_secret" "db_password" {
  secret_id = "oracle-ebs-scm-db-password"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

# The two Oracle EBS passwords are write-only values, so they never reach
# the Terraform state or plan. Terraform writes a new secret version when the
# matching *_password_version variable changes.
resource "google_secret_manager_secret_version" "db_password_version" {
  secret                 = google_secret_manager_secret.db_password.id
  secret_data_wo         = var.oracle_db_password
  secret_data_wo_version = tostring(var.oracle_db_password_version)
}

resource "google_secret_manager_secret" "isg_credentials" {
  secret_id = "oracle-ebs-scm-isg-credentials"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

# HTTP Basic credential (base64 of user:password) for the ISG REST service.
resource "google_secret_manager_secret_version" "isg_credentials_version" {
  secret                 = google_secret_manager_secret.isg_credentials.id
  secret_data_wo         = base64encode("${var.ebs_writeback_user}:${var.ebs_writeback_password}")
  secret_data_wo_version = tostring(var.ebs_writeback_password_version)
}

resource "google_secret_manager_secret" "mcp_tools_config" {
  secret_id = "ebs-mcp-toolbox-tools-yaml"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "mcp_tools_config_version" {
  secret      = google_secret_manager_secret.mcp_tools_config.id
  secret_data = file("${path.module}/../mcp-servers/mcp-toolbox-ebs/tools.yaml")
}

# A deleted API key keeps its name for 30 days, so the key names end with a
# suffix that a new deployment generates again.
resource "random_id" "api_key_suffix" {
  byte_length = 3
}

# Google Maps Platform key for the live Routes API, Weather API, and Places API
# tools, restricted to those three APIs.
resource "google_apikeys_key" "maps" {
  name         = "voltguard-routes-weather-${random_id.api_key_suffix.hex}"
  display_name = "VoltGuard Routes, Weather, and Places APIs"
  project      = var.project_id

  restrictions {
    api_targets {
      service = "routes.googleapis.com"
    }
    api_targets {
      service = "weather.googleapis.com"
    }
    api_targets {
      service = "places.googleapis.com"
    }
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret" "maps_api_key" {
  secret_id = "oracle-ebs-scm-maps-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "maps_api_key_version" {
  secret      = google_secret_manager_secret.maps_api_key.id
  secret_data = google_apikeys_key.maps.key_string
}

# Google Maps Platform key for the agent's Maps Static API map tools,
# restricted to that API. The agent signs every request with the URL signing
# secret below.
resource "google_apikeys_key" "maps_static" {
  name         = "voltguard-maps-static-${random_id.api_key_suffix.hex}"
  display_name = "VoltGuard Maps Static API"
  project      = var.project_id

  restrictions {
    api_targets {
      service = "static-maps-backend.googleapis.com"
    }
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret" "maps_static_api_key" {
  secret_id = "oracle-ebs-scm-maps-static-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "maps_static_api_key_version" {
  secret      = google_secret_manager_secret.maps_static_api_key.id
  secret_data = google_apikeys_key.maps_static.key_string
}

# The Maps Static API URL signing secret comes from the Google Maps Platform
# credentials page in the Google Cloud console. Terraform manages only the
# secret container: deploy_stack.sh adds the version out of band, so the
# signing secret never lands in terraform.tfvars or the Terraform state.
resource "google_secret_manager_secret" "maps_static_signing_secret" {
  secret_id = "oracle-ebs-scm-maps-static-signing-secret"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

# -----------------------------------------------------------------------------
# Service accounts and least-privilege access.
# -----------------------------------------------------------------------------

resource "google_service_account" "voltguard_agent_sa" {
  account_id   = "ebs-scm-agent-sa"
  display_name = "VoltGuard supply chain resiliency agent"
  project      = var.project_id
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_service_account" "mcp_toolbox_sa" {
  account_id   = "ebs-mcp-toolbox-sa"
  display_name = "Oracle EBS MCP Toolbox server"
  project      = var.project_id
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_project_iam_member" "voltguard_agent_roles" {
  for_each = toset(["roles/aiplatform.user"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.voltguard_agent_sa.email}"
}

resource "google_project_iam_member" "mcp_toolbox_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.mcp_toolbox_sa.email}"
}

resource "google_bigquery_dataset_iam_member" "mcp_toolbox_data_viewer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.ebs_scm_agentic_ai.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.mcp_toolbox_sa.email}"

  # A replaced dataset, for example after a location change, loses its
  # access list, so grant the role again.
  lifecycle {
    replace_triggered_by = [google_bigquery_dataset.ebs_scm_agentic_ai]
  }
}

resource "google_secret_manager_secret_iam_member" "db_password_accessor" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mcp_toolbox_sa.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "isg_credentials_accessor" {
  secret_id = google_secret_manager_secret.isg_credentials.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mcp_toolbox_sa.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "mcp_tools_config_accessor" {
  secret_id = google_secret_manager_secret.mcp_tools_config.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mcp_toolbox_sa.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "maps_api_key_accessor" {
  secret_id = google_secret_manager_secret.maps_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mcp_toolbox_sa.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "maps_static_accessor" {
  for_each = {
    api_key        = google_secret_manager_secret.maps_static_api_key.id
    signing_secret = google_secret_manager_secret.maps_static_signing_secret.id
  }
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.voltguard_agent_sa.email}"
  project   = var.project_id
}

# -----------------------------------------------------------------------------
# BigQuery signals dataset and the Gemini connection. The signal views read
# the Google Trends public dataset, which lives in the US multi-region, so the
# dataset uses var.bigquery_location.
# -----------------------------------------------------------------------------

resource "google_bigquery_dataset" "ebs_scm_agentic_ai" {
  dataset_id                 = "ebs_scm_agentic_ai"
  friendly_name              = "VoltGuard Supply Chain Resiliency Signals"
  description                = "TimesFM forecasts, Google Trends search signals, hub market areas, and freight lane rates"
  location                   = var.bigquery_location
  project                    = var.project_id
  delete_contents_on_destroy = true

  depends_on = [google_project_service.enabled_apis]
}

# AI.GENERATE in zone_demand_exposure.sql calls Gemini through this
# connection, as the connection's service account, so the query doesn't
# depend on the Vertex AI access of whoever runs it.
resource "google_bigquery_connection" "voltguard_gemini" {
  connection_id = "voltguard_gemini"
  friendly_name = "VoltGuard Gemini"
  location      = var.bigquery_location
  project       = var.project_id

  cloud_resource {}

  depends_on = [google_project_service.enabled_apis]
}

resource "google_project_iam_member" "gemini_connection_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_bigquery_connection.voltguard_gemini.cloud_resource[0].service_account_id}"
}

# A scheduled query reruns timesfm_forecast.sql every day, so the stored
# forecast follows the issue history. The statements replace their table and
# views, and the run uses a service account that can edit only the signals
# dataset.
resource "google_service_account" "forecast_refresh_sa" {
  account_id   = "ebs-scm-forecast-sa"
  display_name = "VoltGuard daily TimesFM forecast refresh"
  project      = var.project_id
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_project_iam_member" "forecast_refresh_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.forecast_refresh_sa.email}"
}

resource "google_bigquery_dataset_iam_member" "forecast_refresh_data_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.ebs_scm_agentic_ai.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.forecast_refresh_sa.email}"

  lifecycle {
    replace_triggered_by = [google_bigquery_dataset.ebs_scm_agentic_ai]
  }
}

resource "google_bigquery_data_transfer_config" "timesfm_forecast_refresh" {
  display_name         = "VoltGuard daily TimesFM forecast refresh"
  project              = var.project_id
  location             = var.bigquery_location
  data_source_id       = "scheduled_query"
  schedule             = "every day 00:15"
  service_account_name = google_service_account.forecast_refresh_sa.email

  params = {
    query = replace(file("${path.module}/../bigquery/sql/timesfm_forecast.sql"), "your-project-id", var.project_id)
  }

  depends_on = [
    google_project_iam_member.forecast_refresh_job_user,
    google_bigquery_dataset_iam_member.forecast_refresh_data_editor,
  ]
}

# -----------------------------------------------------------------------------
# Oracle EBS MCP Toolbox server (the framework's MCP Toolbox for Databases
# image on Cloud Run). Direct VPC egress reaches the Oracle EBS database
# listener and the ISG REST service. Only IAM-authorized callers can invoke
# it.
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "ebs_mcp_toolbox" {
  name                = "ebs-mcp-toolbox"
  location            = var.region
  project             = var.project_id
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.mcp_toolbox_sa.email

    # With the default min_instance_count of 0, the service scales to zero
    # when idle, so an idle deployment adds no Cloud Run charges. The first
    # tool call after an idle period then waits for a cold start. The maximum
    # is the Cloud Run default. Setting it keeps a minimum of 0 from showing
    # as a change in every plan.
    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = 100
    }

    containers {
      image = var.mcp_toolbox_image
      args = [
        "--config=/app/tools.yaml",
        "--address=0.0.0.0",
        "--port=8080",
        "--logging-format=JSON",
        "--disable-version-check",
      ]

      ports {
        container_port = 8080
      }

      env {
        name  = "EBS_DB_CONNECTION_STRING"
        value = local.resolved_db_dsn
      }
      env {
        name  = "EBS_DB_USER"
        value = var.oracle_db_user
      }
      env {
        name = "EBS_DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = google_secret_manager_secret_version.db_password_version.version
          }
        }
      }
      env {
        name  = "BIGQUERY_PROJECT"
        value = var.project_id
      }
      env {
        name  = "BIGQUERY_LOCATION"
        value = var.bigquery_location
      }
      env {
        name = "MAPS_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.maps_api_key.secret_id
            version = google_secret_manager_secret_version.maps_api_key_version.version
          }
        }
      }
      env {
        name  = "EBS_ISG_URL"
        value = local.ebs_isg_url
      }
      env {
        name  = "EBS_ISG_ALLOWED_RANGE"
        value = "${var.oracle_host}/32"
      }
      env {
        name = "EBS_ISG_BASIC_AUTH"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.isg_credentials.secret_id
            version = google_secret_manager_secret_version.isg_credentials_version.version
          }
        }
      }
      env {
        name  = "EBS_INVENTORY_RESPONSIBILITY"
        value = var.ebs_inventory_responsibility
      }
      env {
        name  = "EBS_PURCHASING_RESPONSIBILITY"
        value = var.ebs_purchasing_responsibility
      }
      env {
        name  = "TOOLS_CONFIG_VERSION"
        value = google_secret_manager_secret_version.mcp_tools_config_version.version
      }

      volume_mounts {
        name       = "tools-config"
        mount_path = "/app"
      }
    }

    volumes {
      name = "tools-config"
      secret {
        secret = google_secret_manager_secret.mcp_tools_config.secret_id
        items {
          version = "latest"
          path    = "tools.yaml"
        }
      }
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"

      network_interfaces {
        network    = local.target_vpc_name
        subnetwork = local.target_subnet_name
      }
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_iam_member.db_password_accessor,
    google_secret_manager_secret_version.isg_credentials_version,
    google_secret_manager_secret_iam_member.isg_credentials_accessor,
    google_secret_manager_secret_iam_member.mcp_tools_config_accessor,
    google_secret_manager_secret_version.maps_api_key_version,
    google_secret_manager_secret_iam_member.maps_api_key_accessor,
    google_bigquery_dataset_iam_member.mcp_toolbox_data_viewer,
    google_project_iam_member.mcp_toolbox_job_user,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "mcp_toolbox_invoker" {
  for_each = merge(
    { agent = "serviceAccount:${google_service_account.voltguard_agent_sa.email}" },
    local.developer_invoker
  )
  name     = google_cloud_run_v2_service.ebs_mcp_toolbox.name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value
  project  = var.project_id
}

# -----------------------------------------------------------------------------
# VoltGuard ADK agent on Cloud Run, exposed to Gemini Enterprise through A2A.
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "voltguard_scm_agent" {
  name                = local.agent_service_name
  location            = var.region
  project             = var.project_id
  deletion_protection = false

  template {
    service_account = google_service_account.voltguard_agent_sa.email

    # Conversation sessions live in memory, so one instance keeps every turn
    # of a Gemini Enterprise conversation together. With the default
    # min_instance_count of 0, the service scales to zero when idle, so an
    # idle deployment adds no Cloud Run charges, and a conversation ends when
    # the idle instance stops. Sessions idle for 2 hours expire.
    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = 1
    }

    containers {
      image = local.container_image_uri

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "GEMINI_FALLBACK_MODELS"
        value = join(",", var.gemini_fallback_models)
      }
      env {
        name  = "GEMINI_LOCATION"
        value = var.gemini_location
      }
      env {
        name  = "MCP_SERVER_URL"
        value = "${google_cloud_run_v2_service.ebs_mcp_toolbox.uri}/mcp"
      }
      env {
        name  = "MCP_TIMEOUT_SECONDS"
        value = tostring(var.mcp_timeout_seconds)
      }
      env {
        name  = "A2A_PUBLIC_URL"
        value = local.agent_public_url
      }
      env {
        name  = "ARTIFACT_BUCKET"
        value = google_storage_bucket.agent_artifacts.name
      }
      env {
        name = "MAPS_STATIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.maps_static_api_key.secret_id
            version = google_secret_manager_secret_version.maps_static_api_key_version.version
          }
        }
      }
      env {
        name = "MAPS_STATIC_SIGNING_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.maps_static_signing_secret.secret_id
            version = "latest"
          }
        }
      }
      # ADK drops A2A part metadata, which Gemini Enterprise sends and only
      # the Gemini Developer API accepts, when this marks the Vertex AI backend.
      env {
        name  = "GOOGLE_GENAI_USE_ENTERPRISE"
        value = "true"
      }
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_artifact_registry_repository.agent_repo,
    google_project_iam_member.voltguard_agent_roles,
    google_cloud_run_v2_service_iam_member.mcp_toolbox_invoker,
    google_secret_manager_secret_version.maps_static_api_key_version,
    google_secret_manager_secret_iam_member.maps_static_accessor,
    google_storage_bucket_iam_member.agent_artifacts_user,
  ]
}

# Chart and map images that the agent attaches to its answers. A turn needs
# them only while it runs, so a lifecycle rule deletes them after a day.
resource "google_storage_bucket" "agent_artifacts" {
  name                        = "${var.project_id}-voltguard-artifacts"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_storage_bucket_iam_member" "agent_artifacts_user" {
  bucket = google_storage_bucket.agent_artifacts.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.voltguard_agent_sa.email}"
}

resource "google_cloud_run_v2_service_iam_member" "agent_invoker" {
  for_each = merge(local.gemini_enterprise_agents, local.developer_invoker)
  name     = google_cloud_run_v2_service.voltguard_scm_agent.name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value
  project  = var.project_id
}
