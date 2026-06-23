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

# Exit on error
set -e

FORCE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
  -f | --force)
    FORCE=true
    shift
    ;;
  *)
    echo "Unknown option: $1"
    exit 1
    ;;
  esac
done

echo "🚀 Initializing Legacy Detox Demo Project..."

SCRIPT_DIR=$(dirname "$0")
TFVARS_FILE="$SCRIPT_DIR/../terraform/terraform.tfvars"

# Check if terraform directory exists
if [ ! -d "$SCRIPT_DIR/../terraform" ]; then
  echo "Error: The 'terraform' directory does not exist at $SCRIPT_DIR/../terraform" >&2
  exit 1
fi

PROMPT_AND_WRITE=false

if [ -f "$TFVARS_FILE" ]; then
  if [ "$FORCE" = true ]; then
    PROMPT_AND_WRITE=true
  else
    echo "⚠️  $TFVARS_FILE already exists."
    echo "Current contents:"
    echo "----------------------------------------"
    cat "$TFVARS_FILE"
    echo "----------------------------------------"

    while true; do
      read -r -p "Do you want to override it? (yes/no): " OVERRIDE
      case "$OVERRIDE" in
      yes | y | YES | Y)
        PROMPT_AND_WRITE=true
        break
        ;;
      no | n | NO | N)
        PROMPT_AND_WRITE=false
        break
        ;;
      *)
        echo "Please answer yes or no."
        ;;
      esac
    done

    if [ "$PROMPT_AND_WRITE" = false ]; then
      echo "Skipping terraform.tfvars creation."
      # Extract project_id from existing file
      PROJECT_ID=$(sed -n 's/^project_id *= *["'\''"]\([^"'\''"]*\)["'\''"].*$/\1/p' "$TFVARS_FILE")
      if [ -z "$PROJECT_ID" ]; then
        echo "Error: Could not extract project_id from $TFVARS_FILE" >&2
        exit 1
      fi
    fi
  fi
else
  PROMPT_AND_WRITE=true
fi

if [ "$PROMPT_AND_WRITE" = true ]; then
  CURRENT_PROJECT=$(gcloud config get-value project)

  # Ask for Project ID
  read -r -p "Enter your Google Cloud Project ID [$CURRENT_PROJECT]: " PROJECT_ID

  if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID="${CURRENT_PROJECT}"
  fi

  # Ask for Region (with default)
  read -r -p "Enter your Google Cloud Region [us-central1]: " REGION
  REGION=${REGION:-us-central1}

  # Create terraform/terraform.tfvars
  echo "📝 Creating terraform/terraform.tfvars..."
  cat <<VARSEOF >"$TFVARS_FILE"
project_id = "$PROJECT_ID"
region     = "$REGION"
VARSEOF
fi

# Set current project
echo "⚙️ Setting gcloud project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "🔌 Enabling required APIs (this may take a minute)..."
SERVICES=(
  "compute.googleapis.com"
  "dataproc.googleapis.com"
  "dataform.googleapis.com"
  "cloudaicompanion.googleapis.com"
  "bigquery.googleapis.com"
  "storage-api.googleapis.com"
  "aiplatform.googleapis.com"
  "bigqueryunified.googleapis.com"
  "artifactregistry.googleapis.com"
  "cloudbuild.googleapis.com"
)

gcloud services enable "${SERVICES[@]}" --project "$PROJECT_ID"

echo "✅ Initialization complete!"
echo ""
echo "👉 Next steps:"
echo "1. cd terraform"
echo "2. terraform init"
echo "3. terraform apply"
