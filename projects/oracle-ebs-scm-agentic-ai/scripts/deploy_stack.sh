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

# Deploy the VoltGuard supply chain resiliency agent end to end: Artifact
# Registry, the agent image, the BigQuery signals and zone demand exposure,
# the Oracle EBS MCP Toolbox and agent Cloud Run services, and the Gemini
# Enterprise agent card.

set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"
TFVARS_FILE="${TERRAFORM_DIR}/terraform.tfvars"
AGENT_CARD_FILE="${PROJECT_ROOT}/src/oracle_ebs_scm_agentic_ai/agent_card.json"
DB_PASSWORD_SECRET_ID="oracle-ebs-scm-db-password"
ISG_CREDENTIALS_SECRET_ID="oracle-ebs-scm-isg-credentials"
SIGNING_SECRET_ID="oracle-ebs-scm-maps-static-signing-secret"
REPOSITORY_ID="oracle-ebs-scm-repo"
SIGNALS_DATASET="ebs_scm_agentic_ai"
PLACES_DATASET="places_insights___us"

extract_tfvar() {
  local key="$1"
  if [[ -f "${TFVARS_FILE}" ]]; then
    # A key that is not in terraform.tfvars is valid: callers fall back to
    # the environment or the gcloud configuration.
    grep -E "^[[:space:]]*${key}[[:space:]]*=" "${TFVARS_FILE}" |
      tail -n 1 |
      cut -d'=' -f2- |
      sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
        -e 's/^"//' -e 's/"$//' || true
  fi
}

run_tf() {
  if command -v terraform >/dev/null 2>&1; then
    terraform -chdir="${TERRAFORM_DIR}" "$@"
  else
    docker run --rm -i \
      -u "$(id -u):$(id -g)" \
      -e HOME=/tmp \
      -e TF_VAR_oracle_db_password \
      -e TF_VAR_ebs_writeback_password \
      -e GOOGLE_APPLICATION_CREDENTIALS=/gcp/application_default_credentials.json \
      -v "${HOME}/.config/gcloud:/gcp:ro" \
      -v "${PROJECT_ROOT}:/workspace" \
      -w /workspace/terraform \
      hashicorp/terraform:1.17.1 "$@"
  fi
}

PROJECT_ID="${PROJECT_ID:-$(extract_tfvar project_id)}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-$(extract_tfvar region)}"
if [[ -z "${PROJECT_ID}" ]] || [[ -z "${REGION}" ]]; then
  echo "Error: set project_id and region in ${TFVARS_FILE}." >&2
  exit 1
fi
# -var takes precedence over terraform.tfvars, so Terraform deploys to the
# same project and region as the gcloud and bq commands.
TF_PROJECT_VARS=(-var="project_id=${PROJECT_ID}" -var="region=${REGION}")

echo "[1/6] Resolving the Oracle EBS passwords..."
# resolve_password KEY PROMPT SECRET_ID [basic]: exports TF_VAR_KEY from the
# environment, terraform.tfvars, Secret Manager, or an interactive prompt.
# With basic, the secret holds base64 of user:password, and the password is
# the part after the first colon.
resolve_password() {
  local key="$1"
  local prompt="$2"
  local secret_id="$3"
  local format="${4:-plain}"
  local var="TF_VAR_${key}"
  local value="${!var:-}"
  if [[ -n "${value}" ]] || [[ -n "$(extract_tfvar "${key}")" ]]; then
    return
  fi
  # The secret does not exist before the first deployment, so prompt instead.
  value="$(gcloud secrets versions access latest \
    --secret="${secret_id}" --project="${PROJECT_ID}" 2>/dev/null || true)"
  if [[ -n "${value}" ]] && [[ "${format}" == "basic" ]]; then
    value="$(printf '%s' "${value}" | base64 --decode)"
    value="${value#*:}"
  fi
  if [[ -z "${value}" ]]; then
    if [[ ! -t 0 ]]; then
      echo "Error: set ${key} in terraform.tfvars or ${var}." >&2
      exit 1
    fi
    read -r -s -p "${prompt}: " value
    echo ""
  fi
  export "${var}=${value}"
}
resolve_password oracle_db_password "Oracle EBS APPS_AI database password" \
  "${DB_PASSWORD_SECRET_ID}"
resolve_password ebs_writeback_password "Oracle EBS writeback user password" \
  "${ISG_CREDENTIALS_SECRET_ID}" basic

echo "[2/6] Creating Artifact Registry, the build bucket, the signing secret, and BigQuery..."
run_tf init -input=false
run_tf validate -no-color
# Step 4 needs the signals dataset and the Gemini connection, and creates the
# views that the scheduled query in step 5 reads.
run_tf apply -auto-approve -input=false "${TF_PROJECT_VARS[@]}" \
  -target=google_artifact_registry_repository_iam_member.cloudbuild_ar_writer \
  -target=google_project_iam_member.cloudbuild_logging \
  -target=google_storage_bucket_iam_member.cloudbuild_source_reader \
  -target=google_secret_manager_secret.maps_static_signing_secret \
  -target=google_bigquery_dataset.ebs_scm_agentic_ai \
  -target=google_project_iam_member.gemini_connection_vertex_ai

# The Maps Static API URL signing secret comes from the Google Maps Platform
# credentials page, so it never passes through terraform.tfvars or the state.
ENABLED_SIGNING_VERSION="$(gcloud secrets versions list "${SIGNING_SECRET_ID}" \
  --project="${PROJECT_ID}" --filter="state:ENABLED" --limit=1 \
  --format="value(name)")"
if [[ -z "${ENABLED_SIGNING_VERSION}" ]]; then
  if [[ ! -t 0 ]]; then
    echo "Error: add the Maps Static API URL signing secret from the Google" \
      "Maps Platform credentials page with: gcloud secrets versions add" \
      "${SIGNING_SECRET_ID} --project=${PROJECT_ID} --data-file=-" >&2
    exit 1
  fi
  read -r -s -p "Maps Static API URL signing secret: " SIGNING_SECRET
  echo ""
  printf '%s' "${SIGNING_SECRET}" |
    gcloud secrets versions add "${SIGNING_SECRET_ID}" \
      --project="${PROJECT_ID}" --data-file=-
  unset SIGNING_SECRET
fi

IMAGE_TAG="${IMAGE_TAG:-v$(date +%Y%m%d-%H%M%S)}"
CONTAINER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}/oracle-ebs-scm-agentic-ai:${IMAGE_TAG}"

echo "[3/6] Building ${CONTAINER_IMAGE} with Cloud Build..."
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "${BUILD_DIR}"' EXIT
cp "${PROJECT_ROOT}/Dockerfile" \
  "${PROJECT_ROOT}/README.md" \
  "${PROJECT_ROOT}/pyproject.toml" \
  "${PROJECT_ROOT}/uv.lock" \
  "${BUILD_DIR}/"
cp -r "${PROJECT_ROOT}/src" "${BUILD_DIR}/src"
# Terraform grants the build service accounts read access to this bucket.
gcloud builds submit "${BUILD_DIR}" \
  --project="${PROJECT_ID}" \
  --gcs-source-staging-dir="gs://${PROJECT_ID}-voltguard-build-source/source" \
  --tag="${CONTAINER_IMAGE}" \
  --quiet

echo "[4/6] Creating the BigQuery signals, forecasts, and zone exposure..."
BIGQUERY_LOCATION="$(bq show --format=json "${PROJECT_ID}:${SIGNALS_DATASET}" |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["location"])')"
SQL_FILES=(external_signals.sql timesfm_forecast.sql)
# The zone files read the Places Insights linked dataset.
if bq show --format=none "${PROJECT_ID}:${PLACES_DATASET}" >/dev/null 2>&1; then
  SQL_FILES+=(distribution_zones.sql zone_demand_exposure.sql market_place_density.sql)
else
  echo "  Skipped the zone exposure and place density tables: link the" \
    "Places Insights dataset ${PLACES_DATASET}, and deploy again."
fi
for sql_file in "${SQL_FILES[@]}"; do
  sed -e "s|your-project-id|${PROJECT_ID}|g" \
    -e "s|your-bigquery-location|${BIGQUERY_LOCATION}|g" \
    "${PROJECT_ROOT}/bigquery/sql/${sql_file}" |
    bq query \
      --project_id="${PROJECT_ID}" \
      --location="${BIGQUERY_LOCATION}" \
      --use_legacy_sql=false \
      --quiet >/dev/null
done

echo "[5/6] Deploying the MCP Toolbox and agent Cloud Run services..."
run_tf apply -auto-approve -input=false "${TF_PROJECT_VARS[@]}" \
  -var="container_image=${CONTAINER_IMAGE}"

A2A_URL="$(run_tf output -raw voltguard_a2a_url)"
TOOLBOX_URI="$(run_tf output -raw mcp_toolbox_uri)"

echo "[6/6] Updating the Gemini Enterprise A2A agent card..."
if [[ -n "${GEMINI_ENTERPRISE_AGENT:-}" ]]; then
  # The update leaves the agent's sharing settings alone: share it only with
  # authorized supply chain planners in Gemini Enterprise.
  PAYLOAD="$(
    python3 - "${AGENT_CARD_FILE}" "${A2A_URL}" <<'PYEOF'
import json
import sys

card_path, a2a_url = sys.argv[1:3]
with open(card_path, encoding="utf-8") as handle:
    card = json.load(handle)
card["url"] = a2a_url
prompts = [
    "Help",
    "Evaluate notification 90412: how does the PO 40912 delay affect "
    "VG-SURGE-PRO at Miami DC?",
    "Simulate reallocating 150 generators to Miami DC and rank the hubs by "
    "net financial benefit.",
    "Show the executive charts for the Miami DC stockout.",
]
print(
    json.dumps(
        {
            "a2aAgentDefinition": {"jsonAgentCard": json.dumps(card)},
            "starterPrompts": [{"text": prompt} for prompt in prompts],
        }
    )
)
PYEOF
  )"
  # curl reads the access token from stdin, so it never appears in the
  # process list.
  printf 'header = "Authorization: Bearer %s"\n' \
    "$(gcloud auth print-access-token)" |
    curl --config - --silent --show-error --fail-with-body \
      --output /dev/null \
      -X PATCH \
      -H "X-Goog-User-Project: ${PROJECT_ID}" \
      -H "Content-Type: application/json" \
      --data "${PAYLOAD}" \
      "https://discoveryengine.googleapis.com/v1alpha/${GEMINI_ENTERPRISE_AGENT}?updateMask=a2aAgentDefinition,starterPrompts"
  echo "  Updated ${GEMINI_ENTERPRISE_AGENT}"
else
  echo "  Skipped: set GEMINI_ENTERPRISE_AGENT to the agent resource name" \
    "(projects/.../assistants/default_assistant/agents/ID)."
fi

echo "-----------------------------------------------------------------------"
echo " VoltGuard agent (A2A) : ${A2A_URL}"
echo " Oracle EBS MCP Toolbox: ${TOOLBOX_URI}/mcp"
echo "-----------------------------------------------------------------------"
