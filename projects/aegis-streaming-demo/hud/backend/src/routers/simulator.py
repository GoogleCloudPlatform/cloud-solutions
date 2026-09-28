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

"""Project Aegis - HUD Backend Simulator Proxy Router.

Proxies simulator operations (start stream, stop stream, create anomaly, status)
to the standalone Telemetry Simulator Cloud Run microservice.

NOTE: As per strict architectural design, this HUD router NEVER exposes or calls
the /api/fix-anomoly endpoint. Anomaly remediation is strictly executed by AI.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import google.auth.exceptions
import google.auth.transport.requests
import google.oauth2.id_token
import httpx
from fastapi import APIRouter, HTTPException, status
from google.api_core.exceptions import GoogleAPICallError
from pydantic import BaseModel, Field

logger = logging.getLogger("aegis-hud-backend")
router = APIRouter(tags=["Simulator Proxy"])

_AUTH_EXCEPTIONS = (
    google.auth.exceptions.GoogleAuthError,
    GoogleAPICallError,
    ValueError,
    OSError,
)
_PROXY_EXCEPTIONS = (
    httpx.HTTPError,
    ValueError,
    KeyError,
    OSError,
)


def get_simulator_service_url() -> str:
    # In Cloud Run production, SIMULATOR_SERVICE_URL is injected by Terraform.
    # Defaults to http://localhost:8080 strictly for local dev and CI unit
    # tests where SIMULATOR_SERVICE_URL is unset.
    return os.getenv(
        "SIMULATOR_SERVICE_URL",
        "http://localhost:8080",
    ).rstrip("/")


async def get_gcp_id_token(audience: str) -> Optional[str]:
    """Fetch OIDC identity token using google.oauth2.id_token."""
    if "localhost" in audience or "127.0.0.1" in audience:
        return None
    try:
        token = await asyncio.to_thread(
            google.oauth2.id_token.fetch_id_token,
            google.auth.transport.requests.Request(),
            audience,
        )
        if token:
            return token
    except _AUTH_EXCEPTIONS as e:
        logger.debug("ID token fetch skipped: %s", e)
    return None


async def _proxy_request(
    method: str, path: str, json_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    base_url = get_simulator_service_url()
    target_url = f"{base_url}{path}"
    headers = {"Content-Type": "application/json"}

    token = await get_gcp_id_token(base_url)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            if method.upper() == "GET":
                resp = await client.get(target_url, headers=headers)
            else:
                resp = await client.post(
                    target_url, json=json_data, headers=headers
                )

            if resp.status_code in [200, 201]:
                return resp.json()
            if resp.status_code == 400:
                logger.warning("Simulator service returned 400: %s", resp.text)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request parameters for simulator service.",
                )
            if resp.status_code == 404:
                logger.warning("Simulator service returned 404: %s", resp.text)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Requested simulator resource was not found.",
                )

            logger.error(
                "Simulator service returned status %s: %s",
                resp.status_code,
                resp.text,
            )
            raise HTTPException(
                status_code=resp.status_code,
                detail="Upstream simulator service returned an error.",
            )
    except HTTPException:
        raise
    except _PROXY_EXCEPTIONS as exc:
        logger.error(
            "Error contacting Telemetry Simulator at %s: %s", target_url, exc
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to Telemetry Simulator service.",
        ) from exc


class StartStreamRequest(BaseModel):
    rate_msgs_per_sec: Optional[int] = Field(
        default=100,
        ge=1,
        le=5000,
        description="Target message generation rate",
    )


@router.post("/api/start-stream")
@router.post("/api/stream-start")
@router.post("/api/simulator/start")
async def start_stream(
    payload: Optional[StartStreamRequest] = None,
) -> Dict[str, Any]:
    """Starts simulating telemetry data streaming."""
    data = payload.model_dump() if payload else {"rate_msgs_per_sec": 100}
    return await _proxy_request("POST", "/api/start-stream", json_data=data)


@router.post("/api/stop-stream")
async def stop_stream() -> Dict[str, Any]:
    """Stops simulating telemetry data streaming."""
    return await _proxy_request("POST", "/api/stop-stream")


@router.post("/api/create-anomoly")
@router.post("/api/inject-anomaly")
@router.post("/api/simulator/inject-anomaly")
@router.post("/api/simulator/create-anomoly")
async def create_anomoly() -> Dict[str, Any]:
    """Instructs simulator to inject an anomaly into a random asset."""
    return await _proxy_request("POST", "/api/create-anomoly")


@router.get("/api/stream-status")
async def get_stream_status() -> Dict[str, Any]:
    """Retrieves current streaming status and 5-minute rolling metrics."""
    try:
        return await _proxy_request("GET", "/api/stream-status")
    except (HTTPException,) + _PROXY_EXCEPTIONS as e:
        logger.warning("Failed to fetch status from simulator service: %s", e)
        return {
            "status": "stopped",
            "running": False,
            "total_messages_last_5m": 0,
            "rate_msgs_per_sec_5m": 0.0,
            "rate_formatted": "0.0 msgs/sec in the last 5 minutes",
            "active_anomalies": [],
            "assets_count": 15,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
