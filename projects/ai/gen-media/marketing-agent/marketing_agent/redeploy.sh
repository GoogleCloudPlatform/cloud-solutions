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

PROJECT_ID="${1:?Usage: ./redeploy.sh PROJECT_ID [REGION]}"
REGION="${2:-us-central1}"
SERVICE_NAME="lj-nest-demo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"

# Update .env with deployment project
sed -i.bak "s|GOOGLE_CLOUD_PROJECT=.*|GOOGLE_CLOUD_PROJECT=${PROJECT_ID}|g" "${SCRIPT_DIR}/.env"
sed -i.bak "s|PROJECT_ID=.*|PROJECT_ID=${PROJECT_ID}|g" "${SCRIPT_DIR}/.env"
sed -i.bak "s|YOUR_PROJECT_ID|${PROJECT_ID}|g" "${SCRIPT_DIR}/.env"
rm -f "${SCRIPT_DIR}/.env.bak"

# Get current bucket from running service
BUCKET_NAME=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(spec.template.spec.containers[0].env[0].value)" 2>/dev/null || echo "lj-nest-demo")
echo "Bucket: ${BUCKET_NAME}"

echo ""
echo "=== Deploying to Cloud Run (from source) ==="
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
echo "=== Done ==="
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --format="value(status.url)"
