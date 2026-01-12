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

# Validate that the password variable is set
if [[ -z "${TF_VAR_rds_password}" ]]; then
  echo "Error: TF_VAR_rds_password is not set."
  exit 1
fi

deploy_infrastructure() {
  echo "Deploying GCP Infrastructure..."
  cd devrel-demos
  find containers/aws-gcp-migration/gcp/src/ledger -type f -name "Dockerfile" -exec sed -i 's|FROM openjdk:17-jdk-alpine|FROM eclipse-temurin:17-jdk-alpine|g' {} +
  sed -i 's/checkout int-federated-learning/checkout main/' ../devrel-demos/containers/aws-gcp-migration/gcp/google-cloud-infra-deploy.sh
  sed -i 's/deploy.sh/deploy-ap.sh/' ../devrel-demos/containers/aws-gcp-migration/gcp/google-cloud-infra-deploy.sh
  echo "$TF_VAR_rds_password" >containers/aws-gcp-migration/dms-user-password-source-database.txt
  export TF_VAR_platform_default_project_id=$GOOGLE_CLOUD_PROJECT_ID
  export GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT_ID
  containers/aws-gcp-migration/gcp/google-cloud-infra-deploy.sh
}

grant_permissions() {
  # Grant Cloud Build service account permissions to manage IAM for Workload Identity
  export KSA_NAME="boa-ksa"
  export GSA_NAME="boa-gsa"
  export NAMESPACE="default"
  export GKE_CLUSTER="acp-a-g-demo"

  gcloud container clusters get-credentials "${GKE_CLUSTER}" --region "us-central1" --project "${GOOGLE_CLOUD_PROJECT_ID}" --dns-endpoint

  # Create Google Service Account if it doesn't exist
  if ! gcloud iam service-accounts describe "${GSA_NAME}@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" --project="${GOOGLE_CLOUD_PROJECT_ID}" &>/dev/null; then
    echo "Creating Google Service Account: ${GSA_NAME}..."
    gcloud iam service-accounts create "${GSA_NAME}" \
      --display-name="${GSA_NAME}" \
      --project="${GOOGLE_CLOUD_PROJECT_ID}"
  else
    echo "Google Service Account ${GSA_NAME} already exists."
  fi

  # Create Kubernetes Service Account if it doesn't exist
  if ! kubectl get serviceaccount "${KSA_NAME}" --namespace "${NAMESPACE}" &>/dev/null; then
    echo "Creating Kubernetes Service Account: ${KSA_NAME}..."
    kubectl create serviceaccount "${KSA_NAME}" --namespace "${NAMESPACE}"
  else
    echo "Kubernetes Service Account ${KSA_NAME} already exists."
  fi

  # Add IAM policy binding for Workload Identity
  echo "Adding Workload Identity IAM binding..."
  gcloud iam service-accounts add-iam-policy-binding \
    "${GSA_NAME}@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" \
    --role "roles/iam.workloadIdentityUser" \
    --member "serviceAccount:${GOOGLE_CLOUD_PROJECT_ID}.svc.id.goog[${NAMESPACE}/${KSA_NAME}]" \
    --project "${GOOGLE_CLOUD_PROJECT_ID}"

  # Annotate Kubernetes Service Account
  echo "Annotating Kubernetes Service Account..."

  kubectl annotate serviceaccount \
    "${KSA_NAME}" \
    --namespace "${NAMESPACE}" \
    --overwrite \
    "iam.gke.io/gcp-service-account=${GSA_NAME}@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com"

  # Grant Cloud SQL Client role
  echo "Granting Cloud SQL Client role to GSA..."
  gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT_ID}" \
    --member "serviceAccount:${GSA_NAME}@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" \
    --role "roles/cloudsql.client"
}

# --- Execution ---
deploy_infrastructure
grant_permissions
