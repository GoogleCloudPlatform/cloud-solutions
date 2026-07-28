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

set -euo pipefail

# Load .env if present
if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi

# ── Configuration (prompt if not set) ─────────────────────
if [ -z "${GOOGLE_CLOUD_PROJECT:-}" ]; then
  GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project 2>/dev/null)
  if [ -z "${GOOGLE_CLOUD_PROJECT}" ]; then
    read -rp "Enter your GCP Project ID: " GOOGLE_CLOUD_PROJECT
  fi
  export GOOGLE_CLOUD_PROJECT
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-video-ads-studio}"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "============================================"
echo "Video Ads Studio — Cloud Run Deployment"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  Image:    ${IMAGE}"
echo "============================================"

# ── Step 1: Build container image ─────────────────────────
echo ""
echo "Step 1/3: Building container image..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE}" \
  --timeout=600 \
  .

# ── Step 2: Deploy to Cloud Run ───────────────────────────
echo ""
echo "Step 2/3: Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --platform=managed \
  --port=8080 \
  --memory=16Gi \
  --cpu=8 \
  --cpu-boost \
  --timeout=3600 \
  --concurrency=10 \
  --min-instances=2 \
  --max-instances=15 \
  --no-cpu-throttling \
  --execution-environment=gen2 \
  --session-affinity \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"

# ── Step 3: Get service URL ───────────────────────────────
echo ""
echo "Step 3/3: Fetching service URL..."
URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(status.url)")

echo ""
echo "============================================"
echo "Deployment complete!"
echo "  URL: ${URL}"
echo "============================================"
