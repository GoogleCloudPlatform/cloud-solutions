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

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <eks_weight> <gke_weight>"
  echo "Example: $0 80 20"
  exit 1
fi

EKS_WEIGHT=$1
GKE_WEIGHT=$2

GKE_GATEWAY_IP=$(kubectl get gateway proxy-demo-gateway \
  -n app \
  -o jsonpath='{.status.addresses[0].value}')

echo "Applying Traffic Patch: EKS=$EKS_WEIGHT, GKE=$GKE_WEIGHT"
echo "---------------------------------------------------"

kubectl patch httproute proxy-demo-httproute -n app --type=json \
  -p="[
    {\"op\": \"replace\", \"path\": \"/spec/rules/0/backendRefs/0/weight\", \"value\": $EKS_WEIGHT},
    {\"op\": \"replace\", \"path\": \"/spec/rules/0/backendRefs/1/weight\", \"value\": $GKE_WEIGHT}
  ]"

echo -e "\nVerifying Cluster Weights:"
kubectl get httproute proxy-demo-httproute -n app -o yaml |
  awk '/name:/ {name=$2} /weight:/ {print "  " name ": " $2}'

echo -e "\nTesting Live Traffic (10 requests):"
echo "---------------------------------------------------"

echo -e "\nStep 3: Waiting for propagation..."
echo "---------------------------------------------------"

if [ "$GKE_WEIGHT" -gt 0 ]; then
  echo "Polling for GKE traffic detection..."
  MAX_RETRIES=60
  COUNT=0
  while true; do
    PROVIDER=$(curl -s -H "Host: proxy-demo.test" "http://${GKE_GATEWAY_IP}/" |
      grep -oP '(?<=<div class="provider">).*?(?=</div>)')

    if [ "$PROVIDER" == "Google Cloud" ]; then
      echo -e "\n[OK] Detected traffic! Propagation in progress."
      break
    fi

    COUNT=$((COUNT + 1))
    if [ "$COUNT" -ge "$MAX_RETRIES" ]; then
      echo -e "\n[TIMEOUT] Proceeding with test traffic not yet seen)."
      break
    fi
    echo -ne "Syncing: attempt $COUNT/$MAX_RETRIES... \r"
    sleep 2
  done
else
  echo "Waiting 10 seconds for weight shift..."
  sleep 10
fi

echo -e "\nPropagation window complete. Starting traffic test."

for i in {1..10}; do
  PROVIDER=$(curl -s -H "Host: proxy-demo.test" "http://${GKE_GATEWAY_IP}/" |
    grep -oP '(?<=<div class="provider">).*?(?=</div>)')

  PROVIDER=${PROVIDER:-"WAITING FOR LB..."}
  echo "Request $i: $PROVIDER"
done

echo "------------------------------------"
echo -e "\nVisual Verification"
echo "---------------------------------------------------"
echo "1. Open your browser to: http://localhost:8080"
echo "2. Refresh 10 times: Orange = EKS (AWS), Blue = GKE (Google Cloud)"
