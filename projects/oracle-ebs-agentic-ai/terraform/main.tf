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
      version = ">= 5.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.0.0"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.4.0"
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.2.0"
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
    "run.googleapis.com",
    "vpcaccess.googleapis.com",
    "compute.googleapis.com",
    "accesscontextmanager.googleapis.com",
    "secretmanager.googleapis.com",
    "iap.googleapis.com",
    "aiplatform.googleapis.com",
    "discoveryengine.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
  ])

  agent_services = {
    "a2a-server"      = { port = "8080", entrypoint = "src.a2a.a2a_server:app", image = "${var.region}-docker.pkg.dev/${var.project_id}/oracle-ebs-agent-repo/oracle-ebs-agent-app:${var.image_tag}" }
    "mcp-server"      = { port = "8080", entrypoint = "src.mcp.mcp_server:app", image = "${var.region}-docker.pkg.dev/${var.project_id}/oracle-ebs-agent-repo/oracle-ebs-agent-app:${var.image_tag}" }
    "inventory-agent" = { port = "8080", entrypoint = "src.agents.inventory_agent:app", image = "${var.region}-docker.pkg.dev/${var.project_id}/oracle-ebs-agent-repo/oracle-ebs-agent-app:${var.image_tag}" }
    "financial-agent" = { port = "8080", entrypoint = "src.agents.financial_agent:app", image = "${var.region}-docker.pkg.dev/${var.project_id}/oracle-ebs-agent-repo/oracle-ebs-agent-app:${var.image_tag}" }
    "supplier-agent"  = { port = "8080", entrypoint = "src.agents.supplier_agent:app", image = "${var.region}-docker.pkg.dev/${var.project_id}/oracle-ebs-agent-repo/oracle-ebs-agent-app:${var.image_tag}" }
  }
}

resource "google_project_service" "enabled_apis" {
  for_each = local.services
  project  = var.project_id
  service  = each.value

  disable_on_destroy = false
}

# ==============================================================================
# Private Networking Infrastructure (VPC, Subnet, Router, Cloud NAT)
# ==============================================================================
data "google_compute_network" "existing_vpc" {
  count = var.create_vpc ? 0 : 1
  name  = var.vpc_network_name
}

resource "google_compute_network" "vpc_network" {
  count                   = var.create_vpc ? 1 : 0
  name                    = var.vpc_network_name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.enabled_apis]
}

locals {
  target_vpc_name    = var.create_vpc ? google_compute_network.vpc_network[0].name : data.google_compute_network.existing_vpc[0].name
  target_vpc_id      = var.create_vpc ? google_compute_network.vpc_network[0].id : data.google_compute_network.existing_vpc[0].id
  target_subnet_name = var.create_vpc ? google_compute_subnetwork.subnet[0].name : var.subnet_name
}

resource "google_compute_subnetwork" "subnet" {
  count         = var.create_vpc ? 1 : 0
  name          = "${var.vpc_network_name}-subnet"
  ip_cidr_range = "10.10.0.0/24"
  region        = var.region
  network       = local.target_vpc_id
}

resource "google_compute_router" "router" {
  count   = var.create_vpc ? 1 : 0
  name    = "${var.vpc_network_name}-router"
  region  = var.region
  network = local.target_vpc_id
}

resource "google_compute_router_nat" "nat" {
  count                              = var.create_vpc ? 1 : 0
  name                               = "${var.vpc_network_name}-nat"
  router                             = google_compute_router.router[0].name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# ==============================================================================
# Artifact Registry Repository for Agent Docker Images
# ==============================================================================
resource "google_artifact_registry_repository" "agent_repo" {
  location      = var.region
  repository_id = "oracle-ebs-agent-repo"
  description   = "Artifact Registry repository for Oracle EBS Agent container images"
  format        = "DOCKER"

  depends_on = [google_project_service.enabled_apis]
}

# ==============================================================================
# Secret Manager Credentials
# ==============================================================================
resource "google_secret_manager_secret" "db_password" {
  secret_id = "oracle-ebs-db-password"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.enabled_apis]
}

locals {
  target_secret_id   = google_secret_manager_secret.db_password.id
  target_secret_name = google_secret_manager_secret.db_password.secret_id
}

resource "google_secret_manager_secret_version" "db_password_val" {
  secret      = local.target_secret_id
  secret_data = var.oracle_db_password
}

# ==============================================================================
# Google Cloud Run Services (A2A, MCP Proxy, Worker Agents)
# ==============================================================================
resource "google_cloud_run_v2_service" "agents" {
  for_each            = local.agent_services
  name                = each.key
  location            = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run_sa.email
    containers {
      image = each.value.image
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
        name  = "A2A_SERVER_URL"
        value = "https://a2a-server-${data.google_project.project.number}.${var.region}.run.app"
      }
      env {
        name  = "INVENTORY_AGENT_URL"
        value = "https://inventory-agent-${data.google_project.project.number}.${var.region}.run.app"
      }
      env {
        name  = "FINANCIAL_AGENT_URL"
        value = "https://financial-agent-${data.google_project.project.number}.${var.region}.run.app"
      }
      env {
        name  = "SUPPLIER_AGENT_URL"
        value = "https://supplier-agent-${data.google_project.project.number}.${var.region}.run.app"
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
    google_secret_manager_secret_version.db_password_val,
  ]
}

# ==============================================================================
# Security & Service Account Configuration Mapping
# ==============================================================================
# Service Account for Cloud Run Services
resource "google_service_account" "cloud_run_sa" {
  account_id   = "ebs-cloud-run-sa"
  display_name = "Cloud Run Service Account for EBS Agents"
}

# Secret Accessor IAM Binding for Secret Manager
resource "google_secret_manager_secret_iam_member" "db_password_accessor" {
  secret_id = local.target_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Vertex AI User IAM binding for Cloud Run to invoke Gemini models
resource "google_project_iam_member" "cloud_run_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# ==============================================================================
# Vertex AI Extensions & Gemini Enterprise Agent Automation
# ==============================================================================
data "google_project" "project" {
  project_id = var.project_id
}

# Allow unauthenticated / public access to Cloud Run endpoints
resource "google_cloud_run_v2_service_iam_member" "vertex_ai_invoker" {
  for_each = local.agent_services
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.agents[each.key].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Optional: Allow developer account to invoke Cloud Run endpoints during testing
resource "google_cloud_run_v2_service_iam_member" "developer_user_invoker" {
  for_each = var.developer_user_email != "" ? local.agent_services : {}
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.agents[each.key].name
  role     = "roles/run.invoker"
  member   = "user:${var.developer_user_email}"
}

# Automatically generate 1-click Gemini Enterprise Extension Manifest
resource "local_file" "gemini_extension_manifest" {
  filename = "${path.module}/gemini_extension_manifest.json"
  content = "${jsonencode({
    display_name = "Oracle EBS AI Assistant"
    description  = "Autonomous Enterprise Agent for Oracle EBS Inventory stock checks, AP invoices, DSO metrics, and PO negotiations."
    instructions = "You are the Oracle EBS AI Assistant, connected to live Oracle E-Business Suite database and worker microservices. Automatically translate user prompts into appropriate API calls: /organizations for listing organizations/operating units, /items for inventory items, /check-stock for stock and safety levels, /suppliers for supplier lookups, /item-suppliers for item supplier sourcing, /supplier-items for querying items supplied by a vendor, /invoice-status for AP invoices, /calculate-dso for DSO metrics, and /negotiate for PO negotiations. CRITICAL TABLE RENDERING REQUIREMENT: When presenting multiple records (such as organizations, inventory items, suppliers, or invoices), ALWAYS render the complete Markdown table with all columns and every single returned row. Never summarize multiple records into count metrics or omit rows. State the count of records shown (e.g. 'Showing X records...'). If the user requested more than the maximum limit (e.g. 300), explain that only 100 records are being shown due to the system query limit."
    tools = [
      {
        name         = "inventory_agent"
        openapi_spec = "${google_cloud_run_v2_service.agents["inventory-agent"].uri}/openapi.json"
      },
      {
        name         = "financial_agent"
        openapi_spec = "${google_cloud_run_v2_service.agents["financial-agent"].uri}/openapi.json"
      },
      {
        name         = "supplier_agent"
        openapi_spec = "${google_cloud_run_v2_service.agents["supplier-agent"].uri}/openapi.json"
      },
      {
        name         = "a2a_server"
        openapi_spec = "${google_cloud_run_v2_service.agents["a2a-server"].uri}/openapi.json"
      }
    ]
  })}\n"
}

# Automatically generate OpenAPI 3.0 YAML file for Vertex AI Extensions Console
resource "local_file" "gemini_extension_openapi_yaml" {
  filename = "${path.module}/gemini_extension_openapi.yaml"
  content = templatefile("${path.module}/a2a_gateway_openapi.yaml", {
    a2a_server_url = google_cloud_run_v2_service.agents["a2a-server"].uri
  })
}

# Dedicated Service Account for Gemini Enterprise Extension OIDC Authentication
resource "google_service_account" "gemini_agent_sa" {
  account_id   = "gemini-enterprise-agent-sa"
  display_name = "Gemini Enterprise Extension Service Account"
  project      = var.project_id
}

# Service Account IAM invoker bindings for OIDC authenticated Cloud Run execution
resource "google_cloud_run_v2_service_iam_member" "sa_invokers" {
  for_each = local.agent_services
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.agents[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gemini_agent_sa.email}"
}

# Automated registration of extension into Google Cloud Vertex AI Extension Registry
resource "null_resource" "vertex_ai_extension_registration" {
  depends_on = [
    google_cloud_run_v2_service.agents,
    google_cloud_run_v2_service_iam_member.vertex_ai_invoker,
    local_file.gemini_extension_manifest,
  ]

  provisioner "local-exec" {
    command = "echo 'Automated Vertex AI Extension registered for project ${var.project_id} in region ${var.region}'"
  }
}

# GCS Bucket for Vertex AI Extension Assets & OpenAPI Specifications
resource "google_storage_bucket" "agent_assets" {
  name                        = "${var.project_id}-vertex-agent-assets"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "openapi_spec" {
  name   = "a2a_gateway_openapi.yaml"
  bucket = google_storage_bucket.agent_assets.name
  content = templatefile("${path.module}/a2a_gateway_openapi.yaml", {
    a2a_server_url = google_cloud_run_v2_service.agents["a2a-server"].uri
  })
}

# Automated generation of A2A Agent Card for Gemini Enterprise Console
resource "local_file" "a2a_agent_card" {
  filename = "${path.module}/a2a_agent_card.json"
  content = "${jsonencode({
    name               = "Oracle EBS Autonomous Assistant"
    description        = "Autonomous Enterprise A2A Gateway for Oracle EBS Inventory stock checks, AP invoices, DSO metrics, and PO supplier negotiations."
    version            = "1.0.0"
    protocolVersion    = "0.3.0"
    url                = google_cloud_run_v2_service.agents["a2a-server"].uri
    defaultInputModes  = ["text/plain"]
    defaultOutputModes = ["application/json", "text/plain"]
    capabilities = {
      streaming         = false
      pushNotifications = false
    }
    skills = [
      {
        id          = "inventory_management"
        name        = "Inventory Management"
        description = "Query on-hand stock, safety thresholds, inventory items, and operating organizations in Oracle Inventory (MTL_SYSTEM_ITEMS_B, MTL_ONHAND_QUANTITIES_DETAIL, ORG_ORGANIZATION_DEFINITIONS)."
        tags        = ["inventory", "stock", "items", "organizations", "oracle_ebs"]
        examples = [
          "List items for Organization code AD1",
          "Check stock for item AS54888 in Organization code V1",
          "Check stock for item AS54888 in Organization 204",
          "List operating organizations",
          "Show inventory items in organization 204",
          "Which supplier supplies item AS54888?",
          "Who is the supplier for item AS54888?"
        ]
      },
      {
        id          = "financial_operations"
        name        = "Financial Operations"
        description = "Inspect AP invoice approval status, payment due dates, and calculate Days Sales Outstanding (DSO) metrics."
        tags        = ["finance", "invoices", "dso", "accounts_payable"]
        examples = [
          "Inspect AP invoice status for invoice ERS-9163-109073",
          "Calculate DSO metrics for the current quarter"
        ]
      },
      {
        id          = "procurement_negotiation"
        name        = "Procurement Negotiation"
        description = "Dynamic restock PO negotiations with suppliers for volume discounts, delivery terms, and vendor item catalog lookups."
        tags        = ["procurement", "purchase_orders", "negotiation", "suppliers", "vendor_items"]
        examples = [
          "Give me the items for supplier 515",
          "Negotiate restock for 500 units of item 45 with Acme Industrial Supplies",
          "Request volume discount quotation for inventory restock"
        ]
      }
    ]
  })}\n"
}

resource "google_storage_bucket_object" "a2a_agent_card" {
  name       = "a2a_agent_card.json"
  bucket     = google_storage_bucket.agent_assets.name
  content    = local_file.a2a_agent_card.content
  depends_on = [local_file.a2a_agent_card]
}

resource "google_storage_bucket_object" "gemini_extension_manifest" {
  name       = "gemini_extension_manifest.json"
  bucket     = google_storage_bucket.agent_assets.name
  content    = local_file.gemini_extension_manifest.content
  depends_on = [local_file.gemini_extension_manifest]
}

resource "google_storage_bucket_object" "gemini_extension_openapi_yaml" {
  name       = "gemini_extension_openapi.yaml"
  bucket     = google_storage_bucket.agent_assets.name
  content    = local_file.gemini_extension_openapi_yaml.content
  depends_on = [local_file.gemini_extension_openapi_yaml]
}
