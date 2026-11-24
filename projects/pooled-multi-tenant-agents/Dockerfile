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

FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    GOOGLE_CLOUD_REGION=us-central1 \
    GOOGLE_CLOUD_LOCATION=us-central1 \
    GOOGLE_GENAI_USE_VERTEXAI=true

COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY config/ ./config/
COPY agents/ ./agents/
COPY mcp_server/ ./mcp_server/
COPY broker_service/ ./broker_service/
COPY runtime_service/ ./runtime_service/
COPY app/ ./app/
COPY plugins/ ./plugins/
COPY runbooks/ ./runbooks/
COPY scripts/ ./scripts/
COPY evals/ ./evals/
COPY docs/assets/ ./docs/assets/
COPY run_breach_simulations.py ./

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
