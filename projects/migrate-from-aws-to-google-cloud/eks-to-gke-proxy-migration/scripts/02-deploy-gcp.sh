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

TF_DIR="terraform/gcp"
terraform -chdir=${TF_DIR} init
terraform -chdir=${TF_DIR} apply -var="project_id=${PROJECT_ID}" -auto-approve

GKE_CLUSTER="$(terraform -chdir=${TF_DIR} output -raw cluster_name)"
GKE_GATEWAY_IP="$(terraform -chdir=${TF_DIR} output -raw gateway_ip)"
NAT_IP="$(terraform -chdir=${TF_DIR} output -raw nat_ip)"
REGION="$(terraform -chdir=${TF_DIR} output -raw region)"

echo "==> configuring kubectl"
gcloud container clusters get-credentials "${GKE_CLUSTER}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}"

echo "==> deploying to GKE"
kubectl apply -f k8s/namespace.yaml
sed -e "s|CLOUD_PROVIDER_PLACEHOLDER|GCP|g" \
  -e "s|PLATFORM_PLACEHOLDER|Google Kubernetes Engine|g" \
  -e "s|CLUSTER_NAME_PLACEHOLDER|${GKE_CLUSTER}|g" \
  -e "s|REGION_PLACEHOLDER|${REGION}|g" \
  k8s/configmap.yaml | kubectl apply -f -
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/gcp/service.yaml

kubectl rollout status deployment/proxy-demo -n "app"

echo ""
echo "======================================================"
echo "  GKE deploy complete"
echo "  GKE_CLUSTER    : ${GKE_CLUSTER}"
echo "  GKE_GATEWAY_IP : ${GKE_GATEWAY_IP}"
echo "  NAT_IP         : ${NAT_IP}"
echo "======================================================"
