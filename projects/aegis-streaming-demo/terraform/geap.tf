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

resource "null_resource" "deploy_geap_agent" {
  triggers = {
    source_hash = sha256(join("", [
      for f in fileset("${path.module}/../agent-service", "**") :
      filesha256("${path.module}/../agent-service/${f}")
      if !can(regex("(__pycache__|\\.pyc$|\\.git/)", f))
    ]))
  }

  provisioner "local-exec" {
    command = "python3 ${path.module}/../agent-service/deploy_geap.py"
    environment = {
      GCP_PROJECT    = var.project_id
      GCP_REGION     = var.region
      STAGING_BUCKET = "gs://${var.project_id}-dataproc-deps"
    }
  }

  depends_on = [google_project_service.enabled_apis]
}

data "external" "geap_agent" {
  program = ["python3", "${path.module}/../agent-service/get_geap_id.py"]
  query = {
    project_id = var.project_id
    region     = var.region
  }
  depends_on = [null_resource.deploy_geap_agent]
}
