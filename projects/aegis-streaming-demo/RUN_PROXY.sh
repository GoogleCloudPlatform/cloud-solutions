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

# =============================================================================
# Project Aegis - Local Cloud Run Auth Proxy Helper Script
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
PORT=${PORT:-8080}

echo "================================================================="
echo " 🚀 Project Aegis - Cloud Run Proxy Helper"
echo "================================================================="

# 1. Verify Terraform installation and state
if ! command -v terraform &>/dev/null; then
  echo "❌ Error: 'terraform' CLI is not installed or not in PATH."
  exit 1
fi

if [ ! -d "${TERRAFORM_DIR}" ]; then
  echo "❌ Error: Terraform directory not found at '${TERRAFORM_DIR}'."
  exit 1
fi

echo "🔍 Verifying Terraform deployment state..."
if ! (cd "${TERRAFORM_DIR}" && terraform output -json >/dev/null 2>&1); then
  echo "❌ Error: Could not read Terraform output state."
  echo "   Please ensure you have initialized and deployed infrastructure via:"
  echo "   cd terraform && terraform init && terraform apply"
  exit 1
fi

# 2. Read required outputs from Terraform state
TF_OUTPUTS=$(cd "${TERRAFORM_DIR}" && terraform output -json)
PROJECT_ID=$(echo "${TF_OUTPUTS}" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('project_id', {}).get('value', ''))")
REGION=$(echo "${TF_OUTPUTS}" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('region', {}).get('value', ''))")

if [ -z "${PROJECT_ID}" ] || [ -z "${REGION}" ]; then
  echo "❌ Error: Missing 'project_id' or 'region' in Terraform output."
  echo "   Please re-run 'terraform apply' in the terraform directory."
  exit 1
fi

echo "✅ Terraform state verified:"
echo "   • Project ID: ${PROJECT_ID}"
echo "   • Region:     ${REGION}"
echo "   • Local Port: ${PORT}"
echo "-----------------------------------------------------------------"

# 3. Check for gcloud cloud-run-proxy component installation
echo "ℹ️  Checking gcloud 'cloud-run-proxy' component status..."
if ! gcloud components list --filter="id:cloud-run-proxy AND state.name=Installed" --format="value(id)" 2>/dev/null | grep -q "cloud-run-proxy"; then
  echo ""
  echo "================================================================="
  echo "⚠️  NOTICE: First-Time Proxy Setup Required"
  echo "   The 'gcloud run services proxy' command requires the"
  echo "   'cloud-run-proxy' gcloud component."
  echo ""
  echo "👉 If gcloud prompts: 'Would you like to install the cloud-run-proxy"
  echo "   component to continue command execution? (Y/n)?'"
  echo "   Please type 'Y' and press Enter to complete installation."
  echo "================================================================="
  echo ""
fi

# 4. Open browser automatically once proxy port becomes active
LOCAL_URL="http://localhost:${PORT}"
echo "🌐 Browser auto-launch ready. Will open ${LOCAL_URL} once proxy starts..."

(
  for _ in $(seq 1 45); do
    if curl -s "${LOCAL_URL}" >/dev/null 2>&1 || (exec 3<>/dev/tcp/127.0.0.1/"${PORT}") 2>/dev/null; then
      echo "✅ Proxy listener detected at ${LOCAL_URL}. Launching browser..."
      # Fall back gracefully if display server or browser opener is unavailable
      if command -v xdg-open &>/dev/null; then
        xdg-open "${LOCAL_URL}" >/dev/null 2>&1 || true
      elif command -v open &>/dev/null; then
        open "${LOCAL_URL}" >/dev/null 2>&1 || true
      elif command -v python3 &>/dev/null; then
        python3 -m webbrowser "${LOCAL_URL}" >/dev/null 2>&1 || true
      fi
      exit 0
    fi
    sleep 1
  done
) &

# 5. Execute gcloud proxy for hud-frontend with auto-reconnect loop
echo "Press Ctrl+C to terminate proxy when finished."
echo "================================================================="

while true; do
  echo "🔑 Executing gcloud authenticated proxy for 'hud-frontend' on port ${PORT}..."
  # Allow proxy auto-reconnect on transient disconnection without terminating the script
  gcloud run services proxy hud-frontend \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --port="${PORT}" || true
  echo "⚠️ Proxy connection interrupted. Auto-reconnecting in 2 seconds..."
  sleep 2
done
