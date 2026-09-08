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

"""Router for Server-Sent Events (SSE) telemetry and Bigtable queries."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from state import state_manager

logger = logging.getLogger("aegis-hud-backend")
router = APIRouter(tags=["Telemetry"])


@router.get("/api/stream")
async def sse_telemetry_stream(request: Request):
    """Server-Sent Events (SSE) streaming real-time telemetry state.

    Reads 15 assets directly from Cloud Bigtable (telemetry_metrics).
    """

    async def event_generator():
        logger.info("Client connected to SSE telemetry stream.")
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("SSE client disconnected.")
                    break

                snapshot = state_manager.get_snapshot()
                source_label = (
                    f"Cloud Bigtable ({state_manager.bigtable_instance_id}:"
                    f"{state_manager.bigtable_table_id})"
                )
                payload = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": source_label,
                    "assets": snapshot,
                }

                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("SSE streaming task cancelled.")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/telemetry/assets")
def get_telemetry_assets():
    """Query current operational asset states directly from Cloud Bigtable."""
    snapshot = state_manager.get_snapshot()
    source_label = (
        f"Cloud Bigtable ({state_manager.bigtable_instance_id}:"
        f"{state_manager.bigtable_table_id})"
    )
    return {
        "source": source_label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_assets": len(snapshot),
        "assets": snapshot,
    }


@router.get("/api/telemetry/bigtable")
def get_bigtable_metadata():
    """Detailed Bigtable diagnostics and schema introspection endpoint."""
    snapshot = state_manager.get_snapshot()
    return {
        "status": "connected" if state_manager.bt_table else "fallback_cache",
        "project_id": state_manager.project_id,
        "instance_id": state_manager.bigtable_instance_id,
        "table_id": state_manager.bigtable_table_id,
        "column_family": state_manager.column_family,
        "row_count": len(snapshot),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rows": snapshot,
    }
