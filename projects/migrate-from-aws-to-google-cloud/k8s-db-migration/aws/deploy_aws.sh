#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -o errexit
set -o nounset
set -o pipefail

export NAMESPACE='default'

AWS_ROOT_DIR="aws"
DEVREL_PROJECT_DIR="containers/aws-gcp-migration/aws"
K8_MANIFESTS="devrel-demos/containers/aws-gcp-migration/aws/kubernetes/app-manifests"
TERRAFORM_DIR="${AWS_ROOT_DIR}/terraform"
deploy_infrastructure() {
  echo "Deploying AWS Infrastructure..."
  terraform -chdir=${TERRAFORM_DIR} init
  terraform -chdir=${TERRAFORM_DIR} apply -auto-approve

  RDS_DB_IDENTIFIER=$(terraform -chdir="${TERRAFORM_DIR}" output -raw rds_db_identifier)
  EKS_CLUSTER_NAME=$(terraform -chdir="${TERRAFORM_DIR}" output -raw eks_cluster_name)
  AWS_REGION=$(terraform -chdir="${TERRAFORM_DIR}" output -raw aws_region)
  ECR_URL=$(terraform -chdir="${TERRAFORM_DIR}" output -raw ecr_registry_url)
  RDS_ENDPOINT=$(terraform -chdir="${TERRAFORM_DIR}" output -raw rds_endpoint)

  echo "Reboot database $RDS_DB_IDENTIFIER..."
  aws rds reboot-db-instance \
    --db-instance-identifier "$RDS_DB_IDENTIFIER" \
    --region "$AWS_REGION" \
    --no-cli-pager

  echo "Waiting for database to come back online (this may take a few minutes)..."

  # Wait (silent)
  aws rds wait db-instance-available \
    --db-instance-identifier "$RDS_DB_IDENTIFIER" \
    --region "$AWS_REGION" \
    --no-cli-pager

  echo "Success! Database is available."

  if [ -z "$RDS_ENDPOINT" ]; then
    echo "Error: Failed to retrieve RDS Endpoint."
    exit 1
  fi

  aws eks update-kubeconfig --name "${EKS_CLUSTER_NAME}" --region "${AWS_REGION}"
  kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
  kubectl create serviceaccount cymbalbank-sa -n "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
  eksctl create iamserviceaccount \
    --name cymbalbank-sa \
    --namespace "${NAMESPACE}" \
    --region "$AWS_REGION" \
    --cluster "${EKS_CLUSTER_NAME}" \
    --attach-policy-arn "$(terraform -chdir="${TERRAFORM_DIR}" output -raw rds_access_policy_arn)" \
    --override-existing-serviceaccounts \
    --approve
}

build_and_push() {
  echo "Building and Pushing Images..."
  (
    echo "  -> Preparing workspace..."
    rm -rf devrel-demos
    echo "  -> Downloading source code from repository..."
    git clone --filter=blob:none --sparse https://github.com/GoogleCloudPlatform/devrel-demos
    cd devrel-demos
    git sparse-checkout set containers/aws-gcp-migration
    git checkout 7a7151a # Checkout the specific "frozen" commit hash

    if [ -z "$DEVREL_PROJECT_DIR" ]; then
      echo "Error: DEVREL_PROJECT_DIR is not set."
      exit 1
    fi

    cd "$DEVREL_PROJECT_DIR"

    echo "  -> Patching Dockerfiles..."
    # openjdk:17-jdk-alpine is deprecated
    find src/ledger -type f -name "Dockerfile" -exec sed -i 's|FROM openjdk:17-jdk-alpine|FROM eclipse-temurin:17-jdk-alpine|g' {} +

    echo "  -> Configuring build script..."
    REPO_PATH="cymbalbank"

    sed -i "s|ECR_URL=\"[^\"]*\"|ECR_URL=\"${ECR_URL}/${REPO_PATH}/\"|" ecr_build_push.sh

    echo "  -> Authenticating with AWS..."
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_URL"

    echo "  -> Running build script..."
    bash ecr_build_push.sh
  )
}

deploy_config_and_jwt() {
  echo "Deploy the Config and JWT files"
  # 1. Apply Secrets & Config
  kubectl apply -f "${K8_MANIFESTS}/config.yaml" -n "${NAMESPACE}"
  kubectl apply -f "${K8_MANIFESTS}/jwt-secret.yaml" -n "${NAMESPACE}"

}

db_load_and_config() {
  echo "Database setup, load and DMS config"

  DB_DMSCONFIG_LOAD_DIR="aws/demo-data"
  RDS_ENDPOINT=$(terraform -chdir="${TERRAFORM_DIR}" output -raw rds_endpoint)
  RDS_USERNAME="postgres"

  export RDS_PASSWORD="${TF_VAR_rds_password:?Error: Environment variable TF_VAR_rds_password is required}"

  echo "  -> Creating the databases..."
  TEMP_DB_JOB_FILE="$(mktemp)"
  sed -e "s|RDS_ENDPOINT_PLACEHOLDER|${RDS_ENDPOINT}|g" \
    -e "s|RDS_USERNAME_PLACEHOLDER|${RDS_USERNAME}|g" \
    -e "s|RDS_PASSWORD_PLACEHOLDER|${RDS_PASSWORD}|g" \
    "${DB_DMSCONFIG_LOAD_DIR}/create-databases-job.yaml" >"${TEMP_DB_JOB_FILE}"
  kubectl apply -f "${TEMP_DB_JOB_FILE}" -n "${NAMESPACE}"
  rm "${TEMP_DB_JOB_FILE}"
  echo "     -> Waiting for database creation job to complete..."
  kubectl wait --for=condition=complete job/create-databases --timeout=120s -n "${NAMESPACE}"

  echo "  -> Configuring DMS setup..."
  TEMP_DMS_JOB_FILE="$(mktemp)"
  sed -e "s|RDS_ENDPOINT_PLACEHOLDER|${RDS_ENDPOINT}|g" \
    -e "s|RDS_USERNAME_PLACEHOLDER|${RDS_USERNAME}|g" \
    -e "s|RDS_PASSWORD_PLACEHOLDER|${RDS_PASSWORD}|g" \
    "${DB_DMSCONFIG_LOAD_DIR}/create-dms-setup-job.yaml" >"${TEMP_DMS_JOB_FILE}"
  kubectl apply -f "${TEMP_DMS_JOB_FILE}" -n "${NAMESPACE}"
  rm "${TEMP_DMS_JOB_FILE}"
  echo "     -> Waiting for DMS setup creation job to complete..."
  kubectl wait --for=condition=complete job/create-dms-setup --timeout=120s -n "${NAMESPACE}"

  echo "  -> Populating the accounts database..."
  sed -e "s|RDS_PASSWORD_PLACEHOLDER|${RDS_PASSWORD}|g" \
    -e "s|RDS_ENDPOINT_PLACEHOLDER|${RDS_ENDPOINT}|g" \
    "${DB_DMSCONFIG_LOAD_DIR}/populate-accounts-db.yaml" | kubectl apply -f - -n "${NAMESPACE}"
  echo "     -> Waiting for accounts database population job to complete..."
  kubectl wait --for=condition=complete job/populate-accounts-db --timeout=120s -n "${NAMESPACE}"

  echo "  -> Populating the ledger database..."
  sed -e "s|RDS_PASSWORD_PLACEHOLDER|${RDS_PASSWORD}|g" \
    -e "s|RDS_ENDPOINT_PLACEHOLDER|${RDS_ENDPOINT}|g" \
    "${DB_DMSCONFIG_LOAD_DIR}/populate-ledger-db.yaml" | kubectl apply -f - -n "${NAMESPACE}"
  echo "     -> Waiting for ledger database population job to complete..."
  kubectl wait --for=condition=complete job/populate-ledger-db --timeout=120s -n "${NAMESPACE}"

  echo "Reboot database $RDS_DB_IDENTIFIER..."
  aws rds reboot-db-instance \
    --region "$AWS_REGION" \
    --db-instance-identifier "$RDS_DB_IDENTIFIER" \
    --no-cli-pager

  echo "Waiting for database to come back online (this may take a few minutes)..."

  # Wait (silent)
  aws rds wait db-instance-available \
    --region "$AWS_REGION" \
    --db-instance-identifier "$RDS_DB_IDENTIFIER" \
    --no-cli-pager

  echo "Success! Database is available."
}

configure_manifests() {
  echo "Configuring Kubernetes Manifests..."
  ACCOUNTS_URI="postgresql://postgres:${RDS_PASSWORD}@${RDS_ENDPOINT}:5432/accounts-db"
  LEDGER_URI="jdbc:postgresql://${RDS_ENDPOINT}:5432/ledger-db"

  # Patch Config
  sed -i "s|ACCOUNTS_DB_URI: .*|ACCOUNTS_DB_URI: \"$ACCOUNTS_URI\"|" "${K8_MANIFESTS}/config.yaml"
  sed -i "s|SPRING_DATASOURCE_URL: .*|SPRING_DATASOURCE_URL: \"$LEDGER_URI\"|" "${K8_MANIFESTS}/config.yaml"

  # Patch Images
  IMAGES=("contacts" "userservice" "frontend" "transactionhistory" "ledgerwriter" "balancereader" "loadgenerator")
  for IMAGE_NAME in "${IMAGES[@]}"; do
    FULL_IMAGE="${ECR_URL}/cymbalbank/${IMAGE_NAME}:latest"
    sed -i "s|image: .*cymbalbank/${IMAGE_NAME}.*|image: ${FULL_IMAGE}|" "${K8_MANIFESTS}"/*.yaml
  done
}

deploy_k8s() {
  echo "Deploying to EKS..."
  PROJECT_TAG=$(terraform -chdir="${TERRAFORM_DIR}" output -raw aws_project_tag)
  ENV_TAG=$(terraform -chdir="${TERRAFORM_DIR}" output -raw aws_environment_tag)
  echo "    -> Applying application manifests..."
  sed -i "s/namespace: default/namespace: ${NAMESPACE}/g" "${K8_MANIFESTS}/frontend.yaml"
  kubectl delete ingressclass alb --ignore-not-found=true
  kubectl apply -f "${K8_MANIFESTS}" -n "${NAMESPACE}"

  echo "    -> Patching frontend Ingress with ALB tags..."
  kubectl patch ingress frontend -n "${NAMESPACE}" --type=merge \
    -p '{"metadata":{"annotations":{"alb.ingress.kubernetes.io/tags":"Project='"$PROJECT_TAG"', Env='"$ENV_TAG"'"}}}'
}

wait_for_ingress() {
  echo "Waiting for Ingress hostname/IP..."
  local EXTERNAL_IP=""
  local RETRIES=0
  local MAX_RETRIES=40

  while [ -z "$EXTERNAL_IP" ]; do
    if [ $RETRIES -ge $MAX_RETRIES ]; then
      echo "FAILED: Timeout waiting for Ingress status."
      exit 1
    fi

    EXTERNAL_IP=$(kubectl get ingress -n "${NAMESPACE}" frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

    if [ -z "$EXTERNAL_IP" ]; then
      echo "Attempt $((RETRIES + 1)): Hostname not assigned. Sleeping 30s..."
      sleep 30
      ((RETRIES++))
    fi
  done

  echo "Hostname assigned: $EXTERNAL_IP"

  echo "Waiting for ALB to pass health checks..."
  until curl --output /dev/null --silent --head --fail "http://$EXTERNAL_IP"; do
    echo "ALB still provisioning... retrying in 20s"
    sleep 20
  done

  echo "🚀 AWS deployment complete!"
  echo "--------------------------------"
  echo "EKS Cluster Name: ${EKS_CLUSTER_NAME}"
  echo "EKS Cluster Config: aws eks update-kubeconfig --region ${AWS_REGION} --name ${EKS_CLUSTER_NAME}"
  echo "RDS Endpoint:     ${RDS_ENDPOINT}"
  echo "Frontend URL:     http://${EXTERNAL_IP}"
  echo "--------------------------------"
}

# --- Execution ---
deploy_infrastructure
build_and_push
deploy_config_and_jwt
db_load_and_config
configure_manifests
deploy_k8s
wait_for_ingress
