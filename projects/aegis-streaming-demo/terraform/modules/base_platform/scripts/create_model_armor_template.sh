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

PROJECT_ID="${PROJECT_ID:-${1:?Missing PROJECT_ID}}"
ENVIRONMENT="${ENVIRONMENT:-${2:-production}}"
LOCATION="${LOCATION:-${3:-us}}"

RESP_FILE="$(mktemp /tmp/model_armor_resp.XXXXXX.json)"
trap 'rm -f "${RESP_FILE}"' EXIT

# Create the Model Armor template, or accept HTTP 409 if it already exists.
HTTP_CODE="$(curl -s -o "${RESP_FILE}" -w "%{http_code}" -X POST \
  -H @- \
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
  }" <<<"Authorization: Bearer $(gcloud auth print-access-token)")"

case "${HTTP_CODE}" in
200 | 201 | 409)
  echo "Model Armor template aegis-defense-shield ready (HTTP ${HTTP_CODE})."
  ;;
*)
  echo "WARNING: Unexpected HTTP status ${HTTP_CODE} from Model Armor API:" >&2
  cat "${RESP_FILE}" >&2
  exit 1
  ;;
esac
