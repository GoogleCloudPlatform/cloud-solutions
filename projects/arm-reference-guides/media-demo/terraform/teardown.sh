#!/bin/bash
#
# Copyright 2025 Google LLC
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

start_timestamp=$(date +%s)

SCRIPT_DIRECTORY_PATH="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# shellcheck disable=SC1091
source "${SCRIPT_DIRECTORY_PATH}/common.sh"

# shellcheck disable=SC2154 # Variable defined in common.sh
echo "Terraservices to destroy: ${terraservices[*]}"

for ((i = ${#terraservices[@]} - 1; i >= 0; i--)); do
  terraservice=${terraservices[i]}
  if [[ "${terraservice}" == "initialize" ]]; then
    echo "Skipping destroying the ${terraservice} Terraservice"
    continue
  fi
  terraform -chdir="${TERRAFORM_DIR}/${terraservice}" init &&
    terraform -chdir="${TERRAFORM_DIR}/${terraservice}" destroy -auto-approve || exit 1
done

rm -rf "${TERRAFORM_DIR}/initialize/backend.tf"
echo "Migrate state to the local backend"
terraform -chdir="${TERRAFORM_DIR}/initialize" init -force-copy -migrate-state

if ! terraform_bucket_name="$(get_terraform_output "${TERRAFORM_DIR}/initialize" "terraform_bucket_name" "raw")"; then
  exit 1
fi
# Quote the globbing expression because we don't want to expand it with the
# shell
gcloud storage rm -r "gs://${terraform_bucket_name}/*"
terraform -chdir="${TERRAFORM_DIR}/initialize" destroy -auto-approve || exit 1

rm -rf \
  "${TERRAFORM_DIR}/initialize/.terraform/" \
  "${TERRAFORM_DIR}/initialize"/terraform.tfstate*

git restore \
  "${TERRAFORM_DIR}/initialize/*.auto.tfvars"

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
