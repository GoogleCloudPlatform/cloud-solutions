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

# Script to set up Storage Transfer Service for HDFS to Cloud Storage migration

set -e

# Default values from Terraform
if [ -d "terraform/source-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/source-environment || exit
  TF_SOURCE_PROJECT=$(terraform output -raw project_id 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

if [ -d "terraform/target-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/target-environment || exit
  TF_TARGET_PROJECT=$(terraform output -raw project_id 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

SOURCE_PROJECT="${TF_SOURCE_PROJECT}"
TARGET_PROJECT="${TF_TARGET_PROJECT}"

# Parse flags
while [[ $# -gt 0 ]]; do
  case $1 in
  --source-project)
    SOURCE_PROJECT="$2"
    shift 2
    ;;
  --target-project)
    TARGET_PROJECT="$2"
    shift 2
    ;;
  *)
    echo "Unknown argument: $1"
    exit 1
    ;;
  esac
done

if [ -z "$SOURCE_PROJECT" ] || [ -z "$TARGET_PROJECT" ]; then
  echo "Usage: $0 [--source-project <id>] [--target-project <id>]"
  echo "If flags are omitted, the script will try to read project IDs from terraform state."
  exit 1
fi

echo "Enabling Storage Transfer API in source project: $SOURCE_PROJECT"
gcloud services enable storagetransfer.googleapis.com --project="$SOURCE_PROJECT"

echo "Enabling Storage Transfer API in target project: $TARGET_PROJECT"
gcloud services enable storagetransfer.googleapis.com --project="$TARGET_PROJECT"

echo "Sleeping for 2 minutes to let the API take effect"
sleep 120

gcloud config set project "$TARGET_PROJECT"
gcloud config set billing/quota_project "$TARGET_PROJECT"

echo "Creating an agent pool in the target project, if it doesn't exist"
if gcloud transfer agent-pools describe hdfs-pool &>/dev/null; then
  echo "Agent pool 'hdfs-pool' already exists in project: $TARGET_PROJECT"
else
  echo "Creating agent pool 'hdfs-pool' in target project: $TARGET_PROJECT"
  gcloud transfer agent-pools create hdfs-pool
fi

# Grant permissions to the Managed Spark service account in the source project
# so that it can register agents in the target project pool and write to Cloud Storage.
DATAPROC_SA="dataproc-source-sa@${SOURCE_PROJECT}.iam.gserviceaccount.com"

echo "Granting required roles to Dataproc service account $DATAPROC_SA in target project $TARGET_PROJECT"
# roles/storage.objectAdmin is required for Hadoop Cloud Storage connector metadata operations
for role in "roles/storagetransfer.admin" "roles/storage.objectAdmin"; do
  gcloud projects add-iam-policy-binding "$TARGET_PROJECT" \
    --member="serviceAccount:$DATAPROC_SA" \
    --role="$role" \
    --quiet
done

echo "Granting Storage Transfer Admin role to Managed Spark service account $DATAPROC_SA in source project $SOURCE_PROJECT"
gcloud projects add-iam-policy-binding "$SOURCE_PROJECT" \
  --member="serviceAccount:$DATAPROC_SA" \
  --role="roles/storagetransfer.admin" \
  --quiet

echo "Setup steps completed."
