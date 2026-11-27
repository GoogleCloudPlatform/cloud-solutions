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

locals {
  resolved_bucket_name = (
    length(trimspace(var.staging_bucket_name)) > 0
    ? trimspace(var.staging_bucket_name)
    : "${var.project_id}-${var.name_prefix}-staging"
  )

  required_apis = toset([
    "agentregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "apphub.googleapis.com",
    "bigquery.googleapis.com",
    "cloudasset.googleapis.com",
    "cloudcli.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "compute.googleapis.com",
    "developerknowledge.googleapis.com",
    "discoveryengine.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "orgpolicy.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
  ])

  runtime_roles = toset([
    "roles/agentregistry.viewer",
    "roles/aiplatform.user",
    "roles/bigquery.jobUser",
    "roles/cloudtrace.agent",
    "roles/discoveryengine.viewer",
    "roles/serviceusage.serviceUsageConsumer",
  ])

  inspection_roles = toset([
    "roles/apphub.viewer",
    "roles/bigquery.metadataViewer",
    "roles/cloudasset.viewer",
    "roles/cloudsql.viewer",
    "roles/compute.viewer",
    "roles/container.viewer",
    "roles/iam.securityReviewer",
    "roles/logging.viewer",
    "roles/mcp.toolUser",
    "roles/monitoring.viewer",
    "roles/orgpolicy.policyViewer",
    "roles/pubsub.viewer",
    "roles/redis.viewer",
    "roles/run.viewer",
    "roles/storage.insightsCollectorService",
    "roles/storage.objectViewer",
  ])

  monitored_projects = toset(concat([var.project_id], tolist(var.target_project_ids)))

  inspection_bindings = {
    for pair in setproduct(local.monitored_projects, local.inspection_roles) :
    "${pair[0]}:${pair[1]}" => {
      project = pair[0]
      role    = pair[1]
    }
  }

  toolbox_map = merge(
    var.database_toolbox.enabled ? { primary = merge(var.database_toolbox, { service_suffix = "mcp-toolbox" }) } : {},
    var.catalog_toolbox.enabled ? { catalog = merge(var.catalog_toolbox, { service_suffix = "catalog-mcp" }) } : {},
  )
}

resource "google_project_service" "apis" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "advisor_reader" {
  account_id   = var.service_account_id
  display_name = "GCP SRE Advisor Read-Only Runtime Service Account"
  project      = var.project_id
  depends_on   = [google_project_service.apis]
}

resource "google_project_iam_member" "runtime_roles" {
  for_each = local.runtime_roles
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.advisor_reader.email}"
}

resource "google_project_iam_member" "inspection_roles" {
  for_each = local.inspection_bindings
  project  = each.value.project
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.advisor_reader.email}"
}

resource "google_storage_bucket" "staging" {
  name                        = local.resolved_bucket_name
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = var.labels

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "staging_reader" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.advisor_reader.email}"
}

resource "google_secret_manager_secret_iam_member" "toolbox_secret_access" {
  for_each  = local.toolbox_map
  project   = var.project_id
  secret_id = each.value.tools_yaml_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.advisor_reader.email}"
}

resource "google_cloud_run_v2_service" "database_toolbox" {
  for_each            = local.toolbox_map
  name                = "${var.name_prefix}-${each.value.service_suffix}"
  project             = var.project_id
  location            = var.region
  deletion_protection = false
  labels              = var.labels

  template {
    service_account = google_service_account.advisor_reader.email

    scaling {
      min_instance_count = each.value.min_instances
      max_instance_count = each.value.max_instances
    }

    dynamic "vpc_access" {
      for_each = (
        length(trimspace(each.value.vpc_network)) > 0 && length(trimspace(each.value.vpc_subnetwork)) > 0
        ? [1]
        : []
      )
      content {
        network_interfaces {
          network    = each.value.vpc_network
          subnetwork = each.value.vpc_subnetwork
        }
        egress = "PRIVATE_RANGES_ONLY"
      }
    }

    volumes {
      name = "toolbox-config"
      secret {
        secret = each.value.tools_yaml_secret_id
        items {
          version = "latest"
          path    = "tools.yaml"
        }
      }
    }

    containers {
      image = each.value.image
      args  = ["--tools-file", "/app/config/tools.yaml", "--address", "0.0.0.0", "--port", "8080"]

      volume_mounts {
        name       = "toolbox-config"
        mount_path = "/app/config"
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.toolbox_secret_access,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "toolbox_invoker" {
  for_each = local.toolbox_map
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.database_toolbox[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.advisor_reader.email}"
}
