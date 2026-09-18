#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Automated Infrastructure Teardown Script for Oracle EBS Agentic AI Stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"

echo "======================================================================="
echo "   Oracle EBS Agentic AI — Automated Infrastructure Teardown"
echo "======================================================================="

if [ ! -d "${TERRAFORM_DIR}" ]; then
  echo "Error: Terraform directory not found at ${TERRAFORM_DIR}" >&2
  exit 1
fi

pushd "${TERRAFORM_DIR}" >/dev/null

echo "[1/2] Destroying Infrastructure Managed by Terraform..."
terraform destroy -auto-approve -input=false

echo "[2/2] Restoring Local Source Templates if needed..."
if [ -f "${PROJECT_ROOT}/.git" ] || [ -d "${PROJECT_ROOT}/.git" ]; then
  # Safely restore tracked template if it was temporarily modified during apply;
  # ignore exit errors if git working tree has no uncommitted diffs.
  git checkout terraform/gemini_extension_openapi.yaml 2>/dev/null || true
fi

popd >/dev/null

echo "======================================================================="
echo " [SUCCESS] Teardown Complete! All Terraform infrastructure has been destroyed."
echo "======================================================================="
