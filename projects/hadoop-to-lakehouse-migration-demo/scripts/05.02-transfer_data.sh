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

# Script to transfer data from HDFS to Cloud Storage Bronze bucket

set -e

# Default values from Terraform
if [ -d "terraform/source-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/source-environment || exit
  TF_PROJECT_ID=$(terraform output -raw project_id 2>/dev/null)
  TF_CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null)
  TF_REGION=$(terraform output -raw cluster_region 2>/dev/null)
  TF_ZONE=$(terraform output -raw cluster_zone 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

if [ -d "terraform/target-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/target-environment || exit
  TF_BRONZE_BUCKET=$(terraform output -raw bronze_bucket 2>/dev/null)
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
  --zone)
    ZONE="$2"
    shift
    ;;
  --bronze-bucket)
    BRONZE_BUCKET="$2"
    shift
    ;;
  *)
    echo "Unknown parameter passed: $1"
    exit 1
    ;;
  esac
  shift
done

# Use defaults from TF if not provided as flags
PROJECT_ID="${PROJECT_ID:-$TF_PROJECT_ID}"
CLUSTER_NAME="${CLUSTER_NAME:-$TF_CLUSTER_NAME}"
REGION="${REGION:-$TF_REGION}"
ZONE="${ZONE:-$TF_ZONE}"
BRONZE_BUCKET="${BRONZE_BUCKET:-$TF_BRONZE_BUCKET}"

if [ -z "$PROJECT_ID" ] || [ -z "$CLUSTER_NAME" ] || [ -z "$REGION" ] || [ -z "$ZONE" ] || [ -z "$BRONZE_BUCKET" ]; then
  echo "Usage: $0 [--project-id <project_id>] [--cluster-name <cluster_name>] [--region <region>] [--zone <zone>] [--bronze-bucket <bronze_bucket>]"
  echo "If flags are omitted, script will try to read values from terraform outputs."
  exit 1
fi

echo "Transferring data from HDFS to Cloud Storage..."

gcloud compute ssh "$CLUSTER_NAME-m" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --command="
    hadoop fs -mkdir -p gs://$BRONZE_BUCKET/mta && \
    hadoop fs -cp -f /data/mta/* gs://$BRONZE_BUCKET/mta/ && \
    hadoop fs -mkdir -p gs://$BRONZE_BUCKET/staged && \
    hadoop fs -cp -r -f /data/staged/* gs://$BRONZE_BUCKET/staged/
  "

echo "Data transfer completed."
