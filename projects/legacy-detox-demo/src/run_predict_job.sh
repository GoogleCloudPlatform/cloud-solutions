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

# Default values
PROJECT_ID=""
REGION=""
CLUSTER="managed-spark-cluster"
BUCKET_NAME=""
JOB_PATH=""
MODEL_PATH=""

# Parse flags
while [[ "$#" -gt 0 ]]; do
  case $1 in
  --project-id)
    PROJECT_ID="$2"
    shift
    ;;
  --region)
    REGION="$2"
    shift
    ;;
  --cluster)
    CLUSTER="$2"
    shift
    ;;
  --bucket-name)
    BUCKET_NAME="$2"
    shift
    ;;
  --job-path)
    JOB_PATH="$2"
    shift
    ;;
  --model-path)
    MODEL_PATH="$2"
    shift
    ;;
  *)
    echo "Unknown parameter passed: $1"
    exit 1
    ;;
  esac
  shift
done

# Validation
if [[ -z "$PROJECT_ID" || -z "$REGION" || -z "$CLUSTER" || -z "$BUCKET_NAME" ]]; then
  echo "Error: --project-id, --region, --cluster, and --bucket-name are required."
  exit 1
fi

# Set defaults if not provided
JOB_PATH=${JOB_PATH:-"gs://${BUCKET_NAME}/predict_job.py"}
MODEL_PATH=${MODEL_PATH:-"gs://${BUCKET_NAME}/models/product_affinity_model"}

echo "--- Configuration ---"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Cluster: $CLUSTER"
echo "Job Path: $JOB_PATH"
echo "Model Path: $MODEL_PATH"
echo "Bucket (Staging): $BUCKET_NAME"
echo "---------------------"

# 1. Verify job file exists on GCS
echo "Verifying job file on GCS..."
if ! gcloud storage ls "$JOB_PATH" >/dev/null 2>&1; then
  echo "Error: Job script not found at $JOB_PATH"
  exit 1
fi

# 2. Check cluster status
echo "Checking cluster status..."
STATUS=$(gcloud dataproc clusters describe "$CLUSTER" --region "$REGION" --project "$PROJECT_ID" --format="value(status.state)" 2>/dev/null)

if [[ -z "$STATUS" ]]; then
  echo "Error: Cluster $CLUSTER not found in region $REGION."
  exit 1
fi

echo "Current status: $STATUS"

if [[ "$STATUS" == "STOPPED" ]]; then
  echo "Starting cluster $CLUSTER..."
  gcloud dataproc clusters start "$CLUSTER" --region "$REGION" --project "$PROJECT_ID" --quiet

  # Wait for cluster to be RUNNING
  echo "Waiting for cluster to become online..."
  while true; do
    STATUS=$(gcloud dataproc clusters describe "$CLUSTER" --region "$REGION" --project "$PROJECT_ID" --format="value(status.state)")
    if [[ "$STATUS" == "RUNNING" ]]; then
      echo "Cluster is now RUNNING."
      break
    fi
    echo "Still $STATUS... waiting 10s"
    sleep 10
  done
elif [[ "$STATUS" != "RUNNING" ]]; then
  echo "Error: Cluster is in $STATUS state. It must be RUNNING or STOPPED."
  exit 1
fi

# 3. Submit the job
echo "Submitting PySpark job..."
# We pass the arguments to the python script using --
gcloud dataproc jobs submit pyspark "$JOB_PATH" \
  --cluster="$CLUSTER" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  -- \
  --project-id "$PROJECT_ID" \
  --bucket-name "$BUCKET_NAME" \
  --model-path "$MODEL_PATH"

echo "Job submission complete."
