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
PROJECT_ROOT="$SCRIPT_DIR"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"

LABS=("postgresql-to-alloydb" "sqlserver-to-alloydb")

echo "=== Building Qwiklabs Deployment Bundles ==="
echo "Project Root: $PROJECT_ROOT"

# Clean up any existing zip files before generating new bundles
rm -f "$PROJECT_ROOT"/*.zip

if ! command -v zip >/dev/null 2>&1; then
  echo "ERROR: zip command not found. Please install zip package." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git command not found." >&2
  exit 1
fi

cd "$PROJECT_ROOT"

for LAB in "${LABS[@]}"; do
  if [ -d "$LAB" ]; then
    OUTPUT_ZIP="${LAB}_${TIMESTAMP}.zip"
    rm -f "$OUTPUT_ZIP"

    echo "Creating deployment bundle for $LAB..."
    (
      cd "$LAB"
      git ls-files -z | xargs -0 zip -q "$PROJECT_ROOT/$OUTPUT_ZIP"
    )

    echo "Successfully created: $PROJECT_ROOT/$OUTPUT_ZIP"
    ls -lh "$PROJECT_ROOT/$OUTPUT_ZIP"
  else
    echo "WARNING: Directory $LAB does not exist. Skipping."
  fi
done

echo "=== Packaging completed successfully ==="
