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

# pylint: disable=line-too-long

"""Cymbal SaaS Multi-Tenant Agent Gateway (PEP) & Interactive Architecture Showcase entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from agents import sandbox_execution
from agents.context_exchange import get_context_token_exchange
from agents.context_signing import ContextSigningUnavailableError
from agents.context_token import ContextKeyUnavailableError
from agents.platform_config import get_platform_config
from agents.skill_loader import CustomSkillUnavailableError
from app.api.v1 import (
    agents_and_sandboxes,
    auth_and_discovery,
    live_verification,
    sandbox_simulations,
    ui_assets,
)
from app.api.v1.agents_and_sandboxes import (
    persona_envelope as _persona_envelope,
)
from app.api.v1.auth_and_discovery import (
    INTERNAL_CONTEXT_JWKS_PATH,
    INTERNAL_PATH_PREFIX,
    _internal_jwks_caller_verifier,
    context_jwks,
    internal_context_jwks,
    internal_jwks_enabled,
)
from app.api.v1.live_verification import (
    verify_live_3p_connectors,
    verify_live_gcp_services,
)
from app.auth import sandbox_mode_active
from app.gateway_tokens import log_user_ref
from app.runtime_state import (
    _CACHED_RLS_POSTURE,
    _TOOL_OUTPUT_TOKEN_ALLOWANCE,
    CONTEXT_KEY_WARMER,
    CONTEXT_TOKEN_ISSUER,
    DB_POOL,
    EDGE_VERIFIER,
    MEMORY_BANK,
    MODEL_ROUTING_PDP,
    OTEL_SINK,
    REGISTRY_PDP,
    REMOTE_RUNTIME,
    RUNTIME_STATUS,
    SANDBOX_MANAGER,
    TOKEN_BULKHEAD,
    TURN_SERVICES,
    Caller,
    OptionalCaller,
    SandboxOnly,
    logger,
)
from app.runtime_state import metering as _metering
from app.runtime_state import (
    public_error_code,
    require_caller,
    routed_agent_binding_enabled,
    sandbox_only,
)
from app.schemas.gateway import (
    AskProEscalationRequest,
    InvokeAgentRequest,
    ModelRoutingDecideRequest,
    SandboxSessionActionRequest,
    SandboxTokenRequest,
    ScenarioTurn,
    TokenExchangeRequest,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute, APIRouter


@asynccontextmanager
async def _gateway_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Verifies PostgreSQL RLS posture once at lifespan startup and caches it for `/healthz`."""
    global _CACHED_RLS_POSTURE
    posture = await DB_POOL.verify_live_rls_posture()
    _CACHED_RLS_POSTURE = (id(DB_POOL), posture)
    CONTEXT_KEY_WARMER.kick()
    yield


_OPENAPI_DOC_PATHS = frozenset(
    {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
)

app = FastAPI(
    title="Cymbal SaaS — Gemini Multi-Tenant Pooled Agent Gateway (Pattern A)",
    version="0.2.4",
    description=(
        "High-Density Pooled Architecture demonstrating the 5-Hop Cryptographic Context Chain, "
        "ADK 2.0 tool pruning, Model Armor + DLP guardrails, and AlloyDB Fail-Closed RLS."
    ),
    lifespan=_gateway_lifespan,
)

get_context_token_exchange().user_ref = log_user_ref


@app.middleware("http")
async def _no_internal_routes_on_public_ingress(
    request: Request, call_next: Any
) -> Response:
    """Blocks `/internal/*` on public ingress except explicitly configured internal JWKS."""
    path = request.url.path
    if path == INTERNAL_CONTEXT_JWKS_PATH and internal_jwks_enabled():
        return await call_next(request)
    if path.startswith(INTERNAL_PATH_PREFIX) or path == "/internal":
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return await call_next(request)


@app.middleware("http")
async def _warm_context_key(request: Request, call_next: Any) -> Response:
    """Retries non-blocking context-key prewarm while a request has active CPU."""
    CONTEXT_KEY_WARMER.kick()
    return await call_next(request)


@app.middleware("http")
async def _security_headers_and_openapi_gate(
    request: Request, call_next: Any
) -> Response:
    """Adds baseline defensive HTTP headers and hides OpenAPI docs outside synthetic sandboxes."""
    if request.url.path in _OPENAPI_DOC_PATHS and not sandbox_mode_active(
        get_platform_config()
    ):
        return JSONResponse(
            status_code=404,
            content={"detail": "Not Found"},
            headers={
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store",
            },
        )
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith(("/api/", "/mcp/")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(ContextSigningUnavailableError)
@app.exception_handler(ContextKeyUnavailableError)
async def _context_key_unavailable(
    _request: Request, exc: Exception
) -> JSONResponse:
    """Maps KMS signing or public-key outages to HTTP 503 + Retry-After (never 401/403)."""
    code = getattr(exc, "code", ContextSigningUnavailableError.code)
    return JSONResponse(
        status_code=503,
        content={"detail": {"error": code}},
        headers={"Retry-After": "10"},
    )


@app.exception_handler(sandbox_execution.SandboxUnavailableError)
async def _sandbox_unavailable(
    _request: Request, exc: sandbox_execution.SandboxUnavailableError
) -> JSONResponse:
    """Maps Agent Sandbox in Gemini warm-pool/control-plane outages to HTTP 503 + Retry-After."""
    return JSONResponse(
        status_code=503,
        content={"detail": {"error": exc.code}},
        headers={"Retry-After": "15", "Cache-Control": "no-store"},
    )


@app.exception_handler(CustomSkillUnavailableError)
async def _custom_skill_unavailable(
    _request: Request, exc: CustomSkillUnavailableError
) -> JSONResponse:
    """Maps GCS / Cloud KMS / Model Armor custom-skill outages to HTTP 503 + Retry-After."""
    return JSONResponse(
        status_code=503,
        content={"detail": {"error": exc.code}},
        headers={"Retry-After": "10", "Cache-Control": "no-store"},
    )


def _mount_flat_api_routes(
    target_app: FastAPI, source_router: APIRouter
) -> None:
    """Registers `APIRouter` endpoints directly onto `target_app` so `app.routes` holds flat
    `APIRoute`s.
    """
    for route in source_router.routes:
        if isinstance(route, APIRoute):
            target_app.add_api_route(
                route.path,
                route.endpoint,
                methods=sorted(route.methods),
                dependencies=list(route.dependencies),
                response_class=route.response_class,
            )


if internal_jwks_enabled():
    app.add_api_route(
        INTERNAL_CONTEXT_JWKS_PATH, internal_context_jwks, methods=["GET"]
    )

for _router_module in (
    auth_and_discovery,
    agents_and_sandboxes,
    sandbox_simulations,
    live_verification,
    ui_assets,
):
    _mount_flat_api_routes(app, _router_module.router)

__all__ = [
    "CONTEXT_KEY_WARMER",
    "CONTEXT_TOKEN_ISSUER",
    "DB_POOL",
    "EDGE_VERIFIER",
    "INTERNAL_CONTEXT_JWKS_PATH",
    "INTERNAL_PATH_PREFIX",
    "MEMORY_BANK",
    "MODEL_ROUTING_PDP",
    "OTEL_SINK",
    "REGISTRY_PDP",
    "REMOTE_RUNTIME",
    "RUNTIME_STATUS",
    "SANDBOX_MANAGER",
    "TOKEN_BULKHEAD",
    "TURN_SERVICES",
    "_CACHED_RLS_POSTURE",
    "_TOOL_OUTPUT_TOKEN_ALLOWANCE",
    "AskProEscalationRequest",
    "Caller",
    "InvokeAgentRequest",
    "ModelRoutingDecideRequest",
    "OptionalCaller",
    "SandboxOnly",
    "SandboxSessionActionRequest",
    "SandboxTokenRequest",
    "ScenarioTurn",
    "TokenExchangeRequest",
    "_internal_jwks_caller_verifier",
    "_metering",
    "_persona_envelope",
    "app",
    "context_jwks",
    "get_platform_config",
    "internal_context_jwks",
    "internal_jwks_enabled",
    "logger",
    "public_error_code",
    "require_caller",
    "routed_agent_binding_enabled",
    "sandbox_mode_active",
    "sandbox_only",
    "verify_live_3p_connectors",
    "verify_live_gcp_services",
]
