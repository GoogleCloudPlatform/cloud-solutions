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

"""Agent-to-Agent (A2A) Discovery and Gateway Server."""

import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from src.a2a.agent_card import AgentCard
from src.a2a.catalog import catalog_router
from src.a2a.proxy import _format_a2a_response, proxy_router

logger = logging.getLogger(__name__)

# Re-export AgentCard for backward compatibility
__all__ = ["AgentCard", "app"]

app = FastAPI(
    title="Oracle EBS A2A Gateway API",
    description=(
        "Unified Gateway API for Oracle EBS Inventory, Financials, and"
        " Supplier Negotiation workers."
    ),
    version="1.0.0",
)


@app.exception_handler(Exception)
async def global_db_exception_handler(request: Request, exc: Exception):
    """Sanitize errors into valid JSON-RPC 2.0 A2A responses to prevent
    crashes."""
    req_id = 1
    try:
        if "_json" in request.scope:
            body = request.scope["_json"]
        elif request.method in ("POST", "PUT", "PATCH"):
            body = await request.json()
        else:
            body = {}
        if isinstance(body, dict):
            req_id = body.get("id", 1)
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        RuntimeError,
    ):
        req_id = 1

    if isinstance(exc, HTTPException):
        err_msg = str(exc.detail)
    elif isinstance(exc, ValidationError):
        err_msg = f"Invalid request parameters: {exc}"
    else:
        logger.error("Unhandled exception on %s: %s", request.url.path, exc)
        err_msg = "The agent encountered an internal operation error."

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=_format_a2a_response(
            {
                "status": "ERROR",
                "detail": err_msg,
                "text": f"Agent Request Error: {err_msg}",
                "content": f"Agent Request Error: {err_msg}",
                "message": f"Agent Request Error: {err_msg}",
            },
            user_query="",
            req_id=req_id,
        ),
    )


# Enable CORS for Google Cloud Console and Vertex AI Extensions UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi() -> Dict[str, Any]:
    """Generate OpenAPI 3.0.0 compliant schema for Vertex AI Extensions."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["openapi"] = "3.0.0"
    server_url = os.environ.get(
        "A2A_SERVER_URL",
        "http://127.0.0.1:8080",
    )
    openapi_schema["servers"] = [{"url": server_url}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


setattr(app, "openapi", custom_openapi)

# Mount decoupled routers
app.include_router(catalog_router)
app.include_router(proxy_router)


@app.api_route(
    "/health",
    methods=["GET", "POST", "OPTIONS"],
    status_code=status.HTTP_200_OK,
)
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "a2a_discovery_server"}
