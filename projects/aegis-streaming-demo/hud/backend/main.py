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
import sys
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import agent, analytics, pipeline, simulator, telemetry
from state import state_manager

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("aegis-hud-backend")

# Initialize FastAPI App
app = FastAPI(
    title="Project Aegis Operations HUD API",
    description=(
        "Backend API serving real-time telemetry SSE streams, simulator "
        "controls, and AI agent execution proxy."
    ),
    version="1.0.0",
)

# Enable CORS for Next.js frontend (default port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(telemetry.router)
app.include_router(simulator.router)
app.include_router(pipeline.router)
app.include_router(agent.router)
app.include_router(analytics.router)


@app.on_event("startup")
async def start_background_telemetry_sync():
    async def sync_loop():
        logger.info("Background Bigtable telemetry sync loop started.")
        while True:
            try:
                await asyncio.to_thread(state_manager.read_from_bigtable)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.debug("Error in background Bigtable sync loop: %s", exc)
            await asyncio.sleep(1.0)

    asyncio.create_task(sync_loop())


@app.on_event("startup")
async def initialize_pipeline_discovery():
    """Continuously refresh Dataproc Spark status in background."""

    async def pipeline_sync_loop():
        import os  # pylint: disable=import-outside-toplevel

        # pylint: disable=import-outside-toplevel
        from dataproc_client import refresh_dataproc_status_sync

        project_id = os.getenv(
            "GCP_PROJECT",
            os.getenv("GOOGLE_CLOUD_PROJECT", "aegis-streaming-1001"),
        )
        region = os.getenv("GCP_REGION", "us-central1")
        while True:
            try:
                if project_id and region:
                    status = await asyncio.to_thread(
                        refresh_dataproc_status_sync, project_id, region
                    )
                    logger.debug(
                        "Dataproc background sync: status=%s",
                        status.get("status"),
                    )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.debug(
                    "Non-critical error in background Dataproc sync: %s", e
                )
            await asyncio.sleep(10.0)

    asyncio.create_task(pipeline_sync_loop())


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "aegis-hud-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "simulator_running": state_manager.simulator_running,
    }


if __name__ == "__main__":
    import uvicorn  # pylint: disable=import-outside-toplevel

    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
