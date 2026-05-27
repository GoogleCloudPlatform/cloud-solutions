terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Resource definitions for Looker (Google Cloud Core) Instance deployment
resource "google_looker_instance" "reporting_core" {
  name             = var.instance_name
  platform_edition = var.edition
  region           = var.region
  project          = var.project_id

  depends_on = [
    google_project_service.looker_api
  ]

  # Enables public IP routing to authorize direct OIDC developer console dashboard queries.
  # In production environments, set private_ip_enabled = true and public_ip_enabled = false to enforce strict VPC Service Controls.
  private_ip_enabled = false
  public_ip_enabled  = true

  oauth_config {
    client_id     = var.oauth_client_id
    client_secret = var.oauth_client_secret
  }
}

output "looker_uri" {
  value       = google_looker_instance.reporting_core.looker_uri
  description = "The public URL of the provisioned Looker Core instance"
}

# Data source to programmatically retrieve the active project number
data "google_project" "active_project" {
  project_id = var.project_id
}

locals {
  looker_sa = "service-${data.google_project.active_project.number}@gcp-sa-looker.iam.gserviceaccount.com"
}

# HCL IAM policy bindings authorizing Looker Service Account to query BigQuery datasets
resource "google_project_iam_member" "looker_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${local.looker_sa}"

  depends_on = [
    google_project_service.iam_api
  ]
}

resource "google_project_iam_member" "looker_bq_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${local.looker_sa}"
}

resource "google_project_iam_member" "looker_bq_user" {
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${local.looker_sa}"
}

resource "google_project_iam_member" "looker_bq_metadata_viewer" {
  project = var.project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:${local.looker_sa}"
}



resource "google_project_iam_member" "looker_project_viewer" {
  project = var.project_id
  role    = "roles/viewer"
  member  = "serviceAccount:${local.looker_sa}"
}
