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

"""Credential broker service entrypoint (ADR-0014 B4). Same image, separate Cloud Run service:

    uvicorn broker_service.main:create_app --factory --host 0.0.0.0 --port 8080

Endpoints: `POST /internal/v1/tenant-credential` and `GET /healthz`. Nothing else. Deploy with
`--no-allow-unauthenticated` and `roles/run.invoker` for the runtime SA only (see
docs/runbooks/credential_broker_b4.md). Imports no ADK or agent modules (tested).

Config (environment):
- `BROKER_ALLOWED_CALLERS`: comma-separated callers allowed to call: service account emails (the
  runtime SA) and/or Cloud Run Agent Identity principals (`principal://agents.global...`,
  ADR-0016). Required: the service refuses to start without it or with a malformed entry.
- `BROKER_REQUIRE_AGENT_BINDING=1`: also require the broker token's signed `agent_id`, a caller
  equal to that agent's principal in `agent_identity.bindings` (platform config), and the
  `broker:<kind>` purpose. Off by default; refuses to start if on with no bindings.
- `agent_identity.org_id` (platform config): pins the issuer of Agent Identity caller tokens (the
  org's agent STS pool); their signature is checked against that pool's JWKS when Cloud Run has
  not already verified it. Without it, agent-identity callers are refused.
- `WORKLOAD_IDENTITY_AGENT_PRINCIPAL_CLAIM` / `WORKLOAD_IDENTITY_SA_PRINCIPAL_CLAIM`: which caller
  ID-token claim carries each principal kind (defaults `sub` / `email`, as seen in the A0 spike).
- `BROKER_EXPECTED_AUDIENCE`: optional; the broker's own URL, matched against the caller ID
  token's `aud`.
- `CYMBAL_ENV` / `GOOGLE_CLOUD_PROJECT`: platform config (tenants, context-signing key).
"""

from __future__ import annotations

import os
from typing import Any, Literal

from agents import platform_config, workload_identity
from broker_service.core import (
    MAX_ACCESS_TOKEN_LIFETIME_SECONDS,
    BrokerRefused,
    BrokerUnavailable,
    CredentialBroker,
)
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class CredentialRequest(BaseModel):
    """What to mint. The tenant comes only from the broker token; naming one is rejected (422)."""

    model_config = {"extra": "forbid"}

    kind: Literal["access_token", "id_token"] = "access_token"
    audience: str | None = Field(default=None, max_length=512)
    lifetime_seconds: int | None = Field(default=None, ge=60, le=3600)


class Store3LOCredentialRequest(BaseModel):
    """Stores a 3LO token in the out-of-process vault; tenant & user come only from `ctx+jwt`."""

    model_config = {"extra": "forbid"}

    token_handle: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(min_length=1, max_length=32)
    access_token: str = Field(min_length=1, max_length=8192)
    expires_at: int = Field(ge=1)


class Checkout3LOCredentialRequest(BaseModel):
    """Checks out a 3LO token for the `(tenant_id, sub)` authenticated by `ctx+jwt`."""

    model_config = {"extra": "forbid"}

    token_handle: str = Field(min_length=1, max_length=128)
    required_scope: str = Field(min_length=1, max_length=128)


def _onboarded_tenants() -> dict[str, tuple[str, ...]]:
    return {
        t.tenant_id: tuple(t.broker_id_token_audiences)
        for t in platform_config.get_platform_config().tenants
    }


def broker_from_env(*, require_cloud_run: bool = True) -> CredentialBroker:
    """Production configuration; refuses to start on a wrong deployment (fail closed).

    `require_cloud_run=False` is for tests only.
    """
    from broker_service.core import google_id_token_signature_verifier
    from broker_service.iam_backend import IamCredentialsBackend

    if require_cloud_run and not os.getenv("K_SERVICE"):
        raise RuntimeError(
            "E_BROKER_CONFIG: the broker runs only on Cloud Run behind IAM (K_SERVICE unset)"
        )
    callers = frozenset(
        c.strip()
        for c in os.getenv("BROKER_ALLOWED_CALLERS", "").split(",")
        if c.strip()
    )
    if not callers:
        raise RuntimeError(
            "E_BROKER_CONFIG: set BROKER_ALLOWED_CALLERS (the runtime SA email)"
        )
    if any(workload_identity.normalize_principal(c) is None for c in callers):
        raise RuntimeError(
            "E_BROKER_CONFIG: BROKER_ALLOWED_CALLERS entries must be SA emails or Agent Identity "
            "principals"
        )
    expected_aud = (os.getenv("BROKER_EXPECTED_AUDIENCE") or "").strip()
    if not expected_aud.startswith("https://"):
        raise RuntimeError(
            "E_BROKER_CONFIG: set BROKER_EXPECTED_AUDIENCE to the broker URL (the same string as "
            "the runtime's CREDENTIAL_BROKER_URL)"
        )
    active_config = platform_config.get_platform_config()
    token_policy = platform_config.resolve_effective_token_policy(active_config)
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or active_config.gcp.project_id
    require_binding = workload_identity.flag_enabled(
        "BROKER_REQUIRE_AGENT_BINDING"
    )
    if require_binding and not workload_identity.bindings_from_config(
        active_config
    ):
        raise RuntimeError(
            "E_BROKER_CONFIG: BROKER_REQUIRE_AGENT_BINDING=1 needs agent_identity.bindings in the "
            "platform config"
        )
    org_id = workload_identity.agent_org_id_from_config(active_config)
    google_verify = google_id_token_signature_verifier(expected_aud)
    caller_verify = workload_identity.routing_signature_verifier(
        google_verifier=lambda token, _aud: google_verify(token),
        agent_verifier=(
            workload_identity.agent_identity_token_verifier(org_id)
            if org_id
            else None
        ),
        agent_org_id=org_id,
    )
    return CredentialBroker(
        project_id=project,
        allowed_callers=callers,
        backend=IamCredentialsBackend(),
        tenants=_onboarded_tenants,
        expected_caller_audience=expected_aud,
        caller_signature_verifier=lambda token: caller_verify(
            token, expected_aud
        ),
        max_access_token_lifetime_seconds=min(
            token_policy.tenant_sa_token_ttl_seconds,
            MAX_ACCESS_TOKEN_LIFETIME_SECONDS,
        ),
        require_agent_binding=require_binding,
        agent_bindings=lambda: workload_identity.bindings_from_config(
            platform_config.get_platform_config()
        ),
        principal_claims=workload_identity.PrincipalClaimConfig.from_env(),
        agent_org_id=org_id,
    )


def create_app(broker: CredentialBroker | None = None) -> FastAPI:
    broker = (
        broker or broker_from_env()
    )  # fail closed at startup on missing config
    app = FastAPI(
        title="Cymbal credential broker",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/internal/v1/tenant-credential")
    async def tenant_credential(
        req: CredentialRequest,
        x_serverless_authorization: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        x_cymbal_context_token: str | None = Header(default=None),
    ) -> Any:
        import asyncio

        # Header precedence matters: when `X-Serverless-Authorization` is present, Cloud Run IAM
        # verifies THAT header and passes `Authorization` through unverified (it is free for
        # application use). So the caller identity must come from X-Serverless-Authorization
        # whenever it is present; `Authorization` is used only when it is the header Cloud Run
        # verified (no X-Serverless-Authorization at all).
        caller_header = x_serverless_authorization or authorization
        try:
            cred, tenant_id = await asyncio.to_thread(
                broker.mint,
                caller_header=caller_header,
                context_token=x_cymbal_context_token,
                kind=req.kind,
                audience=req.audience,
                lifetime_seconds=req.lifetime_seconds,
            )
        except BrokerRefused as exc:
            return JSONResponse(
                status_code=exc.status, content={"detail": {"error": exc.code}}
            )
        except BrokerUnavailable as exc:
            return JSONResponse(
                status_code=503,
                content={"detail": {"error": exc.code}},
                headers={"Retry-After": "10"},
            )
        return {
            "kind": cred.kind,
            req.kind: cred.token,
            "expires_at": cred.expires_at,
            "principal": cred.principal,
            "tenant_id": tenant_id,
        }

    @app.post("/internal/v1/3lo-credential/store")
    async def store_3lo_credential(
        req: Store3LOCredentialRequest,
        x_serverless_authorization: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        x_cymbal_context_token: str | None = Header(default=None),
    ) -> Any:
        import asyncio

        caller_header = x_serverless_authorization or authorization
        try:
            stored = await asyncio.to_thread(
                broker.store_3lo_credential,
                caller_header=caller_header,
                context_token=x_cymbal_context_token,
                token_handle=req.token_handle,
                provider=req.provider,
                scopes=tuple(req.scopes),
                access_token=req.access_token,
                expires_at=req.expires_at,
            )
        except BrokerRefused as exc:
            return JSONResponse(
                status_code=exc.status, content={"detail": {"error": exc.code}}
            )
        except BrokerUnavailable as exc:
            return JSONResponse(
                status_code=503,
                content={"detail": {"error": exc.code}},
                headers={"Retry-After": "10"},
            )
        return {
            "token_handle": stored.token_handle,
            "tenant_id": stored.tenant_id,
            "user_sub": stored.user_sub,
            "provider": stored.provider,
            "scopes": list(stored.scopes),
            "expires_at": stored.expires_at,
        }

    @app.post("/internal/v1/3lo-credential/checkout")
    async def checkout_3lo_credential(
        req: Checkout3LOCredentialRequest,
        x_serverless_authorization: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        x_cymbal_context_token: str | None = Header(default=None),
    ) -> Any:
        import asyncio

        caller_header = x_serverless_authorization or authorization
        try:
            stored = await asyncio.to_thread(
                broker.checkout_3lo_credential,
                caller_header=caller_header,
                context_token=x_cymbal_context_token,
                token_handle=req.token_handle,
                required_scope=req.required_scope,
            )
        except BrokerRefused as exc:
            return JSONResponse(
                status_code=exc.status, content={"detail": {"error": exc.code}}
            )
        except BrokerUnavailable as exc:
            return JSONResponse(
                status_code=503,
                content={"detail": {"error": exc.code}},
                headers={"Retry-After": "10"},
            )
        return {
            "token_handle": stored.token_handle,
            "tenant_id": stored.tenant_id,
            "user_sub": stored.user_sub,
            "provider": stored.provider,
            "scopes": list(stored.scopes),
            "access_token": stored.access_token,
            "expires_at": stored.expires_at,
        }

    @app.post("/internal/v1/3lo-credential/evict")
    async def evict_3lo_credentials(
        x_serverless_authorization: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        x_cymbal_context_token: str | None = Header(default=None),
    ) -> Any:
        import asyncio

        caller_header = x_serverless_authorization or authorization
        try:
            tenant_id, evicted_count = await asyncio.to_thread(
                broker.evict_tenant_3lo_credentials,
                caller_header=caller_header,
                context_token=x_cymbal_context_token,
            )
        except BrokerRefused as exc:
            return JSONResponse(
                status_code=exc.status, content={"detail": {"error": exc.code}}
            )
        except BrokerUnavailable as exc:
            return JSONResponse(
                status_code=503,
                content={"detail": {"error": exc.code}},
                headers={"Retry-After": "10"},
            )
        return {"tenant_id": tenant_id, "evicted_count": evicted_count}

    return app
