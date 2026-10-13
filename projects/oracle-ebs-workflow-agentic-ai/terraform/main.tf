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
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 8.6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 8.6.0"
    }
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

locals {
  services = toset([
    "accesscontextmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "discoveryengine.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "vpcaccess.googleapis.com",
  ])

  container_image_uri = coalesce(
    var.container_image != "" ? var.container_image : null,
    "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agent_repo.repository_id}/oracle-ebs-workflow-app:${var.image_tag}"
  )

  agent_services = {
    "a2a-workflow-server" = { port = "8080", entrypoint = "src.a2a.a2a_server:app", image = local.container_image_uri }
    "workflow-agent"      = { port = "8080", entrypoint = "src.agents.workflow_agent:app", image = local.container_image_uri }
  }

  cloudbuild_builder_accounts = [
    "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com",
    "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com",
  ]

  target_vpc_id          = var.create_vpc ? google_compute_network.vpc_network[0].id : "projects/${var.project_id}/global/networks/${var.vpc_network_name}"
  target_vpc_name        = var.create_vpc ? google_compute_network.vpc_network[0].name : var.vpc_network_name
  target_subnet_name     = var.create_vpc ? google_compute_subnetwork.subnet[0].name : var.subnet_name
  target_secret_name     = "oracle-ebs-workflow-db-password-${var.environment}"
  target_isg_secret_name = "oracle-ebs-workflow-isg-password-${var.environment}"
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
}

resource "google_compute_network" "vpc_network" {
  count                   = var.create_vpc ? 1 : 0
  name                    = var.vpc_network_name
  auto_create_subnetworks = false
  project                 = var.project_id
  depends_on              = [google_project_service.enabled_apis]
}

resource "google_compute_subnetwork" "subnet" {
  count         = var.create_vpc ? 1 : 0
  name          = var.subnet_name
  ip_cidr_range = "10.10.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc_network[0].id
  project       = var.project_id
}

resource "google_artifact_registry_repository" "agent_repo" {
  location      = var.region
  repository_id = "oracle-ebs-workflow-repo-${var.environment}"
  description   = "Docker repository for Oracle EBS Workflow Agentic AI container images"
  format        = "DOCKER"
  project       = var.project_id
  depends_on    = [google_project_service.enabled_apis]
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_ar_writer" {
  for_each   = toset(local.cloudbuild_builder_accounts)
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.agent_repo.name
  role       = "roles/artifactregistry.writer"
  member     = each.value
}

resource "google_project_iam_member" "cloudbuild_logging" {
  project    = var.project_id
  role       = "roles/logging.logWriter"
  member     = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = local.target_secret_name
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret" "isg_password" {
  secret_id = local.target_isg_secret_name
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_service_account" "workflow_sa" {
  account_id   = "ebs-workflow-agent-sa-${var.environment}"
  display_name = "Oracle EBS Workflow Agent Service Account (${var.environment})"
  project      = var.project_id
}

# Dedicated Service Account for Gemini Enterprise / Vertex AI Extension Authentication
resource "google_service_account" "gemini_agent_sa" {
  account_id   = "gemini-ebs-workflow-sa-${var.environment}"
  display_name = "Gemini Enterprise Workflow Extension Service Account (${var.environment})"
  project      = var.project_id
  depends_on   = [google_project_service.enabled_apis]
}

# Allow Google-managed Discovery Engine & Cloud AI Companion agents to mint OIDC tokens for Gemini SA
resource "google_service_account_iam_member" "gemini_agent_sa_token_creator" {
  for_each = toset(concat(
    [
      "serviceAccount:service-${data.google_project.project.number}@gcp-sa-discoveryengine.iam.gserviceaccount.com",
      "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudaicompanion.iam.gserviceaccount.com",
    ],
    var.developer_user_email != "" ? ["user:${var.developer_user_email}"] : []
  ))
  service_account_id = google_service_account.gemini_agent_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = each.value
}

resource "google_secret_manager_secret_iam_member" "db_password_accessor" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workflow_sa.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "isg_password_accessor" {
  secret_id = google_secret_manager_secret.isg_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workflow_sa.email}"
  project   = var.project_id
}

resource "google_project_iam_member" "cloud_run_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.workflow_sa.email}"
}

resource "google_cloud_run_v2_service" "agents" {
  for_each            = local.agent_services
  name                = "${each.key}-${var.environment}"
  location            = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.workflow_sa.email
    containers {
      image = each.value.image
      args = [
        each.value.entrypoint,
        "--host",
        "0.0.0.0",
        "--port",
        tostring(each.value.port),
      ]
      ports {
        container_port = tonumber(each.value.port)
      }
      env {
        name  = "SERVICE_ENTRYPOINT"
        value = each.value.entrypoint
      }
      env {
        name  = "ORACLE_HOST"
        value = var.oracle_host
      }
      env {
        name  = "ORACLE_PORT"
        value = tostring(var.oracle_port)
      }
      env {
        name  = "ORACLE_SERVICE_NAME"
        value = var.oracle_service_name
      }
      env {
        name  = "ORACLE_USER"
        value = var.oracle_db_user
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "VERTEX_LOCATION"
        value = "global"
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "GEMINI_FALLBACK_MODEL"
        value = var.gemini_fallback_model
      }
      env {
        name  = "GEMINI_FLASH_LITE_MODEL"
        value = var.gemini_flash_lite_model
      }
      env {
        name  = "FND_USER_ID"
        value = tostring(var.fnd_user_id)
      }
      env {
        name  = "FND_RESP_ID"
        value = tostring(var.fnd_resp_id)
      }
      env {
        name  = "FND_RESP_APPL_ID"
        value = tostring(var.fnd_resp_appl_id)
      }
      env {
        name  = "WORKFLOW_EXECUTION_PATH"
        value = var.workflow_execution_path
      }
      env {
        name  = "ISG_REST_BASE_URL"
        value = coalesce(var.isg_rest_base_url != "" ? var.isg_rest_base_url : null, "http://${var.oracle_host}:8000")
      }
      env {
        name  = "ISG_USERNAME"
        value = var.isg_username
      }
      env {
        name  = "A2A_SERVER_URL"
        value = "https://a2a-workflow-server-${var.environment}-${data.google_project.project.number}.${var.region}.run.app"
      }
      env {
        name  = "WORKFLOW_AGENT_URL"
        value = "https://workflow-agent-${var.environment}-${data.google_project.project.number}.${var.region}.run.app"
      }
      env {
        name = "ORACLE_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = local.target_secret_name
            version = "latest"
          }
        }
      }
      env {
        name = "ISG_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = local.target_isg_secret_name
            version = "latest"
          }
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
    google_artifact_registry_repository.agent_repo,
    google_secret_manager_secret.db_password,
    google_secret_manager_secret_iam_member.db_password_accessor,
    google_secret_manager_secret.isg_password,
    google_secret_manager_secret_iam_member.isg_password_accessor,
  ]
}

# Grant Gemini Enterprise Service Account invoker permissions on Cloud Run endpoints
resource "google_cloud_run_v2_service_iam_member" "sa_invokers" {
  for_each = local.agent_services
  name     = google_cloud_run_v2_service.agents[each.key].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gemini_agent_sa.email}"
  project  = var.project_id
}

# Grant Google-managed Discovery Engine Service Agent invoker permissions on Cloud Run endpoints
resource "google_cloud_run_v2_service_iam_member" "discovery_engine_invokers" {
  for_each = local.agent_services
  name     = google_cloud_run_v2_service.agents[each.key].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
  project  = var.project_id
}

# Grant Google-managed Cloud AI Companion Service Agent invoker permissions on Cloud Run endpoints
resource "google_cloud_run_v2_service_iam_member" "cloud_ai_companion_invokers" {
  for_each = local.agent_services
  name     = google_cloud_run_v2_service.agents[each.key].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudaicompanion.iam.gserviceaccount.com"
  project  = var.project_id
}

# Grant internal Cloud Run Service Account invoker permissions for A2A -> Worker routing
resource "google_cloud_run_v2_service_iam_member" "cloud_run_internal_invokers" {
  for_each = local.agent_services
  name     = google_cloud_run_v2_service.agents[each.key].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.workflow_sa.email}"
  project  = var.project_id
}

resource "google_cloud_run_v2_service_iam_member" "developer_user_invoker" {
  for_each = var.developer_user_email != "" ? local.agent_services : {}
  name     = google_cloud_run_v2_service.agents[each.key].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "user:${var.developer_user_email}"
  project  = var.project_id
}

resource "google_storage_bucket" "agent_assets" {
  name                        = "${var.project_id}-oracle-ebs-workflow-assets-${var.environment}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  project                     = var.project_id
  depends_on                  = [google_project_service.enabled_apis]
}

locals {
  a2a_agent_card_content = format(
    "%s\n",
    jsonencode(
      merge(
        jsondecode(file("${path.module}/../src/a2a/agent_card_spec.json")),
        {
          url = google_cloud_run_v2_service.agents["a2a-workflow-server"].uri
        }
      )
    )
  )

  gemini_extension_manifest_content = format("%s\n", jsonencode({
    display_name = "Oracle EBS Workflow AI Assistant"
    description  = "Autonomous Enterprise Agent for Oracle EBS Workflow inspection, policy verification, approval triage, and certified action execution."
    instructions = "You are the Oracle EBS Workflow AI Assistant, connected to live Oracle E-Business Suite database and workflow microservices. Translate user requests into appropriate API operations: /notifications for listing pending notifications, /notifications/{notification_id} for detailed inspection, /verify-policy for corporate policy validation, /triage for multi-item evaluation with Markdown table formatting, and /execute for certified approvals/rejections. CRITICAL POLICY AND CONFIRMATION GATE: Never perform workflow mutations (APPROVE or REJECT) without explicit manager confirmation. If unconfirmed, generate a ConfirmationProposal detailing notification IDs, item types, subjects, amounts, risk levels, policy violations, and the required confirmation prompt. CRITICAL TABLE RENDERING REQUIREMENT: When presenting multiple notifications or triage results, ALWAYS render the complete Markdown table with all columns and every returned row. State the count of records shown."
    tools = [
      {
        name         = "workflow_agent"
        openapi_spec = "${google_cloud_run_v2_service.agents["workflow-agent"].uri}/openapi.json"
      },
      {
        name         = "a2a_workflow_server"
        openapi_spec = "${google_cloud_run_v2_service.agents["a2a-workflow-server"].uri}/openapi.json"
      }
    ]
  }))

  gemini_extension_openapi_yaml_content = templatefile("${path.module}/gemini_extension_openapi.yaml.tpl", {
    a2a_workflow_server_url = google_cloud_run_v2_service.agents["a2a-workflow-server"].uri
    workflow_agent_url      = google_cloud_run_v2_service.agents["workflow-agent"].uri
  })
}

# Google Cloud Storage Bucket Objects with rendered live content
resource "google_storage_bucket_object" "openapi_spec" {
  name       = "gemini_extension_openapi.yaml"
  bucket     = google_storage_bucket.agent_assets.name
  content    = local.gemini_extension_openapi_yaml_content
  depends_on = [google_cloud_run_v2_service.agents]
}

resource "google_storage_bucket_object" "a2a_agent_card" {
  name       = "a2a_agent_card.json"
  bucket     = google_storage_bucket.agent_assets.name
  content    = local.a2a_agent_card_content
  depends_on = [google_cloud_run_v2_service.agents]
}

resource "google_storage_bucket_object" "gemini_extension_manifest" {
  name       = "gemini_extension_manifest.json"
  bucket     = google_storage_bucket.agent_assets.name
  content    = local.gemini_extension_manifest_content
  depends_on = [google_cloud_run_v2_service.agents]
}
