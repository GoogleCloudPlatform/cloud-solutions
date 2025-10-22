#! /bin/bash

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

# Update list of available packages
sudo apt update

# Install git
sudo apt install -y git

# Install unzip
sudo apt install -y unzip

# Install kubectl
sudo apt install -y kubectl

# Install gke-gcloud-auth-plugin
sudo apt install -y google-cloud-sdk-gke-gcloud-auth-plugin

# Install dnsutils, dig etc.
sudo apt install -y dnsutils

# Install poetry
curl -sSL https://install.python-poetry.org | python3 -

# Get the latest stable Terraform version from the HashiCorp releases page
LATEST_TERRAFORM_VERSION=$(curl -s https://api.github.com/repos/hashicorp/terraform/releases/latest | grep "tag_name" | cut -d: -f2 | tr -d '",v ')

# Check if the version was successfully fetched
if [ -z "${LATEST_TERRAFORM_VERSION}" ]; then
  echo "Error: Could not determine the latest Terraform version. Exiting."
  exit 1
fi

# Set the TERRAFORM_VERSION variable to the fetched value
export TERRAFORM_VERSION="${LATEST_TERRAFORM_VERSION}"
echo "Installing Terraform version: ${TERRAFORM_VERSION}"

# Download the Terraform binary for Linux
curl -Os "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip"

# Unzip the binary
unzip "terraform_${TERRAFORM_VERSION}_linux_amd64.zip"

# Move the binary to /usr/local/bin (requires sudo)
sudo mv terraform /usr/local/bin/

# Clean up the zip file
rm "terraform_${TERRAFORM_VERSION}_linux_amd64.zip"

# Verify the installation
terraform --version
