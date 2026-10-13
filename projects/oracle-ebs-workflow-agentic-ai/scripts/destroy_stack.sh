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

# Automated Infrastructure Teardown Script for Oracle EBS Workflow Agentic AI Stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"

echo "======================================================================="
echo "   Oracle EBS Workflow Agentic AI — Automated Infrastructure Teardown"
echo "======================================================================="

if [ ! -d "${TERRAFORM_DIR}" ]; then
  echo "Error: Terraform directory not found at ${TERRAFORM_DIR}" >&2
  exit 1
fi

pushd "${TERRAFORM_DIR}" >/dev/null || exit 1

PROJECT_ID=""
REGION=""
ENVIRONMENT=""
if [ -f "terraform.tfvars" ]; then
  # Suppress grep non-zero exit codes when optional keys are absent in terraform.tfvars
  PROJECT_ID="$(grep -E '^\s*project_id\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
  REGION="$(grep -E '^\s*region\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
  ENVIRONMENT="$(grep -E '^\s*environment\s*=' terraform.tfvars | cut -d'=' -f2 | tr -d ' "' || echo "")"
fi

if [ -z "${PROJECT_ID}" ]; then
  # Suppress gcloud non-zero exit code if no default project is configured in the active profile
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null || echo "")"
fi

REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

echo "[1/1] Destroying Infrastructure Managed by Terraform..."
terraform destroy \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="environment=${ENVIRONMENT}" \
  -auto-approve -input=false

popd >/dev/null || exit 1

echo "======================================================================="
echo " [SUCCESS] Teardown Complete! All Terraform infrastructure has been destroyed."
echo "======================================================================="
