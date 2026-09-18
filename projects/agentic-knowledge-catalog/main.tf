# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
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
      version = ">= 5.45.2, < 7.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.45.2, < 7.0.0"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.9.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
    external = {
      source  = "hashicorp/external"
      version = ">= 2.3.0"
    }
  }
}

# 1. Project ID Dynamic Resolution and Provider Configuration
data "external" "gcloud_project" {
  program = ["sh", "-c", "echo \"{\\\"project\\\": \\\"$(gcloud config get-value project 2>/dev/null)\\\"}\""]
}

locals {
  gcp_project_id = var.gcp_project_id != "" ? var.gcp_project_id : data.external.gcloud_project.result.project
}

provider "google" {
  project = local.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}

provider "google-beta" {
  project = local.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}

data "google_project" "project" {
  project_id = local.gcp_project_id
  depends_on = [google_project_service.apis]
}

# 2. Google Cloud API Enablement
resource "google_project_service" "apis" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "bigquery.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "bigquerydatatransfer.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "aiplatform.googleapis.com",
    "notebooks.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "storage.googleapis.com",
    "datacatalog.googleapis.com",
    "dataplex.googleapis.com",
    "datalineage.googleapis.com",
    "cloudaicompanion.googleapis.com",
    "bigqueryunified.googleapis.com",
    "geminidataanalytics.googleapis.com",
    "dataform.googleapis.com",
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com"
  ])

  project            = local.gcp_project_id
  service            = each.key
  disable_on_destroy = false
}

# 3. Managed Service Identities and IAM Propagation
resource "google_project_service_identity" "dataplex_sa" {
  provider = google-beta
  project  = local.gcp_project_id
  service  = "dataplex.googleapis.com"

  depends_on = [google_project_service.apis]
}

resource "google_project_service_identity" "bq_transfer_sa" {
  provider = google-beta
  project  = local.gcp_project_id
  service  = "bigquerydatatransfer.googleapis.com"

  depends_on = [google_project_service.apis]
}

resource "google_project_service_identity" "vertex_ai_sa" {
  provider = google-beta
  project  = local.gcp_project_id
  service  = "aiplatform.googleapis.com"

  depends_on = [google_project_service.apis]
}

resource "time_sleep" "wait_for_service_agents" {
  depends_on = [
    google_project_service_identity.dataplex_sa,
    google_project_service_identity.bq_transfer_sa,
    google_project_service_identity.vertex_ai_sa
  ]

  create_duration = "30s"
}

# 4. Isolated VPC Network Architecture
resource "google_compute_network" "vpc" {
  name                    = "adc-demo-vpc"
  auto_create_subnetworks = false
  project                 = local.gcp_project_id

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "private_subnet" {
  name                     = "adc-demo-private-subnet-${var.gcp_region}"
  ip_cidr_range            = "10.0.100.0/24"
  region                   = var.gcp_region
  network                  = google_compute_network.vpc.id
  project                  = local.gcp_project_id
  private_ip_google_access = true
}

resource "google_project_iam_member" "vertex_ai_network_user" {
  project    = local.gcp_project_id
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:${google_project_service_identity.vertex_ai_sa.email}"
  depends_on = [time_sleep.wait_for_service_agents]
}

# 5. BigQuery Dataset & Governance Setup
resource "google_bigquery_dataset" "thelook" {
  dataset_id                  = var.dataset_id
  friendly_name               = "TheLook eCommerce"
  description                 = "Cloned public dataset thelook_ecommerce for Agentic Data Cloud Demo"
  location                    = var.gcp_region
  default_table_expiration_ms = null
  project                     = local.gcp_project_id
  delete_contents_on_destroy  = true

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset_iam_member" "dataplex_editor" {
  dataset_id = google_bigquery_dataset.thelook.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_project_service_identity.dataplex_sa.email}"
  project    = local.gcp_project_id

  depends_on = [time_sleep.wait_for_service_agents]
}

resource "google_project_iam_member" "dataplex_job_user" {
  project    = local.gcp_project_id
  role       = "roles/bigquery.jobUser"
  member     = "serviceAccount:${google_project_service_identity.dataplex_sa.email}"
  depends_on = [time_sleep.wait_for_service_agents]
}

resource "google_bigquery_connection" "vertex_connection" {
  connection_id = "vertex-connection"
  project       = local.gcp_project_id
  location      = var.gcp_region
  friendly_name = "Vertex AI Connection"
  description   = "Connection to Vertex AI for remote models"
  cloud_resource {}

  depends_on = [google_project_service.apis]
}

resource "time_sleep" "wait_for_connection_sa" {
  depends_on      = [google_bigquery_connection.vertex_connection]
  create_duration = "30s"
}

resource "google_project_iam_member" "vertex_connection_aiplatform_user" {
  project    = local.gcp_project_id
  role       = "roles/aiplatform.user"
  member     = "serviceAccount:${google_bigquery_connection.vertex_connection.cloud_resource[0].service_account_id}"
  depends_on = [time_sleep.wait_for_connection_sa]
}

# 6. Automated Public Dataset Replication (BigQuery Data Transfer Service)
resource "google_service_account" "bootstrap_sa" {
  account_id   = "adc-bootstrap-sa"
  display_name = "ADC Lab Bootstrap Service Account"
  project      = local.gcp_project_id

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "bootstrap_sa_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser"
  ])

  project = local.gcp_project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.bootstrap_sa.email}"
}

resource "google_service_account_iam_member" "bq_transfer_impersonation" {
  for_each = toset([
    "roles/iam.serviceAccountTokenCreator",
    "roles/iam.serviceAccountShortTermTokenMinter"
  ])

  service_account_id = google_service_account.bootstrap_sa.name
  role               = each.key
  member             = "serviceAccount:${google_project_service_identity.bq_transfer_sa.email}"
  depends_on         = [time_sleep.wait_for_service_agents]
}

resource "time_sleep" "wait_for_bq_transfer_impersonation" {
  depends_on = [
    google_service_account_iam_member.bq_transfer_impersonation,
    google_project_iam_member.bootstrap_sa_roles
  ]

  create_duration = "90s"
}

resource "google_bigquery_data_transfer_config" "thelook_copy" {
  depends_on = [
    google_project_service.apis,
    google_bigquery_dataset.thelook,
    time_sleep.wait_for_bq_transfer_impersonation
  ]

  display_name           = "thelook-ecommerce-copy"
  location               = var.gcp_region
  data_source_id         = "cross_region_copy"
  destination_dataset_id = google_bigquery_dataset.thelook.dataset_id
  project                = local.gcp_project_id
  service_account_name   = google_service_account.bootstrap_sa.email

  params = {
    source_project_id           = "bigquery-public-data"
    source_dataset_id           = "thelook_ecommerce"
    overwrite_destination_table = "true"
  }

  schedule = "every 24 hours"
}

# 7. Colab Enterprise Runtime Template Provisioning
resource "random_id" "colab_suffix" {
  byte_length = 4
}

resource "google_colab_runtime_template" "colab_template" {
  name         = "adc-demo-template-${random_id.colab_suffix.hex}"
  display_name = "Colab Runtime Template (${var.gcp_region})"
  location     = var.gcp_region
  description  = "Colab Enterprise Runtime Template for Agentic Knowledge Catalog"
  project      = local.gcp_project_id

  machine_spec {
    machine_type = var.colab_machine_type
  }

  network_spec {
    enable_internet_access = true
    network                = google_compute_network.vpc.id
    subnetwork             = google_compute_subnetwork.private_subnet.id
  }

  shielded_vm_config {
    enable_secure_boot = true
  }

  depends_on = [
    google_compute_subnetwork.private_subnet,
    google_project_iam_member.vertex_ai_network_user
  ]
}

# 8. Cloud Storage Bucket & Lab Notebook Hydration
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "notebook_bucket" {
  name                        = "adc-demo-${local.gcp_project_id}-${random_id.bucket_suffix.hex}"
  location                    = var.gcp_region
  project                     = local.gcp_project_id
  force_destroy               = true
  uniform_bucket_level_access = true

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_object" "notebooks" {
  for_each = {
    "01_data_profile_quality.ipynb"     = "${path.module}/analytics/notebooks/01_data_profile_quality.ipynb"
    "01_data_profile_quality_ko.ipynb"  = "${path.module}/analytics/notebooks/01_data_profile_quality_ko.ipynb"
    "02_data_insight.ipynb"             = "${path.module}/analytics/notebooks/02_data_insight.ipynb"
    "02_data_insight_ko.ipynb"          = "${path.module}/analytics/notebooks/02_data_insight_ko.ipynb"
    "03_dataset_insights.ipynb"         = "${path.module}/analytics/notebooks/03_dataset_insights.ipynb"
    "03_dataset_insights_ko.ipynb"      = "${path.module}/analytics/notebooks/03_dataset_insights_ko.ipynb"
    "04_glossary_setup.ipynb"           = "${path.module}/analytics/notebooks/04_glossary_setup.ipynb"
    "04_glossary_setup_ko.ipynb"        = "${path.module}/analytics/notebooks/04_glossary_setup_ko.ipynb"
    "05_graph_analysis.ipynb"           = "${path.module}/analytics/notebooks/05_graph_analysis.ipynb"
    "05_graph_analysis_ko.ipynb"        = "${path.module}/analytics/notebooks/05_graph_analysis_ko.ipynb"
    "06_bigquery_ai_ml_demo.ipynb"      = "${path.module}/analytics/notebooks/06_bigquery_ai_ml_demo.ipynb"
    "06_bigquery_ai_ml_demo_ko.ipynb"   = "${path.module}/analytics/notebooks/06_bigquery_ai_ml_demo_ko.ipynb"
    "07_bigquery_ai_functions.ipynb"    = "${path.module}/analytics/notebooks/07_bigquery_ai_functions.ipynb"
    "07_bigquery_ai_functions_ko.ipynb" = "${path.module}/analytics/notebooks/07_bigquery_ai_functions_ko.ipynb"
  }

  name   = each.key
  bucket = google_storage_bucket.notebook_bucket.name
  source = each.value
}

resource "google_storage_bucket_object" "resources" {
  for_each = {
    "resources/business_glossary.json"    = "${path.module}/analytics/resources/business_glossary.json"
    "resources/business_glossary_ko.json" = "${path.module}/analytics/resources/business_glossary_ko.json"
    "resources/agent_test_queries.md"     = "${path.module}/analytics/resources/agent_test_queries.md"
    "resources/agent_test_queries_ko.md"  = "${path.module}/analytics/resources/agent_test_queries_ko.md"
  }

  name   = each.key
  bucket = google_storage_bucket.notebook_bucket.name
  source = each.value
}
