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

# ============================================================================
# WS4 hybrid shape (Pattern C): the tenant keeps its data in its own project (tenant_data_plane:
# CMEK it holds, AlloyDB with PSC), while compute stays in the pooled platform. The pooled side
# only gets a PSC endpoint in its VPC; there is no VPC peering and no shared database.
#
# The pooled platform itself is NOT created here: it is referenced by project and network (it is
# the root sandbox composition, or any platform_core stamp). Example only:
#
#   terraform init -backend-config="bucket=<tenant-project>-tfstate" -backend-config="prefix=hybrid"
#   terraform plan -var-file=example.tfvars
# ============================================================================

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

  backend "gcs" {} # partial config: pass bucket/prefix with -backend-config
}

# Default provider: the tenant's data project.
provider "google" {
  project = var.tenant_project_id
  region  = var.region
}

provider "google-beta" {
  project = var.tenant_project_id
  region  = var.region
}

# The pooled platform project (consumer side of PSC).
provider "google" {
  alias   = "pooled"
  project = var.pooled_project_id
  region  = var.region
}

module "tenant_data_plane" {
  source = "../../modules/tenant_data_plane"

  project_id                = var.tenant_project_id
  region                    = var.region
  tenant_id                 = var.tenant_id
  name_prefix               = var.name_prefix
  allowed_consumer_projects = [var.pooled_project_id]
  labels = {
    architecture_pattern = "pattern-c-hybrid"
    workstream           = "gemini-multitenancy-ws4"
    managed_by           = "terraform"
  }
}

# --- Pooled side: a PSC endpoint for this tenant's data plane -----------------------------------

resource "google_compute_address" "tenant_psc" {
  provider     = google.pooled
  name         = "${var.name_prefix}-psc"
  region       = var.region
  subnetwork   = var.pooled_subnetwork
  address_type = "INTERNAL"
}

resource "google_compute_forwarding_rule" "tenant_psc" {
  provider              = google.pooled
  name                  = "${var.name_prefix}-psc"
  region                = var.region
  network               = var.pooled_network
  ip_address            = google_compute_address.tenant_psc.id
  target                = module.tenant_data_plane.psc_service_attachment
  load_balancing_scheme = "" # PSC endpoint for a published service
}
