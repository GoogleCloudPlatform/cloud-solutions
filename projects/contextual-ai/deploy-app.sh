#!/bin/bash

# Copyright 2025 Google LLC
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

export CURRENT_DIR
CURRENT_DIR=$(pwd)

echo "Deploying Backend API..."

cd "${CURRENT_DIR}"/api || exit

gcloud run deploy contextial-ai-api --source . --allow-unauthenticated \
  --project "$GOOGLE_CLOUD_PROJECT" --region "$GOOGLE_CLOUD_LOCATION" \
  --service-account "cloud-sa@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT,GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION,VERTEX_AI_LOCATION=global" \
  --quiet

cd "${CURRENT_DIR}"/client || exit

export API_URL
API_URL=$(gcloud run services describe contextial-ai-api \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region us-central1 \
  --format="value(status.address.url)")

echo "Deploying Web frontend"
echo "REACT_APP_API_URL=${API_URL}" >.env.production

gcloud run deploy contextial-ai-client --source . --allow-unauthenticated \
  --project "$GOOGLE_CLOUD_PROJECT" --region "$GOOGLE_CLOUD_LOCATION" \
  --set-env-vars="REACT_APP_API_URL=$API_URL" \
  --port 80 \
  --service-account "cloud-sa@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --quiet

export WEB_URL
WEB_URL=$(gcloud run services describe contextial-ai-client \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region us-central1 \
  --format="value(status.address.url)")

cd "${CURRENT_DIR}" || exit

echo ">> Backend URL: ${API_URL}"
echo ">> Frontend URL: ${WEB_URL}"
