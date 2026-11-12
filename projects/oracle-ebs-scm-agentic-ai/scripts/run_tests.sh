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

# Run the unit tests and the Python checks that Super-linter and CI enforce.

set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LINT_CONFIG_DIR="$(git -C "${PROJECT_DIR}" rev-parse --show-toplevel)/config/lint"

pushd "${PROJECT_DIR}" >/dev/null
pytest tests/ -v --cov=oracle_ebs_scm_agentic_ai --cov-fail-under=90
ruff check src/ tests/
ruff format --check src/ tests/
isort --settings-path "${LINT_CONFIG_DIR}/python-isort.toml" --check-only \
  src/ tests/
mypy
popd >/dev/null
