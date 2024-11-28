# Copyright 2024 Google LLC
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

locals {
  connector_def = {
    connectorVersion = "projects/${var.project_id}/locations/global/providers/gcp/connectors/firestore/versions/1"
    authConfig = {
      additionalVariables = [
        {
          key         = "scopes"
          stringValue = "https://www.googleapis.com/auth/cloud-platform"
        }
      ]
      authKey = "service_account"
    }
    serviceAccount   = "${var.project_number}-compute@developer.gserviceaccount.com"
    serviceDirectory = "projects/gbb43fbbad33edd7c-tp/locations/us-central1/namespaces/cloudrun/services/runtime"
    nodeConfig = {
      minNodeCount = 2
      maxNodeCount = 50
    }
    logConfig = {
      enabled = true
      level   = "INFO"
    }
    sslConfig = {
      privateServerCertificate = {}
      clientCertificate        = {}
      clientPrivateKey         = {}
      clientPrivateKeyPass     = {}
    }
  }
}

resource "terraform_data" "firestore_connector" {
  # Create firestore connector
  input = {
    name          = var.name
    project_id    = var.project_id
    region        = var.region
    connector_def = jsonencode(local.connector_def)
  }

  provisioner "local-exec" {
    command    = <<EOT
    curl -f  \
      -H "X-Goog-User-Project: ${self.input.project_id}" \
      --header "Authorization: Bearer $(gcloud auth print-access-token)" \
      --json '${self.input.connector_def}' \
      https://connectors.googleapis.com/v1/projects/${self.input.project_id}/locations/${self.input.region}/connections?connectionId=${self.input.name}
EOT
    on_failure = fail
  }

  provisioner "local-exec" {
    when       = destroy
    command    = <<EOT
gcloud auth print-access-token | curl -f --variable '%token@-' -X DELETE \
  -H "X-Goog-User-Project: ${self.input.project_id}" \
  --expand-header "Authorization: Bearer {{token}}" \
  https://connectors.googleapis.com/v1/projects/${self.input.project_id}/locations/${self.input.region}/connections/${self.input.name}
EOT
    on_failure = continue
  }
}
