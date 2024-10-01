#!/bin/bash
#
# Copyright 2024 Google LLC
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
set -Eeuo pipefail

SCRIPT=$(realpath "$0")
SCRIPT_DIR=$(dirname "${SCRIPT}")
DOCS_DIR="${SCRIPT_DIR}"
PROJECTS_DIR=$(realpath "${SCRIPT_DIR}/../projects")
BUILD_DIR="${DOCS_DIR}/build"
VENV_DIR="${BUILD_DIR}/venv"

#
# The script creates a temporary build directory that uses
# the following structure:
#
# build/
#   + python-venv/     Python venv for running mkdocs
#   + docs/            Root directory for mkdocs content
#     + common/        Symlink to /docs/common/
#     + projects/
#       + [project]    Symlink to /projects/[project]/docs/
#
# This directory structure helps limit the number of directories
# mkdocs needs to watch for file changes.
#

#
# Make sure pip is installed.
#
if ! command python3 --version &>/dev/null; then
  >&2 echo "python3 not found. Make sure python3 is installed and available in PATH."
  exit
fi

# ReInitialize build folder if it exists
if [[ -d "${BUILD_DIR}" ]]; then

  rm -rf "${BUILD_DIR}/docs"
  mkdir -p "${BUILD_DIR}/docs"
fi

# Create symlinks.
## Setup common config and folders
RUN_DOCS_BASE="${BUILD_DIR}/docs"
echo "Initializing docs folder at: ${RUN_DOCS_BASE}"
mkdir -p "${RUN_DOCS_BASE}"

ln -sf "${DOCS_DIR}/index.md" "${RUN_DOCS_BASE}/index.md"
ln -sf "${DOCS_DIR}/google13f96ebf51862cf4.html" "${RUN_DOCS_BASE}/google13f96ebf51862cf4.html"
ln -sf "${DOCS_DIR}/common" "${RUN_DOCS_BASE}/common"

RUN_SOLUTIONS_FOLDER="$(realpath "${RUN_DOCS_BASE}")"
mkdir -p "${RUN_SOLUTIONS_FOLDER}"

for CURRENT_PROJECT_DIR in "${PROJECTS_DIR}"/*/; do
  if [[ -d "${CURRENT_PROJECT_DIR}/docs" ]]; then
    ln -s "${CURRENT_PROJECT_DIR}/docs" "${RUN_SOLUTIONS_FOLDER}/$(basename "$CURRENT_PROJECT_DIR")"
  fi
done

# Ensure user-guide is top of the nav list
[[ -e "${RUN_SOLUTIONS_FOLDER}/user-guide" ]] &&
  mv "${RUN_SOLUTIONS_FOLDER}/user-guide" "${RUN_SOLUTIONS_FOLDER}/aaa-user-guide"

# Create Python venv if not present
if [[ ! -d "${VENV_DIR}" ]]; then
  # Create Python venv.
  echo "Initialize Python venv at: ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

## Activate python virtual environment to install and launch mkdocs
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

echo "Installing python requirements: ${VENV_DIR}"
pip install \
  --quiet \
  --exists-action i \
  --require-hashes \
  -r "${SCRIPT_DIR}/requirements.txt"

# Run mkdocs.
(cd "${SCRIPT_DIR}" && python3 -m mkdocs "$@")
