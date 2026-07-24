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

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY streamlit_demo/adk_common/ adk_common/
COPY streamlit_demo/ads_agent/ ads_agent/
COPY streamlit_demo/lj_marketing_agent/ lj_marketing_agent/
COPY streamlit_app.py .
COPY demo_overrides.py .
COPY .env .
COPY logo.jpg .
COPY .streamlit/ .streamlit/

RUN pip install --no-cache-dir \
    adk_common/ \
    lj_marketing_agent/ \
    streamlit \
    google-ads==30.0.0 \
    rapidfuzz==3.14.5

ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true", "--theme.base=dark", "--theme.backgroundColor=#000000", "--theme.secondaryBackgroundColor=#1a1a1a", "--theme.textColor=#FFFFFF"]
