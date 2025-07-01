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

set -o nounset
set -o pipefail

COMMON_SCRIPT_DIRECTORY_PATH="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Path to the directory of this script: ${COMMON_SCRIPT_DIRECTORY_PATH}"

# shellcheck disable=SC2034 # Var used in other scripts
TERRAFORM_DIR="${COMMON_SCRIPT_DIRECTORY_PATH}"

declare -a terraservices
# shellcheck disable=SC2034 # Var used in other scripts
terraservices=(
  initialize
  networking
)

get_terraform_output() {
  terraservice="${1}"
  output_name="${2}"
  output_type="${3}"

  if [[ ! -d "${terraservice}" ]]; then
    echo "${terraservice} directory doesn't exist or is not readable"
    return 1
  fi

  local output
  if ! output="$(terraform -chdir="${terraservice}" init)"; then
    echo "Error while initializing ${terraservice} to get ${output_name} output: ${output}"
    return 1
  fi

  local -a output_command=(terraform -chdir="${terraservice}" output)
  if [[ "${output_type}" == "json" ]]; then
    output_command+=(-json)
  elif [[ "${output_type}" == "raw" ]]; then
    output_command+=(-raw)
  fi
  output_command+=("${output_name}")

  if ! output="$(
    "${output_command[@]}"
  )"; then
    echo "Error while getting ${output_name} output: ${output}. Output command: ${output_command[*]}"
    return 1
  fi
  echo "${output}"
}
