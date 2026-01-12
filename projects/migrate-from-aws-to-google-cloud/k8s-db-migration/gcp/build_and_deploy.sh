#!/bin/bash
#
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

set -o errexit
set -o nounset
set -o pipefail

export TAG="latest"

# --- Main Script ---
echo "--- Authenticating and setting up ---"

# Configure Docker to authenticate with Artifact Registry
echo "🔐 Configuring Docker authentication for ${REGION}-docker.pkg.dev"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Get GKE cluster credentials
echo "🔑 Getting credentials for GKE cluster ${GKE_CLUSTER}"
gcloud container clusters get-credentials "${GKE_CLUSTER}" --region "${REGION}" --project "${GOOGLE_CLOUD_PROJECT_ID}" --dns-endpoint

kubectl create secret -n default generic cloud-sql-admin \
  --from-literal=username=postgres --from-literal=password=Chiapet22! \
  --from-literal=connectionName="$INSTANCE_CONNECTION_NAME"

SERVICES=(
  "contacts:devrel-demos/containers/aws-gcp-migration/gcp/src/accounts/contacts"
  "userservice:devrel-demos/containers/aws-gcp-migration/gcp/src/accounts/userservice"
  "frontend:devrel-demos/containers/aws-gcp-migration/gcp/src/frontend"
  "transactionhistory:devrel-demos/containers/aws-gcp-migration/gcp/src/ledger/transactionhistory"
  "ledgerwriter:devrel-demos/containers/aws-gcp-migration/gcp/src/ledger/ledgerwriter"
  "balancereader:devrel-demos/containers/aws-gcp-migration/gcp/src/ledger/balancereader"
)

KUSTOMIZE_DIR="devrel-demos/containers/aws-gcp-migration/gcp/kubernetes"

echo "--- Building, pushing, and updating images ---"

for service in "${SERVICES[@]}"; do
  # Split the service string into image name and context path
  IFS=':' read -r -a service_parts <<<"$service"
  IMAGE_NAME="${service_parts[0]}"
  CONTEXT_PATH="${service_parts[1]}"

  DOCKER_TAG="${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${TAG}"

  echo "--- Processing ${IMAGE_NAME} ---"
  echo "🐳 Building and pushing container image: ${DOCKER_TAG}"

  # Build and push the Docker image
  docker build --tag "${DOCKER_TAG}" "${CONTEXT_PATH}"
  docker push "${DOCKER_TAG}"

  # Update the kustomization to use the new image tag
  echo "📝 Updating kustomization for ${IMAGE_NAME} to use tag ${TAG}"
  (cd "${KUSTOMIZE_DIR}" && kustomize edit set image "${IMAGE_NAME}"="${DOCKER_TAG}")
done

echo "--- Deploying to GKE ---"
kubectl apply -k "${KUSTOMIZE_DIR}"

echo "--- Deployment complete ---"
