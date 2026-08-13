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

set -euo pipefail

# Load environment variables from .env
if [ -f .env ]; then
  echo "Loading environment variables from .env..."
  # Parse env file ignoring comments and exporting variables
  while IFS= read -r line || [ -n "$line" ]; do
    if [[ ! "$line" =~ ^# ]] && [[ "$line" =~ = ]]; then
      # Strip surrounding quotes if present
      key=$(echo "$line" | cut -d'=' -f1 | xargs)
      value=$(
        echo "$line" | cut -d'=' -f2- |
          sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
      )
      export "$key"="$value"
    fi
  done <.env
else
  echo "Error: .env file not found."
  exit 1
fi

# Ensure required env variables are present
if [ -z "${GCP_PROJECT_ID:-}" ]; then
  echo "Error: GCP_PROJECT_ID is not set in .env"
  exit 1
fi

echo "Enabling required Google Cloud APIs for project $GCP_PROJECT_ID..."
gcloud services enable --project="$GCP_PROJECT_ID" \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  orgpolicy.googleapis.com \
  iam.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  compute.googleapis.com \
  run.googleapis.com \
  bigquery.googleapis.com \
  dialogflow.googleapis.com \
  discoveryengine.googleapis.com \
  ces.googleapis.com \
  storage.googleapis.com \
  iap.googleapis.com --quiet

echo "Setting ADC quota project to $GCP_PROJECT_ID..."
gcloud auth application-default set-quota-project \
  "$GCP_PROJECT_ID" --quiet || true

echo "Checking and unblocking Org Policies for Cloud Run access..."
gcloud org-policies reset constraints/run.managed.requireInvokerIam \
  --project="$GCP_PROJECT_ID" --quiet || true

TMP_DIR=$(mktemp -d -p .)
trap 'rm -rf "$TMP_DIR"' EXIT

cat <<EOF >"$TMP_DIR/iam_policy.yaml"
name: projects/$GCP_PROJECT_ID/policies/iam.allowedPolicyMemberDomains
spec:
  rules:
  - allowAll: true
EOF
gcloud org-policies set-policy "$TMP_DIR/iam_policy.yaml" \
  --project="$GCP_PROJECT_ID" --quiet || true

echo "Instantiating Google-managed service identities..."
gcloud beta services identity create --service=ces.googleapis.com \
  --project="$GCP_PROJECT_ID" 2>/dev/null || true
gcloud beta services identity create --service=dialogflow.googleapis.com \
  --project="$GCP_PROJECT_ID" 2>/dev/null || true

if [ -z "${GCP_REGION:-}" ]; then
  export GCP_REGION="us-central1"
fi

if [ -z "${CES_SERVICE_AGENT:-}" ]; then
  echo "CES_SERVICE_AGENT not set in .env. Auto-detecting..."
  PROJECT_NUMBER=$(
    gcloud projects describe "$GCP_PROJECT_ID" \
      --format="value(projectNumber)" 2>/dev/null || true
  )
  if [ -n "$PROJECT_NUMBER" ]; then
    export CES_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-ces.iam.gserviceaccount.com"
    echo "  [Auto-Detected] CES_SERVICE_AGENT = '$CES_SERVICE_AGENT'"
  else
    echo "Error: Could not determine project number for $GCP_PROJECT_ID"
    exit 1
  fi
fi

if [ -z "${CONVERSATION_PROFILE_ID:-}" ]; then
  export CONVERSATION_PROFILE_ID=""
fi

IMAGE_TAG=$(date +"%Y%m%d%H%M%S")
echo "Using container image tag: $IMAGE_TAG"

echo "Ensuring Artifact Registry repository exists..."
gcloud artifacts repositories create "cymbal-demo-repo-$GCP_PROJECT_ID" \
  --repository-format=docker \
  --location="$GCP_REGION" \
  --project="$GCP_PROJECT_ID" \
  --quiet || true

echo "Building and pushing container image via Cloud Build..."
IMAGE_PATH="${GCP_PROJECT_ID}/cymbal-demo-repo-${GCP_PROJECT_ID}"
IMAGE_URI="${GCP_REGION}-docker.pkg.dev/${IMAGE_PATH}/cymbal-bff:${IMAGE_TAG}"
gcloud builds submit --tag "$IMAGE_URI" . \
  --project="$GCP_PROJECT_ID" --quiet

echo "Generating terraform/terraform.tfvars..."
cat <<EOF >terraform/terraform.tfvars
project_id              = "$GCP_PROJECT_ID"
region                  = "$GCP_REGION"
conversation_profile_id = "$CONVERSATION_PROFILE_ID"
ces_service_agent       = "$CES_SERVICE_AGENT"
image_tag               = "$IMAGE_TAG"
EOF

echo "Initializing Terraform..."
terraform -chdir=terraform init

echo "Applying Terraform configuration..."
terraform -chdir=terraform apply -auto-approve

if [ ! -d "venv" ]; then
  echo "Virtual environment './venv' not found. Creating and installing..."
  python3 -m venv venv
  ./venv/bin/pip install --require-hashes -r scripts/requirements.txt
fi

COACH_CFG="terraform/assets/coaches/ai-coach.json"
if [ -f scripts/manage_agent_assist_coaches.py ] && [ -f "$COACH_CFG" ]; then
  echo "Deploying and linking AI Coach Generator to Conversation Profile..."
  ./venv/bin/python3 scripts/manage_agent_assist_coaches.py deploy \
    --project="$GCP_PROJECT_ID" \
    --config="$COACH_CFG" \
    --id="generator-ai-coach"

  GENERATOR_PATH="projects/$GCP_PROJECT_ID/locations/global/generators/generator-ai-coach"
  ./venv/bin/python3 scripts/manage_agent_assist_coaches.py link \
    --project="$GCP_PROJECT_ID" \
    --profile="Cymbal Coach - Cymbal Demo" \
    --generator="$GENERATOR_PATH"
fi
