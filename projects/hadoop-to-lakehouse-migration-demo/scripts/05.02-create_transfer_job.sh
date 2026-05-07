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

# Script to create Storage Transfer Service job from HDFS to Cloud Storage

set -e

# Default values from Terraform
if [ -d "terraform/target-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/target-environment || exit
  TF_TARGET_PROJECT=$(terraform output -raw project_id 2>/dev/null)
  TF_BRONZE_BUCKET=$(terraform output -raw bronze_bucket 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

TARGET_PROJECT="${TF_TARGET_PROJECT}"
BRONZE_BUCKET="${TF_BRONZE_BUCKET}"
SOURCE_PATH="/data/"

# Parse flags
while [[ $# -gt 0 ]]; do
  case $1 in
  --target-project)
    TARGET_PROJECT="$2"
    shift 2
    ;;
  --bronze-bucket)
    BRONZE_BUCKET="$2"
    shift 2
    ;;
  --source-path)
    SOURCE_PATH="$2"
    shift 2
    ;;
  *)
    echo "Unknown argument: $1"
    exit 1
    ;;
  esac
done

if [ -z "$TARGET_PROJECT" ] || [ -z "$BRONZE_BUCKET" ]; then
  echo "Usage: $0 [--target-project <id>] [--bronze-bucket <name>] [--source-path <path>]"
  exit 1
fi

echo "Creating transfer job in project: $TARGET_PROJECT"
gcloud transfer jobs create "hdfs://$SOURCE_PATH" "gs://$BRONZE_BUCKET/" \
  --source-agent-pool="projects/$TARGET_PROJECT/agentPools/hdfs-pool" \
  --project="$TARGET_PROJECT"

echo "Transfer job creation command sent."
echo ""
echo "To list your transfer jobs and find the job name, run:"
echo "gcloud transfer jobs list --project=\"$TARGET_PROJECT\""
echo ""
echo "To check the detailed status of a specific job, run:"
echo "gcloud transfer jobs describe <JOB_NAME> --project=\"$TARGET_PROJECT\""
