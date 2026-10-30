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

set -euo pipefail

DOCKER_CONFIG=$(mktemp -d)
export DOCKER_CONFIG
trap 'rm -rf "$DOCKER_CONFIG"' EXIT

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <run_dir> <output_dir> [aws_profile]"
  exit 1
fi

RUN_DIR="$1"
OUTPUT_DIR="$2"
PROFILE=${3:-}

AWS_ARGS=()
[ -n "$PROFILE" ] && AWS_ARGS=(--profile "$PROFILE")

OUTPUT_MAPPING="${OUTPUT_DIR}/image-map.json"
INVENTORY_FILE="${RUN_DIR}/01-discovery/inventory.json"
ORCHESTRATOR_FILE="${RUN_DIR}/platform-handoff.json"

if [[ ! -f "${INVENTORY_FILE}" ]]; then
  echo "Error: Inventory file not found at ${INVENTORY_FILE}"
  exit 1
fi

if [[ ! -f "${ORCHESTRATOR_FILE}" ]]; then
  echo "Error: Orchestrator state file not found at ${ORCHESTRATOR_FILE}"
  exit 1
fi

# Extract target registry
TARGET_REGISTRY=$(jq -r '.registry_endpoint' "${ORCHESTRATOR_FILE}")
if [[ -z "${TARGET_REGISTRY}" || "${TARGET_REGISTRY}" == "null" ]]; then
  echo "Error: Could not extract registry_endpoint from ${ORCHESTRATOR_FILE}"
  exit 1
fi

echo "Target Artifact Registry: ${TARGET_REGISTRY}"

# Extract unique ECR images using grep, filtering out AWS/EKS infrastructure images.
# || true prevents the script from failing if grep finds no matching images.
ECR_IMAGES=$(grep -oE '(public\.ecr\.aws|[0-9]+\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com)[a-zA-Z0-9./:_-]+(@sha256:[a-f0-9]+)?' "${INVENTORY_FILE}" | grep -vE '/(kube-proxy|aws-ebs-csi-driver|aws-load-balancer-controller|amazon-k8s-cni|karpenter)(/|:|@|$)' | sort -u || true)

mkdir -p "${OUTPUT_DIR}"

if [[ -z "${ECR_IMAGES}" ]]; then
  echo "No ECR images found in inventory."
  echo "[]" >"${OUTPUT_MAPPING}"
  exit 0
fi

echo "Found ECR images to migrate:"
echo "${ECR_IMAGES}"

# Authenticate to Target Registry
echo "Authenticating to target Artifact Registry..."
GAR_HOST=$(echo "${TARGET_REGISTRY}" | cut -d'/' -f1)
gcloud auth print-access-token | gcrane auth login -u oauth2accesstoken --password-stdin "${GAR_HOST}"

# || true prevents failure if no private ECR domains are found in the image list.
DOMAINS=$(echo "${ECR_IMAGES}" | grep '\.amazonaws\.com' | cut -d'/' -f1 | sort -u || true)
if [[ -n "${DOMAINS}" ]]; then
  for domain in ${DOMAINS}; do
    region=$(echo "${domain}" | cut -d'.' -f4)
    echo "Authenticating to ECR domain ${domain} in region ${region}..."
    aws ecr get-login-password --region "${region}" "${AWS_ARGS[@]}" | gcrane auth login --username AWS --password-stdin "${domain}"
  done
fi

echo "Authenticating to public ECR..."
# || true prevents failure if public ECR login fails, allowing script to attempt private registry migration.
aws ecr-public get-login-password --region us-east-1 "${AWS_ARGS[@]}" | gcrane auth login --username AWS --password-stdin public.ecr.aws || true

# Prepare output mapping
echo "[" >"${OUTPUT_MAPPING}"
FIRST=true

for img in ${ECR_IMAGES}; do
  echo "Processing image: ${img}"

  # Strip domain to get path and tag/digest
  if [[ "${img}" == *"public.ecr.aws"* ]]; then
    IMG_PATH=${img#public.ecr.aws/}
  else
    IMG_PATH=$(echo "${img}" | cut -d'/' -f2-)
  fi

  # Separate repo path from tag/digest
  REPO_PATH="${IMG_PATH%%[:@]*}"
  TAG_OR_DIGEST=""
  if [[ "${IMG_PATH}" == *":"* ]]; then
    TAG_OR_DIGEST=":${IMG_PATH#*:}"
  elif [[ "${IMG_PATH}" == *"@"* ]]; then
    TAG_OR_DIGEST="@${IMG_PATH#*@}"
  fi

  # Clean up path to be a valid GAR repo name (lowercase, hyphens only)
  GAR_REPO_NAME=$(echo "${REPO_PATH}" | tr '/' '-' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')

  # Extract package name (last segment of original path)
  PACKAGE_NAME="${REPO_PATH##*/}"

  # Construct TARGET_IMG (3 segments: project/repo/package)
  TARGET_IMG="${TARGET_REGISTRY}/${GAR_REPO_NAME}/${PACKAGE_NAME}${TAG_OR_DIGEST}"

  echo "Copying ${img} to ${TARGET_IMG}..."
  gcrane cp "${img}" "${TARGET_IMG}" || echo "Warning: Failed to copy ${img}"

  if [ "${FIRST}" = true ]; then
    FIRST=false
  else
    echo "," >>"${OUTPUT_MAPPING}"
  fi

  # Append JSON object for this image
  jq -n --arg src "${img}" \
    --arg dst "${TARGET_IMG}" \
    '{ source: $src, target: $dst }' >>"${OUTPUT_MAPPING}"
done

echo "]" >>"${OUTPUT_MAPPING}"

echo "Migration complete. Mapping saved to ${OUTPUT_MAPPING}"
