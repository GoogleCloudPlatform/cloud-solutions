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

FROM python:3.9

ENV JAVA_HOME=/opt/java/openjdk
COPY --from=eclipse-temurin:17-jdk $JAVA_HOME $JAVA_HOME
ENV PATH="${JAVA_HOME}/bin:${PATH}"

ARG PROJECT_SUBDIRECTORY
WORKDIR "$PROJECT_SUBDIRECTORY"

ENTRYPOINT [ "/bin/bash", "-e", "-x", "-c" ]
CMD [ " \
  [[ \"$(id -u)\" != 0 ]] && { echo 'This test needs to run as root'; exit 1; }; \
  python3 -m venv .venv && \
  . .venv/bin/activate && \
  python3 -m pip  install --no-deps --require-hashes -r requirements_dev.txt && \
  cd ./src && \
  python3 dataflow_gcs_to_alloydb_test.py \
  " ]
