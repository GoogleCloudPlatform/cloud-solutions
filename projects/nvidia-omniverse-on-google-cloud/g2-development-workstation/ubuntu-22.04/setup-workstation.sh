#!/usr/bin/env bash

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -o errexit
set -o nounset
set -o pipefail

echo "Verifying that NVIDIA drivers are installed"
if [[ "${CONTAINERIZED_TEST_ENVIRONMENT:-"false"}" == "true" ]]; then
  echo "Skip NVIDIA drivers installation check because we're in a containerized test environment"
elif ! command -v nvidia-smi; then
  echo "NVIDIA drivers are not installed."
  exit 1
else
  echo "Running nvidia-smi as a quick NVIDIA drivers installation check"
  nvidia-smi
fi

sudo apt-get update

sudo DEBIAN_FRONTEND=noninteractive apt-get --yes install \
  curl \
  git-lfs \
  gpg

echo "Installing Docker"

sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# shellcheck disable=SC1091
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" |
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get --yes install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

if ! getent group docker; then
  sudo groupadd docker
fi
if [[ -n "${USER:-}" ]]; then
  echo "Adding ${USER} to the docker group"
  sudo usermod -aG docker "${USER}"
  newgrp docker
fi

echo "Install NVIDIA Container Toolkit"

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg &&
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update

sudo DEBIAN_FRONTEND=noninteractive apt-get --yes install \
  nvidia-container-toolkit \
  nvidia-container-toolkit-base \
  libnvidia-container-tools \
  libnvidia-container1

sudo nvidia-ctk runtime configure --runtime=docker

echo "Restarting the docker service"
if [[ "${CONTAINERIZED_TEST_ENVIRONMENT:-"false"}" == "true" ]]; then
  echo "Skip restarting the docker service because we're in a containerized test environment"
else
  sudo systemctl restart docker
fi

echo "Install the desktop environment"
sudo DEBIAN_FRONTEND=noninteractive apt-get --yes install ubuntu-desktop dialog
