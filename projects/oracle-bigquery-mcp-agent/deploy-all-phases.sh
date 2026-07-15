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

echo "========================================================================================"
echo "FynanceAI: Automated Multi-Phase Google Cloud Deployment Pipeline"
echo "Orchestrating Oracle 19c, Datastream CDC, BigQuery ML, Cloud Run MCP, Dialogflow CX, and Looker"
echo "========================================================================================"

# Ensure local execution environment starts inside the script's root base directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# --- 0. Initialize & Generate Centralized Configuration ---
if [ ! -f "$ROOT_DIR/terraform.tfvars" ]; then
  echo "-----------------------------------------------------------------------------"
  echo "INITIAL CONFIGURATION GENERATOR"
  echo "No terraform.tfvars detected. Launching interactive setup to generate it..."
  echo "-----------------------------------------------------------------------------"
  terraform init -input=false
  terraform apply -auto-approve
fi

# --- Load Custom Environment Overrides ---
if [ -f "$ROOT_DIR/terraform.tfvars" ]; then
  echo "Sourcing custom configurations from terraform.tfvars..."
  eval "$("$ROOT_DIR/parse_tfvars.py" "$ROOT_DIR/terraform.tfvars")"
fi

# --- Regional Deployment Scope Parameterization ---
DEPLOY_REGION="${DEPLOY_REGION:-us-central1}"
DEPLOY_ZONE="${DEPLOY_ZONE:-us-central1-a}"

# --- Networking & Staging Customization ---
VPC_NAME="${VPC_NAME:-oracle-vpc}"
SUBNETWORK_NAME="${SUBNETWORK_NAME:-oracle-subnet}"
CREATE_VPC="${CREATE_VPC:-true}"
CREATE_SUBNETWORK="${CREATE_SUBNETWORK:-true}"
CREATE_GCS_BUCKET="${CREATE_GCS_BUCKET:-true}"

export TF_VAR_vpc_name="$VPC_NAME"
export TF_VAR_subnetwork_name="$SUBNETWORK_NAME"
export TF_VAR_create_vpc="$CREATE_VPC"
export TF_VAR_create_subnetwork="$CREATE_SUBNETWORK"
export TF_VAR_create_gcs_bucket="$CREATE_GCS_BUCKET"

# --- 0. Secure Database Master Password Collection ---
echo "-----------------------------------------------------------------------------"
echo "SECURE DATABASE MASTER PASSWORD COLLECTION"
echo "Please specify a strong, master database password to authorize Oracle schemas"
echo "and secure connection strings (minimum 8 chars, e.g., include capital, digits, _)."
echo "-----------------------------------------------------------------------------"
if [ -z "${DB_PASSWORD:-}" ]; then
  read -s -r -p "Enter Oracle Database Master Password: " DB_PASSWORD
  echo ""
  if [ -z "$DB_PASSWORD" ]; then
    echo "Error: Master password cannot be empty."
    exit 1
  fi
fi

# Export as Terraform environment variables to authorize all sub-modules headlessly
export TF_VAR_db_password="$DB_PASSWORD"

# --- 1. Verify Google Cloud Active Session Auth ---
if [ -z "${ACTIVE_PROJECT:-}" ]; then
  ACTIVE_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
  if [ -z "$ACTIVE_PROJECT" ] || [ "$ACTIVE_PROJECT" == "(unset)" ] || [ "$ACTIVE_PROJECT" == "YOUR_GCP_PROJECT_ID" ]; then
    read -r -p "Enter your Google Cloud Project ID: " ACTIVE_PROJECT
    if [ -z "$ACTIVE_PROJECT" ]; then
      echo "Error: Google Cloud Project ID cannot be empty."
      exit 1
    fi
    gcloud config set project "$ACTIVE_PROJECT" || true
  fi
fi

# Export core parameters as project-wide Terraform environment variables.
# Eliminates the need for developers to manually maintain separate local terraform.tfvars files across 5 phases.
export TF_VAR_project_id="$ACTIVE_PROJECT"
export TF_VAR_region="$DEPLOY_REGION"
export TF_VAR_zone="$DEPLOY_ZONE"
export TF_VAR_gcs_bucket_name="${GCS_BUCKET_NAME:-oracle-staging-${ACTIVE_PROJECT}}"

# Export SSH custom options if specified by environment overrides
if [ -n "${SSH_USER:-}" ]; then
  export TF_VAR_ssh_user="$SSH_USER"
fi
if [ -n "${SSH_KEY_PATH:-}" ]; then
  export TF_VAR_ssh_key_path="$SSH_KEY_PATH"
fi

# Export Looker OAuth custom parameters if specified by environment overrides
if [ -n "${OAUTH_CLIENT_ID:-}" ]; then
  export TF_VAR_oauth_client_id="$OAUTH_CLIENT_ID"
fi
if [ -n "${OAUTH_CLIENT_SECRET:-}" ]; then
  export TF_VAR_oauth_client_secret="$OAUTH_CLIENT_SECRET"
fi

# --- Centralized Infrastructure Orchestrator Helper ---
run_terraform_step() {
  local step_num="$1"
  local step_desc="$2"
  local dir_path="$3"
  shift 3

  echo "-----------------------------------------------------------------------------"
  echo "[$step_num] $step_desc"
  echo "-----------------------------------------------------------------------------"

  cd "$ROOT_DIR/$dir_path"
  terraform init -input=false
  terraform apply -input=false -auto-approve "$@" || {
    echo "Error: Terraform execution failed inside $dir_path"
    exit 1
  }
  cd "$ROOT_DIR"
}

echo "[Step 1/7] Verifying active evaluation project context: $ACTIVE_PROJECT..."
gcloud auth list
gcloud auth application-default set-quota-project "$ACTIVE_PROJECT" || true

# --- 2. Verify Phase 1 (Oracle VM) State ---
run_terraform_step "Step 2/7" "Provisioning and verifying upstream Phase 1 (Oracle VM) infrastructure..." "ora-vm-tf-19c"

# Create the database password version immediately so the VM startup script can read it on boot
echo "Securing database credentials in Secret Manager for VM startup..."
echo -n "$DB_PASSWORD" | gcloud secrets versions add oracle-db-password --data-file=- --quiet

# Extract persistent Phase 1 GCE zone target dynamically
ORA_ZONE=$(terraform -chdir="$ROOT_DIR/ora-vm-tf-19c" output -raw oracle_db_zone)

# --- 2.1 Poll GCE Startup Bootstrap Sentinel Completion ---
echo "-----------------------------------------------------------------------------"
echo "WAITING FOR ORACLE DATABASE BOOTSTRAP & DATA SEEDING TO COMPLETE..."
echo "This runs unattended in the GCE background and takes ~10-15 minutes."
echo "-----------------------------------------------------------------------------"

for i in {1..240}; do
  if gcloud compute instances get-serial-port-output oracle-db-19c --zone="$ORA_ZONE" 2>/dev/null | grep -q "Finished running startup scripts"; then
    echo ""
    echo "Oracle Database bootstrap and data seeding successfully verified!"
    break
  fi
  if [ $((i % 4)) -eq 0 ]; then
    echo "Still waiting for Oracle bootstrap to complete... (elapsed $((i * 5))s)"
  fi
  sleep 5
done

# --- 3. Deploy Phase 2 (Datastream CDC to BigQuery) ---
run_terraform_step "Step 3/7" "Compiling Phase 2 Streaming CDC & BigQuery forecasting datasets..." "datastream-bq"

# --- 4. Deploy Phase 3 (Dialogflow CX Conversational Agent) ---
run_terraform_step "Step 4/7" "Deploying Phase 3 Dialogflow CX autonomous AI agent entity..." "dialogflow-cx-agent-tf"
AGENT_UUID=$(terraform -chdir="$ROOT_DIR/dialogflow-cx-agent-tf" output -raw agent_uuid)
echo "Conversational Agent UUID successfully captured: $AGENT_UUID"
echo "Phase 3 Dialogflow CX Agent playbooks successfully provisioned and restored via HCL!"

# --- 5. Deploy Phase 4 (Cloud Run MCP Middleware Connector) ---
echo "Extracting persistent Phase 1 internal database private IP target..."
ORA_IP=$(terraform -chdir="$ROOT_DIR/ora-vm-tf-19c" output -raw oracle_db_private_ip)

# Credentials are already secured in Secret Manager during Step 2

run_terraform_step "Step 5/7" "Instantiating Phase 4 Cloud Run service and Dialogflow webhook via Terraform..." "mcp-server-tf" -var="agent_id=$AGENT_UUID"
MCP_URI=$(terraform -chdir="$ROOT_DIR/mcp-server-tf" output -raw mcp_service_url)
echo "Baseline Cloud Run Service successfully provisioned at: $MCP_URI"

echo "Waiting 15s for IAM service account permissions to propagate globally..."
sleep 15

cd "$ROOT_DIR/mcp-server"
echo "Compiling and updating active operational service code revision via Google Cloud serverless source buildpacks..."
gcloud run deploy oracle-mcp-server \
  --source . \
  --platform managed \
  --region "$DEPLOY_REGION" \
  --no-allow-unauthenticated \
  --vpc-egress private-ranges-only \
  --subnet "$SUBNETWORK_NAME" \
  --set-env-vars "PROJECT_ID=${ACTIVE_PROJECT},AGENT_ID=${AGENT_UUID},DB_USER=c##datastream,DB_DSN=${ORA_IP}:1521/ORCLPDB1,VERTEX_REGION=${DEPLOY_REGION}" \
  --set-secrets "DB_PASSWORD=oracle-db-password:latest" \
  --quiet || exit 1

echo "Operational Cloud Run MCP Service successfully live at: $MCP_URI"

echo "-----------------------------------------------------------------------------"
echo "UPDATING DIALOGFLOW CX CUSTOM TOOL OPENAPI SCHEMAS"
echo "Replacing tool server placeholder with live service endpoint: $MCP_URI"
echo "-----------------------------------------------------------------------------"
python3 -c '
import sys, re
mcp_uri = sys.argv[1]
files = sys.argv[2:]
for filepath in files:
    with open(filepath, "r") as f:
        text = f.read()
    text_updated = re.sub(r"url:\s*https://\S+", f"url: {mcp_uri}", text)
    with open(filepath, "w") as f:
        f.write(text_updated)
' "$MCP_URI" "$ROOT_DIR/dialogflow-cx-agent-tf/agent/tools/Oracle_FinOps_MCP/schema.yaml" "$ROOT_DIR/dialogflow-cx-agent-tf/mcp_openapi_schema.yaml"

# Re-run Step 4/7 via Terraform to packaging and restore updated OpenAPI custom tools.
run_terraform_step "Step 5.1/7" "Refreshing Phase 3 Dialogflow CX agent customized tool schema configuration..." "dialogflow-cx-agent-tf"

# Reset local schema files back to placeholders to keep local Git status 100% clean and prevent URI leakage.
git checkout -- "$ROOT_DIR/dialogflow-cx-agent-tf/agent/tools/Oracle_FinOps_MCP/schema.yaml" "$ROOT_DIR/dialogflow-cx-agent-tf/mcp_openapi_schema.yaml"

cd "$ROOT_DIR"

# --- 6. Deploy Phase 5 (Looker Core Enterprise Reporting) ---
echo "[Step 6/7] Evaluating Phase 5 Looker Core enterprise reporting integration scope..."
RUN_LOOKER="false"
if [ -n "${TF_VAR_oauth_client_id:-}" ] && [ -n "${TF_VAR_oauth_client_secret:-}" ] && [ "$TF_VAR_oauth_client_id" != "YOUR_OAUTH_WEB_CLIENT_ID" ]; then
  RUN_LOOKER="true"
elif [ -f "$ROOT_DIR/looker-core-tf/terraform.tfvars" ] && ! grep -q "YOUR_OAUTH_WEB_CLIENT_ID" "$ROOT_DIR/looker-core-tf/terraform.tfvars"; then
  RUN_LOOKER="true"
fi

if [ "$RUN_LOOKER" = "false" ]; then
  echo "Warning: Looker Core OAuth client credentials placeholder detected or not set. Skipping Phase 5 reporting."
  echo "Please generate your custom OAuth keys inside your Google Cloud Console, paste them into looker-core-tf/terraform.tfvars or your root .env file,"
  echo "and execute 'cd looker-core-tf && terraform apply' to provision Phase 5 reporting manually."
else
  run_terraform_step "Step 6/7" "Provisioning Phase 5 Looker Core enterprise reporting instance..." "looker-core-tf"

  # --- 7. Dynamically Bake Looker Dashboard Link into Cloud Run Service ---
  echo "Retrieving Looker instance endpoint dynamically..."
  LOOKER_URI=$(terraform -chdir="$ROOT_DIR/looker-core-tf" output -raw looker_uri 2>/dev/null || echo "")

  if [ -n "$LOOKER_URI" ]; then
    # Ensure looker_uri has a trailing slash before appending the dashboards path
    case "$LOOKER_URI" in
    */)
      LOOKER_DASHBOARD_URL="${LOOKER_URI}dashboards/executive_ledger::fynanceai_enterprise_financial_operations"
      ;;
    *)
      LOOKER_DASHBOARD_URL="${LOOKER_URI}/dashboards/executive_ledger::fynanceai_enterprise_financial_operations"
      ;;
    esac
    echo "Looker Dashboard URL resolved: $LOOKER_DASHBOARD_URL"

    run_terraform_step "Step 7/7" "Baking Looker URL and Agent UUID into CFO Module (Cloud Run)..." "mcp-server-tf" -var="agent_id=$AGENT_UUID" -var="looker_dashboard_url=$LOOKER_DASHBOARD_URL"
    echo "CFO Module Cloud Run service environment updated via HCL!"
  else
    echo "Warning: Could not retrieve Looker instance endpoint; skipping environment automation."
  fi
fi

echo "========================================================================================"
echo "ENTIRE FYNANCEAI STACK SUCCESSFULLY AUTOMATED END-TO-END!"
echo "========================================================================================"
echo ""
echo "LOOKML REPORTING TILES INTEGRATION INSTRUCTIONS:"
echo "Once your Looker instance is fully provisioned, navigate to your Looker IDE console and link"
echo "your Git workspace tracking path targeting the pre-authored looker-core-tf/lookml_dashboards/"
echo "suite to instantly render your premium operational spending and predictive metrics tiles!"
echo "========================================================================================"
echo ""
echo "CONVERSATIONAL MESSENGER INTEGRATION MANDATORY MANUAL SETUP:"
echo "To authorize public client web sessions to interact with your Agent:"
echo "1. Open the Google Cloud Conversational Agents console: https://conversational-agents.cloud.google.com/projects"
echo "2. Select project: '${TF_VAR_project_id}' and agent: '${TF_VAR_agent_display_name:-FinAgent}'."
echo "3. In the left menu, select 'Manage' > 'Integrations'."
echo "4. Locate the 'Conversational Messenger' integration card and click 'Connect'."
echo "5. Toggle 'Enable unauthenticated access' to active and click 'Done' or 'Save'."
echo "========================================================================================"
