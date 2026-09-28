#!/bin/bash
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

# Terminates any active Spark streaming jobs on the warm Dataproc cluster and
# submits a fresh PySpark Structured Streaming job.

set -o errexit
set -o nounset
set -o pipefail

# Query active jobs on the cluster. Terminate active jobs when Terraform
# triggers this script after an ETL or config change so the updated job claims
# the cluster worker resources.
ACTIVE_JOBS="$(gcloud dataproc jobs list \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --cluster="${CLUSTER_NAME}" \
  --state-filter=active \
  --format="value(reference.jobId)" 2>/dev/null || true)"

if [[ -n "${ACTIVE_JOBS}" ]]; then
  while IFS= read -r old_job; do
    if [[ -n "${old_job}" ]]; then
      echo "Terminating previous Spark streaming job ${old_job} on ${CLUSTER_NAME}..."
      # Ignore kill failure if the job already completed or exited concurrently.
      gcloud dataproc jobs kill "${old_job}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --quiet || true
    fi
  done <<<"${ACTIVE_JOBS}"
  sleep 5
fi

# Note: All required Spark SQL Kafka and Google OAuth2 JARs are verified with
# SHA-256 checksums and pre-installed into `/usr/lib/spark/jars/` on every
# cluster node during initialization via `data-ingestion/src/init_spark_deps.sh`.

# Partition & Cluster Scaling Note:
# `spark.sql.shuffle.partitions` (and `--shuffle-partitions`) should match total
# Dataproc worker vCPUs (`num_workers * vcpus_per_worker`, default 8 for 2x 4-vCPU
# workers) so stateful 10s tumbling windows commit 8 Cloud Storage state
# partitions per micro-batch instead of 200.
SHUFFLE_PARTITIONS="${SPARK_SHUFFLE_PARTITIONS:-8}"

JOB_ID="aegis-etl-$(date -u +%Y%m%d-%H%M%S)"
echo "Submitting PySpark Structured Streaming job (${JOB_ID}, shuffle.partitions=${SHUFFLE_PARTITIONS}) to ${CLUSTER_NAME}..."
gcloud dataproc jobs submit pyspark \
  "gs://${DEPS_BUCKET}/dependencies/aegis_etl.py" \
  --id="${JOB_ID}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --cluster="${CLUSTER_NAME}" \
  --async \
  --properties="spark.driver.extraClassPath=/usr/lib/spark/jars/*,spark.executor.extraClassPath=/usr/lib/spark/jars/*,spark.dataproc.lineage.enabled=true,spark.sql.shuffle.partitions=${SHUFFLE_PARTITIONS},spark.scheduler.mode=FAIR,spark.sql.session.timeZone=UTC" \
  -- \
  --project-id="${PROJECT_ID}" \
  --source-type="kafka" \
  --kafka-bootstrap-servers="${KAFKA_BOOTSTRAP_SERVERS}" \
  --kafka-topic="${KAFKA_TOPIC}" \
  --bigtable-instance="${BIGTABLE_INSTANCE_ID}" \
  --bigtable-table="telemetry_metrics" \
  --bigquery-dataset="${BIGQUERY_DATASET_ID}" \
  --bigquery-table="telemetry_events" \
  --checkpoint-location="gs://${DEPS_BUCKET}/checkpoints/${JOB_ID}" \
  --shuffle-partitions="${SHUFFLE_PARTITIONS}"
