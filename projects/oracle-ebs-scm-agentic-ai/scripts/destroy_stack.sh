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

# Destroy every resource that Terraform manages for the VoltGuard agent.

set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"

# Terraform requires a value for every variable, even to destroy. Destroy
# never reads the passwords, so any non-empty value works when
# terraform.tfvars does not set them.
export TF_VAR_oracle_db_password="${TF_VAR_oracle_db_password:-unused-during-destroy}"
export TF_VAR_ebs_writeback_password="${TF_VAR_ebs_writeback_password:-unused-during-destroy}"

if command -v terraform >/dev/null 2>&1; then
  terraform -chdir="${TERRAFORM_DIR}" destroy -auto-approve -input=false
else
  docker run --rm -i \
    -u "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -e TF_VAR_oracle_db_password \
    -e TF_VAR_ebs_writeback_password \
    -e GOOGLE_APPLICATION_CREDENTIALS=/gcp/application_default_credentials.json \
    -v "${HOME}/.config/gcloud:/gcp:ro" \
    -v "${PROJECT_ROOT}:/workspace" \
    -w /workspace/terraform \
    hashicorp/terraform:1.17.1 destroy -auto-approve -input=false
fi

echo "Destroyed all Terraform-managed VoltGuard resources."
