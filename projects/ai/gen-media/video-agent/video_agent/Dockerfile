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

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY video_ads_agent/ video_ads_agent/
COPY streamlit_video_ads.py .
COPY ge_video_ads.py .
COPY google_logo.png .
COPY .streamlit/ .streamlit/

# Copy hash-verified requirements manifest
COPY requirements.txt .

# Install dependencies verifiably with checksum hashes and install local project module
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && pip install --no-cache-dir --no-index --no-build-isolation --no-deps .

ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["streamlit", "run", "streamlit_video_ads.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true"]
