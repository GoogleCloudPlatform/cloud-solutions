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

# Load env variables
source "$(dirname "$0")/../env.sh"

if [ -z "$REGION" ]; then
  echo "REGION is not set. Please set the gcloud run/region."
  exit 1
fi

# Get the latest tags.
git fetch

#
# Build & push the container
#
echo "Building and pushing the container"
TAG_NAME=$(git describe --abbrev=0 --tags --always)
IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/cymbalshops/cymbalshops:$TAG_NAME

docker build --rm -t "$IMAGE" .
docker push "$IMAGE"

#
# Step 3: Deploy to Cloud Run
#
echo "Deploying to Cloud Run"
gcloud beta run deploy cymbalshops \
  --image="$IMAGE" \
  --execution-environment=gen2 \
  --cpu-boost \
  --network="$VPC_NETWORK" \
  --subnet="$VPC_SUBNET" \
  --vpc-egress=private-ranges-only \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --allow-unauthenticated \
  --set-env-vars=PGHOST="$PGHOST",PGPORT="$PGPORT",PGDATABASE="$PGDATABASE",PGUSER="$PGUSER",PGPASSWORD="$PGPASSWORD",PROJECT_ID="$PROJECT_ID",REGION="$REGION"
