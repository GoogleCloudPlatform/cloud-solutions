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

# VTO Complete Suite - Redeploy Script
# Usage: ./redeploy.sh
# Redeploys the app to Cloud Run without recreating bucket or re-uploading assets.
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  VTO Complete Suite - Redeploy           ${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# ---- Step 1: Detect Project ID ----
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

# ---- Step 2: Detect existing bucket from Cloud Run service ----
echo ""
echo -e "${BLUE}[1/3] Detecting existing configuration...${NC}"
gcloud config set project "$PROJECT_ID" --quiet

BUCKET_NAME=$(gcloud run services describe vto-demo \
  --platform managed \
  --region us-central1 \
  --format 'value(spec.template.spec.containers[0].env.filter("name","GCS_BUCKET_NAME").value)' \
  --project "$PROJECT_ID" 2>/dev/null || echo "")

if [ -z "$BUCKET_NAME" ]; then
  echo -e "${YELLOW}Could not detect bucket from existing deployment.${NC}"
  echo -n "Enter GCS Bucket Name: "
  read -r BUCKET_NAME
  if [ -z "$BUCKET_NAME" ]; then
    echo -e "${RED}Error: Bucket name is required.${NC}"
    exit 1
  fi
fi

echo -e "  Project: ${GREEN}$PROJECT_ID${NC}"
echo -e "  Bucket:  ${GREEN}$BUCKET_NAME${NC}"
echo ""
echo -n "Redeploy with these settings? (y/n): "
read -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "Redeploy cancelled."
  exit 0
fi

# ---- Step 3: Fix certificate issues ----
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false
export CLOUDSDK_PYTHON_SITEPACKAGES=1
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
unset CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE 2>/dev/null || true
unset CLOUDSDK_CONTEXT_AWARE_ACCESS_USE_CLIENT_CERTIFICATE 2>/dev/null || true
gcloud config unset context_aware/use_client_certificate 2>/dev/null || true
gcloud config set core/disable_prompts true 2>/dev/null || true

# ---- Step 4: Deploy to Cloud Run ----
echo ""
echo -e "${BLUE}[2/3] Deploying to Cloud Run...${NC}"
echo "  Building and deploying..."

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

# ---- Step 5: Get URL ----
echo -e "${BLUE}[3/3] Getting deployment URL...${NC}"
URL=$(gcloud run services describe vto-demo \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)' \
  --project "$PROJECT_ID")

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  Redeploy Complete!                      ${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo -e "  App URL:     ${GREEN}$URL${NC}"
echo -e "  Project:     $PROJECT_ID"
echo -e "  Bucket:      gs://$BUCKET_NAME"
echo ""
