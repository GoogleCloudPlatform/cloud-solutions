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
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.0"
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
  required_apis = [
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "orgpolicy.googleapis.com",
    "iam.googleapis.com",
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "dialogflow.googleapis.com",
    "discoveryengine.googleapis.com",
    "compute.googleapis.com",
    "iap.googleapis.com",
    "secretmanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

data "google_project" "project" {
  project_id = var.project_id
}

# 1. BigQuery Dataset
resource "google_bigquery_dataset" "cymbal_demo" {
  project                    = var.project_id
  dataset_id                 = "cymbal_demo_${replace(var.project_id, "-", "_")}"
  friendly_name              = "Cymbal Demo Dataset"
  description                = "Dataset for storing support tickets for the Cymbal Demo"
  location                   = "US"
  delete_contents_on_destroy = false

  depends_on = [google_project_service.apis]
}

# 2. BigQuery Table
resource "google_bigquery_table" "support_tickets" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.cymbal_demo.dataset_id
  table_id            = "support_tickets"
  deletion_protection = false

  schema = <<EOF
[
  {
    "name": "ticket_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Unique Ticket UUID"
  },
  {
    "name": "account",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "User's bank account number"
  },
  {
    "name": "isin",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Financial instrument ISIN code"
  },
  {
    "name": "reference_id",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "External transaction reference ID"
  },
  {
    "name": "description",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "User issue detail description"
  },
  {
    "name": "status",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Ticket status: open, in-progress, resolved"
  },
  {
    "name": "created_at",
    "type": "TIMESTAMP",
    "mode": "NULLABLE",
    "description": "Ticket creation time"
  },
  {
    "name": "resolution",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Resolution summary entered by agent"
  }
]
EOF
}

# 2.1 BigQuery Dataset & Table for Cymbal Support Agent Metrics (query_bigquery_metrics)
resource "google_bigquery_dataset" "ds1" {
  project                    = var.project_id
  dataset_id                 = "ds1_${replace(var.project_id, "-", "_")}"
  friendly_name              = "Cymbal Support Agent Metrics Dataset"
  description                = "Dataset for storing real-time metrics queried by cymbal_support_agent"
  location                   = "US"
  delete_contents_on_destroy = false

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_table" "t1" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.ds1.dataset_id
  table_id            = "t1"
  deletion_protection = false

  schema = <<EOF
[
  {
    "name": "c1",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Metric name / identifier"
  },
  {
    "name": "c2",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Metric value / status"
  },
  {
    "name": "c3",
    "type": "INTEGER",
    "mode": "NULLABLE",
    "description": "Metric ranking or sequence number"
  }
]
EOF
}

# 3. Artifact Registry Repo
resource "google_artifact_registry_repository" "repo" {
  project       = var.project_id
  location      = var.region
  repository_id = "cymbal-demo-repo-${var.project_id}"
  description   = "Docker repository for Cymbal Demo"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

# 5. Cloud Run Runtime Service Account
resource "google_service_account" "cloud_run_sa" {
  project      = var.project_id
  account_id   = "cymbal-run-sa"
  display_name = "Service Account for Cloud Run Services"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# 5.1 Secret Manager for SECRET_KEY
resource "google_secret_manager_secret" "secret_key" {
  project   = var.project_id
  secret_id = "cymbal-secret-key-${var.project_id}"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "secret_key_val" {
  secret      = google_secret_manager_secret.secret_key.id
  secret_data = "cymbal-secure-secret-999"
}

resource "google_secret_manager_secret_iam_member" "sa_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.secret_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# 6. Cloud Run Webhook Service (cymbal-gecx-webhook)
resource "google_cloud_run_v2_service" "webhook" {
  project             = var.project_id
  name                = "cymbal-gecx-webhook-${var.project_id}"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/cymbal-bff:${var.image_tag}"

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "DF_AGENT_ID"
        value = google_dialogflow_cx_agent.agent.name
      }
      env {
        name  = "CONVERSATION_PROFILE_ID"
        value = var.conversation_profile_id
      }
      env {
        name  = "BQ_DATASET_ID"
        value = google_bigquery_dataset.cymbal_demo.dataset_id
      }
      env {
        name  = "BQ_TABLE_ID"
        value = google_bigquery_table.support_tickets.table_id
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.repo,
    google_dialogflow_cx_agent.agent,
    google_secret_manager_secret_version.secret_key_val
  ]
}

# IAM Auth for all users (anonymous) to invoke Webhook
resource "google_cloud_run_v2_service_iam_member" "gecx_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.webhook.location
  name     = google_cloud_run_v2_service.webhook.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# 7. Cloud Run Web Service (cymbal-bff-web)
resource "google_cloud_run_v2_service" "web" {
  project             = var.project_id
  name                = "cymbal-bff-web-${var.project_id}"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/cymbal-bff:${var.image_tag}"

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "DF_AGENT_ID"
        value = google_dialogflow_cx_agent.agent.name
      }
      env {
        name  = "CONVERSATION_PROFILE_ID"
        value = var.conversation_profile_id != "" ? var.conversation_profile_id : google_dialogflow_conversation_profile.coach_profiles["ai-coach"].id
      }
      env {
        name  = "BQ_DATASET_ID"
        value = google_bigquery_dataset.cymbal_demo.dataset_id
      }
      env {
        name  = "BQ_TABLE_ID"
        value = google_bigquery_table.support_tickets.table_id
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.repo,
    google_dialogflow_cx_agent.agent,
    google_secret_manager_secret_version.secret_key_val
  ]
}

# IAM Auth for all users (anonymous) to invoke Web Service
resource "google_cloud_run_v2_service_iam_member" "web_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.web.location
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Serverless NEG for HTTP Load Balancer
resource "google_compute_region_network_endpoint_group" "neg" {
  project               = var.project_id
  name                  = "cymbal-web-neg-${var.project_id}"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  cloud_run {
    service = google_cloud_run_v2_service.web.name
  }

  depends_on = [google_project_service.apis]
}

# Backend Service for HTTPS Load Balancer with IAP
resource "google_compute_backend_service" "web_backend" {
  project               = var.project_id
  name                  = "cymbal-web-backend-${var.project_id}"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL"

  backend {
    group = google_compute_region_network_endpoint_group.neg.id
  }

  depends_on = [google_project_service.apis]
}

# URL Map
resource "google_compute_url_map" "default" {
  project         = var.project_id
  name            = "cymbal-web-urlmap-${var.project_id}"
  default_service = google_compute_backend_service.web_backend.id

  depends_on = [google_project_service.apis]
}

# Target HTTP Proxy
resource "google_compute_target_http_proxy" "default" {
  project = var.project_id
  name    = "cymbal-web-target-proxy-${var.project_id}"
  url_map = google_compute_url_map.default.id

  depends_on = [google_project_service.apis]
}

# Global Forwarding Rule
resource "google_compute_global_forwarding_rule" "default" {
  project               = var.project_id
  name                  = "cymbal-web-forwarding-rule-${var.project_id}"
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.default.id
  load_balancing_scheme = "EXTERNAL"

  depends_on = [google_project_service.apis]
}



# 8. GECX Dialogflow CX Agent Resource
resource "google_dialogflow_cx_agent" "agent" {
  project               = var.project_id
  display_name          = "Cymbal Support Agent"
  location              = var.region
  default_language_code = "en"
  time_zone             = "America/New_York"
  description           = "Cymbal customer support agent for ticket intake and PIN verification"

  depends_on = [google_project_service.apis]
}

# 9. IAM role bindings for GECX/CES service agent
resource "google_project_iam_member" "ces_dialogflow_client" {
  project = var.project_id
  role    = "roles/dialogflow.client"
  member  = "serviceAccount:${var.ces_service_agent}"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "ces_discoveryengine_viewer" {
  project = var.project_id
  role    = "roles/discoveryengine.viewer"
  member  = "serviceAccount:${var.ces_service_agent}"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "ces_bigquery_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${var.ces_service_agent}"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "ces_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.ces_service_agent}"

  depends_on = [google_project_service.apis]
}


resource "google_project_iam_member" "cloud_run_df_client" {
  project = var.project_id
  role    = "roles/dialogflow.admin"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "cloudbuild_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "compute_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "compute_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}
