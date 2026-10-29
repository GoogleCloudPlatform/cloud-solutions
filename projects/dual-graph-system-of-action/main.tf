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

data "external" "gcloud_project" {
  count   = var.gcp_project_id == "" ? 1 : 0
  program = ["sh", "-c", "echo \"{\\\"project\\\": \\\"$(gcloud config get-value project 2>/dev/null || true)\\\"}\""]
}

locals {
  gcp_project_id = var.gcp_project_id != "" ? var.gcp_project_id : data.external.gcloud_project[0].result["project"]
  base_apis = [
    "spanner.googleapis.com",
    "bigquery.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "dataplex.googleapis.com",
    "aiplatform.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "logging.googleapis.com",
    "storage.googleapis.com",
  ]
  enable_iap            = var.argolis || var.enable_iap
  enabled_apis          = local.enable_iap ? concat(local.base_apis, ["iap.googleapis.com"]) : local.base_apis
  spanner_connection_id = "${local.gcp_project_id}.${var.gcp_region}.${google_bigquery_connection.spanner_data_boost.connection_id}"
  spanner_ddl_statements = [
    for stmt in split(";", replace(file("${path.module}/data/spanner_schema.sql"), "/(?m)^--.*$/", "")) :
    trimspace(stmt)
    if trimspace(stmt) != ""
  ]
  app_build_triggers = {
    dockerfile_hash   = filesha256("${path.module}/app/Dockerfile")
    main_py_hash      = filesha256("${path.module}/app/main.py")
    workflow_hash     = filesha256("${path.module}/app/agent/workflow.py")
    bq_lineage_hash   = filesha256("${path.module}/app/agent/bq_lineage.py")
    glossary_hash     = filesha256("${path.module}/data/policies/business_glossary.json")
    policy_md_hash    = filesha256("${path.module}/data/policies/return_policy_v1.md")
    u2g_triples_hash  = filesha256("${path.module}/data/policies/u2g_policy_triples.json")
    shop_html_hash    = filesha256("${path.module}/app/frontend/shop.html")
    console_html_hash = filesha256("${path.module}/app/frontend/console.html")
    shop_js_hash      = filesha256("${path.module}/app/frontend/static/shop.js")
    console_js_hash   = filesha256("${path.module}/app/frontend/static/console.js")
    products_img_hash = sha256(join(",", [for f in fileset("${path.module}/app/frontend/static/products", "*.png") : filesha256("${path.module}/app/frontend/static/products/${f}")]))
    seed_py_hash      = filesha256("${path.module}/data/spanner_seed.py")
    qwiklab_sh_hash   = filesha256("${path.module}/scripts/qwiklab.sh")
  }
}

resource "google_project_service" "apis" {
  for_each           = toset(local.enabled_apis)
  project            = local.gcp_project_id
  service            = each.key
  disable_on_destroy = false
}

data "google_project" "current" {
  project_id = local.gcp_project_id
  depends_on = [google_project_service.apis]
}

data "google_client_openid_userinfo" "me" {
  count = local.enable_iap ? 1 : 0
}

# 1. Cloud Spanner Enterprise Instance and OperationalContextGraph Database
resource "google_spanner_instance" "soa_instance" {
  name                         = var.spanner_instance_id
  config                       = "regional-${var.gcp_region}"
  display_name                 = "Dual-Graph System of Action"
  edition                      = "ENTERPRISE"
  processing_units             = 100
  project                      = local.gcp_project_id
  force_destroy                = true
  default_backup_schedule_type = "NONE"

  depends_on = [google_project_service.apis]
}

resource "google_spanner_database" "soa_database" {
  instance            = google_spanner_instance.soa_instance.name
  name                = var.spanner_database_id
  project             = local.gcp_project_id
  ddl                 = local.spanner_ddl_statements
  deletion_protection = false
}

# 2. BigQuery Action Lineage Dataset, Tables, and Spanner Data Boost Connection
resource "google_bigquery_dataset" "action_lineage" {
  dataset_id                 = var.bigquery_dataset_id
  friendly_name              = "System of Action Lineage Graph"
  description                = "Action Lineage Graph dataset for ADK 2.0 refund workflow traces"
  location                   = var.gcp_region
  project                    = local.gcp_project_id
  delete_contents_on_destroy = true

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_table" "agent_sessions" {
  dataset_id          = google_bigquery_dataset.action_lineage.dataset_id
  table_id            = "agent_sessions"
  project             = local.gcp_project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "trace_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "INT64", mode = "REQUIRED" },
    { name = "target_order_id", type = "INT64", mode = "NULLABLE" },
    { name = "user_prompt", type = "STRING", mode = "REQUIRED" },
    { name = "started_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "workflow_nodes" {
  dataset_id          = google_bigquery_dataset.action_lineage.dataset_id
  table_id            = "workflow_nodes"
  project             = local.gcp_project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "node_exec_id", type = "STRING", mode = "REQUIRED" },
    { name = "trace_id", type = "STRING", mode = "REQUIRED" },
    { name = "node_name", type = "STRING", mode = "REQUIRED" },
    { name = "step_order", type = "INT64", mode = "REQUIRED" },
    { name = "latency_ms", type = "FLOAT64", mode = "REQUIRED" },
    { name = "executed_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "policy_evaluations" {
  dataset_id          = google_bigquery_dataset.action_lineage.dataset_id
  table_id            = "policy_evaluations"
  project             = local.gcp_project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "eval_id", type = "STRING", mode = "REQUIRED" },
    { name = "node_exec_id", type = "STRING", mode = "REQUIRED" },
    { name = "trace_id", type = "STRING", mode = "REQUIRED" },
    { name = "catalog_term_id", type = "STRING", mode = "REQUIRED" },
    { name = "policy_id", type = "STRING", mode = "REQUIRED" },
    { name = "policy_name", type = "STRING", mode = "REQUIRED" },
    { name = "observed_refunds_100d", type = "INT64", mode = "REQUIRED" },
    { name = "max_refunds_100d", type = "INT64", mode = "REQUIRED" },
    { name = "observed_order_age_days", type = "INT64", mode = "NULLABLE" },
    { name = "return_window_days", type = "INT64", mode = "REQUIRED" },
    { name = "evaluation_result", type = "STRING", mode = "REQUIRED" },
    { name = "evaluated_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "agent_actions" {
  dataset_id          = google_bigquery_dataset.action_lineage.dataset_id
  table_id            = "agent_actions"
  project             = local.gcp_project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "action_id", type = "STRING", mode = "REQUIRED" },
    { name = "eval_id", type = "STRING", mode = "REQUIRED" },
    { name = "trace_id", type = "STRING", mode = "REQUIRED" },
    { name = "action_type", type = "STRING", mode = "REQUIRED" },
    { name = "decision_status", type = "STRING", mode = "REQUIRED" },
    { name = "rejection_reason", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_connection" "spanner_data_boost" {
  connection_id = "spanner-data-boost"
  project       = local.gcp_project_id
  location      = var.gcp_region
  friendly_name = "Spanner Data Boost Connection"
  description   = "Federated BigQuery to Cloud Spanner Data Boost connection"

  cloud_spanner {
    database        = "projects/${local.gcp_project_id}/instances/${google_spanner_instance.soa_instance.name}/databases/${google_spanner_database.soa_database.name}"
    use_data_boost  = true
    use_parallelism = true
  }

  depends_on = [google_project_service.apis]
}

# 3. Dataplex Knowledge Catalog Aspect Type and Business Glossary
resource "google_dataplex_aspect_type" "refund_metric_contract" {
  aspect_type_id    = "refund-metric-contract"
  location          = "global"
  project           = local.gcp_project_id
  display_name      = "Refund Metric Contract"
  description       = "Governed semantic contract for refund eligibility metrics and customer loyalty tiers"
  metadata_template = <<EOF
{
  "name": "RefundMetricContract",
  "type": "record",
  "recordFields": [
    {
      "name": "returned_status",
      "type": "string",
      "index": 1,
      "annotations": {
        "displayName": "Returned Order Item Status"
      },
      "constraints": {
        "required": true
      }
    },
    {
      "name": "eligible_order_status",
      "type": "string",
      "index": 2,
      "annotations": {
        "displayName": "Eligible Delivered Order Status"
      },
      "constraints": {
        "required": true
      }
    },
    {
      "name": "rolling_window_days",
      "type": "int",
      "index": 3,
      "annotations": {
        "displayName": "Rolling Refund Window Days"
      },
      "constraints": {
        "required": true
      }
    },
    {
      "name": "standard_tier",
      "type": "string",
      "index": 4,
      "annotations": {
        "displayName": "Standard Customer Tier Code"
      },
      "constraints": {
        "required": true
      }
    },
    {
      "name": "vip_tier",
      "type": "string",
      "index": 5,
      "annotations": {
        "displayName": "VIP Customer Tier Code"
      },
      "constraints": {
        "required": true
      }
    }
  ]
}
EOF
  depends_on        = [google_project_service.apis]
}

resource "google_dataplex_glossary" "soa_business_glossary" {
  glossary_id  = "soa-business-glossary"
  location     = "global"
  project      = local.gcp_project_id
  display_name = "System of Action Business Glossary"
  description  = "Governed business glossary for refund metrics, order age, and customer loyalty tiers"

  depends_on = [google_project_service.apis]
}

resource "google_dataplex_glossary_term" "rolling_refund_count" {
  glossary_id  = google_dataplex_glossary.soa_business_glossary.glossary_id
  term_id      = "rolling-100d-refund-count"
  location     = "global"
  project      = local.gcp_project_id
  display_name = "Rolling 100-Day Refund Count"
  description  = "Count of distinct returned order items (order_items.status = 'Returned') for a customer over the trailing 100 days, excluding the target order."
  parent       = "projects/${local.gcp_project_id}/locations/global/glossaries/${google_dataplex_glossary.soa_business_glossary.glossary_id}"
}

resource "google_dataplex_glossary_term" "order_age_days" {
  glossary_id  = google_dataplex_glossary.soa_business_glossary.glossary_id
  term_id      = "order-age-days"
  location     = "global"
  project      = local.gcp_project_id
  display_name = "Order Age in Days"
  description  = "Elapsed days since order delivery (TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), orders.delivered_at, DAY)) for orders with status 'Complete'."
  parent       = "projects/${local.gcp_project_id}/locations/global/glossaries/${google_dataplex_glossary.soa_business_glossary.glossary_id}"
}

resource "google_dataplex_glossary_term" "customer_loyalty_tier" {
  glossary_id  = google_dataplex_glossary.soa_business_glossary.glossary_id
  term_id      = "customer-loyalty-tier"
  location     = "global"
  project      = local.gcp_project_id
  display_name = "Customer Loyalty Tier"
  description  = "Governed loyalty tier classification ('STANDARD' with 10-item refund cap vs. 'VIP' with 20-item refund cap in 100 days)."
  parent       = "projects/${local.gcp_project_id}/locations/global/glossaries/${google_dataplex_glossary.soa_business_glossary.glossary_id}"
}

# 4. Artifact Registry, Cloud Build, and Cloud Run Service Account
resource "google_artifact_registry_repository" "soa_repo" {
  location      = var.gcp_region
  repository_id = "soa-repo"
  description   = "Container repository for the Dual-Graph System of Action Cloud Run application"
  format        = "DOCKER"
  project       = local.gcp_project_id

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "soa_app_sa" {
  account_id   = "soa-app-sa"
  display_name = "Dual-Graph System of Action Cloud Run Service Account"
  project      = local.gcp_project_id

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "soa_app_sa_roles" {
  for_each = toset([
    "roles/spanner.databaseUser",
    "roles/spanner.databaseReaderWithDataBoost",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/bigquery.connectionUser",
    "roles/dataplex.catalogEditor",
    "roles/aiplatform.user",
    "roles/logging.logWriter"
  ])

  project = local.gcp_project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.soa_app_sa.email}"
}

resource "google_project_iam_member" "cloudbuild_sa_roles" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/storage.admin",
    "roles/logging.logWriter"
  ])

  project = local.gcp_project_id
  role    = each.key
  member  = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "compute_sa_build_roles" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/storage.admin",
    "roles/logging.logWriter",
    "roles/cloudbuild.builds.editor"
  ])

  project = local.gcp_project_id
  role    = each.key
  member  = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}

resource "time_sleep" "wait_for_iam" {
  create_duration = "20s"

  depends_on = [
    google_artifact_registry_repository.soa_repo,
    google_project_iam_member.cloudbuild_sa_roles,
    google_project_iam_member.compute_sa_build_roles
  ]
}

module "cli" {
  source  = "terraform-google-modules/gcloud/google"
  version = "~> 4.0"

  platform                 = "linux"
  skip_download            = false
  upgrade                  = false
  gcloud_sdk_version       = "420.0.0"
  service_account_key_file = var.service_account_key_file
  module_depends_on        = [time_sleep.wait_for_iam]

  create_cmd_triggers   = local.app_build_triggers
  create_cmd_entrypoint = "chmod +x ${path.module}/scripts/qwiklab.sh;${path.module}/scripts/qwiklab.sh"
  create_cmd_body       = "${local.gcp_project_id} ${var.gcp_region} ${google_artifact_registry_repository.soa_repo.repository_id}"
}

# 5. Cloud Run v2 Service (UI 1 /shop, UI 2 /console, and /api/*)
resource "google_cloud_run_v2_service" "soa_app" {
  provider            = google-beta
  name                = "soa-refund-agent-app"
  location            = var.gcp_region
  project             = local.gcp_project_id
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  launch_stage        = local.enable_iap ? "BETA" : "GA"
  iap_enabled         = local.enable_iap

  template {
    service_account = google_service_account.soa_app_sa.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${local.gcp_project_id}/${google_artifact_registry_repository.soa_repo.repository_id}/soa-refund-agent-app:latest"

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
        name  = "GCP_PROJECT_ID"
        value = local.gcp_project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.gcp_region
      }
      env {
        name  = "SPANNER_INSTANCE_ID"
        value = google_spanner_instance.soa_instance.name
      }
      env {
        name  = "SPANNER_DATABASE_ID"
        value = google_spanner_database.soa_database.name
      }
      env {
        name  = "BIGQUERY_DATASET_ID"
        value = google_bigquery_dataset.action_lineage.dataset_id
      }
      env {
        name  = "SPANNER_CONNECTION_ID"
        value = local.spanner_connection_id
      }
      env {
        name  = "DATAPLEX_GLOSSARY_ID"
        value = google_dataplex_glossary.soa_business_glossary.glossary_id
      }
      env {
        name  = "DATAPLEX_ASPECT_TYPE_ID"
        value = google_dataplex_aspect_type.refund_metric_contract.aspect_type_id
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "True"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = local.gcp_project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = "global"
      }
      env {
        name  = "ADK_MODEL_NAME"
        value = var.adk_model_name
      }
      env {
        name  = "MAX_REFUNDS_100D_LIMIT"
        value = tostring(var.max_refunds_100d_limit)
      }
      env {
        name  = "VIP_MAX_REFUNDS_100D_LIMIT"
        value = tostring(var.vip_max_refunds_100d_limit)
      }
      env {
        name  = "APP_BUILD_HASH"
        value = "${module.cli.wait}-${sha256(jsonencode(local.app_build_triggers))}"
      }
    }
  }

  depends_on = [
    module.cli,
    google_spanner_database.soa_database,
    google_bigquery_table.agent_sessions,
    google_bigquery_table.workflow_nodes,
    google_bigquery_table.policy_evaluations,
    google_bigquery_table.agent_actions,
    google_project_iam_member.soa_app_sa_roles
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count    = local.enable_iap ? 0 : 1
  project  = google_cloud_run_v2_service.soa_app.project
  location = google_cloud_run_v2_service.soa_app.location
  name     = google_cloud_run_v2_service.soa_app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_project_service_identity" "iap_sa" {
  count    = local.enable_iap ? 1 : 0
  provider = google-beta
  project  = local.gcp_project_id
  service  = "iap.googleapis.com"

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "iap_service_agent_invoker" {
  count    = local.enable_iap ? 1 : 0
  project  = google_cloud_run_v2_service.soa_app.project
  location = google_cloud_run_v2_service.soa_app.location
  name     = google_cloud_run_v2_service.soa_app.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap_sa[0].email}"
}

resource "google_cloud_run_v2_service_iam_member" "iap_caller_invoker" {
  count    = local.enable_iap ? 1 : 0
  project  = google_cloud_run_v2_service.soa_app.project
  location = google_cloud_run_v2_service.soa_app.location
  name     = google_cloud_run_v2_service.soa_app.name
  role     = "roles/run.invoker"
  member   = length(regexall("gserviceaccount\\.com$", data.google_client_openid_userinfo.me[0].email)) > 0 ? "serviceAccount:${data.google_client_openid_userinfo.me[0].email}" : "user:${data.google_client_openid_userinfo.me[0].email}"
}

resource "google_project_iam_member" "iap_caller_accessor" {
  count   = local.enable_iap ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/iap.httpsResourceAccessor"
  member  = length(regexall("gserviceaccount\\.com$", data.google_client_openid_userinfo.me[0].email)) > 0 ? "serviceAccount:${data.google_client_openid_userinfo.me[0].email}" : "user:${data.google_client_openid_userinfo.me[0].email}"
}

data "http" "app_health_check" {
  count = local.enable_iap ? 0 : 1
  url   = "${google_cloud_run_v2_service.soa_app.uri}/api/health"

  retry {
    attempts     = 10
    min_delay_ms = 3000
    max_delay_ms = 10000
  }

  depends_on = [google_cloud_run_v2_service_iam_member.public_invoker]
}
