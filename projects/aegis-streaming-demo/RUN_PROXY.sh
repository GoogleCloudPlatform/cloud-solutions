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
# Usage:
#   ./RUN_PROXY.sh [oss | first-party | low-code]
#   STACK=first-party ./RUN_PROXY.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Resolve stack selection from positional parameter, environment variable, or default to oss
STACK="${1:-${STACK:-oss}}"
if [ -d "${SCRIPT_DIR}/terraform/stacks/${STACK}" ]; then
  TERRAFORM_DIR="${SCRIPT_DIR}/terraform/stacks/${STACK}"
else
  TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
fi
PORT=${PORT:-8080}

echo "================================================================="
echo " [INFO] Project Aegis - Cloud Run Proxy Helper (Stack: ${STACK})"
echo "================================================================="

# 1. Verify Terraform and Python installations and state
if ! command -v terraform &>/dev/null; then
  echo "[ERROR] 'terraform' CLI is not installed or not in PATH."
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "[ERROR] 'python3' is not installed or not in PATH."
  exit 1
fi

if [ ! -d "${TERRAFORM_DIR}" ]; then
  echo "[ERROR] Terraform directory not found at '${TERRAFORM_DIR}'."
  exit 1
fi

echo "[INFO] Verifying Terraform deployment state..."
if ! terraform -chdir="${TERRAFORM_DIR}" output -json >/dev/null 2>&1; then
  echo "[ERROR] Could not read Terraform output state."
  echo "   Ensure you have initialized and deployed infrastructure using:"
  echo "   terraform -chdir=terraform/stacks/${STACK} init && terraform -chdir=terraform/stacks/${STACK} apply"
  exit 1
fi

# 2. Read required outputs from Terraform state
TF_OUTPUTS=$(terraform -chdir="${TERRAFORM_DIR}" output -json)
if command -v jq >/dev/null 2>&1; then
  PROJECT_ID=$(echo "${TF_OUTPUTS}" | jq -r '.project_id.value')
  REGION=$(echo "${TF_OUTPUTS}" | jq -r '.region.value')
  HUD_FRONTEND_URL=$(echo "${TF_OUTPUTS}" | jq -r '.hud_frontend_url.value')
  SA_EMAIL=$(echo "${TF_OUTPUTS}" | jq -r '.service_account_email.value')
else
  PROJECT_ID=$(echo "${TF_OUTPUTS}" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('project_id', {}).get('value', ''))")
  REGION=$(echo "${TF_OUTPUTS}" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('region', {}).get('value', ''))")
  HUD_FRONTEND_URL=$(echo "${TF_OUTPUTS}" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('hud_frontend_url', {}).get('value', ''))")
  SA_EMAIL=$(echo "${TF_OUTPUTS}" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('service_account_email', {}).get('value', ''))")
fi

if [ -z "${PROJECT_ID}" ] || [ -z "${REGION}" ]; then
  echo "[ERROR] Missing 'project_id' or 'region' in Terraform output."
  echo "   Re-run 'terraform apply' in the stack directory."
  exit 1
fi

echo "[INFO] Terraform state verified:"
echo "   - Project ID:    ${PROJECT_ID}"
echo "   - Region:        ${REGION}"
echo "   - Frontend URL:  ${HUD_FRONTEND_URL}"
echo "   - Service Acct:  ${SA_EMAIL}"
echo "   - Local Port:    ${PORT}"
echo "-----------------------------------------------------------------"

# 3. Check for gcloud cloud-run-proxy component installation
echo "[INFO] Checking gcloud 'cloud-run-proxy' component status..."
if ! gcloud components list --filter="id:cloud-run-proxy AND state.name=Installed" --format="value(id)" 2>/dev/null | grep -q "cloud-run-proxy"; then
  echo ""
  echo "================================================================="
  echo "[NOTICE] First-Time Proxy Setup Required"
  echo "   The 'gcloud run services proxy' command requires the"
  echo "   'cloud-run-proxy' gcloud component."
  echo ""
  echo "   If gcloud prompts: 'Would you like to install the cloud-run-proxy"
  echo "   component to continue command execution? (Y/n)?'"
  echo "   Type 'Y' and press Enter to complete installation."
  echo "================================================================="
  echo ""
fi

# 4. Open browser once proxy port becomes active
LOCAL_URL="http://localhost:${PORT}"
echo "[INFO] Browser launch ready. Will open ${LOCAL_URL} once proxy starts..."

(
  for _ in $(seq 1 45); do
    if curl -s "${LOCAL_URL}" >/dev/null 2>&1 || (exec 3<>/dev/tcp/127.0.0.1/"${PORT}") 2>/dev/null; then
      echo "[INFO] Proxy listener detected at ${LOCAL_URL}. Launching browser..."
      # Fall back gracefully if display server or browser opener is unavailable
      if command -v xdg-open &>/dev/null; then
        xdg-open "${LOCAL_URL}" >/dev/null 2>&1 || true # Ignore browser exit in headless shells
      elif command -v open &>/dev/null; then
        open "${LOCAL_URL}" >/dev/null 2>&1 || true # Ignore browser exit in headless shells
      elif command -v python3 &>/dev/null; then
        python3 -m webbrowser "${LOCAL_URL}" >/dev/null 2>&1 || true # Ignore browser exit in headless shells
      fi
      exit 0
    fi
    sleep 1
  done
) &

# 5. Execute gcloud proxy for hud-frontend with reconnect loop
echo "Press Ctrl+C to terminate proxy when finished."
echo "================================================================="

while true; do
  echo "[INFO] Minting audience-scoped identity token for 'hud-frontend'..."
  ID_TOKEN=""
  # Tier 1: Try service account impersonation with audience scope; ignore failure if caller lacks tokenCreator role
  if [ -n "${SA_EMAIL}" ] && [ -n "${HUD_FRONTEND_URL}" ]; then
    ID_TOKEN=$(gcloud auth print-identity-token --project="${PROJECT_ID}" --impersonate-service-account="${SA_EMAIL}" --audiences="${HUD_FRONTEND_URL}" 2>/dev/null || true)
  fi

  # Tier 2: Fall back to user identity token with audience scope; ignore failure if user credentials disallow custom audiences
  if [ -z "${ID_TOKEN}" ] && [ -n "${HUD_FRONTEND_URL}" ]; then
    ID_TOKEN=$(gcloud auth print-identity-token --project="${PROJECT_ID}" --audiences="${HUD_FRONTEND_URL}" 2>/dev/null || true)
  fi

  # Tier 3: Fall back to default user identity token; ignore failure to allow gcloud proxy built-in auth
  if [ -z "${ID_TOKEN}" ]; then
    ID_TOKEN=$(gcloud auth print-identity-token --project="${PROJECT_ID}" 2>/dev/null || true)
  fi

  echo "[INFO] Executing gcloud authenticated proxy for 'hud-frontend' on port ${PORT}..."
  # Allow proxy reconnect on transient disconnection without terminating the script
  if [ -n "${ID_TOKEN}" ]; then
    gcloud run services proxy hud-frontend \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --port="${PORT}" \
      --token="${ID_TOKEN}" || true # Reconnect loop handles proxy exit
  else
    gcloud run services proxy hud-frontend \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --port="${PORT}" || true # Reconnect loop handles proxy exit
  fi
  echo "[WARN] Proxy connection interrupted. Reconnecting in 2 seconds..."
  sleep 2
done
