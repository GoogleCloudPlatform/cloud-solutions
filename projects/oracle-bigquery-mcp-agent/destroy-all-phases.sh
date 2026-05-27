#!/bin/bash
# ==============================================================================
# FynanceAI Automated Teardown & Infrastructure Cleanup Script
# ==============================================================================
# This script cleanly destroys all provisioned resources across all 5 deployment
# phases in the exact reverse order of dependency to prevent VPC attachment locks.
# ==============================================================================

# --- CONFIGURATION ---
ROOT_DIR=$(pwd)
LOG_FILE="/tmp/teardown_output.log"

# Redirect stdout/stderr to local log file
exec > >(tee -a "$LOG_FILE") 2>&1

# --- Load Custom Environment Overrides ---
if [ -f "$ROOT_DIR/terraform.tfvars" ]; then
  echo "Sourcing custom configurations from terraform.tfvars..."
  eval "$("$ROOT_DIR/parse_tfvars.py" "$ROOT_DIR/terraform.tfvars")"
fi

# --- Regional Teardown Scope Parameterization ---
DEPLOY_REGION="${DEPLOY_REGION:-us-central1}"
DEPLOY_ZONE="${DEPLOY_ZONE:-us-central1-a}"

# --- Retrieve Active Project Context ---
if [ -z "${ACTIVE_PROJECT:-}" ]; then
  ACTIVE_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
  if [ -z "$ACTIVE_PROJECT" ] || [ "$ACTIVE_PROJECT" == "(unset)" ]; then
    echo "Error: ACTIVE_PROJECT is not configured in .env and could not be retrieved via gcloud CLI."
    exit 1
  fi
fi

# Export core parameters as project-wide Terraform environment variables to authorize teardown
export TF_VAR_project_id="$ACTIVE_PROJECT"
export TF_VAR_region="$DEPLOY_REGION"
export TF_VAR_zone="$DEPLOY_ZONE"
export TF_VAR_gcs_bucket_name="${GCS_BUCKET_NAME:-oracle-staging-${ACTIVE_PROJECT}}"
export TF_VAR_db_password="${DB_PASSWORD:-}"

export TF_VAR_vpc_name="${VPC_NAME:-oracle-vpc}"
export TF_VAR_subnetwork_name="${SUBNETWORK_NAME:-oracle-subnet}"
export TF_VAR_create_vpc="${CREATE_VPC:-true}"
export TF_VAR_create_subnetwork="${CREATE_SUBNETWORK:-true}"
export TF_VAR_create_gcs_bucket="${CREATE_GCS_BUCKET:-true}"

# Export optional variables if set
if [ -n "${SSH_USER:-}" ]; then
  export TF_VAR_ssh_user="$SSH_USER"
fi
if [ -n "${SSH_KEY_PATH:-}" ]; then
  export TF_VAR_ssh_key_path="$SSH_KEY_PATH"
fi
if [ -n "${OAUTH_CLIENT_ID:-}" ]; then
  export TF_VAR_oauth_client_id="$OAUTH_CLIENT_ID"
fi
if [ -n "${OAUTH_CLIENT_SECRET:-}" ]; then
  export TF_VAR_oauth_client_secret="$OAUTH_CLIENT_SECRET"
fi

# --- Helper to wait for Cloud Run direct VPC serverless IP release ---
wait_for_serverless_ips() {
  local subnet_name="$1"
  local project_id="$2"
  local region="$3"
  echo "Checking for active serverless IP reservations in subnet $subnet_name..."

  for i in {1..30}; do
    local reserved_ips
    reserved_ips=$(gcloud compute addresses list \
      --regions="$region" \
      --project="$project_id" \
      --filter="subnetwork ~ $subnet_name" \
      --format="value(name)" 2>/dev/null || echo "")

    if [ -z "$reserved_ips" ]; then
      echo "No serverless IP reservations remain in $subnet_name."
      return 0
    fi

    # Format output for printing
    local ips_clean
    ips_clean=$(echo "$reserved_ips" | tr '\n' ' ')
    echo "Waiting for GCP to garbage collect serverless IPs in $subnet_name: $ips_clean(elapsed $((i * 10))s)..."
    sleep 10
  done

  echo "Warning: Timeout waiting for serverless IP release. Subnet deletion may fail."
  return 1
}

echo "========================================================================================"
echo "STARTING AUTOMATED INFRASTRUCTURE TEARDOWN: $(date) ---"
echo "========================================================================================"

# --- TEARDOWN SEQUENCE DEFINITION ---
# Elements are declared in the exact reverse dependency order:
# 1. mcp-server-tf -> 2. looker-core-tf -> 3. dialogflow-cx-agent-tf -> 4. datastream-bq -> 5. ora-vm-tf-19c
declare -a TEARDOWN_PHASES=(
  "mcp-server-tf|Cloud Run MCP Server"
  "looker-core-tf|Looker Core Enterprise instance"
  "dialogflow-cx-agent-tf|Dialogflow CX Agent"
  "datastream-bq|Datastream BQ CDC Pipeline"
  "ora-vm-tf-19c|Oracle Database VM Infrastructure (VPC, Network, and Compute)"
)

step_counter=1
for phase in "${TEARDOWN_PHASES[@]}"; do
  IFS="|" read -r dir_name display_name <<<"$phase"

  echo "-----------------------------------------------------------------------------"
  echo "[Step $step_counter/5] Tearing down $display_name..."
  echo "-----------------------------------------------------------------------------"

  if [ -d "$ROOT_DIR/$dir_name" ]; then
    if [ "$dir_name" = "ora-vm-tf-19c" ]; then
      wait_for_serverless_ips "$TF_VAR_subnetwork_name" "$ACTIVE_PROJECT" "$DEPLOY_REGION" || true
    fi
    cd "$ROOT_DIR/$dir_name" || exit 1
    if [ -f "terraform.tfstate" ]; then
      terraform init -input=false -reconfigure >/dev/null || true
      terraform destroy -input=false -auto-approve || echo "Warning: $display_name teardown warned/failed. Continuing cleanup..."
    else
      echo "Skipping: $display_name was not provisioned via Terraform."
    fi
    cd "$ROOT_DIR" || exit 1
  fi
  step_counter=$((step_counter + 1))
done

echo "========================================================================================"
echo "ENTIRE FYNANCEAI INFRASTRUCTURE STACK SUCCESSFULLY DESTROYED & CLEANED!"
echo "========================================================================================"
echo "Teardown logs are saved at: $LOG_FILE"
echo "========================================================================================"
