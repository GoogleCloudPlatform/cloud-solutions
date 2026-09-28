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

FROM gcr.io/dataflow-templates-base/python311-template-launcher-base:20260901-rc00

ARG WORKDIR=/template
WORKDIR ${WORKDIR}

COPY requirements.txt .
COPY src/ ./src/

ENV FLEX_TEMPLATE_PYTHON_PY_FILE="${WORKDIR}/src/pipeline.py"
ENV FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE="${WORKDIR}/beam-requirements.txt"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN pip install --no-cache-dir --require-hashes -r ${WORKDIR}/requirements.txt \
    && pip download --no-cache-dir --require-hashes --dest /tmp/beam-requirements-cache -r ${WORKDIR}/requirements.txt \
    && grep -E '^google-cloud-(bigtable|bigquery|pubsub)==' ${WORKDIR}/requirements.txt | sed 's/ .*//' > ${WORKDIR}/beam-requirements.txt

ENV PIP_NO_DEPS=True
# NOTE: Dataflow Flex Template launcher images (python311-template-launcher-base)
# must run as the default base image user (root) because the Dataflow GCE
# Launcher VM bind-mounts /var/log/dataflow/template_launcher from the host as
# root:root (0755) for python_template_launcher to create runner-json.log.
