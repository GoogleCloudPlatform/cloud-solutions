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

FROM hashicorp/terraform:1.15.6 AS terraform_bin

FROM python:3.12-slim AS python_deps

WORKDIR /build
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --require-hashes --prefix=/install -r requirements.txt

FROM python:3.12-slim AS test_runner

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=${PROJECT_SUBDIRECTORY} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_DATA_DIR=/tmp/.terraform

COPY --from=terraform_bin /bin/terraform /usr/local/bin/terraform
COPY --from=python_deps /install /usr/local
COPY scripts/run_buildtest.sh /usr/local/bin/run_buildtest.sh
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && chmod +x /usr/local/bin/run_buildtest.sh

WORKDIR ${PROJECT_SUBDIRECTORY}

ENTRYPOINT ["/usr/local/bin/run_buildtest.sh"]
