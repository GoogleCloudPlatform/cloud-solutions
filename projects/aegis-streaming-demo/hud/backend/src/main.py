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

"""Project Aegis - HUD Operations Control Backend API.

FastAPI Python server serving streaming telemetry data and agent mitigation
endpoints:
- GET /api/stream: Server-Sent Events (SSE) streaming real-time asset telemetry.
- POST /api/simulator/start & POST /api/simulator/stop: CDC simulator controls.
- POST /api/simulator/inject-anomaly: Inject thermal/CPU spikes.
- POST /api/agent/mitigate: Forward anomaly alerts to agent-service.
- GET /health: Health check route.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.api_core.exceptions import GoogleAPICallError
from pipeline_clients import get_pipeline_client
from routers import agent, analytics, pipeline, simulator, telemetry
from state import state_manager

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("aegis-hud-backend")

_BACKGROUND_SYNC_EXCEPTIONS = (
    GoogleAPICallError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    OSError,
)


async def _bigtable_sync_loop() -> None:
    """Background loop polling Cloud Bigtable for live asset telemetry."""
    logger.info("Background Bigtable telemetry sync loop started.")
    while True:
        try:
            await asyncio.to_thread(state_manager.read_from_bigtable)
        except _BACKGROUND_SYNC_EXCEPTIONS as exc:
            logger.debug("Error in background Bigtable sync loop: %s", exc)
        await asyncio.sleep(1.0)


async def _pipeline_sync_loop() -> None:
    """Background loop continuously refreshing active streaming pipeline."""
    project_id = (
        os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""
    ).strip()
    region = os.getenv("GCP_REGION", "us-central1")
    while True:
        try:
            if project_id and region:
                client = get_pipeline_client()
                status = await asyncio.to_thread(
                    client.refresh_status_sync, project_id, region
                )
                logger.debug(
                    "Pipeline background sync (%s): status=%s",
                    client.engine_name,
                    status.get("status"),
                )
        except _BACKGROUND_SYNC_EXCEPTIONS as e:
            logger.debug(
                "Non-critical error in background pipeline sync: %s", e
            )
        await asyncio.sleep(10.0)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage background telemetry and pipeline status synchronization tasks."""
    bt_task = asyncio.create_task(_bigtable_sync_loop())
    pipe_task = asyncio.create_task(_pipeline_sync_loop())
    try:
        yield
    finally:
        bt_task.cancel()
        pipe_task.cancel()
        await asyncio.gather(bt_task, pipe_task, return_exceptions=True)


# Initialize FastAPI App
app = FastAPI(
    title="Project Aegis Operations HUD API",
    description=(
        "Backend API serving real-time telemetry SSE streams, simulator "
        "controls, and AI agent execution proxy."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Next.js frontend (default port 3000)
_cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "*").strip()
_cors_origins = [
    origin.strip() for origin in _cors_origins_raw.split(",") if origin.strip()
] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(telemetry.router)
app.include_router(simulator.router)
app.include_router(pipeline.router)
app.include_router(agent.router)
app.include_router(analytics.router)


@app.get("/health", tags=["Health"])
def health_check():
    """Return HUD backend health status and simulator running state."""
    return {
        "status": "healthy",
        "service": "aegis-hud-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "simulator_running": state_manager.simulator_running,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
