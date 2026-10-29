#!/bin/sh
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

set -eu

PROJECT_ID="$1"
REGION="$2"
REPO_ID="$3"

SCRIPT_DIR="$(CDPATH="" cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH="" cd -- "${SCRIPT_DIR}/.." && pwd)"

if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "${GOOGLE_APPLICATION_CREDENTIALS}" ]; then
  gcloud auth activate-service-account --key-file="${GOOGLE_APPLICATION_CREDENTIALS}" --quiet || true
fi

rm -rf "${PROJECT_ROOT}/app/data"
cp -r "${PROJECT_ROOT}/data" "${PROJECT_ROOT}/app/data"
trap 'rm -rf "${PROJECT_ROOT}/app/data"' EXIT

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_ID}/soa-refund-agent-app:latest"

for attempt in 1 2 3; do
  echo "Attempt ${attempt}: Building and pushing ${IMAGE_URI} via Cloud Build..."
  if gcloud builds submit "${PROJECT_ROOT}/app" \
    --tag="${IMAGE_URI}" \
    --project="${PROJECT_ID}" \
    --quiet; then
    exit 0
  fi
  sleep 15
done

exit 1
