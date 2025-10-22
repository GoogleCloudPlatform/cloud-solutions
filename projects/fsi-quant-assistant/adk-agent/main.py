# Copyright 2025 Google LLC
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

"""Main entry point for the FastAPI application."""

import os
import sys

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
import logging

_SOLUTION_USER_AGENT = "cloud-solutions/fsi-quant-assistant-v0.0.1"

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# Get the directory where main.py is located
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Example session service URI (e.g., SQLite)
SESSION_SERVICE_URI = "sqlite:///./sessions.db"
# Example allowed origins for CORS
ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:9000",
    "*",
]
# Set web=True if you intend to serve a web interface, False otherwise
SERVE_WEB_INTERFACE = True

# Call the function to get the FastAPI app instance
# Ensure the agent directory name (\'capital_agent\') matches your agent folder
app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
)


# You can add more FastAPI routes or configurations below if needed
# Example:
@app.get("/hello")
async def read_root():
    return {"Hello": "World"}


@app.get("/healthz")
async def healthz():
    return "ok"


if __name__ == "__main__":
    # Use the PORT environment variable provided by Cloud Run,
    # or defaulting to 8080
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        log_config=None,
    )
