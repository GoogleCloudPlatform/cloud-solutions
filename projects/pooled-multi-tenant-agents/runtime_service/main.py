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

# pylint: disable=import-outside-toplevel,line-too-long
# pylint: disable=missing-class-docstring

"""Agent runtime service entrypoint (ADR-0014 B5, plan S1). Same image, one Cloud Run service per
agent (`--identity-type=agent-identity --functional-type=agent`):

    uvicorn runtime_service.main:create_app --factory --host 0.0.0.0 --port 8080

Endpoints: `POST /internal/v1/turn` and `GET /healthz`. Nothing else.

Per turn it checks, in order, and refuses on the first failure:
1. **caller** = the gateway: the Cloud Run-verified ID token (`X-Serverless-Authorization`) names
   an allowed principal (`RUNTIME_ALLOWED_CALLERS`, the gateway SA) for this service's audience;
2. **context token**: verified with public keys only (`aud` runtime), never signed here;
3. **agent**: the token's signed `agent_id` == this service's `RUNTIME_AGENT_ID` (and the turn's);
then runs the shared Hop 3-5 turn (`agents.turn_engine.run_agent_turn`), with the gateway's
pre-minted broker token as the only way to get tenant credentials.

This process imports no signing code (tested): no KMS signer, no gateway token service, no
context-token exchange. It cannot mint context tokens or broker tokens.

Config (environment):
- `RUNTIME_AGENT_ID` (required): the one agent this service runs.
- `RUNTIME_ALLOWED_CALLERS` (required): comma-separated principals allowed to call (the gateway SA).
- `RUNTIME_EXPECTED_AUDIENCE` (required on Cloud Run): this service's URL (the gateway's ID-token
  audience); also used to verify the caller signature if Cloud Run did not.
- `CONTEXT_JWKS_URL` (optional): fetch context public keys from the gateway's internal JWKS route
  instead of KMS `getPublicKey` (the default); `CONTEXT_JWKS_AUDIENCE` is the ID-token audience.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Mapping
from typing import Any, Literal

from agents import sandbox_execution
from agents import workload_identity as wi
from agents.context import MemoryBankPartitioner
from agents.context_token import (
    AGENT_ID_CLAIM,
    AUDIENCE_RUNTIME,
    ContextKeyUnavailableError,
    ContextTokenError,
    get_context_verifier,
    install_public_key_source,
)
from agents.interceptors import OTelAuditSink
from agents.model_routing import SharedModelRoutingPDP
from agents.platform_config import get_platform_config
from agents.registry import AGENT_CATALOG, AgentRegistryPDP
from agents.runtime_protocol import (
    SANDBOX_PAUSE_PATH,
    SANDBOX_RELEASE_PATH,
    TURN_PATH,
    SandboxLifecycleRequest,
    envelope_from_claims,
    verified_claims_from_cloud_run_header,
)
from agents.tenant_credentials import disable_local_exchange, turn_broker_token
from agents.turn_engine import TurnServices, run_agent_turn
from fastapi import FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from mcp_server.db import build_rls_db_pool_from_env
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("cymbal.audit.runtime")


class TurnFields(BaseModel):
    model_config = {"extra": "forbid"}

    agent_id: str = Field(max_length=64)
    prompt: str = Field(max_length=16000)
    tool_name: str = Field(max_length=64)
    requested_thinking_tokens: int = Field(ge=0)
    raw_sql_override: str | None = None
    live_cloud: bool = False
    sandbox_code: str | None = Field(default=None, max_length=8192)
    sandbox_language: Literal["python", "javascript", "bash"] = "python"


class Admission(BaseModel):
    model_config = {"extra": "forbid"}

    hops: list[dict[str, Any]] = Field(default_factory=list, max_length=8)
    finops: dict[str, Any] = Field(default_factory=dict)
    estimated_tokens: int = Field(ge=0)
    prompt_cache_hit: bool = False
    identity_source: str = Field(default="HOP0_VERIFIED", max_length=64)
    trace_id: str = Field(default="", max_length=128)
    correlation_id: str = Field(default="", max_length=128)


class TurnRequest(BaseModel):
    """Nothing here names a tenant or user: those come only from the verified context token."""

    model_config = {"extra": "forbid"}

    context_token: str | None = Field(default=None, max_length=16384)
    broker_token: str | None = Field(default=None, max_length=16384)
    turn: TurnFields
    admission: Admission


def _refuse(status: int, code: str) -> JSONResponse:
    audit_logger.info("runtime_turn_refused %s", code)
    return JSONResponse(status_code=status, content={"detail": {"error": code}})


def _sandbox_mode_active() -> bool:
    """Same rule as the gateway (synthetic sandbox config running in its own project)."""
    from app.auth import sandbox_mode_active

    return sandbox_mode_active(get_platform_config())


def _default_turn_services() -> TurnServices:
    registry_pdp = AgentRegistryPDP()
    return TurnServices(
        registry_pdp=registry_pdp,
        otel_sink=OTelAuditSink(),
        memory_bank=MemoryBankPartitioner(),
        model_routing_pdp=SharedModelRoutingPDP(),
        db_pool=build_rls_db_pool_from_env(),
        sandbox_mode_active=_sandbox_mode_active,
        sandbox_manager=sandbox_execution.GeminiAgentSandboxManager(
            backend=sandbox_execution.LiveGeminiAgentSandboxClient(),
            registry_pdp=registry_pdp,
        ),
    )


def _install_context_key_source_from_env() -> None:
    url = (os.getenv("CONTEXT_JWKS_URL") or "").strip()
    if not url:
        return  # default: the configured KMS key's public key (viewPublicKey)
    from agents.context_jwks_source import (
        JwksPublicKeySource,
        authenticated_jwks_fetcher,
    )
    from agents.tenant_credentials import _fetch_cloud_run_id_token
    from mcp_server.external_verifier import JwksCache

    audience = (os.getenv("CONTEXT_JWKS_AUDIENCE") or "").strip()
    if not audience.startswith("https://"):
        raise RuntimeError(
            "E_RUNTIME_CONFIG: CONTEXT_JWKS_AUDIENCE must be the gateway URL"
        )
    fetch = authenticated_jwks_fetcher(
        _fetch_cloud_run_id_token, audience=audience
    )
    install_public_key_source(JwksPublicKeySource(JwksCache(url, fetch=fetch)))


class RuntimeService:
    def __init__(
        self,
        *,
        agent_id: str,
        allowed_callers: frozenset[str],
        expected_audience: str | None,
        caller_signature_verifier: (
            Callable[[str], Mapping[str, Any]] | None
        ) = None,
        agent_org_id: str | None = None,
        services: TurnServices | None = None,
        verifier: Callable[[], Any] = get_context_verifier,
    ) -> None:
        if agent_id not in AGENT_CATALOG:
            raise ValueError(
                "E_RUNTIME_CONFIG: RUNTIME_AGENT_ID is not a catalog agent"
            )
        normalized = {wi.normalize_principal(c) for c in allowed_callers}
        if not allowed_callers or None in normalized:
            raise ValueError(
                "E_RUNTIME_CONFIG: RUNTIME_ALLOWED_CALLERS must list SA emails or agent principals"
            )
        if any(
            p is not None
            and p.kind == "agent"
            and wi.principal_org(p.value) != agent_org_id
            for p in normalized
        ):  # same rule as the broker: an agent principal needs agent_identity.org_id of its org
            raise ValueError(
                "E_RUNTIME_CONFIG: agent-identity callers need agent_identity.org_id of their org"
            )
        self.agent_id = agent_id
        self._allowed = frozenset(p.value for p in normalized if p is not None)
        self._aud = expected_audience
        self._verify_caller_signature = caller_signature_verifier
        self._org = agent_org_id
        self._services = services or _default_turn_services()
        self._verifier = verifier

    def _caller(self, header: str | None) -> wi.CallerPrincipal:
        claims = verified_claims_from_cloud_run_header(
            header, verify_signature=self._verify_caller_signature
        )
        principal = wi.principal_from_verified_claims(
            claims, audience=self._aud, agent_org_id=self._org
        )
        if principal.value not in self._allowed:
            raise wi.CallerIdentityError("E_RUNTIME_CALLER_NOT_ALLOWED")
        return principal

    async def _verify_caller_and_envelope(
        self,
        *,
        caller_header: str | None,
        context_token: str | None,
        requested_agent_id: str,
        trace_id: str,
        correlation_id: str,
    ) -> tuple[Any, JSONResponse | None]:
        """Verifies gateway Cloud Run IAM identity, `ctx+jwt` signature, agent binding, and
        tenant.
        """
        try:
            self._caller(caller_header)
        except wi.CallerIdentityError as exc:
            return None, _refuse(
                401,
                (
                    exc.code
                    if exc.code.startswith("E_RUNTIME")
                    else "E_RUNTIME_CALLER"
                ),
            )
        if not context_token:
            return None, _refuse(401, "E_RUNTIME_NO_CONTEXT_TOKEN")
        try:
            verifier = self._verifier()
            claims = await asyncio.to_thread(
                verifier.verify, context_token, audience=AUDIENCE_RUNTIME
            )
        except ContextTokenError as exc:
            return None, _refuse(401, exc.code)
        except ContextKeyUnavailableError as exc:
            return None, JSONResponse(
                status_code=503,
                content={"detail": {"error": exc.code}},
                headers={"Retry-After": "10"},
            )
        signed_agent = claims.get(AGENT_ID_CLAIM)
        if signed_agent != self.agent_id or requested_agent_id != self.agent_id:
            return None, _refuse(403, "E_RUNTIME_AGENT_MISMATCH")
        try:
            envelope = envelope_from_claims(
                claims,
                context_token,
                trace_id=trace_id,
                correlation_id=correlation_id,
            )
        except PermissionError as exc:
            return None, _refuse(403, str(exc).split(":", 1)[0])
        except (KeyError, TypeError, ValueError):
            return None, _refuse(401, "E_CONTEXT_TOKEN_CLAIMS")
        return envelope, None

    async def handle(
        self, body: TurnRequest, caller_header: str | None
    ) -> JSONResponse:
        adm = body.admission
        envelope, refusal = await self._verify_caller_and_envelope(
            caller_header=caller_header,
            context_token=body.context_token,
            requested_agent_id=body.turn.agent_id,
            trace_id=adm.trace_id,
            correlation_id=adm.correlation_id,
        )
        if refusal is not None:
            return refusal
        if (
            body.turn.raw_sql_override is not None
            and not self._services.sandbox_mode_active()
        ):
            return _refuse(
                422, "E_RAW_SQL_SANDBOX_ONLY"
            )  # same rule as the gateway
        hops = list(adm.hops)
        try:
            with turn_broker_token(body.broker_token):
                result = await run_agent_turn(
                    body.turn,
                    envelope,
                    services=self._services,
                    hops=hops,
                    finops=dict(adm.finops),
                    estimated_tokens=adm.estimated_tokens,
                    prompt_cache_hit=adm.prompt_cache_hit,
                    identity_source=adm.identity_source,
                )
        except PermissionError as exc:
            return JSONResponse(
                content={
                    "outcome": "blocked",
                    "message": str(exc),
                    "hops": hops,
                }
            )
        except sandbox_execution.SandboxUnavailableError as exc:
            return JSONResponse(
                content={
                    "outcome": "http_error",
                    "status_code": 503,
                    "detail": {"error": exc.code},
                }
            )
        except HTTPException as exc:
            return JSONResponse(
                content={
                    "outcome": "http_error",
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                }
            )
        return JSONResponse(
            content=jsonable_encoder({"outcome": "ok", "result": result})
        )

    async def handle_sandbox_lifecycle(
        self,
        body: SandboxLifecycleRequest,
        caller_header: str | None,
        *,
        action: Literal["pause", "release"],
    ) -> JSONResponse:
        """Executes session sandbox pause or release on the agent runtime's own manager."""
        envelope, refusal = await self._verify_caller_and_envelope(
            caller_header=caller_header,
            context_token=body.context_token,
            requested_agent_id=body.agent_id,
            trace_id=body.trace_id,
            correlation_id=body.correlation_id,
        )
        if refusal is not None:
            return refusal
        lifecycle_fn = (
            self._services.sandbox_manager.pause_session_sandbox
            if action == "pause"
            else self._services.sandbox_manager.release_session_sandbox
        )
        lifecycle_kwargs: dict[str, Any] = {
            "envelope": envelope,
            "agent_id": body.agent_id,
        }
        if body.language is not None:
            lifecycle_kwargs["language"] = sandbox_execution.SandboxLanguage(
                body.language
            )
        try:
            receipt = await asyncio.to_thread(lifecycle_fn, **lifecycle_kwargs)
        except PermissionError as exc:
            return JSONResponse(
                content={"outcome": "blocked", "message": str(exc), "hops": []}
            )
        except sandbox_execution.SandboxUnavailableError as exc:
            return JSONResponse(
                content={
                    "outcome": "http_error",
                    "status_code": 503,
                    "detail": {"error": exc.code},
                }
            )
        return JSONResponse(
            content=jsonable_encoder({"outcome": "ok", "result": receipt})
        )


def runtime_from_env(*, require_cloud_run: bool = True) -> RuntimeService:
    """Production configuration; refuses to start on a wrong deployment (fail closed).

    `require_cloud_run=False` is for tests only.
    """
    from agents.kms_rest import configure_client_certificate_env

    configure_client_certificate_env()
    if require_cloud_run and not os.getenv("K_SERVICE"):
        raise RuntimeError(
            "E_RUNTIME_CONFIG: the runtime runs only on Cloud Run (K_SERVICE unset)"
        )
    agent_id = (os.getenv("RUNTIME_AGENT_ID") or "").strip()
    if not agent_id:
        raise RuntimeError("E_RUNTIME_CONFIG: set RUNTIME_AGENT_ID")
    callers = frozenset(
        c.strip()
        for c in os.getenv("RUNTIME_ALLOWED_CALLERS", "").split(",")
        if c.strip()
    )
    if not callers:
        raise RuntimeError(
            "E_RUNTIME_CONFIG: set RUNTIME_ALLOWED_CALLERS (the gateway SA)"
        )
    aud = (os.getenv("RUNTIME_EXPECTED_AUDIENCE") or "").strip()
    if require_cloud_run and not aud.startswith("https://"):
        raise RuntimeError(
            "E_RUNTIME_CONFIG: set RUNTIME_EXPECTED_AUDIENCE to this service's URL"
        )
    org_id = wi.agent_org_id_from_config(get_platform_config())
    caller_verify: Callable[[str], Mapping[str, Any]] | None = None
    if aud:
        from broker_service.core import google_id_token_signature_verifier

        google_verify = google_id_token_signature_verifier(aud)
        route = wi.routing_signature_verifier(
            google_verifier=lambda token, _aud: google_verify(token),
            agent_verifier=(
                wi.agent_identity_token_verifier(org_id) if org_id else None
            ),
            agent_org_id=org_id,
        )

        def caller_verify(token: str) -> Mapping[str, Any]:
            return route(token, aud)

    _install_context_key_source_from_env()
    disable_local_exchange()
    try:
        return RuntimeService(
            agent_id=agent_id,
            allowed_callers=callers,
            expected_audience=aud or None,
            caller_signature_verifier=caller_verify,
            agent_org_id=org_id,
        )
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc


def create_app(runtime: RuntimeService | None = None) -> FastAPI:
    runtime = (
        runtime or runtime_from_env()
    )  # fail closed at startup on missing config
    disable_local_exchange()
    app = FastAPI(
        title="Cymbal agent runtime",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "agent_id": runtime.agent_id}

    @app.post(TURN_PATH)
    async def turn(
        body: TurnRequest,
        x_serverless_authorization: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> Any:
        # Same precedence as the broker: when X-Serverless-Authorization is present Cloud Run IAM
        # verified THAT header and passed Authorization through unverified.
        return await runtime.handle(
            body, x_serverless_authorization or authorization
        )

    @app.post(SANDBOX_PAUSE_PATH)
    async def pause_sandbox(
        body: SandboxLifecycleRequest,
        x_serverless_authorization: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> Any:
        return await runtime.handle_sandbox_lifecycle(
            body, x_serverless_authorization or authorization, action="pause"
        )

    @app.post(SANDBOX_RELEASE_PATH)
    async def release_sandbox(
        body: SandboxLifecycleRequest,
        x_serverless_authorization: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> Any:
        return await runtime.handle_sandbox_lifecycle(
            body, x_serverless_authorization or authorization, action="release"
        )

    return app
