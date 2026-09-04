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

# ==============================================================================
# Model Armor Security Shield Template (Google Cloud AI Safety Guardrails)
# ==============================================================================

resource "null_resource" "model_armor_template" {
  triggers = {
    project  = var.project_id
    revision = "20260730-v1"
  }

  provisioner "local-exec" {
    command = <<EOT
      TOKEN=$(gcloud auth print-access-token)
      curl -s -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        "https://modelarmor.us.rep.googleapis.com/v1/projects/${var.project_id}/locations/us/templates?template_id=aegis-defense-shield" \
        -d '{
          "filterConfig": {
            "piAndJailbreakFilterSettings": {
              "filterEnforcement": "ENABLED",
              "confidenceLevel": "MEDIUM_AND_ABOVE"
            },
            "sdpSettings": {
              "basicConfig": {
                "filterEnforcement": "ENABLED"
              }
            }
          },
          "templateMetadata": {
            "logSanitizeOperations": true,
            "logTemplateOperations": true,
            "customPromptSafetyErrorMessage": "Model Armor: Payload blocked due to security policy violation.",
            "customLlmResponseSafetyErrorMessage": "Model Armor: Response blocked due to security policy violation."
          },
          "labels": {
            "system": "project-aegis",
            "environment": "production"
          }
        }' || true
    EOT
  }

  depends_on = [google_project_service.enabled_apis]
}
