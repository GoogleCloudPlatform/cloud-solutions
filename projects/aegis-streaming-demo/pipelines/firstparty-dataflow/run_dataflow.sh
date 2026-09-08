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

# =============================================================================
# Project Aegis - Cloud Dataflow Streaming Pipeline Launcher Script
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ID="${GCP_PROJECT:-${GOOGLE_CLOUD_PROJECT:-aegis-streaming-demo-fp-1001}}"
REGION="${GCP_REGION:-us-central1}"
RUNNER="${RUNNER:-FlexTemplate}"
STAGING_BUCKET="${STAGING_BUCKET:-${PROJECT_ID}-dataflow-staging}"
TOPIC_NAME="projects/${PROJECT_ID}/topics/telemetry-raw"
BIGTABLE_INSTANCE="aegis-bigtable"
BIGTABLE_TABLE="telemetry_metrics"
BIGQUERY_TABLE="${PROJECT_ID}:analytics.telemetry_events"
JOB_NAME="aegis-dataflow-streaming-$(date +%s)"

echo "================================================================="
echo " [INFO] Project Aegis - Launching Cloud Dataflow Streaming Pipeline"
echo "================================================================="
echo " - Project ID:         ${PROJECT_ID}"
echo " - Region:             ${REGION}"
echo " - Runner:             ${RUNNER}"
echo " - Input Topic:        ${TOPIC_NAME}"
echo " - Bigtable Sink:      ${BIGTABLE_INSTANCE}.${BIGTABLE_TABLE}"
echo " - BigQuery Sink:      ${BIGQUERY_TABLE}"
echo " - Staging Bucket:     gs://${STAGING_BUCKET}"
echo " - Job Name:           ${JOB_NAME}"
echo "================================================================="

if [ "${RUNNER}" == "FlexTemplate" ]; then
  if ! command -v gcloud &>/dev/null; then
    echo "[ERROR] 'gcloud' CLI is required for FlexTemplate runner." >&2
    exit 1
  fi
  gcloud dataflow flex-template run "${JOB_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --template-file-gcs-location="gs://${STAGING_BUCKET}/templates/aegis_dataflow_template.json" \
    --parameters="input_topic=${TOPIC_NAME},bigtable_project=${PROJECT_ID},bigtable_instance=${BIGTABLE_INSTANCE},bigtable_table=${BIGTABLE_TABLE},bigquery_table=${BIGQUERY_TABLE},window_seconds=10" \
    --service-account-email="aegis-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --subnetwork="https://www.googleapis.com/compute/v1/projects/${PROJECT_ID}/regions/${REGION}/subnetworks/aegis-subnet" \
    --disable-public-ips \
    --enable-streaming-engine \
    --max-workers=5 \
    --num-workers=1 \
    "$@"
elif [ "${RUNNER}" == "DataflowRunner" ]; then
  python3 "${SCRIPT_DIR}/src/pipeline.py" \
    --input_topic="${TOPIC_NAME}" \
    --bigtable_project="${PROJECT_ID}" \
    --bigtable_instance="${BIGTABLE_INSTANCE}" \
    --bigtable_table="${BIGTABLE_TABLE}" \
    --bigquery_table="${BIGQUERY_TABLE}" \
    --window_seconds=10 \
    --runner=DataflowRunner \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --temp_location="gs://${STAGING_BUCKET}/temp" \
    --staging_location="gs://${STAGING_BUCKET}/staging" \
    --job_name="${JOB_NAME}" \
    --service_account_email="aegis-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --subnetwork="https://www.googleapis.com/compute/v1/projects/${PROJECT_ID}/regions/${REGION}/subnetworks/aegis-subnet" \
    --no_use_public_ips \
    --streaming \
    --max_num_workers=5 \
    --num_workers=1 \
    --autoscaling_algorithm=THROUGHPUT_BASED \
    --enable_streaming_engine \
    "$@"
else
  python3 "${SCRIPT_DIR}/src/pipeline.py" \
    --input_topic="${TOPIC_NAME}" \
    --bigtable_project="${PROJECT_ID}" \
    --bigtable_instance="${BIGTABLE_INSTANCE}" \
    --bigtable_table="${BIGTABLE_TABLE}" \
    --bigquery_table="${BIGQUERY_TABLE}" \
    --window_seconds=10 \
    --runner=DirectRunner \
    --streaming \
    "$@"
fi
