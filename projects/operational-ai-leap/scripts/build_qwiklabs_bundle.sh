#!/usr/bin/env bash
# Copyright 2026 Google LLC
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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR_NAME="$(basename "$PROJECT_ROOT")"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"

OUTPUT_ZIP="${ROOT_DIR_NAME}_${TIMESTAMP}.zip"

echo "=== Building Qwiklabs Deployment Bundle from Git Tracked Files ==="
echo "Project Root: $PROJECT_ROOT"
echo "Output Archive: $OUTPUT_ZIP"

cd "$PROJECT_ROOT"

if ! command -v zip >/dev/null 2>&1; then
  echo "ERROR: zip command not found. Please install zip package." >&2
  exit 1
fi

rm -f "$OUTPUT_ZIP"

# Package all files tracked by git in the current project directory
git ls-files -z | xargs -0 zip -q "$OUTPUT_ZIP"

echo "=== Successfully created Qwiklabs deployment bundle: $PROJECT_ROOT/$OUTPUT_ZIP ==="
ls -lh "$PROJECT_ROOT/$OUTPUT_ZIP"
