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

# Script to run legacy Spark job on source Managed Spark cluster

# Default values from Terraform
if [ -d "terraform/source-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/source-environment || exit
  TF_PROJECT_ID=$(terraform output -raw project_id 2>/dev/null)
  TF_CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null)
  TF_REGION=$(terraform output -raw cluster_region 2>/dev/null)
  TF_BUCKET_NAME=$(terraform output -raw staging_bucket 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

# Parse arguments
while [[ "$#" -gt 0 ]]; do
  case $1 in
  --project-id)
    PROJECT_ID="$2"
    shift
    ;;
  --cluster-name)
    CLUSTER_NAME="$2"
    shift
    ;;
  --region)
    REGION="$2"
    shift
    ;;
  *)
    echo "Unknown parameter passed: $1"
    exit 1
    ;;
  esac
  shift
done

PROJECT_ID="${PROJECT_ID:-$TF_PROJECT_ID}"
CLUSTER_NAME="${CLUSTER_NAME:-$TF_CLUSTER_NAME}"
REGION="${REGION:-$TF_REGION}"
BUCKET_NAME="${BUCKET_NAME:-$TF_BUCKET_NAME}"

if [ -z "$PROJECT_ID" ] || [ -z "$CLUSTER_NAME" ] || [ -z "$REGION" ] || [ -z "$BUCKET_NAME" ]; then
  echo "Usage: $0 [--project-id <project_id>] [--cluster-name <cluster_name>] [--region <region>]"
  exit 1
fi

echo "Uploading legacy_spark_job.py to Cloud Storage..."
gcloud storage cp "scripts/pyspark/05.04-legacy_spark_job.py" "gs://$BUCKET_NAME/scripts/"

echo "Submitting Spark job to cluster: $CLUSTER_NAME..."
gcloud dataproc jobs submit pyspark "gs://$BUCKET_NAME/scripts/05.04-legacy_spark_job.py" \
  --cluster="$CLUSTER_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID"

echo "Spark job completed."
