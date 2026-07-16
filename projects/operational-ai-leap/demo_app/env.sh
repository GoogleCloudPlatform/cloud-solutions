#!/usr/bin/env bash
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

# Update env variables here
export REGION="us-central1"
export ZONE="us-central1-a"
export IMAGE_BUCKET="your-image-bucket"
export ALLOYDB_CLUSTER="alloydb-cluster"
export ALLOYDB_INSTANCE="alloydb-instance"
export ALLOYDB_DATABASE="ecom_masked"
export VPC_NETWORK=demo-vpc

# Prompt for AlloyDB password
if [[ -z "$ALLOYDB_PASSWORD" ]]; then
  # If it's empty/unset, prompt the user
  read -r -s -p "Enter password for the postgres database user: " ALLOYDB_PASSWORD
  # Add a newline after the prompt for cleaner output, only if we prompted
  echo ""
fi

# Keep all defaults below
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
export PROJECT_ID
ALLOYDB_IP=$(gcloud alloydb instances describe "$ALLOYDB_INSTANCE" --cluster="$ALLOYDB_CLUSTER" --region="$REGION" --view=BASIC --format=json 2>/dev/null | jq -r .ipAddress)
export ALLOYDB_IP
export PGPORT=5432
export PGDATABASE=${ALLOYDB_DATABASE}
export PGUSER=postgres
export PGHOST=${ALLOYDB_IP}
export PGPASSWORD=${ALLOYDB_PASSWORD}
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
export PROJECT_NUMBER
ORGANIZATION=$(gcloud projects get-ancestors "${PROJECT_ID}" --format=json | jq -r '.[] | select(.type == "organization").id')
export ORGANIZATION
export VPC_SUBNET=$VPC_NETWORK
export VPC_NAME=$VPC_NETWORK
