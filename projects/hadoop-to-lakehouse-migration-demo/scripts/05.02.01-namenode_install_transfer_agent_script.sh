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

# Script to be run on the namenode/masternode of the cluster to install
# Storage Transfer Service agents

set -e

CLUSTER_NAME=$1
TARGET_PROJECT=$2

if ! dpkg --list docker.io | grep "^ii" 2>/dev/null; then
  echo "docker.io is not installed. Installing docker.io..."
  sudo apt-get update
  sudo apt-get install -y docker.io
  sudo systemctl start docker
  sudo systemctl enable docker
elif ! sudo systemctl is-active --quiet docker; then
  echo "Docker is installed but not running. Starting Docker..."
  sudo systemctl start docker
fi

if ! sudo systemctl is-active --quiet docker; then
  echo "Error: Docker is not running. Please ensure Docker is installed and started." >&2
  exit 1
fi

gcloud transfer agents install --pool=hdfs-pool \
  --hdfs-namenode-uri="rpc://${CLUSTER_NAME}-m:8020" \
  --project="${TARGET_PROJECT}" --quiet \
  --docker-network=host
