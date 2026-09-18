#!/usr/bin/env bash
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

# Automated End-to-End Deployment Script for Oracle EBS Agentic AI Stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"

echo "======================================================================="
echo "   Oracle EBS Agentic AI — Automated Deployment Stack"
echo "======================================================================="

if [ ! -d "${TERRAFORM_DIR}" ]; then
  echo "Error: Terraform directory not found at ${TERRAFORM_DIR}" >&2
  exit 1
fi

pushd "${TERRAFORM_DIR}" >/dev/null

PROJECT_ID=""
REGION=""
if [ -f "terraform.tfvars" ]; then
  PROJECT_ID="$(grep -E '^\s*project_id\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
  REGION="$(grep -E '^\s*region\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
fi

if [ -z "${PROJECT_ID}" ]; then
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null || echo "")"
fi

if [ -z "${REGION}" ]; then
  REGION="${CLOUD_RUN_REGION:-us-central1}"
fi

if [ -z "${PROJECT_ID}" ]; then
  echo "Error: Unable to determine Google Cloud project_id from terraform.tfvars or gcloud config." >&2
  popd >/dev/null
  exit 1
fi

check_health() {
  local service_name="$1"
  local url="$2"
  if [ -z "${url}" ]; then
    echo "  [FAIL] ${service_name}: URL not available"
    return
  fi

  local http_code
  http_code="$(curl -s -o /dev/null -w "%{http_code}" "${url}/health" 2>/dev/null || echo "000")"
  if [ "${http_code}" = "200" ] || [ "${http_code}" = "403" ] || [ "${http_code}" = "401" ]; then
    echo "  [PASS] ${service_name} (${url}) -> HTTP ${http_code}"
  else
    echo "  [WARN] ${service_name} (${url}) -> HTTP ${http_code}"
  fi
}

REPO_NAME="oracle-ebs-agent-repo"
REGISTRY_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

echo "[1/5] Initializing Terraform..."
terraform init -input=false

echo "[2/5] Target-provisioning Artifact Registry & Service Accounts..."
terraform apply \
  -target=google_artifact_registry_repository.agent_repo \
  -target=google_service_account.cloud_run_sa \
  -target=google_service_account.gemini_agent_sa \
  -target=google_storage_bucket.agent_assets \
  -auto-approve -input=false

popd >/dev/null

echo "[3/5] Building & Pushing Container Images using Cloud Build..."
pushd "${PROJECT_ROOT}" >/dev/null

TIMESTAMP="$(date +%s)"

echo "  Building unified agent image tag ${TIMESTAMP}..."
gcloud builds submit --tag "${REGISTRY_URL}/oracle-ebs-agent-app:${TIMESTAMP}" --quiet .

popd >/dev/null

echo "[4/5] Applying Full Infrastructure Stack with Terraform..."
pushd "${TERRAFORM_DIR}" >/dev/null

terraform apply -var="image_tag=${TIMESTAMP}" -auto-approve -input=false

echo "[5/5] Extracting Deployed Service Endpoints and Asset URIs..."
A2A_SERVER_URL="$(terraform output -raw a2a_server_url 2>/dev/null || echo "")"
INV_URL="$(terraform output -raw inventory_agent_url 2>/dev/null || echo "")"
FIN_URL="$(terraform output -raw financial_agent_url 2>/dev/null || echo "")"
SUP_URL="$(terraform output -raw supplier_agent_url 2>/dev/null || echo "")"
MCP_URL="$(terraform output -raw mcp_server_url 2>/dev/null || echo "")"
AGENT_CARD_PATH="${TERRAFORM_DIR}/a2a_agent_card.json"
GCS_CARD_URI="$(terraform output -raw a2a_agent_card_gcs_uri 2>/dev/null || echo "")"
GCS_MANIFEST_URI="$(terraform output -raw gemini_extension_manifest_gcs_uri 2>/dev/null || echo "")"
GCS_OPENAPI_URI="$(terraform output -raw gcs_openapi_yaml_uri 2>/dev/null || echo "")"
GCS_EXT_OPENAPI_URI="$(terraform output -raw gemini_extension_openapi_gcs_uri 2>/dev/null || echo "")"

popd >/dev/null

echo "-----------------------------------------------------------------------"
echo " Cloud Run Microservices Deployed:"
echo "   - A2A Gateway Server : ${A2A_SERVER_URL:-}"
echo "   - Inventory Agent    : ${INV_URL:-}"
echo "   - Financial Agent    : ${FIN_URL:-}"
echo "   - Supplier Agent     : ${SUP_URL:-}"
echo "   - MCP Database Server: ${MCP_URL:-}"
echo "-----------------------------------------------------------------------"
echo " Vertex AI & Gemini Assets in Google Cloud Storage:"
echo "   - A2A Agent Card     : ${GCS_CARD_URI:-}"
echo "   - Gemini Manifest    : ${GCS_MANIFEST_URI:-}"
echo "   - A2A OpenAPI YAML   : ${GCS_OPENAPI_URI:-}"
echo "   - Ext OpenAPI YAML   : ${GCS_EXT_OPENAPI_URI:-}"
echo "-----------------------------------------------------------------------"

echo "Verifying Microservice Health Checks..."
check_health "A2A Gateway Server" "${A2A_SERVER_URL:-}"
check_health "Inventory Agent" "${INV_URL:-}"
check_health "Financial Agent" "${FIN_URL:-}"
check_health "Supplier Agent" "${SUP_URL:-}"
check_health "MCP Server" "${MCP_URL:-}"

echo "======================================================================="
echo " [SUCCESS] End-to-End Deployment Complete!"
echo " A2A Agent Card Generated at: ${AGENT_CARD_PATH:-}"
echo " Display Name: Oracle EBS Autonomous Assistant"
echo "======================================================================="
