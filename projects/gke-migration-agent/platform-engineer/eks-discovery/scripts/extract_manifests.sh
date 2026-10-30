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

CLUSTER=$1
REGION=$2
PROFILE=${3:-}
OUTPUT_DIR=${4:-}

NAMESPACED_RESOURCES=(
  "configmaps"
  "cronjobs"
  "daemonsets"
  "deployments"
  "gateways"
  "horizontalpodautoscalers"
  "httproutes"
  "ingresses"
  "jobs"
  "networkpolicies"
  "persistentvolumeclaims"
  "poddisruptionbudgets"
  "rolebindings"
  "roles"
  "secrets"
  "serviceaccounts"
  "services"
  "statefulsets"
  "verticalpodautoscalers"
)

CLUSTER_SCOPED_RESOURCES=(
  "clusterrolebindings"
  "clusterroles"
  "persistentvolumes"
  "storageclasses"
)

if [ -z "$CLUSTER" ] || [ -z "$REGION" ]; then
  echo "Usage: $0 <cluster_name> <region> [aws_profile] [output_dir]"
  exit 1
fi

if [ -n "$PROFILE" ]; then
  export AWS_PROFILE="$PROFILE"
  echo "Using AWS Profile: $PROFILE"
fi

# Define project root relative to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."

if [ -n "$OUTPUT_DIR" ]; then
  RAW_DIR="$OUTPUT_DIR"
else
  RAW_DIR="$PROJECT_ROOT/01-discovery/raw"
fi
mkdir -p "$RAW_DIR"
RAW_DIR="$(cd "$RAW_DIR" && pwd)"
rm -f "$RAW_DIR/extraction_errors.log"

echo "=========================================================="
echo "Processing manifests for cluster: $CLUSTER in region: $REGION"
echo "=========================================================="

AWS_ARGS=()
[ -n "$PROFILE" ] && AWS_ARGS=(--profile "$PROFILE")

# Authenticate and isolate kubeconfig to avoid disrupting user's default environment
export KUBECONFIG="$RAW_DIR/kubeconfig.$CLUSTER"
aws eks update-kubeconfig --name "$CLUSTER" --region "$REGION" --alias "$CLUSTER" "${AWS_ARGS[@]}" >/dev/null || {
  echo "Failed to authenticate to cluster: $CLUSTER" >>"$RAW_DIR/extraction_errors.log"
  exit 1
}
kubectl config use-context "$CLUSTER" >/dev/null || {
  echo "Failed to set kubeconfig context for cluster: $CLUSTER" >>"$RAW_DIR/extraction_errors.log"
  exit 1
}

# Fetch bearer token once to avoid rate limiting on aws eks get-token exec calls.
# If token retrieval fails or is not supported by the environment, fall back to default kubeconfig auth.
EKS_TOKEN=$(aws eks get-token --cluster-name "$CLUSTER" --region "$REGION" "${AWS_ARGS[@]}" --query "status.token" --output text 2>/dev/null || true)
KUBECTL=(kubectl --kubeconfig "$RAW_DIR/kubeconfig.$CLUSTER")
[ -n "$EKS_TOKEN" ] && KUBECTL=(kubectl --kubeconfig "$RAW_DIR/kubeconfig.$CLUSTER" --token "$EKS_TOKEN")

MANIFEST_DIR="$RAW_DIR/manifests/$CLUSTER"
mkdir -p "$MANIFEST_DIR"

# Exclude kube-* namespaces to prevent migrating AWS/EKS-specific resources.
if ! NS_LIST=$("${KUBECTL[@]}" get ns -o jsonpath='{.items[*].metadata.name}' 2>&1 | tr ' ' '\n' | grep -v '^kube-'); then
  echo "Failed to get namespaces. Error: $NS_LIST" >>"$RAW_DIR/extraction_errors.log"
  NS_LIST=""
fi

if ! FS_STR=$("${KUBECTL[@]}" get ns -o name 2>&1 | grep '^namespace/kube-' | sed 's|^namespace/|metadata.namespace!=|' | paste -sd, -); then
  echo "Failed to get namespace field selector. Error: $FS_STR" >>"$RAW_DIR/extraction_errors.log"
  FS_STR=""
fi

FS_ARGS=()
[ -n "$FS_STR" ] && FS_ARGS=(--field-selector "$FS_STR")

# Disable errexit during extraction loops so missing CRDs/resources don't abort discovery
set +e

echo "Extracting namespaced Kubernetes resources per namespace..."
if [ -n "$NS_LIST" ]; then
  for NS in $NS_LIST; do
    echo "Processing namespace: $NS"
    NS_DIR="$MANIFEST_DIR/$NS"
    mkdir -p "$NS_DIR"
    "${KUBECTL[@]}" get namespace "$NS" --ignore-not-found -o yaml | yq '(.. | select(has("metadata"))).metadata |= del(.resourceVersion, .uid, .creationTimestamp, .selfLink) | (.. | select(has("status"))) |= del(.status)' >"$NS_DIR/namespace.yaml" ||
      echo "Failed to extract namespace resource: $NS" >>"$RAW_DIR/extraction_errors.log"
    for kind in "${NAMESPACED_RESOURCES[@]}"; do
      KIND_OUT=$("${KUBECTL[@]}" get "$kind" -n "$NS" --ignore-not-found -o name 2>&1)
      if [[ "$KIND_OUT" == *"error:"* ]]; then
        echo "Failed to check resource: $kind in namespace $NS. Error: $KIND_OUT" >>"$RAW_DIR/extraction_errors.log"
        continue
      fi

      if [ "$kind" = "configmaps" ]; then
        # Exclude system configmaps. grep returns non-zero exit code if all items match the exclusion; ignore to keep pipeline moving.
        KIND_OUT=$(printf '%s\n' "$KIND_OUT" | grep -v '^configmap/kube-root-ca.crt$' || true)
      fi

      if [ -n "$KIND_OUT" ]; then
        if [ "$kind" = "configmaps" ]; then
          readarray -t KIND_ARR <<<"$KIND_OUT"
          "${KUBECTL[@]}" get "${KIND_ARR[@]}" -n "$NS" -o yaml | yq '(.. | select(has("metadata"))).metadata |= del(.resourceVersion, .uid, .creationTimestamp, .selfLink) | (.. | select(has("status"))) |= del(.status)' >"$NS_DIR/$kind.yaml" ||
            echo "Failed to extract resource: $kind in namespace $NS" >>"$RAW_DIR/extraction_errors.log"
        else
          "${KUBECTL[@]}" get "$kind" -n "$NS" -o yaml | yq '(.. | select(has("metadata"))).metadata |= del(.resourceVersion, .uid, .creationTimestamp, .selfLink) | (.. | select(has("status"))) |= del(.status)' >"$NS_DIR/$kind.yaml" ||
            echo "Failed to extract resource: $kind in namespace $NS" >>"$RAW_DIR/extraction_errors.log"
        fi
      fi
    done
    # Prune directory if no resources were extracted for this namespace; ignore error if directory contains files.
    rmdir "$NS_DIR" 2>/dev/null || true
  done
fi

echo "Extracting cluster-scoped Kubernetes resources..."
CLUSTER_SCOPED_DIR="$MANIFEST_DIR/_cluster_scoped"
mkdir -p "$CLUSTER_SCOPED_DIR"
for kind in "${CLUSTER_SCOPED_RESOURCES[@]}"; do
  echo "Checking cluster-scoped resource: $kind"
  KIND_OUT=$("${KUBECTL[@]}" get "$kind" --ignore-not-found -o name 2>&1)
  echo "KIND_OUT for $kind: [${KIND_OUT:0:100}...]" # Truncated for safety if long
  if [[ "$KIND_OUT" == *"error:"* ]]; then
    echo "Failed to check cluster-scoped resource: $kind. Error: $KIND_OUT" >>"$RAW_DIR/extraction_errors.log"
    continue
  fi

  if [ -n "$KIND_OUT" ]; then
    "${KUBECTL[@]}" get "$kind" -o yaml | yq '(.. | select(has("metadata"))).metadata |= del(.resourceVersion, .uid, .creationTimestamp, .selfLink) | (.. | select(has("status"))) |= del(.status)' >"$CLUSTER_SCOPED_DIR/$kind.yaml" ||
      echo "Failed to extract cluster-scoped resource: $kind" >>"$RAW_DIR/extraction_errors.log"
  fi
done
# Prune directory if no cluster-scoped resources were extracted; ignore error if directory contains files.
rmdir "$CLUSTER_SCOPED_DIR" 2>/dev/null || true

echo "Extracting Custom Resources (CRDs)..."
rm -f "$MANIFEST_DIR/crds.yaml"
if ! API_RES=$("${KUBECTL[@]}" api-resources --verbs=list --namespaced -o name 2>/dev/null | grep -vE '^events$|^events\.events\.k8s\.io$|^componentstatuses$|^endpoints$|^endpointslices'); then
  echo "Failed to list API resources. Error: $API_RES" >>"$RAW_DIR/extraction_errors.log"
  API_RES=""
fi

[ -n "$API_RES" ] && echo "$API_RES" | while read -r R; do
  R_OUT=$("${KUBECTL[@]}" get "$R" --all-namespaces "${FS_ARGS[@]}" --ignore-not-found -o name 2>&1)
  if [[ "$R_OUT" == *"error:"* ]]; then
    echo "Failed to check CRD: $R. Error: $R_OUT" >>"$RAW_DIR/extraction_errors.log"
    continue
  fi

  if [ -n "$R_OUT" ]; then
    echo "---" >>"$MANIFEST_DIR/crds.yaml"
    "${KUBECTL[@]}" get "$R" --all-namespaces "${FS_ARGS[@]}" -o yaml | yq '(.. | select(has("metadata"))).metadata |= del(.resourceVersion, .uid, .creationTimestamp, .selfLink) | (.. | select(has("status"))) |= del(.status)' >>"$MANIFEST_DIR/crds.yaml" ||
      echo "Failed to extract CRD: $R" >>"$RAW_DIR/extraction_errors.log"
  fi
done

echo "Extracting IRSA Mapping (IAM Roles for Service Accounts)..."
SA_OUT=$("${KUBECTL[@]}" get sa --all-namespaces "${FS_ARGS[@]}" -o json 2>/dev/null | jq -r --arg cluster "$CLUSTER" '.items[] | select(.metadata.annotations["eks.amazonaws.com/role-arn"]) | [$cluster, .metadata.namespace, .metadata.name, .metadata.annotations["eks.amazonaws.com/role-arn"], "irsa"] | @tsv')
echo "SA_OUT: [${SA_OUT:0:100}...]" # Truncated for safety
if [ -n "$SA_OUT" ]; then
  echo "$SA_OUT" >"$RAW_DIR/irsa.$CLUSTER.tsv"
else
  echo "SA_OUT is empty"
  touch "$RAW_DIR/irsa.$CLUSTER.tsv"
fi

if [ -s "$RAW_DIR/irsa.$CLUSTER.tsv" ]; then
  while IFS=$'\t' read -r _ _ _ arn_role _; do
    ROLE=$(echo "$arn_role" | awk -F/ '{print $NF}')

    # Log failures to a file instead of crashing if a service account references a role that was deleted from AWS.
    aws iam get-role --role-name "$ROLE" "${AWS_ARGS[@]}" >"$RAW_DIR/iam.role.$ROLE.json" ||
      echo "Failed to get IAM role: $ROLE" >>"$RAW_DIR/extraction_errors.log"

    aws iam list-attached-role-policies --role-name "$ROLE" "${AWS_ARGS[@]}" >"$RAW_DIR/iam.role.$ROLE.attached.json" ||
      echo "Failed to list attached policies for role: $ROLE" >>"$RAW_DIR/extraction_errors.log"

    if [ -s "$RAW_DIR/iam.role.$ROLE.attached.json" ]; then
      for ARN in $(jq -r '.AttachedPolicies[].PolicyArn' "$RAW_DIR/iam.role.$ROLE.attached.json"); do
        POLICY_NAME=$(basename "$ARN")
        if VERSION_ID=$(aws iam get-policy --policy-arn "$ARN" --query 'Policy.DefaultVersionId' --output text "${AWS_ARGS[@]}" 2>/dev/null); then
          aws iam get-policy-version --policy-arn "$ARN" --version-id "$VERSION_ID" "${AWS_ARGS[@]}" >"$RAW_DIR/iam.role.$ROLE.attached.$POLICY_NAME.json" ||
            echo "Failed to get attached policy version for $ARN" >>"$RAW_DIR/extraction_errors.log"
        else
          echo "Failed to get policy info for $ARN" >>"$RAW_DIR/extraction_errors.log"
        fi
      done
    fi

    aws iam list-role-policies --role-name "$ROLE" "${AWS_ARGS[@]}" >"$RAW_DIR/iam.role.$ROLE.inline.json" ||
      echo "Failed to list inline policies for role: $ROLE" >>"$RAW_DIR/extraction_errors.log"

    if [ -s "$RAW_DIR/iam.role.$ROLE.inline.json" ]; then
      for P in $(jq -r '.PolicyNames[]' "$RAW_DIR/iam.role.$ROLE.inline.json"); do
        aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" "${AWS_ARGS[@]}" >"$RAW_DIR/iam.role.$ROLE.inline.$P.json" ||
          echo "Failed to get inline policy $P for role $ROLE" >>"$RAW_DIR/extraction_errors.log"
      done
    fi
  done <"$RAW_DIR/irsa.$CLUSTER.tsv"
fi

echo "Completed extraction for $CLUSTER."
