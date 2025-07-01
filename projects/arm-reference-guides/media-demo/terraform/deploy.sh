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
echo "Terraservices to provision: ${terraservices[*]}"

# Initialize the environment and the local backend, in case this is the first
# run, because there's no remote backend yet
terraform -chdir="${TERRAFORM_DIR}/initialize" init -force-copy -migrate-state &&
  terraform -chdir="${TERRAFORM_DIR}/initialize" plan -input=false -out=tfplan &&
  terraform -chdir="${TERRAFORM_DIR}/initialize" apply -input=false tfplan || exit 1
rm "${TERRAFORM_DIR}/initialize/tfplan"

for terraservice in "${terraservices[@]}"; do
  echo "Current directory: $(pwd)" &&
    terraform -chdir="${TERRAFORM_DIR}/${terraservice}" init -force-copy -migrate-state &&
    terraform -chdir="${TERRAFORM_DIR}/${terraservice}" plan -input=false -out=tfplan &&
    terraform -chdir="${TERRAFORM_DIR}/${terraservice}" apply -input=false tfplan || exit 1
  rm "${TERRAFORM_DIR}/${terraservice}/tfplan"
done

if ! terraform_bucket_name="$(get_terraform_output "${TERRAFORM_DIR}/initialize" "terraform_bucket_name" "raw")"; then
  exit 1
fi

echo "Checking if the Terraform state has been migrated to ${terraform_bucket_name}"
if gcloud storage ls "gs://${terraform_bucket_name}/terraform/initialize/default.tfstate" &>/dev/null; then
  echo "Remove local state files because we migrated them to ${terraform_bucket_name}"
  rm -rf terraform.tfstate*
fi

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
