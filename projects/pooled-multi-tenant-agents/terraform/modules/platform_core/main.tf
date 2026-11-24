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

# Platform core: everything shared by the tenants of one pooled platform project (APIs, the
# gateway and broker with their identities, guardrail templates, context-signing and platform
# keys, telemetry, pooled data stores, IAP). Providers are configured by the caller.
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.50"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.50"
    }
  }
}

locals {
  bootstrap_apis = toset([
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
  ])

  required_apis = toset([
    "aiplatform.googleapis.com",
    "alloydb.googleapis.com",
    "artifactregistry.googleapis.com", # Cloud Run source deploys (image repository)
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com", # Cloud Run source deploys (builds)
    "cloudkms.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "compute.googleapis.com",
    "dlp.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com", # credential broker: generateAccessToken / generateIdToken
    "iap.googleapis.com",
    "logging.googleapis.com",
    "modelarmor.googleapis.com",
    "monitoring.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ])

  common_labels = var.labels
}

# Stage Service Usage & Cloud Resource Manager first so fresh GCP projects can enable KMS and
# downstream APIs without a 403 SERVICE_DISABLED race.
resource "google_project_service" "bootstrap_apis" {
  for_each           = local.bootstrap_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_service" "enabled_apis" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
  depends_on         = [google_project_service.bootstrap_apis]
}
