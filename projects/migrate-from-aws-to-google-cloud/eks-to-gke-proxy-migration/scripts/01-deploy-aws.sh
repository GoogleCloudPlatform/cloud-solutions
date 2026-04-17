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

TF_DIR="terraform/aws"
terraform -chdir=${TF_DIR} init
terraform -chdir=${TF_DIR} apply -auto-approve

EKS_CLUSTER_NAME="$(terraform -chdir=${TF_DIR} output -raw cluster_name)"
AWS_REGION="$(terraform -chdir=${TF_DIR} output -raw region)"

echo "==> configuring kubectl"
aws eks update-kubeconfig \
  --name "${EKS_CLUSTER_NAME}" \
  --region "${AWS_REGION}"

echo "==> deploying to EKS"
kubectl apply -f k8s/namespace.yaml
sed -e "s|CLOUD_PROVIDER_PLACEHOLDER|AWS|g" \
  -e "s|PLATFORM_PLACEHOLDER|Amazon EKS|g" \
  -e "s|CLUSTER_NAME_PLACEHOLDER|${EKS_CLUSTER_NAME}|g" \
  -e "s|REGION_PLACEHOLDER|${AWS_REGION}|g" \
  k8s/configmap.yaml | kubectl apply -f -
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/aws/service.yaml

kubectl rollout status deployment/proxy-demo -n "app"

echo "==> waiting for load balancer"
until kubectl get svc proxy-demo \
  -n "app" \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' \
  2>/dev/null | grep -q '.'; do
  sleep 5
done

EKS_ALB_HOSTNAME=$(kubectl get svc proxy-demo \
  -n "app" \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
export EKS_ALB_HOSTNAME

EKS_ALB_IP=""
echo "Waiting for ALB DNS to resolve..."
while [ -z "$EKS_ALB_IP" ]; do
  EKS_ALB_IP=$(dig +short "${EKS_ALB_HOSTNAME}" | head -1)
  if [ -z "$EKS_ALB_IP" ]; then
    sleep 5
  fi
done

echo ""
echo "======================================================"
echo "  EKS deploy complete"
echo "  EKS_CLUSTER_NAME : ${EKS_CLUSTER_NAME}"
echo "  EKS_ALB_HOSTNAME : ${EKS_ALB_HOSTNAME}"
echo "  EKS_ALB_IP       : ${EKS_ALB_IP}"
echo "======================================================"
