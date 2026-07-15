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

# Script to enable required Google Cloud APIs for the TARGET project

PROJECT_ID="$1"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 <project_id>"
  exit 1
fi

echo "Enabling APIs for TARGET project: $PROJECT_ID"

APIS=(
  "cloudresourcemanager.googleapis.com"
  "serviceusage.googleapis.com"
  "compute.googleapis.com"
  "dataproc.googleapis.com"
  "storage.googleapis.com"
  "metastore.googleapis.com"
  "bigquery.googleapis.com"
  "dataplex.googleapis.com"
  "biglake.googleapis.com"
)

echo "Enabling APIs: ${APIS[*]}"
gcloud services enable "${APIS[@]}" --project="$PROJECT_ID"

echo "All required TARGET APIs enabled."
