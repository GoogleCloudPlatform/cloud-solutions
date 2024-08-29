# Copyright 2024 Google LLC
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

FROM gcr.io/dataflow-templates-base/python312-template-launcher-base:20240812-rc01 as dataflow_template_container

ENV JAVA_HOME=/opt/java/openjdk
COPY --from=eclipse-temurin:17-jdk $JAVA_HOME $JAVA_HOME
ENV PATH="${JAVA_HOME}/bin:${PATH}"

ENV FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE=requirements.txt
ENV FLEX_TEMPLATE_PYTHON_PY_FILE=dataflow_gcs_to_alloydb.py

ARG WORKDIR=/template
COPY requirements.txt ${WORKDIR}/
COPY src/dataflow_gcs_to_alloydb.py ${WORKDIR}/
WORKDIR ${WORKDIR}

RUN apt-get update \
    && apt-get --no-install-recommends install -y libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --require-hashes -r $FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE \
    && pip download --no-cache-dir --require-hashes --dest /tmp/dataflow-requirements-cache -r $FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE

ENV PIP_NO_DEPS=True

ENTRYPOINT ["/opt/google/dataflow/python_template_launcher"]
