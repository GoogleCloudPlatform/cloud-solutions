#!/usr/bin/env bash
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

set -euo pipefail

PROJECT_ID="${1:?Missing PROJECT_ID}"
ENVIRONMENT="${2:-production}"
LOCATION="${3:-us}"

TOKEN="$(gcloud auth print-access-token)"

# Create or ignore if the Model Armor template already exists (HTTP 409)
curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "https://modelarmor.${LOCATION}.rep.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/templates?template_id=aegis-defense-shield" \
  -d "{
    \"filterConfig\": {
      \"piAndJailbreakFilterSettings\": {
        \"filterEnforcement\": \"ENABLED\",
        \"confidenceLevel\": \"MEDIUM_AND_ABOVE\"
      },
      \"sdpSettings\": {
        \"basicConfig\": {
          \"filterEnforcement\": \"ENABLED\"
        }
      }
    },
    \"templateMetadata\": {
      \"logSanitizeOperations\": true,
      \"logTemplateOperations\": true,
      \"customPromptSafetyErrorMessage\": \"Model Armor: Payload blocked due to security policy violation.\",
      \"customLlmResponseSafetyErrorMessage\": \"Model Armor: Response blocked due to security policy violation.\"
    },
    \"labels\": {
      \"system\": \"project-aegis\",
      \"environment\": \"${ENVIRONMENT}\"
    }
  }" || true # Ignore conflict if template already exists in the project
