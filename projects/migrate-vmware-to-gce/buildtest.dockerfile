# Copyright 2026 Google LLC
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

FROM hashicorp/terraform:1.15.5

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}

# Terraform writes its working directory to TF_DATA_DIR. Point it at a
# world-writable path so that the checks run as a non-root user. The validation
# script initializes each module immediately before validating it, so they can
# share the path.
ENV TF_DATA_DIR=/tmp/terraform.d

COPY validate.sh ./
RUN chmod +x validate.sh

USER nobody

ENTRYPOINT [ "./validate.sh" ]
