#!/bin/bash
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
# Run Personalized Marketing Agent locally
# Supports: direct ADC, Service Account impersonation, or service account key file

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env
if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
fi

# --- Auth Setup ---
# Priority: GOOGLE_APPLICATION_CREDENTIALS > SA_EMAIL impersonation > ADC

if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
  echo "Auth: Using service account key file"

elif [ -n "$SA_EMAIL" ]; then
  echo "Auth: Setting up Service Account impersonation for $SA_EMAIL"

  ADC_FILE="$HOME/.config/gcloud/application_default_credentials.json"
  if [ ! -f "$ADC_FILE" ]; then
    echo "ERROR: No ADC found. Run: gcloud auth application-default login"
    exit 1
  fi

  REFRESH_TOKEN=$(python3 -c "import json; print(json.load(open('$ADC_FILE')).get('refresh_token',''))" 2>/dev/null)
  if [ -z "$REFRESH_TOKEN" ]; then
    echo "ERROR: No refresh token in ADC. Run: gcloud auth application-default login"
    exit 1
  fi

  SA_ADC="/tmp/marketing_agent_sa_adc.json"
  cat >"$SA_ADC" <<EOF
{
  "delegates": [],
  "service_account_impersonation_url": "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${SA_EMAIL}:generateAccessToken",
  "source_credentials": {
    "client_id": "<your-oauth-client-id>",
    "client_secret": "<your-oauth-client-secret>",
    "refresh_token": "${REFRESH_TOKEN}",
    "type": "authorized_user",
    "universe_domain": "googleapis.com"
  },
  "type": "impersonated_service_account"
}
EOF
  export GOOGLE_APPLICATION_CREDENTIALS="$SA_ADC"
  echo "  SA credentials written to $SA_ADC"

else
  echo "Auth: Using Application Default Credentials (ADC)"
  echo "  Tip: For Google Ads video upload, run with SA impersonation:"
  echo "  SA_EMAIL=your-sa@project.iam.gserviceaccount.com ./run.sh"
fi

echo ""
echo "Project: ${GOOGLE_CLOUD_PROJECT:-not set}"
echo "Starting Marketing Agent..."
echo "Web UI: http://localhost:8000"
echo ""

# Run — try uv first, fall back to python
if command -v uv &>/dev/null; then
  uv run adk web marketing_agent
elif command -v adk &>/dev/null; then
  adk web marketing_agent
else
  python -m google.adk.cli web marketing_agent
fi
