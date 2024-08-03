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
#

## Description: Run unit tests in this directory isolated in a docker container.

FROM gradle:8-jdk21

# Install node, npm and yarn
COPY --from=node:20.16.0-slim /opt /opt/
COPY --from=node:20.16.0-slim /usr/local/bin /usr/local/bin/
COPY --from=node:20.16.0-slim /usr/local/include/node /usr/local/include/node/
COPY --from=node:20.16.0-slim /usr/local/lib/node_modules /usr/local/lib/node_modules/
ENV PATH=${PATH}:/usr/local/bin

ARG PROJECT_SUBDIRECTORY
WORKDIR "${PROJECT_SUBDIRECTORY}/.."

ENTRYPOINT [ "/bin/bash", "-e", "-x", "-c" ]
CMD [ " \
    cd common/ui && yarn install && cd - && \
    gradle -p perf-benchmark :api:test -i \
  " ]
