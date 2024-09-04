#!/bin/bash

# Copyright 2024 Google LLC
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

set -e

location="us"
repository="visual-inspection-ml-training"

# read command line arguments
while getopts "l:r:" arg; do
  case $arg in
  l)
    location=$OPTARG
    ;;
  r)
    repository=$OPTARG
    ;;
  *)
    echo "Invalid argument: $arg"
    ;;
  esac
done

#TODO: enable all necessary GCP services
gcloud services enable aiplatform.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com

#Change to main project directory
cd "$(dirname "$0")"/.. || exit 1

# Create the registry
gcloud artifacts repositories describe "$repository" --location="$location" &>/dev/null ||
  (echo "Creating registry..." &&
    gcloud artifacts repositories create "$repository" --location="$location" --repository-format=docker)

# Run the build
echo "Running trainer container build..."
#TODO: add replacement parameters
gcloud builds submit --substitutions=_REPO_LOCATION="$location",_REPO_NAME="$repository"
