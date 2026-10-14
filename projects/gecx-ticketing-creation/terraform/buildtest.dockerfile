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

FROM hashicorp/terraform:1.16.4

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=${PROJECT_SUBDIRECTORY}
ENV TF_DATA_DIR=/tmp/.terraform
WORKDIR ${PROJECT_SUBDIRECTORY}

ENTRYPOINT ["/bin/ash", "-e", "-x", "-c"]
CMD ["terraform init -backend=false -input=false -no-color -lockfile=readonly && terraform validate -no-color"]
