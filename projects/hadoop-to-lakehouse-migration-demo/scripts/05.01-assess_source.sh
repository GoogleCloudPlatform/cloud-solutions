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

# Script to assess source Hadoop system using dwh-migration-tools

set -e

# Default values from Terraform
if [ -d "terraform/source-environment" ]; then
  # Save current dir
  CUR_DIR=$(pwd)
  cd terraform/source-environment || exit
  TF_SOURCE_PROJECT_ID=$(terraform output -raw project_id 2>/dev/null)
  TF_SOURCE_CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null)
  TF_REGION=$(terraform output -raw cluster_region 2>/dev/null)
  TF_BUCKET_NAME=$(terraform output -raw staging_bucket 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

# Parse arguments
while [[ "$#" -gt 0 ]]; do
  case $1 in
  --project-id)
    SOURCE_PROJECT_ID="$2"
    shift
    ;;
  --cluster-name)
    SOURCE_CLUSTER_NAME="$2"
    shift
    ;;
  --region)
    REGION="$2"
    shift
    ;;
  --output-dir)
    OUTPUT_DIR="$2"
    shift
    ;;
  --bucket-name)
    BUCKET_NAME="$2"
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
SOURCE_PROJECT_ID=${SOURCE_PROJECT_ID:-$TF_SOURCE_PROJECT_ID}
SOURCE_CLUSTER_NAME=${SOURCE_CLUSTER_NAME:-$TF_SOURCE_CLUSTER_NAME}
REGION=${REGION:-$TF_REGION}
BUCKET_NAME=${BUCKET_NAME:-$TF_BUCKET_NAME}
OUTPUT_DIR=${OUTPUT_DIR:-"assessment_output"}

if [ -z "$SOURCE_PROJECT_ID" ] || [ -z "$SOURCE_CLUSTER_NAME" ] || [ -z "$REGION" ] || [ -z "$BUCKET_NAME" ]; then
  echo "Usage: $0 [--project-id <project_id>] [--cluster-name <cluster_name>] [--region <region>] [--output-dir <path>] [--bucket-name <bucket_name>]"
  echo "If flags are omitted, script will try to read values from terraform/source-environment outputs."
  exit 1
fi

echo "Assessing source cluster: $SOURCE_CLUSTER_NAME"

mkdir -p "$OUTPUT_DIR"

# 1. Use dwh-migration-tools for comprehensive assessment
TOOL_VERSION="1.9.1"
TOOL_ZIP="dwh-migration-tools-v${TOOL_VERSION}.zip"
TOOL_URL="https://github.com/google/dwh-migration-tools/releases/download/v${TOOL_VERSION}/${TOOL_ZIP}"
TMP_DIR="tmp"
mkdir -p "$TMP_DIR"

if [ ! -f "$TMP_DIR/$TOOL_ZIP" ]; then
  echo "Downloading dwh-migration-tools v$TOOL_VERSION..."
  curl -L "$TOOL_URL" -o "$TMP_DIR/$TOOL_ZIP"
fi

# Get the zone of the master node
ZONE=$(gcloud dataproc clusters describe "$SOURCE_CLUSTER_NAME" --region="$REGION" --project="$SOURCE_PROJECT_ID" --format='get(config.gceClusterConfig.zoneUri)' | awk -F/ '{print $NF}')
MASTER_NODE="${SOURCE_CLUSTER_NAME}-m"

echo "Uploading dumper zip to master node ($MASTER_NODE) in zone $ZONE..."
gcloud compute scp "$TMP_DIR/$TOOL_ZIP" "${MASTER_NODE}:~/" \
  --project="$SOURCE_PROJECT_ID" --zone="$ZONE" --quiet

# List of hive databases to extract. You can change this to multiple, comma-seperated.
DATABASES="default"

echo "Unzipping and running dwh-migration-dumper on master node..."
# Unzip the tool and run the starter script from its original structure
DUMPER_PATH="dwh-migration-tools-v${TOOL_VERSION}/dumper/bin/dwh-migration-dumper"

gcloud compute ssh "$MASTER_NODE" \
  --project="$SOURCE_PROJECT_ID" \
  --zone="$ZONE" \
  --quiet \
  --command="unzip -q -o ~/$TOOL_ZIP -d ~/ && chmod +x ~/$DUMPER_PATH && ~/$DUMPER_PATH --connector hiveql \
  --database ${DATABASES} \
  --assessment \
  --output gs://$BUCKET_NAME/assessment_tool_output"

echo "Assessment completed. Results saved in gs://$BUCKET_NAME/assessment_tool_output/"
