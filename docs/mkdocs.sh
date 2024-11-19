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

# Build docs directory by copying or linking files/folders from projects
# directories

echo "Initializing docs build folder at: ${BUILD_DIR}/docs"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/docs"

## Setup common files and folders
ln -sf "${DOCS_DIR}/index.md" "${BUILD_DIR}/docs/index.md"
ln -sf "${DOCS_DIR}/google13f96ebf51862cf4.html" "${BUILD_DIR}/docs/google13f96ebf51862cf4.html"
ln -sf "${DOCS_DIR}/common" "${BUILD_DIR}/docs/common"

for CURRENT_PROJECT_DIR in "${PROJECTS_DIR}"/*/; do
  PROJECT_DIRNAME="$(basename "$CURRENT_PROJECT_DIR")"
  if [[ -d "${CURRENT_PROJECT_DIR}/docs" ]]; then
    ln -s "${CURRENT_PROJECT_DIR}/docs" "${BUILD_DIR}/docs/${PROJECT_DIRNAME}"
  fi
done

cd "${DOCS_DIR}"

# Ensure user-guide is top of the nav list
[[ -e "${BUILD_DIR}/docs/user-guide" ]] &&
  mv "${BUILD_DIR}/docs/user-guide" "${BUILD_DIR}/docs/aaa-user-guide"

# Create Python venv.
echo "Initialize Python venv at: ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

## Activate python virtual environment to install and launch mkdocs
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"
echo "Installing python requirements: ${VENV_DIR}"
pip3 install \
  --quiet \
  --exists-action i \
  --require-hashes \
  --require-virtualenv \
  -r "${SCRIPT_DIR}/requirements.txt"

# Run mkdocs.
(cd "${SCRIPT_DIR}" && python3 -m mkdocs "$@")
