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
rm -rf "${BUILD_DIR}/docs" "${BUILD_DIR}/site"
mkdir -p "${BUILD_DIR}/docs"

## Setup common files and folders
ln -sf "${DOCS_DIR}/index.md" "${BUILD_DIR}/docs/index.md"
ln -sf "${DOCS_DIR}/google13f96ebf51862cf4.html" "${BUILD_DIR}/docs/google13f96ebf51862cf4.html"
ln -sf "${DOCS_DIR}/common" "${BUILD_DIR}/docs/common"
ln -sf "${DOCS_DIR}/stylesheets" "${BUILD_DIR}/docs/stylesheets"

for CURRENT_PROJECT_DIR in "${PROJECTS_DIR}"/*/; do
  PROJECT_DIRNAME="$(basename "$CURRENT_PROJECT_DIR")"
  if [[ -e "${CURRENT_PROJECT_DIR}/docs/index.md" || -e "${CURRENT_PROJECT_DIR}/docs/README.md" ]]; then
    # Use docs dir for documentation
    ln -s "${CURRENT_PROJECT_DIR}/docs" "${BUILD_DIR}/docs/${PROJECT_DIRNAME}"
  elif [[ -f "${CURRENT_PROJECT_DIR}/README.md" ]]; then
    echo "Using README.md for ${PROJECT_DIRNAME}"
    cd "${PROJECTS_DIR}"

    # We need the README and any referenced markdown or image files, including
    # their paths, copied to the docs directory
    # mkdocs will use either READNE.md or index.md as index page
    #
    # Use find with included and excluded file and dir patterns, dirs and
    # pass to cp --parent to copy with paths.
    INCLUDED_FILES_ARGS=(-name "*.md" -o -name "*.png" -o -name "*.jpg" -o -name "*.svg" -o -name ".pages")
    EXCLUDED_FILES_ARGS=(-iname "CHANGELOG*" -o -iname "LICENSE*" -o -iname "CONTRIBUTING*")
    EXCLUDED_DIRS_ARGS=(-path "*/node_modules/*" -o -path "*/build/*" -o -path "*/venv/*")
    find "${PROJECT_DIRNAME}" \
      \( "${INCLUDED_FILES_ARGS[@]}" \) \
      -a -not \( "${EXCLUDED_FILES_ARGS[@]}" \) \
      -a -not \( "${EXCLUDED_DIRS_ARGS[@]}" -prune \) \
      -print0 |
      xargs -0 -I '{}' cp --parent '{}' "${BUILD_DIR}/docs"
  fi
done

cd "${DOCS_DIR}"

# Ensure user-guide is top of the nav list
[[ -e "${BUILD_DIR}/docs/user-guide" ]] &&
  mv "${BUILD_DIR}/docs/user-guide" "${BUILD_DIR}/docs/aaa-user-guide"

# Check/setup python venv.
# * We could already be in a venv
#   (when run by 03-mkdocs-check)
# * Or there could already be a reusable local venv in known location
#   (when running locally)
# * Or there is none and we have to create one.
#   (when running locally for the first time, or when in github actions)
#
# Check if we are already in a venv?
# Checking for the VIRTUAL_ENV variable is not foolproof (a venv
# can be used without activation), in the context of where this script is run,
# it is a good enough check.
#
if [[ -z "${VIRTUAL_ENV:-}" || ! -x "${VIRTUAL_ENV}/bin/python3" ]]; then
  # No, check for an existing local venv:
  VENV_DIR="${DOCS_DIR}/../kokoro/.venv"
  if [[ ! -x "${VENV_DIR}/bin/python3" ]]; then
    # No - proably running in Github Actions, create a new local one.
    VENV_DIR="${BUILD_DIR}/venv"
    echo "Initialize Python venv at: ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  fi
  # shellcheck disable=SC1091 # do not follow
  source "${VENV_DIR}/bin/activate"
fi

## Activate python virtual environment to install and launch mkdocs
echo "Installing python requirements to ${VIRTUAL_ENV}"
pip3 install \
  --quiet \
  --exists-action i \
  --require-hashes \
  --require-virtualenv \
  -r "${SCRIPT_DIR}/requirements.txt"

# Run mkdocs.
(cd "${SCRIPT_DIR}" && python3 -m mkdocs "$@")
