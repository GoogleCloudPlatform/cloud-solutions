#
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

# buildtest.dockerfile is only used for ci.

FROM python:3.8.18 as base

SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

ARG PROJECT_SUBDIRECTORY
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}

RUN apt-get update \
    && apt-get --assume-yes --no-install-recommends install \
    apt-transport-https \
    curl \
    git \
    gnupg \
    libusb-1.0-0 \
    lsb-release \
    make \
    openssh-client \
    libopencv-dev python3-opencv \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade --no-cache-dir \
    pip==24.2 \
    setuptools==72.1.0 \
    wheel==0.43.0

COPY requirements.txt requirements.txt
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY cameras.proto "${PROJECT_SUBDIRECTORY}"/
RUN protoc -I="${PROJECT_SUBDIRECTORY}" --python_out="${PROJECT_SUBDIRECTORY}" "${PROJECT_SUBDIRECTORY}"/cameras.proto

FROM base as camera-integration-test

COPY tests/requirements-dev.txt tests/requirements-dev.txt
RUN python3 -m pip install --no-cache-dir -r tests/requirements-dev.txt

COPY . "${PROJECT_SUBDIRECTORY}"/
RUN python3 -m pytest tests/
CMD ["/usr/bin/echo", "Unit tests run as part of the container image build"]
