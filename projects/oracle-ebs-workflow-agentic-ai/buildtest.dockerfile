# Copyright 2026 Google LLC
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

FROM python:3.14-slim AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-dev.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.txt


FROM python:3.14-slim AS test

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=${PROJECT_SUBDIRECTORY}
WORKDIR ${PROJECT_SUBDIRECTORY}

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="."
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/tmp

USER nobody

ENTRYPOINT ["pytest"]
CMD ["tests/", "-o", "cache_dir=/tmp/.pytest_cache"]
