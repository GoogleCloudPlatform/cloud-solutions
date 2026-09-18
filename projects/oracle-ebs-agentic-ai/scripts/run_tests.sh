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

set -euo pipefail

export ORACLE_MOCK_DB=true
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-test-project}"

PYTEST_CMD="pytest"
PYTHON_CMD="python3"

if ! command -v pytest &>/dev/null; then
  if [ -f ".venv/bin/pytest" ]; then
    PYTEST_CMD=".venv/bin/pytest"
    PYTHON_CMD=".venv/bin/python3"
  elif [ -f "${HOME}/.venv/bin/pytest" ]; then
    PYTEST_CMD="${HOME}/.venv/bin/pytest"
    PYTHON_CMD="${HOME}/.venv/bin/python3"
  fi
fi

echo "=== Running Python Bytecode Compilation ==="
$PYTHON_CMD -m py_compile src/a2a/a2a_server.py src/mcp/ebs_db_client.py src/agents/*.py tests/*.py

echo "=== Running Pytest Integration Suite ==="
$PYTEST_CMD tests/test_integration.py -v
