#!/bin/bash
# Copyright 2025 Google LLC
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

set -o errexit
set -o nounset
set -o pipefail

PROJECT_ID=$1
BUCKET_NAME=$2
JOB_NAME=$3

# Function to print usage
usage() {
  echo "Usage: $0 <PROJECT_ID> <BUCKET_NAME> <JOB_NAME>"
  echo "  <PROJECT_ID>:  The Google Cloud Project ID"
  echo "  <BUCKET_NAME>: The name of the GCS bucket (without gs://)"
  echo "  <JOB_NAME>:    The ID of the Storage Transfer Job"
  exit 1
}

# Validate arguments
if [ -z "$PROJECT_ID" ] || [ -z "$BUCKET_NAME" ] || [ -z "$JOB_NAME" ]; then
  echo "Error: Missing arguments."
  usage
fi

echo "--------------------------------------------------------"
echo "Target Project: $PROJECT_ID"
echo "--------------------------------------------------------"

# 1. Delete the Storage Transfer Job
# We use --quiet to suppress the "Are you sure?" interactive prompt
echo "[1/2] Deleting Transfer Job: $JOB_NAME..."

gcloud transfer jobs delete "$JOB_NAME" \
  --project="$PROJECT_ID" \
  --quiet

echo ""

# 2. Delete the GCS Bucket
# --recursive allows deleting a bucket that contains objects
# gs:// prefix is added automatically if you forget it, but good practice to include it here
echo "[2/2] Deleting GCS Bucket: gs://$BUCKET_NAME..."

gcloud storage rm "gs://$BUCKET_NAME" \
  --project="$PROJECT_ID" \
  --recursive \
  --quiet

echo "--------------------------------------------------------"
echo "Operation Complete"
