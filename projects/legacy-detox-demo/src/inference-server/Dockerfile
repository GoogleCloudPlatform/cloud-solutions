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

FROM python:3.10-slim-bookworm

# Standard environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# NOTE: Java (OpenJDK) is no longer required!
# By moving to a pure Python/Numpy serving model, we have eliminated the JVM dependency,
# shrinking the Docker image by hundreds of megabytes and simplifying the stack.

# Set up work directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir --require-hashes -r /app/requirements.txt

# Copy application files
COPY main.py /app/main.py

# Expose port 8080 for Gemini Enterprise Agent Platform routing
EXPOSE 8080

# Run Uvicorn server bound to port 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
