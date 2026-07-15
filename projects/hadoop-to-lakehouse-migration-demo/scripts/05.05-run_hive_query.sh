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

# Run sample Hive query on legacy Hadoop cluster

# Default values from Terraform
if [ -d "terraform/source-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/source-environment || exit
  TF_PROJECT_ID=$(terraform output -raw project_id 2>/dev/null)
  TF_CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null)
  TF_REGION=$(terraform output -raw cluster_region 2>/dev/null)
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
  --file)
    FILE="$2"
    shift
    ;;
  *)
    echo "Unknown parameter passed: $1"
    exit 1
    ;;
  esac
  shift
done

PROJECT_ID=${PROJECT_ID:-$TF_PROJECT_ID}
CLUSTER_NAME=${CLUSTER_NAME:-$TF_CLUSTER_NAME}
REGION=${REGION:-$TF_REGION}
FILE=${FILE:-"scripts/05.05-sample_hive_query.sql"}

if [ -z "$PROJECT_ID" ] || [ -z "$CLUSTER_NAME" ] || [ -z "$REGION" ]; then
  echo "Usage: $0 [--project-id <project_id>] [--cluster-name <cluster_name>] [--region <region>] [--file <file>]"
  exit 1
fi

echo "Submitting Hive job to $CLUSTER_NAME..."
gcloud dataproc jobs submit hive \
  --cluster="$CLUSTER_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --file="$FILE"
