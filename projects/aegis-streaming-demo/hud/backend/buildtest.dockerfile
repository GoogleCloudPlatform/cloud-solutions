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

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

FROM python:3.11-slim

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=${PROJECT_SUBDIRECTORY} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NO_GCE_CHECK="true" \
    PYTHONPATH="${PROJECT_SUBDIRECTORY}/src" \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

WORKDIR ${PROJECT_SUBDIRECTORY}
COPY . .

ENTRYPOINT ["python3", "-m", "unittest"]
CMD ["discover", "-s", "tests", "-p", "test_*.py"]
