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

"""Project Aegis - Telemetry Simulator Microservice.

Standalone API managing in-memory asset fleet state, synthetic IIoT
telemetry streaming to Google Cloud Managed Kafka, and anomaly injection.
"""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from models import (
    AssetState,
    CreateAnomalyResponse,
    FixAnomalyRequest,
    FixAnomalyResponse,
    StartStreamRequest,
    StreamActionResponse,
    StreamStatusResponse,
)
from simulator import FleetSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("aegis-telemetry-simulator")

app = FastAPI(
    title="Project Aegis - Telemetry Simulator API",
    description="Headless IIoT Telemetry Fleet Generator.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fleet_simulator = FleetSimulator()


@app.get("/health", tags=["Health"])
@app.get("/", tags=["Health"])
def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "service": "aegis-telemetry-simulator",
        "running": str(fleet_simulator.running),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post(
    "/api/start-stream",
    response_model=StreamActionResponse,
    tags=["Streaming Control"],
    summary="Start simulating telemetry and streaming to Kafka",
)
async def start_stream(
    body: StartStreamRequest = StartStreamRequest(),
) -> StreamActionResponse:
    """Starts simulating telemetry data and publishing messages."""
    res = await fleet_simulator.start_stream(target_rate=body.rate_msgs_per_sec)
    return StreamActionResponse(**res)


@app.post(
    "/api/stop-stream",
    response_model=StreamActionResponse,
    tags=["Streaming Control"],
    summary="Stop simulating telemetry data and Kafka streaming",
)
async def stop_stream() -> StreamActionResponse:
    """Stops the background telemetry simulation loop."""
    res = await fleet_simulator.stop_stream()
    return StreamActionResponse(**res)


@app.post(
    "/api/create-anomoly",
    response_model=CreateAnomalyResponse,
    tags=["Anomaly Management"],
    summary="Inject thermal/CPU anomaly into a randomly selected asset",
)
async def create_anomoly() -> CreateAnomalyResponse:
    """Chooses one asset at random and creates an anomaly in its state."""
    try:
        fleet_simulator.create_anomaly()
        return CreateAnomalyResponse(
            status="anomaly_created",
            message="Thermal and compute anomaly injected into random asset.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@app.post(
    "/api/fix-anomoly",
    response_model=FixAnomalyResponse,
    tags=["Anomaly Management"],
    summary="Normalize an asset back to healthy baseline (Agent-only)",
)
async def fix_anomoly(body: FixAnomalyRequest) -> FixAnomalyResponse:
    """Receives an asset ID and normalizes its state back to healthy."""
    target_id = body.asset_id
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="asset_id must be provided in request body.",
        )

    try:
        normalized_state = fleet_simulator.fix_anomaly(target_id)
        return FixAnomalyResponse(
            status="normalized",
            message=(
                f"Asset {target_id} normalized to healthy operating baseline."
            ),
            asset_id=target_id,
            asset=AssetState(**normalized_state),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@app.get(
    "/api/stream-status",
    response_model=StreamStatusResponse,
    tags=["Telemetry Metrics"],
    summary="Get current stream state and 5-minute rolling metrics",
)
def get_stream_status() -> StreamStatusResponse:
    """Returns the current streaming state and rolling metrics."""
    return fleet_simulator.get_status()


if __name__ == "__main__":
    import uvicorn  # pylint: disable=import-outside-toplevel

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
