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
ENV FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE="${WORKDIR}/requirements.txt"

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 appuser \
    && useradd -u 1000 -g appuser -d ${WORKDIR} -s /bin/bash appuser \
    && pip install --no-cache-dir --require-hashes -r ${FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE} \
    && pip download --no-cache-dir --require-hashes --dest /tmp/dataflow-requirements-cache -r ${FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE} \
    && chown -R appuser:appuser ${WORKDIR} /tmp/dataflow-requirements-cache

ENV PIP_NO_DEPS=True

USER appuser
