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

"""Lightweight Gateway FastAPI application for Oracle EBS Workflow A2A."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from src.a2a.catalog import catalog_router
from src.a2a.proxy import _format_a2a_response
from src.a2a.proxy import router as proxy_router
from src.config import get_settings

logger = logging.getLogger(__name__)


class WorkflowA2AGatewayApp(FastAPI):
    """FastAPI gateway subclass customizing OpenAPI schema cleanly."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.openapi_schema: dict[str, Any] | None = None

    def openapi(self) -> dict[str, Any]:
        """Generate and cache customized OpenAPI schema for A2A and Gemini."""
        if self.openapi_schema:
            return self.openapi_schema
        settings = get_settings()
        custom_openapi = get_openapi(
            title="Oracle EBS Workflow A2A Gateway",
            version="1.0.0",
            openapi_version="3.0.0",
            description=(
                "A2A Protocol v0.3.0 Gateway for Oracle EBS Workflow"
                " and Approval Triage"
            ),
            routes=self.routes,
        )
        custom_openapi["info"]["x-a2a-agent-card"] = "/a2a/card"
        custom_openapi["servers"] = [
            {
                "url": settings.a2a_server_url,
                "description": "Workflow A2A Gateway Server",
            }
        ]
        self.openapi_schema = custom_openapi
        return self.openapi_schema


def create_gateway_app() -> WorkflowA2AGatewayApp:
    """Factory creating lightweight A2A gateway app (<100 lines)."""
    gateway_app = WorkflowA2AGatewayApp(
        title="Oracle EBS Workflow A2A Gateway",
        description="A2A Gateway Microservice for Oracle EBS Workflow",
        version="1.0.0",
    )

    @gateway_app.exception_handler(ValidationError)
    @gateway_app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Sanitize errors into valid JSON-RPC 2.0 A2A responses.

        Prevents client crashes on malformed requests.
        """
        req_id = 1
        try:
            if request.method in ("POST", "PUT", "PATCH"):
                body = await request.json()
                if isinstance(body, dict):
                    req_id = body.get("id", 1)
        except ValueError:
            req_id = 1

        if isinstance(exc, HTTPException):
            err_msg = str(exc.detail)
        elif isinstance(exc, ValidationError):
            logger.warning("Validation error on %s: %s", request.url.path, exc)
            err_msg = "Invalid request payload or parameters."
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
                },
                user_query="",
                req_id=req_id,
            ),
        )

    gateway_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    gateway_app.include_router(catalog_router)
    gateway_app.include_router(proxy_router)

    @gateway_app.get("/health", tags=["Health"])
    @gateway_app.post("/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {
            "status": "healthy",
            "service": "oracle-ebs-workflow-a2a-gateway",
        }

    return gateway_app


app = create_gateway_app()
