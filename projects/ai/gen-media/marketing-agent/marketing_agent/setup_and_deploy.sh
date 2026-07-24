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
set -e

PROJECT_ID="${1:?Usage: ./setup_and_deploy.sh PROJECT_ID [REGION]}"
REGION="${2:-us-central1}"
SERVICE_NAME="lj-nest-demo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"

# Generate unique bucket name if not already set
BUCKET_NAME="${DEMO_BUCKET:-nest-demo-${PROJECT_ID}-$(date +%s | tail -c 7)}"

# ============================================
# STEP 0: Enable required APIs + update .env
# ============================================
echo ""
echo "=== Step 0: Enable APIs, configure project, grant permissions ==="
gcloud services enable aiplatform.googleapis.com run.googleapis.com cloudbuild.googleapis.com storage.googleapis.com bigquery.googleapis.com --project="${PROJECT_ID}" 2>/dev/null || true

# Grant default compute SA all needed permissions
PROJECT_NUM=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)" 2>/dev/null)
if [ -n "$PROJECT_NUM" ]; then
    SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"
    echo "Granting permissions to ${SA}..."
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA}" --role="roles/storage.admin" --quiet 2>/dev/null || true
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA}" --role="roles/bigquery.admin" --quiet 2>/dev/null || true
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA}" --role="roles/aiplatform.user" --quiet 2>/dev/null || true
    echo "Service account permissions granted."
fi

# Grant deploying user BigQuery access
CURRENT_USER=$(gcloud config get-value account 2>/dev/null)
if [ -n "$CURRENT_USER" ]; then
    echo "Granting BigQuery access to ${CURRENT_USER}..."
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="user:${CURRENT_USER}" --role="roles/bigquery.admin" --quiet 2>/dev/null || true
fi

# Update .env with deployment project
sed -i.bak "s|GOOGLE_CLOUD_PROJECT=.*|GOOGLE_CLOUD_PROJECT=${PROJECT_ID}|g" "${SCRIPT_DIR}/.env"
sed -i.bak "s|PROJECT_ID=.*|PROJECT_ID=${PROJECT_ID}|g" "${SCRIPT_DIR}/.env"
sed -i.bak "s|YOUR_PROJECT_ID|${PROJECT_ID}|g" "${SCRIPT_DIR}/.env"
sed -i.bak "s|WITH_MOCKED_DATA=false|WITH_MOCKED_DATA=true|g" "${SCRIPT_DIR}/.env"
rm -f "${SCRIPT_DIR}/.env.bak"
echo "Updated .env with project: ${PROJECT_ID}"

# Create analyst bucket for agent session state
ANALYST_BUCKET="${PROJECT_ID}-analyst-bucket"
gcloud storage buckets describe "gs://${ANALYST_BUCKET}" --project="${PROJECT_ID}" 2>/dev/null || \
    gcloud storage buckets create "gs://${ANALYST_BUCKET}" --project="${PROJECT_ID}" --location="${REGION}" 2>/dev/null || true

# Create artifacts bucket
ARTIFACTS_BUCKET="${PROJECT_ID}-artifacts"
gcloud storage buckets describe "gs://${ARTIFACTS_BUCKET}" --project="${PROJECT_ID}" 2>/dev/null || \
    gcloud storage buckets create "gs://${ARTIFACTS_BUCKET}" --project="${PROJECT_ID}" --location="${REGION}" 2>/dev/null || true

# ============================================
# STEP 1: Upload demo assets + product images
# ============================================
echo ""
echo "=== Step 1: Upload assets ==="

gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" 2>/dev/null || \
    gcloud storage buckets create "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" --location="${REGION}"

ASSETS_DIR="${SCRIPT_DIR}/assets"
if [ -d "$ASSETS_DIR" ]; then
    echo "Uploading demo assets (top-level files only)..."
    find "${ASSETS_DIR}" -maxdepth 1 -type f | while read f; do
        gcloud storage cp "$f" "gs://${BUCKET_NAME}/" --project="${PROJECT_ID}" 2>/dev/null
    done
    echo "Demo assets uploaded."
else
    echo "WARNING: No assets found in ${ASSETS_DIR}/"
fi

echo ""
gcloud storage ls "gs://${BUCKET_NAME}/" --project="${PROJECT_ID}"

# Upload product images to artifacts bucket
PRODUCT_IMAGES_DIR="${SCRIPT_DIR}/assets/product_images"
if [ -d "$PRODUCT_IMAGES_DIR" ] && [ "$(ls -A $PRODUCT_IMAGES_DIR 2>/dev/null)" ]; then
    echo ""
    echo "=== Uploading product images to gs://${ARTIFACTS_BUCKET}/products/ ==="
    gcloud storage cp "${PRODUCT_IMAGES_DIR}/"* "gs://${ARTIFACTS_BUCKET}/products/" --project="${PROJECT_ID}"
    echo "$(ls "$PRODUCT_IMAGES_DIR" | wc -l | tr -d ' ') product images uploaded."
fi

# ============================================
# STEP 2: Setup BigQuery tables
# ============================================
BQ_DIR="${SCRIPT_DIR}/assets/bq"
if [ -d "$BQ_DIR" ] && [ -f "$BQ_DIR/products.csv" ]; then
    echo ""
    echo "=== Step 2: Setting up BigQuery ==="

    # Enable BigQuery API
    gcloud services enable bigquery.googleapis.com --project="${PROJECT_ID}" 2>/dev/null || true

    # Create dataset
    bq --project_id="${PROJECT_ID}" mk --dataset "${PROJECT_ID}:retail_analytics" 2>/dev/null || true

    # Update image_uri placeholder with actual bucket name
    sed "s|<your-artifacts-bucket>|${ARTIFACTS_BUCKET}|g" "$BQ_DIR/products.csv" > "/tmp/products_updated.csv"

    # Load products table
    echo "Loading products table..."
    bq --project_id="${PROJECT_ID}" load --replace --source_format=CSV --skip_leading_rows=1 --autodetect \
        "retail_analytics.products" "/tmp/products_updated.csv" 2>/dev/null || \
    bq --project_id="${PROJECT_ID}" load --replace --source_format=CSV --skip_leading_rows=1 --autodetect \
        "${PROJECT_ID}:retail_analytics.products" "/tmp/products_updated.csv"

    # Load inventory_analysis table
    if [ -f "$BQ_DIR/inventory_analysis.csv" ]; then
        echo "Loading inventory_analysis table..."
        bq --project_id="${PROJECT_ID}" load --replace --source_format=CSV --skip_leading_rows=1 --autodetect \
            "retail_analytics.inventory_analysis" "$BQ_DIR/inventory_analysis.csv" 2>/dev/null || \
        bq --project_id="${PROJECT_ID}" load --replace --source_format=CSV --skip_leading_rows=1 --autodetect \
            "${PROJECT_ID}:retail_analytics.inventory_analysis" "$BQ_DIR/inventory_analysis.csv"
    fi

    rm -f "/tmp/products_updated.csv"
    echo "BigQuery tables loaded."
else
    echo "No BQ data found — skipping BigQuery setup."
fi

# ============================================
# STEP 3: Deploy to Cloud Run (from source)
# ============================================
echo ""
echo "=== Step 3: Deploying to Cloud Run ==="

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --memory 8Gi \
  --cpu 4 \
  --timeout 900 \
  --concurrency 10 \
  --min-instances 1 \
  --port 8080 \
  --set-env-vars "DEMO_BUCKET=${BUCKET_NAME}" \
  --project "${PROJECT_ID}"

echo ""
echo "=== Deployment complete ==="
URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --format="value(status.url)")
echo ""
echo "App URL: ${URL}"
echo "Assets: gs://${BUCKET_NAME}/"
echo "Service: ${SERVICE_NAME}"
echo ""
echo "To redeploy: ./redeploy.sh ${PROJECT_ID} ${REGION}"
echo "To reuse bucket: DEMO_BUCKET=${BUCKET_NAME} ./setup_and_deploy.sh ${PROJECT_ID} ${REGION}"
