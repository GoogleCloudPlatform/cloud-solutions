# Copyright 2025 Google LLC
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

# pylint: disable=C0114, C0301

import os
from pathlib import Path

import google.auth
from app.app_utils.gcs import create_bucket_if_not_exists
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging

setup_telemetry()
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Artifact bucket for ADK
bucket_name = f"gs://{project_id}-deep-search-logs"
create_bucket_if_not_exists(
    bucket_name=bucket_name, project=project_id, location="us-central1"
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# In-memory session configuration - no persistent storage
session_service_uri = None

# Create the ADK API app (will be mounted under /api)
adk_app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=False,  # Disable ADK web UI since we use custom frontend
    artifact_service_uri=bucket_name,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=True,
)

# Create main app and mount ADK under /api
app = FastAPI(title="deep-search", description="API for interacting with the Agent deep-search")
app.mount("/api", adk_app)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    # Redirect root to /app/
    @app.get("/")
    async def root_redirect():
        return RedirectResponse(url="/app/")


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
