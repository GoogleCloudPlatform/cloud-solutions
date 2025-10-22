#!/bin/bash

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This script creates a Google Cloud Storage bucket with a predefined name.

# --- Configuration ---
# Define the desired bucket name.
# It's good practice to ensure bucket names are globally unique and follow GCS naming conventions.
# Fetch the current GCP project ID to use in the bucket name.
GCP_PROJECT_ID=$(gcloud config get-value project)
if [ -z "$GCP_PROJECT_ID" ]; then
  echo "Error: Could not determine GCP Project ID. Please ensure gcloud is configured and authenticated."
  echo "Run 'gcloud config list' to check your active project or 'gcloud auth login' if not logged in."
  exit 1
fi

BUCKET_NAME="${GCP_PROJECT_ID}-tf-state"

# Define the location for the bucket (e.g., US-CENTRAL1, europe-west1, asia-east1).
# Choose a location that is appropriate for your project.
# You can find available locations here: https://cloud.google.com/storage/docs/locations
LOCATION="us"

# --- Pre-requisites Check ---
# Check if gcloud is installed and authenticated.
if ! command -v gcloud &>/dev/null; then
  echo "gcloud command not found. Please install Google Cloud SDK."
  echo "Refer to: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

# Ensure the user is logged in to gcloud.
# This check is basic; for production, consider more robust authentication checks.
if ! gcloud auth list --filter="status:ACTIVE" --format="value(account)" &>/dev/null; then
  echo "You are not logged in to gcloud. Please run 'gcloud auth login' and try again."
  exit 1
fi

# --- Bucket Creation ---
echo "Attempting to create GCS bucket: gs://${BUCKET_NAME} in project: ${GCP_PROJECT_ID} in location: ${LOCATION}"

# Use 'gcloud storage buckets create' to create the bucket.
# The '--uniform-bucket-level-access' flag is recommended for new buckets to simplify permissions.
# The '--project' flag is optional; if omitted, gcloud uses the currently active project.
if gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --location="${LOCATION}" \
  --uniform-bucket-level-access; then
  echo "Successfully created GCS bucket: gs://${BUCKET_NAME}"
  echo "You can view it in the Google Cloud Console or manage with 'gcloud storage'."
else
  echo "Failed to create GCS bucket: gs://${BUCKET_NAME}"
  echo "Possible reasons include: bucket name already exists, insufficient permissions, or invalid location."
  echo "Please check the error message above for more details."
  exit 1
fi

echo "Script finished."
