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

echo "==> applying Gateway"
kubectl apply -f k8s/migration/gateway.yaml

echo "==> waiting for Gateway to be PROGRAMMED"
until kubectl get gateway proxy-demo-gateway \
  -n app \
  -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}' \
  2>/dev/null | grep -q "True"; do
  sleep 10
done
echo "Gateway is PROGRAMMED"

if [[ -z "${EKS_ALB_HOSTNAME:-}" ]]; then
  echo "ERROR: EKS_ALB_HOSTNAME is empty or could not be retrieved. Ensure AWS deploy completed successfully."
  exit 1
fi

echo "==> applying proxy ConfigMap"
sed "s|EKS_ALB_HOSTNAME_PLACEHOLDER|${EKS_ALB_HOSTNAME}|g" \
  k8s/migration/proxy-configmap.yaml |
  kubectl apply -f -

echo "==> applying proxy Deployment"
kubectl apply -f k8s/migration/proxy-deployment.yaml

echo "==> waiting for proxy rollout"
kubectl rollout status deployment/eks-proxy \
  -n app

echo "==> applying proxy Service"
kubectl apply -f "k8s/migration/proxy-service.yaml"

echo "==> applying HTTPRoute (100% proxy / 0% GKE)"
kubectl apply -f k8s/migration/httproute.yaml

GATEWAY_IP=$(kubectl get gateway proxy-demo-gateway \
  -n app \
  -o jsonpath='{.status.addresses[0].value}')

echo "==> waiting for Gateway data plane to propagate (this can take 2-3 minutes)..."
until curl -s -o /dev/null -w "%{http_code}" -H "Host: proxy-demo.test" "http://${GATEWAY_IP}/" | grep -q "200"; do
  sleep 10
done
echo "Gateway is fully ready!"

echo ""
echo "======================================================"
echo "  Migration resources deployed"
echo ""
echo "  Gateway IP   : ${GATEWAY_IP}"
echo "  Proxy target : ${EKS_ALB_HOSTNAME}"
echo "  HTTPRoute    : 100% proxy / 0% GKE"
echo "======================================================"
