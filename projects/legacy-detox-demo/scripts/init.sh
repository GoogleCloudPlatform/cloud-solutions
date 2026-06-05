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

# Ask for Project ID
read -r -p "Enter your Google Cloud Project ID: " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
  echo "❌ Project ID is required. Exiting."
  exit 1
fi

# Ask for Region (with default)
read -r -p "Enter your Google Cloud Region [us-central1]: " REGION
REGION=${REGION:-us-central1}

# Create terraform/terraform.tfvars
echo "📝 Creating terraform/terraform.tfvars..."
cat <<VARSEOF >terraform/terraform.tfvars
project_id = "$PROJECT_ID"
region     = "$REGION"
VARSEOF

# Set current project
echo "⚙️ Setting gcloud project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "🔌 Enabling required APIs (this may take a minute)..."
SERVICES=(
  "compute.googleapis.com"
  "dataproc.googleapis.com"
  "dataform.googleapis.com"
  "bigquery.googleapis.com"
  "storage-api.googleapis.com"
  "aiplatform.googleapis.com"
)

gcloud services enable "${SERVICES[@]}"

echo "✅ Initialization complete!"
echo ""
echo "👉 Next steps:"
echo "1. cd terraform"
echo "2. terraform init"
echo "3. terraform apply"
