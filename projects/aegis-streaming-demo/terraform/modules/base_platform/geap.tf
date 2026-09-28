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

# =============================================================================
# Gemini Enterprise Agent Platform (GEAP) Reasoning Engine Provisioner
# =============================================================================

# Dedicated staging bucket created when a stack (such as low-code) does not
# pass its own staging_bucket variable, ensuring fresh installations on new
# projects always have a valid Cloud Storage bucket for Vertex AI staging.
resource "google_storage_bucket" "geap_staging" {
  count                       = var.staging_bucket == "" ? 1 : 0
  name                        = "${var.project_id}-geap-staging"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = true

  labels = {
    environment = var.environment
    component   = "geap-staging"
  }

  depends_on = [google_project_service.enabled_apis]
}

locals {
  resolved_geap_staging_bucket = (
    var.staging_bucket != ""
    ? (startswith(var.staging_bucket, "gs://") ? var.staging_bucket : "gs://${var.staging_bucket}")
    : "gs://${google_storage_bucket.geap_staging[0].name}"
  )
}

resource "null_resource" "deploy_geap_agent" {
  triggers = {
    source_hash = sha256(join("", [
      for f in fileset("${path.module}/../../../agent-service", "**") :
      filesha256("${path.module}/../../../agent-service/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.git/|/tests/)", f))
    ]))
    simulator_url  = google_cloud_run_v2_service.telemetry_simulator.uri
    staging_bucket = local.resolved_geap_staging_bucket
  }

  provisioner "local-exec" {
    command = "python3 ${path.module}/../../../agent-service/src/deploy_geap.py"
    environment = {
      GCP_PROJECT           = var.project_id
      GCP_REGION            = var.region
      STAGING_BUCKET        = local.resolved_geap_staging_bucket
      SIMULATOR_SERVICE_URL = google_cloud_run_v2_service.telemetry_simulator.uri
      FORCE_RECREATE        = "true"
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_project_iam_member.aegis_sa_roles,
    google_storage_bucket.geap_staging,
    google_cloud_run_v2_service.telemetry_simulator,
  ]
}

data "external" "geap_agent" {
  program = ["python3", "${path.module}/../../../agent-service/src/get_geap_id.py"]
  query = {
    project_id = var.project_id
    region     = var.region
  }
  depends_on = [null_resource.deploy_geap_agent]
}
