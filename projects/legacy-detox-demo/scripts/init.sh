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

echo "🚀 Initializing Legacy Detox Demo Project..."
CURRENT_PROJECT=$(gcloud config get-value project)

# Ask for Project ID
read -r -p "Enter your Google Cloud Project ID [$CURRENT_PROJECT]: " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID="${CURRENT_PROJECT}"
fi

# Ask for Region (with default)
read -r -p "Enter your Google Cloud Region [us-central1]: " REGION
REGION=${REGION:-us-central1}

SCRIPT_DIR=$(dirname "$0")

# Check if terraform directory exists
if [ ! -d "$SCRIPT_DIR/../terraform" ]; then
  echo "Error: The 'terraform' directory does not exist at $SCRIPT_DIR/../terraform" >&2
  exit 1
fi

# Create terraform/terraform.tfvars
echo "📝 Creating terraform/terraform.tfvars..."
if [ ! -f "$SCRIPT_DIR/../terraform/terraform.tfvars" ]; then
  cat <<VARSEOF >"$SCRIPT_DIR/../terraform/terraform.tfvars"
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

gcloud services enable "${SERVICES[@]}"

echo "✅ Initialization complete!"
echo ""
echo "👉 Next steps:"
echo "1. cd terraform"
echo "2. terraform init"
echo "3. terraform apply"
