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

FROM python:3.10.12 as base

SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

ARG PROJECT_SUBDIRECTORY
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}

ENTRYPOINT [ "/bin/bash", "-e", "-x", "-c" ]

RUN apt-get update \
    && apt-get --assume-yes --no-install-recommends install protobuf-compiler \
    libopencv-dev python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Integration Tests
CMD [ " \
python3 -m venv .venv && \
. .venv/bin/activate && \
python -m pip install --require-hashes -r base-tooling-requirements.txt && \
python -m pip install --require-hashes --no-deps --no-cache-dir -r requirements.txt && \
python -m pip install --require-hashes --no-deps --no-cache-dir -r tests/requirements-dev.txt  && \
protoc -I=. --python_out=. ./cameras.proto && \
python -m pytest tests/ \
" ]
