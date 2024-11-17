# Copyright 2024 Google LLC
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

FROM python:3

ARG PROJECT_SUBDIRECTORY
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}/src/python
ENTRYPOINT [ "/bin/bash", "-e", "-x", "-c" ]
CMD [ " \
    python3 -m venv .venv && \
    source .venv/bin/activate && \
    python3 -m pip install --require-hashes -r requirements.txt && \
    python3 -m unittest discover -s . -p '*_test.py'               \
  " ]
