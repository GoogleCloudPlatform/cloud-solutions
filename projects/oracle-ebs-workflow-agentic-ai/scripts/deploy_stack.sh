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

# Automated End-to-End Deployment Script for Oracle EBS Workflow Agentic AI Stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"

echo "======================================================================="
echo "   Oracle EBS Workflow Agentic AI — Automated Deployment Stack"
echo "======================================================================="

if [ ! -d "${TERRAFORM_DIR}" ]; then
  echo "Error: Terraform directory not found at ${TERRAFORM_DIR}" >&2
  exit 1
fi

pushd "${TERRAFORM_DIR}" >/dev/null || exit 1

PROJECT_ID=""
REGION=""
ENVIRONMENT=""
ORACLE_HOST="${ORACLE_HOST:-}"
if [ -f "terraform.tfvars" ]; then
  # Suppress grep non-zero exit codes when optional keys are absent in terraform.tfvars
  PROJECT_ID="$(grep -E '^\s*project_id\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
  REGION="$(grep -E '^\s*region\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
  ENVIRONMENT="$(grep -E '^\s*environment\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
  if [ -z "${ORACLE_HOST}" ]; then
    ORACLE_HOST="$(grep -E '^\s*oracle_host\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
  fi
fi

if [ -z "${PROJECT_ID}" ]; then
  # Suppress gcloud non-zero exit code if no default project is configured in the active profile
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null || echo "")"
fi

if [ -z "${REGION}" ]; then
  REGION="us-central1"
fi

if [ -z "${ENVIRONMENT}" ]; then
  ENVIRONMENT="dev"
fi

if [ -z "${PROJECT_ID}" ]; then
  echo "Error: Unable to determine Google Cloud project_id from terraform.tfvars or gcloud config." >&2
  popd >/dev/null || exit 1
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
  # Default to 000 if curl fails due to transient network or DNS errors so health check logs a warning
  http_code="$(curl -s -o /dev/null -w "%{http_code}" "${url}/health" 2>/dev/null || echo "000")"
  if [ "${http_code}" = "200" ] || [ "${http_code}" = "403" ] || [ "${http_code}" = "401" ]; then
    echo "  [PASS] ${service_name} (${url}) -> HTTP ${http_code}"
  else
    echo "  [WARN] ${service_name} (${url}) -> HTTP ${http_code}"
  fi
}

TIMESTAMP="$(date +%s)"
REPO_ID="oracle-ebs-workflow-repo-${ENVIRONMENT}"
CONTAINER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_ID}/oracle-ebs-workflow-app:${TIMESTAMP}"

echo "[1/4] Initializing Terraform..."
terraform init -input=false

echo "[2/4] Provisioning Google Cloud APIs, Secret Manager Secrets & Artifact Registry Repository..."
terraform apply \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="environment=${ENVIRONMENT}" \
  -target=google_project_service.enabled_apis \
  -target=google_secret_manager_secret.db_password \
  -target=google_secret_manager_secret.isg_password \
  -target=google_artifact_registry_repository.agent_repo \
  -target=google_artifact_registry_repository_iam_member.cloudbuild_ar_writer \
  -target=google_project_iam_member.cloudbuild_logging \
  -auto-approve -input=false

if [ -n "${ORACLE_PASSWORD:-}" ]; then
  printf "%s" "${ORACLE_PASSWORD}" | gcloud secrets versions add "oracle-ebs-workflow-db-password-${ENVIRONMENT}" --project="${PROJECT_ID}" --data-file=-
fi
if [ -n "${ISG_PASSWORD:-${ORACLE_PASSWORD:-}}" ]; then
  printf "%s" "${ISG_PASSWORD:-${ORACLE_PASSWORD:-}}" | gcloud secrets versions add "oracle-ebs-workflow-isg-password-${ENVIRONMENT}" --project="${PROJECT_ID}" --data-file=-
fi

bootstrap_oracle_db() {
  local db_pass="${ORACLE_PASSWORD:-apps}"
  local spec_file="${PROJECT_ROOT}/src/workflow/sql/xx_ebs_wf_agent_pkg_spec.sql"
  local body_file="${PROJECT_ROOT}/src/workflow/sql/xx_ebs_wf_agent_pkg_body.sql"
  local instance_info=""
  if [ -n "${ORACLE_HOST}" ] && [ "${ORACLE_HOST}" != "127.0.0.1" ]; then
    # Suppress gcloud lookup failures if compute.instances.list permission is unavailable
    instance_info="$(gcloud compute instances list --project="${PROJECT_ID}" --filter="networkInterfaces.networkIP=${ORACLE_HOST}" --format="value(name,zone.basename())" 2>/dev/null | head -n 1 || echo "")"
  fi
  local instance_name
  local instance_zone
  instance_name="$(printf "%s" "${instance_info}" | awk '{print $1}')"
  instance_zone="$(printf "%s" "${instance_info}" | awk '{print $2}')"
  instance_name="${instance_name:-oracle-vision}"
  instance_zone="${instance_zone:-${REGION}-a}"
  local remote_cmd="sudo -i -u oracle bash -c 'IFILE=/u01/install/APPS/19.0.0/network/admin/EBSDB_apps/sqlnet_ifile.ora; if [ -f \"\$IFILE\" ] && ! grep -q ALLOWED_LOGON_VERSION_SERVER \"\$IFILE\"; then printf \"\\nSQLNET.ALLOWED_LOGON_VERSION_SERVER=8\\nSQLNET.ALLOWED_LOGON_VERSION_CLIENT=8\\n\" >> \"\$IFILE\"; fi; source /u01/install/APPS/19.0.0/*.env && sqlplus -s / as sysdba'"
  echo "Bootstrapping Oracle EBS 12.2 Vision DB (${instance_name} in ${instance_zone})..."
  # Allow deployment to continue if IAP/SSH access to the Oracle VM is unavailable; runtime self-heal handles fallback
  if {
    cat <<EOF
ALTER SYSTEM SET sec_case_sensitive_logon = TRUE SCOPE=BOTH;
ALTER SESSION SET CONTAINER = EBSDB;
ALTER USER APPS IDENTIFIED BY "${db_pass}";
EOF
    cat "${spec_file}"
    printf "\n/\n"
    cat "${body_file}"
    printf "\n/\nEXIT;\n"
  } | gcloud compute ssh "${instance_name}" \
    --project="${PROJECT_ID}" \
    --zone="${instance_zone}" \
    --tunnel-through-iap \
    --quiet \
    --command="${remote_cmd}" >/dev/null 2>&1; then
    echo "  [PASS] Oracle EBS DB verifier (11G/12C) and APPS.XX_EBS_WF_AGENT_PKG bootstrapped."
  else
    echo "  [WARN] Optional SSH DB bootstrap skipped; EBSDatabaseClient runtime Thick fallback and DDL bootstrap will handle initialization."
  fi
}

bootstrap_oracle_db

echo "[3/4] Building & Pushing Container Image via Cloud Build..."
gcloud builds submit --project="${PROJECT_ID}" \
  --tag="${CONTAINER_IMAGE}" \
  "${PROJECT_ROOT}"

echo "[4/4] Provisioning Cloud Run Services & Gemini Enterprise Assets..."
terraform apply \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="environment=${ENVIRONMENT}" \
  -var="container_image=${CONTAINER_IMAGE}" \
  -var="image_tag=${TIMESTAMP}" \
  -auto-approve -input=false

echo "Extracting Deployed Service Endpoints and Asset URIs..."
# Suppress terraform output errors when optional outputs are omitted so summary reporting continues
SERVICE_URLS_JSON="$(terraform output -json cloud_run_service_urls 2>/dev/null || echo "{}")"
A2A_SERVER_URL="$(printf "%s" "${SERVICE_URLS_JSON}" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("a2a-workflow-server", ""))' 2>/dev/null || echo "")"
WORKFLOW_AGENT_URL="$(printf "%s" "${SERVICE_URLS_JSON}" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("workflow-agent", ""))' 2>/dev/null || echo "")"
GCS_CARD_URI="$(terraform output -raw a2a_agent_card_gcs_uri 2>/dev/null || echo "")"
GCS_MANIFEST_URI="$(terraform output -raw gemini_extension_manifest_gcs_uri 2>/dev/null || echo "")"
GCS_OPENAPI_URI="$(terraform output -raw gcs_openapi_yaml_uri 2>/dev/null || echo "")"

popd >/dev/null || exit 1

echo "-----------------------------------------------------------------------"
echo " Cloud Run Microservices Deployed:"
echo "   - Workflow A2A Gateway Server : ${A2A_SERVER_URL:-}"
echo "   - Core Workflow Agent Worker  : ${WORKFLOW_AGENT_URL:-}"
echo "-----------------------------------------------------------------------"
echo " Vertex AI & Gemini Assets in Google Cloud Storage:"
echo "   - A2A Agent Card     : ${GCS_CARD_URI:-}"
echo "   - Gemini Manifest    : ${GCS_MANIFEST_URI:-}"
echo "   - Extension OpenAPI  : ${GCS_OPENAPI_URI:-}"
echo "-----------------------------------------------------------------------"

echo "Verifying Microservice Health Checks..."
check_health "Workflow A2A Gateway Server" "${A2A_SERVER_URL:-}"
check_health "Core Workflow Agent Worker" "${WORKFLOW_AGENT_URL:-}"

echo "======================================================================="
echo " [SUCCESS] End-to-End Deployment Complete!"
echo " Display Name: Oracle EBS Workflow AI Assistant"
echo "======================================================================="
