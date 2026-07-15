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

# Script to install Storage Transfer Service agents on Managed Spark cluster
set -e

# Default values from Terraform
if [ -d "terraform/source-environment" ]; then
  CUR_DIR=$(pwd)
  cd terraform/source-environment || exit
  TF_PROJECT_ID=$(terraform output -raw project_id 2>/dev/null)
  TF_CLUSTER_NAME=$(terraform output -raw cluster_name 2>/dev/null)
  TF_REGION=$(terraform output -raw cluster_region 2>/dev/null)
  TF_ZONE=$(terraform output -raw cluster_zone 2>/dev/null)
  cd "$CUR_DIR" || exit
fi

# Parse arguments
while [[ "$#" -gt 0 ]]; do
  case $1 in
  --target-project)
    TARGET_PROJECT="$2"
    shift
    ;;
  --source-project)
    SOURCE_PROJECT="$2"
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
  --zone)
    ZONE="$2"
    shift
    ;;
  *)
    echo "Unknown parameter passed: $1"
    exit 1
    ;;
  esac
  shift
done

SOURCE_PROJECT="${SOURCE_PROJECT:-$TF_PROJECT_ID}"
CLUSTER_NAME="${CLUSTER_NAME:-$TF_CLUSTER_NAME}"
REGION="${REGION:-$TF_REGION}"
ZONE="${ZONE:-$TF_ZONE}"

if [ -z "$TARGET_PROJECT" ] || [ -z "$SOURCE_PROJECT" ] || [ -z "$CLUSTER_NAME" ] || [ -z "$REGION" ] || [ -z "$ZONE" ]; then
  echo "Usage: $0 --target-project <target_project_id> [--source-project <source_project_id>] [--cluster-name <cluster_name>] [--region <region>] [--zone <zone>]"
  exit 1
fi

echo "SCP the install script to the cluster master..."
gcloud compute scp \
  "$(dirname "$0")/05.02.01-namenode_install_transfer_agent_script.sh" \
  "$CLUSTER_NAME-m":~/install_transfer_agents.sh \
  --project="$SOURCE_PROJECT" \
  --zone="$ZONE" \
  --tunnel-through-iap

echo "Installing Storage Transfer Agent on cluster master..."
gcloud compute ssh "$CLUSTER_NAME-m" \
  --project="$SOURCE_PROJECT" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --command="chmod +x ~/install_transfer_agents.sh && . ~/install_transfer_agents.sh $CLUSTER_NAME $TARGET_PROJECT"

echo "Agent installation command sent."
