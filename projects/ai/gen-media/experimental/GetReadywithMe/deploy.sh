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

# VTO Complete Suite - One-Line Deployment Script
# Usage: ./deploy.sh
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  VTO Complete Suite - Deployment         ${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# ---- Step 1: Collect Project Info ----
if [ -n "$1" ]; then
  PROJECT_ID="$1"
else
  DEFAULT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
  if [ -n "$DEFAULT_PROJECT" ]; then
    echo -e "Detected project: ${GREEN}${DEFAULT_PROJECT}${NC}"
    echo -n "Use this project? (y/n): "
    read -r USE_DEFAULT
    if [[ "$USE_DEFAULT" =~ ^[Yy]$ ]]; then
      PROJECT_ID="$DEFAULT_PROJECT"
    else
      echo -n "Enter Google Cloud Project ID: "
      read -r PROJECT_ID
    fi
  else
    echo -n "Enter Google Cloud Project ID: "
    read -r PROJECT_ID
  fi
fi

if [ -z "$PROJECT_ID" ]; then
  echo -e "${RED}Error: Project ID is required.${NC}"
  exit 1
fi

# Generate unique bucket name
RANDOM_STR=$(openssl rand -hex 3 2>/dev/null || echo "$RANDOM")
BUCKET_NAME="vto-demo-${PROJECT_ID}-${RANDOM_STR}"

echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Project ID:  $PROJECT_ID"
echo "  Bucket Name: $BUCKET_NAME"
echo ""
echo -n "Proceed with deployment? (y/n): "
read -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "Deployment cancelled."
  exit 0
fi

# ---- Step 2: Fix certificate issues ----
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false
export CLOUDSDK_PYTHON_SITEPACKAGES=1
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
unset CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE 2>/dev/null || true
unset CLOUDSDK_CONTEXT_AWARE_ACCESS_USE_CLIENT_CERTIFICATE 2>/dev/null || true
gcloud config unset context_aware/use_client_certificate 2>/dev/null || true
gcloud config set core/disable_prompts true 2>/dev/null || true

# ---- Step 3: Configure project ----
echo ""
echo -e "${BLUE}[1/6] Configuring project...${NC}"
gcloud config set project "$PROJECT_ID" --quiet

# ---- Step 4: Enable APIs ----
echo -e "${BLUE}[2/6] Enabling required APIs...${NC}"
gcloud services enable \
  run.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  --project="$PROJECT_ID" --quiet

# ---- Step 5: Create bucket ----
echo -e "${BLUE}[3/6] Creating GCS bucket...${NC}"
if gsutil mb -p "$PROJECT_ID" -l us-central1 "gs://$BUCKET_NAME" 2>/dev/null; then
  echo "  Created: gs://$BUCKET_NAME"
else
  if gsutil ls -b "gs://$BUCKET_NAME" &>/dev/null; then
    echo "  Using existing: gs://$BUCKET_NAME"
  else
    echo -e "${RED}Error: Could not create bucket. Name may be taken.${NC}"
    exit 1
  fi
fi

# ---- Step 6: Unzip and upload assets ----
echo -e "${BLUE}[4/6] Uploading assets to GCS bucket...${NC}"

ASSETS_DIR="$(cd "$(dirname "$0")" && pwd)/assets"
TEMP_DIR=$(mktemp -d)

if [ -d "$ASSETS_DIR" ]; then
  # Unzip each asset file and upload preserving directory structure
  for zipfile in "$ASSETS_DIR"/*.zip; do
    if [ -f "$zipfile" ]; then
      BASENAME=$(basename "$zipfile" .zip)
      echo "  Extracting and uploading: $BASENAME..."
      unzip -q -o "$zipfile" -d "$TEMP_DIR"
    fi
  done

  # Upload all extracted files to bucket
  echo "  Uploading all files to gs://$BUCKET_NAME/..."
  gsutil -m cp -r "$TEMP_DIR"/* "gs://$BUCKET_NAME/" 2>/dev/null || true
  echo "  Upload complete."

  # Clean up
  rm -rf "$TEMP_DIR"
else
  echo -e "${YELLOW}  No assets directory found. Skipping asset upload.${NC}"
fi

# ---- Step 7: Deploy to Cloud Run ----
echo -e "${BLUE}[5/6] Deploying to Cloud Run...${NC}"
echo "  Building and deploying (this may take 5-8 minutes)..."

gcloud run deploy vto-demo \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 8Gi \
  --cpu 4 \
  --timeout 600 \
  --concurrency 20 \
  --max-instances 3 \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET_NAME=$BUCKET_NAME,GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --project "$PROJECT_ID" \
  --quiet

# ---- Step 8: Get URL ----
echo -e "${BLUE}[6/6] Getting deployment URL...${NC}"
URL=$(gcloud run services describe vto-demo \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)' \
  --project "$PROJECT_ID")

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  Deployment Complete!                    ${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo -e "  App URL:     ${GREEN}$URL${NC}"
echo -e "  Project:     $PROJECT_ID"
echo -e "  Bucket:      gs://$BUCKET_NAME"
echo ""
echo -e "${YELLOW}To clean up later:${NC}"
echo "  gcloud run services delete vto-demo --region us-central1 --quiet"
echo "  gsutil -m rm -r gs://$BUCKET_NAME"
echo ""
