#!/bin/bash
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
# Script to grant BigQuery dataset read permissions to Agent Engine and Discovery Engine Service Accounts

set -e

# Load environment variables from .env file
SCRIPT_DIR="$(dirname "$0")"

# Prioritize .env in the current working directory
if [ -f "$PWD/.env" ]; then
  ENV_FILE="$PWD/.env"
elif [ -f "${SCRIPT_DIR}/../../.env" ]; then
  ENV_FILE="${SCRIPT_DIR}/../../.env"
else
  echo "Warning: .env file not found"
fi

# Security: Parse variables instead of sourcing to avoid arbitrary code execution
if [ -n "$ENV_FILE" ] && [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  GOOGLE_CLOUD_PROJECT=$(grep "^GOOGLE_CLOUD_PROJECT=" "$ENV_FILE" | cut -d= -f2- | tr -d "'\"")
fi
export GOOGLE_CLOUD_PROJECT

# Get the project ID from environment variable
PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project)
fi

if [ -z "$PROJECT_ID" ]; then
  echo "No project ID found. Please set your project ID."
  exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
if [ -z "$PROJECT_NUMBER" ]; then
  echo "Failed to retrieve project number for project $PROJECT_ID"
  exit 1
fi

echo "Triggering GCP platform service identity creation to ensure service accounts exist..."
# Proactively trigger service identity creation for Agent Engine and Discovery Engine
# (Ignored on error in case APIs are not fully initialized or if identities are already generated)
gcloud beta services identity create --service=aiplatform.googleapis.com --project="$PROJECT_ID" || true
gcloud beta services identity create --service=discoveryengine.googleapis.com --project="$PROJECT_ID" || true

# Load and clean ASSET_DATASET
if [ -n "$ENV_FILE" ]; then
  ASSET_DATASET=$(grep "^ASSET_DATASET=" "$ENV_FILE" | cut -d= -f2- | tr -d "'\"")
fi
if [ -z "$ASSET_DATASET" ]; then
  ASSET_DATASET="mfg_assets"
fi
# Replace invalid characters like dash with underscore
ASSET_DATASET_CLEANED="${ASSET_DATASET//-/_}"

# Service Accounts definition
SERVICE_ACCOUNT_RE="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
SERVICE_ACCOUNT_DISCOVERY="service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com"

# Helper function to apply binding with error handling
apply_binding() {
  local sa_name="$1"
  local description="$2"
  local command="$3"

  echo "  - Granting $description..."
  set +e
  eval "$command" >/dev/null 2>&1
  local status=$?
  set -e

  if [ $status -ne 0 ]; then
    echo "⚠️ Warning: Failed to apply IAM binding for $sa_name."
    echo "   Command failed: $description"
    echo "   Please verify that:"
    echo "     1. The required Google Cloud API is fully enabled (e.g., aiplatform.googleapis.com or discoveryengine.googleapis.com)"
    echo "     2. You have appropriate Admin / Project Owner permissions to modify IAM policies."
    echo "   You can try running the following command to enable the target API:"
    echo "     gcloud services enable aiplatform.googleapis.com discoveryengine.googleapis.com"
    return 1
  fi
  return 0
}

echo "Granting permissions to Agent Engine Service Agent ($SERVICE_ACCOUNT_RE)..."
apply_binding "$SERVICE_ACCOUNT_RE" \
  "dataset-level Data Viewer role on $ASSET_DATASET_CLEANED" \
  "gcloud bigquery datasets add-iam-policy-binding '$PROJECT_ID:$ASSET_DATASET_CLEANED' --member='serviceAccount:$SERVICE_ACCOUNT_RE' --role='roles/bigquery.dataViewer'"

apply_binding "$SERVICE_ACCOUNT_RE" \
  "project-level Job User role" \
  "gcloud projects add-iam-policy-binding '$PROJECT_ID' --member='serviceAccount:$SERVICE_ACCOUNT_RE' --role='roles/bigquery.jobUser'"

echo "Granting permissions to Discovery Engine Service Agent ($SERVICE_ACCOUNT_DISCOVERY)..."
apply_binding "$SERVICE_ACCOUNT_DISCOVERY" \
  "dataset-level Data Viewer role on $ASSET_DATASET_CLEANED" \
  "gcloud bigquery datasets add-iam-policy-binding '$PROJECT_ID:$ASSET_DATASET_CLEANED' --member='serviceAccount:$SERVICE_ACCOUNT_DISCOVERY' --role='roles/bigquery.dataViewer'"

apply_binding "$SERVICE_ACCOUNT_DISCOVERY" \
  "project-level Job User role" \
  "gcloud projects add-iam-policy-binding '$PROJECT_ID' --member='serviceAccount:$SERVICE_ACCOUNT_DISCOVERY' --role='roles/bigquery.jobUser'"

echo "✅ BigQuery read/query permissions configuration attempt finished."
