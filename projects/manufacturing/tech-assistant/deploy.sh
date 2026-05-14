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

# Configuration
REGION="us-central1" # Or your desired region
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
SERVICE_NAME="tech-assistant" # Set your desired service name

# Ensure we have a project
if [ -z "$PROJECT_ID" ]; then
  echo "No Google Cloud project found. Please set your project first:"
  echo "  gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

# Deploy
echo "Deploying Tech Assistant to $PROJECT_ID in $REGION..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT_ID"
