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

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Running Oracle EBS Workflow Agentic AI Verification Suite ==="
pushd "${PROJECT_ROOT}" >/dev/null || exit 1

# Activate local virtual environment if present; .venv is dynamically created and not tracked in git
if [[ -f "${PROJECT_ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.venv/bin/activate"
fi

echo "--> 1. Compiling Python bytecode..."
python3 -m compileall src tests

echo "--> 2. Running Ruff linter..."
ruff check src tests

echo "--> 3. Running Pylint..."
RCFILE="${PROJECT_ROOT}/../../config/lint/python-lint.rc"
if [[ -f "${RCFILE}" ]]; then
  pylint --rcfile="${RCFILE}" src tests
else
  pylint src tests
fi

echo "--> 4. Running Mypy type checker..."
mypy src tests

echo "--> 5. Running Pytest test suite..."
pytest tests -v

popd >/dev/null || exit 1
echo "=== All checks passed successfully! 100% compliant with enterprise standards ==="
