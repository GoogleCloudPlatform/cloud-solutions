#
# Copyright 2023 Google LLC
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

FROM gradle:8-jdk21 AS build-api-server
### Copy Source Code
COPY . /sa-tools-src

### Build and test API server (Java)
WORKDIR /sa-tools-src
RUN gradle -p perf-benchmark  \
    :ui:yarn_style-check  \
    :api:spotlessCheck  \
    :api:test  \
    :api:jibBuildTar
