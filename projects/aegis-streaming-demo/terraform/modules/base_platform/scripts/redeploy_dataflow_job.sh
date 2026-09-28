#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-${1:?Missing PROJECT_ID}}"
REGION="${REGION:-${2:?Missing REGION}}"
STAGING_BUCKET="${STAGING_BUCKET:-${3:?Missing STAGING_BUCKET}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

echo "[INFO] Cancelling any existing active Aegis Dataflow jobs in ${PROJECT_ID} (${REGION})..."
# Listing jobs may fail transiently or return empty if Dataflow API is still warming up.
ACTIVE_JOBS="$(gcloud dataflow jobs list \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --status=active \
  --filter="name:aegis" \
  --format="value(id)" || true)"

if [[ -n "${ACTIVE_JOBS}" ]]; then
  while IFS= read -r job_id; do
    if [[ -n "${job_id}" ]]; then
      echo "[INFO] Cancelling Dataflow job ${job_id}..."
      # Ignore cancel error if the job already transitioned out of an active state.
      gcloud dataflow jobs cancel "${job_id}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" || true
    fi
  done <<<"${ACTIVE_JOBS}"
fi

echo "[INFO] Cleaning up orphaned auto-created Pub/Sub subscriptions in ${PROJECT_ID}..."
# Listing subscriptions is a best-effort cleanup. Ignore a non-zero exit code if none match.
ORPHAN_SUBS="$(gcloud pubsub subscriptions list \
  --project="${PROJECT_ID}" \
  --filter="name:telemetry-raw.subscription-" \
  --format="value(name)" || true)"

if [[ -n "${ORPHAN_SUBS}" ]]; then
  while IFS= read -r sub_name; do
    if [[ -n "${sub_name}" ]]; then
      echo "[INFO] Deleting orphaned subscription ${sub_name}..."
      # Ignore deletion error if the subscription no longer exists.
      gcloud pubsub subscriptions delete "${sub_name}" \
        --project="${PROJECT_ID}" --quiet || true
    fi
  done <<<"${ORPHAN_SUBS}"
fi

NOW_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[INFO] Seeking telemetry-raw-dataflow-sub to ${NOW_UTC}..."
# Ignore seek error if the subscription is newly created or has no retained backlog.
gcloud pubsub subscriptions seek \
  "projects/${PROJECT_ID}/subscriptions/telemetry-raw-dataflow-sub" \
  --project="${PROJECT_ID}" \
  --time="${NOW_UTC}" || true

echo "[INFO] Launching fresh Cloud Dataflow Flex Template streaming job..."
GCP_PROJECT="${PROJECT_ID}" \
  GCP_REGION="${REGION}" \
  STAGING_BUCKET="${STAGING_BUCKET}" \
  bash "${REPO_ROOT}/pipelines/firstparty-dataflow/run_dataflow.sh"
