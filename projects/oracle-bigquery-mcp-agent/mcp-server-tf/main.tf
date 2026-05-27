terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

locals {
  resolved_region = coalesce(var.region, "us-central1")
}

provider "google" {
  project               = var.project_id
  region                = local.resolved_region
  billing_project       = var.project_id
  user_project_override = true

  dialogflow_cx_custom_endpoint = "https://${local.resolved_region}-dialogflow.mtls.googleapis.com/v3/"
}

# Dynamically queries the compute instance metadata properties to extract the live internal private IP address, preventing static configuration mismatches.
data "google_compute_instance" "oracle_vm" {
  name    = var.oracle_vm_name
  zone    = var.zone
  project = var.project_id
}

# Dynamic lookup of the target VPC subnetwork to retrieve the self-link for Serverless VPC Access Connector peering.
data "google_compute_subnetwork" "oracle_subnet" {
  name    = var.subnetwork_name
  project = var.project_id
  region  = local.resolved_region
}

# Declarative custom dedicated Service Account for the Cloud Run MCP server to adhere to SRE least privilege standards
resource "google_service_account" "mcp_sa" {
  account_id   = "oracle-mcp-sa"
  display_name = "Oracle MCP Serverless Connector Service Account"
  project      = var.project_id
}

# Declarative Cloud Run v2 Service deployment hosting the FastAPI Model Context Protocol server
resource "google_cloud_run_v2_service" "mcp_connector" {
  name                = var.service_name
  location            = local.resolved_region
  project             = var.project_id
  deletion_protection = false

  depends_on = [
    google_project_service.run_api,
    google_project_service.secretmanager_api
  ]

  template {
    service_account = google_service_account.mcp_sa.email

    # Establishes a serverless VPC network connector, routing outbound database queries privately into the VPC subnetwork.
    vpc_access {
      network_interfaces {
        subnetwork = data.google_compute_subnetwork.oracle_subnet.name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.container_image

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "DB_USER"
        value = var.oracle_db_user
      }
      # Mounts the database master password directly from Secret Manager at container instantiation time.
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret_name
            version = "latest"
          }
        }
      }
      env {
        name  = "DB_DSN"
        value = "${data.google_compute_instance.oracle_vm.network_interface[0].network_ip}:1521/ORCLPDB1"
      }
      env {
        name  = "VERTEX_REGION"
        value = local.resolved_region
      }
      env {
        name  = "AGENT_ID"
        value = var.agent_id
      }
      env {
        name  = "LOOKER_DASHBOARD_URL"
        value = var.looker_dashboard_url
      }
    }
  }

  # Ignores minor client-side metadata and automated image digest overrides to prevent Terraform from attempting destructive container recycles on drift.
  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
    ]
  }
}

# Dynamically queries target Google Cloud project metadata numbers required to construct service account email strings.
data "google_project" "project" {
  project_id = var.project_id
}

# Grants Secret Manager Accessor permission on the database password secret strictly to the custom Cloud Run Service Account.
resource "google_secret_manager_secret_iam_member" "mcp_secret_accessor" {
  project   = var.project_id
  secret_id = var.db_password_secret_name
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mcp_sa.email}"
}

# Grants Vertex AI User permissions to the custom Service Account, enabling the MCP server to generate gecko text-embeddings on startup.
resource "google_project_iam_member" "mcp_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.mcp_sa.email}"
}

# Grant Artifact Registry Writer role to the default Compute Service Account for serverless builds
resource "google_project_iam_member" "compute_artifact_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Grant Artifact Registry Writer role to the Cloud Build Service Account for serverless builds
resource "google_project_iam_member" "cloudbuild_artifact_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

# Grant Storage Object Viewer role to the default Compute Service Account for serverless builds
resource "google_project_iam_member" "compute_storage_object_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Grant Storage Object Viewer role to the Cloud Build Service Account for serverless builds
resource "google_project_iam_member" "cloudbuild_storage_object_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

# Establishes the Dialogflow CX integration webhook, linking chatbot playbooks directly to the secure Cloud Run FastAPI microservice.
resource "google_dialogflow_cx_webhook" "mcp_webhook" {
  parent       = "projects/${var.project_id}/locations/${local.resolved_region}/agents/${var.agent_id}"
  display_name = "Oracle_MCP_Middleware_Connector"

  generic_web_service {
    uri = "${google_cloud_run_v2_service.mcp_connector.uri}/tools/call"
  }
}
