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

# pylint: disable=line-too-long,protected-access

"""Health, Hop 0 token exchange, caller identity, ARD/A2A discovery, and JWKS endpoints."""

from __future__ import annotations

import asyncio
import os
import secrets
import time
from typing import Any

from agents import workload_identity as wi
from agents.auth.vault_and_bulkhead import (
    AuthManager3LOVault,
    Delegated3LOToken,
    RemoteBroker3LOVault,
)
from agents.context import _ACTIVE_TENANT_ENVELOPE
from agents.context_token import (
    JWKS_MAX_AGE_SECONDS,
    ContextKeyUnavailableError,
    ContextTokenError,
    get_context_verifier,
    public_key_to_jwk,
)
from agents.pooled_resilience_and_standards import A2AAgentCardRegistry
from agents.workspace_plugins import WorkspacePluginRegistry
from app.auth import (
    DEV_ISSUER_TOKEN_TTL_SECONDS,
    SandboxIssuerDisabled,
    get_hop0,
    mint_sandbox_token,
)
from app.gateway_tokens import (
    GatewayTokenError,
    consume_proof,
    gateway_error,
    get_token_service,
    request_htu,
    unauthorized,
    verify_fresh_dpop_proof,
)
from app.runtime_state import (
    Caller,
    active_platform_config,
    gateway_module,
    logger,
    public_error_code,
    stripped_header_names,
)
from app.schemas.gateway import (
    OAuth3LOAuthorizeRequest,
    OAuth3LOCallbackRequest,
    SandboxTokenRequest,
    TokenExchangeRequest,
)
from broker_service.core import google_id_token_signature_verifier
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

router = APIRouter()

INTERNAL_PATH_PREFIX = "/internal/"
INTERNAL_CONTEXT_JWKS_PATH = "/internal/v1/context-jwks"


def internal_jwks_enabled() -> bool:
    """Returns True when internal JWKS caller allowlist and audience env vars are configured."""
    return bool(
        (os.getenv("CONTEXT_JWKS_ALLOWED_CALLERS") or "").strip()
        and (os.getenv("CONTEXT_JWKS_AUDIENCE") or "").strip()
    )


def _internal_jwks_caller_verifier() -> Any:
    """Builds the workload-identity signature verifier for `/internal/v1/context-jwks`."""
    audience = (os.getenv("CONTEXT_JWKS_AUDIENCE") or "").strip()
    org_id = wi.agent_org_id_from_config(active_platform_config())
    google_verify = google_id_token_signature_verifier(audience)
    return (
        audience,
        org_id,
        wi.routing_signature_verifier(
            google_verifier=lambda token, _aud: google_verify(token),
            agent_verifier=(
                wi.agent_identity_token_verifier(org_id) if org_id else None
            ),
            agent_org_id=org_id,
        ),
    )


async def internal_context_jwks(request: Request) -> JSONResponse:
    """Serves context-token public keys to verified internal agent runtime callers only."""
    gateway = gateway_module()
    active_jwks_enabled = getattr(
        gateway, "internal_jwks_enabled", internal_jwks_enabled
    )
    if not active_jwks_enabled():
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    allowed = {
        principal.value
        for candidate in (
            os.getenv("CONTEXT_JWKS_ALLOWED_CALLERS") or ""
        ).split(",")
        if (principal := wi.normalize_principal(candidate)) is not None
    }
    scheme, _, token = (
        request.headers.get("x-cymbal-caller-token") or ""
    ).partition(" ")
    verifier_hook = getattr(
        gateway,
        "_internal_jwks_caller_verifier",
        _internal_jwks_caller_verifier,
    )
    try:
        if scheme.lower() != "bearer":
            raise wi.CallerIdentityError("E_CALLER_TOKEN_MISSING")
        audience, org_id, verify = verifier_hook()
        principal = await asyncio.to_thread(
            wi.verify_caller_identity,
            token,
            audience,
            verify_signature=verify,
            agent_org_id=org_id,
        )
        if principal.value not in allowed:
            raise wi.CallerIdentityError("E_CALLER_NOT_ALLOWED")
    except wi.CallerIdentityError as exc:
        return JSONResponse(
            status_code=401, content={"detail": {"error": exc.code}}
        )
    active_context_jwks = getattr(gateway, "context_jwks", context_jwks)
    return await active_context_jwks()


@router.get("/.well-known/cymbal-context-jwks.json")
async def context_jwks() -> JSONResponse:
    """Publishes ES256 public keys verifying `ctx+jwt` context tokens (ADR-0014 D3)."""
    try:
        verifier = get_context_verifier()
        keys = await asyncio.to_thread(verifier.published_keys)
    except (ContextKeyUnavailableError, ContextTokenError) as exc:
        logger.warning("context JWKS unavailable (%s)", type(exc).__name__)
        keys = {}
    if not keys:
        return JSONResponse(
            status_code=503,
            content={"detail": {"error": ContextKeyUnavailableError.code}},
            headers={"Cache-Control": "no-store", "Retry-After": "10"},
        )
    return JSONResponse(
        content={
            "keys": [
                public_key_to_jwk(kid, key) for kid, key in sorted(keys.items())
            ]
        },
        headers={"Cache-Control": f"public, max-age={JWKS_MAX_AGE_SECONDS}"},
    )


@router.get("/healthz")
@router.get("/api/v1/health")
async def healthz() -> dict[str, Any]:
    """Returns gateway runtime status and cached/live PostgreSQL RLS posture verification."""
    gateway = gateway_module()
    db_pool = gateway.DB_POOL
    cached = getattr(gateway, "_CACHED_RLS_POSTURE", None)
    try:
        if cached is not None and cached[0] == id(db_pool):
            rls_posture = cached[1]
        else:
            rls_posture = await db_pool.verify_live_rls_posture()
            gateway._CACHED_RLS_POSTURE = (id(db_pool), rls_posture)
    except PermissionError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": public_error_code(exc)},
        ) from exc
    runtime_status = gateway.RUNTIME_STATUS
    return {
        "status": "ok",
        "pattern": "Pattern A (High-Density Pooled)",
        "environment": runtime_status["environment"],
        "data_classification": runtime_status["data_classification"],
        "live_mode": runtime_status["live_mode"],
        "gcp_project": runtime_status["project_id"],
        "region": os.getenv(
            "GOOGLE_CLOUD_REGION", active_platform_config().gcp.region
        ),
        "tenants": len(runtime_status["tenants"]),
        "rls_posture_verified": bool(rls_posture.get("verified")),
        "rls_posture_mode": str(rls_posture.get("mode", "schema_ddl_verified")),
    }


@router.post("/api/v1/sandbox/token")
async def sandbox_token(
    req: SandboxTokenRequest, response: Response
) -> dict[str, Any]:
    """SANDBOX ONLY: Mints a synthetic user ID token in the tenant's configured IdP format."""
    try:
        token = mint_sandbox_token(
            tenant_id=req.tenant_id, sub=req.sub, role=req.role
        )
    except SandboxIssuerDisabled as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=400, detail="E_SANDBOX_TOKEN_REQUEST_INVALID"
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {
        "id_token": token,
        "token_type": "Bearer",
        "expires_in": DEV_ISSUER_TOKEN_TTL_SECONDS,
        "tenant_id": req.tenant_id,
        "sandbox_only": True,
    }


@router.post("/api/v1/auth/token")
async def exchange_token(
    request: Request, req: TokenExchangeRequest, response: Response
) -> dict[str, Any]:
    """Exchanges a verified Hop 0 IdP ID token + DPoP proof for a sender-constrained gateway
    token.
    """
    gateway = gateway_module()
    service = get_token_service()
    try:
        proof = verify_fresh_dpop_proof(
            request.headers.get("dpop", ""),
            htm="POST",
            htu=request_htu(request),
            access_token=None,
        )
        claims = get_hop0().gate.verify_and_normalize(req.subject_token)
        consume_proof(proof, service.exchange_replay)
        service.subject_bindings.bind(
            req.subject_token, proof["jkt"], float(claims["exp"])
        )
        envelope = gateway.EDGE_VERIFIER.exchange_obo_token(
            verified_idp_claims=claims,
            dpop_proof={"jkt": proof["jkt"], "jti": proof["jti"]},
            replay_checked=True,
            issue_context_token=False,
        )
        token, ttl = service.issue(envelope)
    except GatewayTokenError as exc:
        public = {
            "E_SUBJECT_TOKEN_BOUND_TO_OTHER_KEY": "E_SUBJECT_TOKEN_INVALID"
        }
        if exc.code not in public:
            raise gateway_error(exc.code) from exc
        logger.warning("token exchange refused: %s", exc.code)
        raise unauthorized(public[exc.code]) from exc
    except PermissionError as exc:
        logger.info("token exchange refused (%s)", type(exc).__name__)
        raise unauthorized("E_SUBJECT_TOKEN_INVALID") from exc
    except (OSError, TimeoutError) as exc:
        logger.error(
            "token exchange: IdP key fetch failed (%s)", type(exc).__name__
        )
        raise HTTPException(
            status_code=503, detail={"error": "E_IDP_UNAVAILABLE"}
        ) from exc
    except Exception as exc:
        logger.info("token exchange refused (%s)", type(exc).__name__)
        raise unauthorized("E_SUBJECT_TOKEN_INVALID") from exc
    finally:
        _ACTIVE_TENANT_ENVELOPE.set(None)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {
        "access_token": token,
        "token_type": "DPoP",
        "expires_in": ttl,
        "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
    }


@router.get("/api/v1/whoami")
async def whoami(envelope: Caller) -> dict[str, Any]:
    """Returns caller tenancy and RBAC role derived strictly from the verified gateway token."""
    return {
        "tenant_id": envelope.tenant.tenant_id,
        "user_role": envelope.security.user_role,
        "idp_provider": envelope.security.idp_provider,
        "identity_source": "HOP0_VERIFIED",
    }


@router.get("/.well-known/ai-catalog.json")
async def ard_catalog(request: Request, envelope: Caller) -> dict[str, Any]:
    """Hop 2 Agent Resource Discovery (ARD) filtered strictly to the caller's tenant."""
    gateway = gateway_module()
    try:
        catalog = gateway.REGISTRY_PDP.discover_ai_catalog(
            envelope.tenant.tenant_id
        )
        catalog["stripped_untrusted_headers"] = stripped_header_names(
            request.headers
        )
        return catalog
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="E_CATALOG_FORBIDDEN"
        ) from exc


@router.get("/.well-known/agent.json")
async def a2a_agent_cards(envelope: Caller) -> dict[str, Any]:
    """Returns A2A Agent Cards with tier-scoped tool allowlists for the caller's tenant."""
    return A2AAgentCardRegistry.build_a2a_agent_cards(envelope=envelope)


@router.post("/api/v1/oauth/3lo/authorize")
async def authorize_3lo_oauth(
    req: OAuth3LOAuthorizeRequest,
    envelope: Caller,
    response: Response,
) -> dict[str, Any]:
    """Mints a tenant- and session-bound 3LO OAuth consent `state` token for the caller."""
    if req.required_scope not in envelope.tenant.authorized_scopes:
        raise HTTPException(
            status_code=403,
            detail={"error": "E_3LO_SCOPE_NOT_ENTITLED"},
            headers={"Cache-Control": "no-store"},
        )
    oauth_state = WorkspacePluginRegistry.mint_csrf_bound_oauth_state(
        envelope=envelope,
        required_scope=req.required_scope,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "OAUTH_CONSENT_CHALLENGE",
        "tenant_id": envelope.tenant.tenant_id,
        "provider": req.provider,
        "required_scope": req.required_scope,
        "oauth_state": oauth_state,
    }


@router.post("/api/v1/oauth/3lo/callback")
async def callback_3lo_oauth(
    req: OAuth3LOCallbackRequest,
    envelope: Caller,
    response: Response,
) -> dict[str, Any]:
    """Verifies CSRF `oauth_state` and binds the 3LO grant to `(tenant_id, sub, scope)`."""
    if req.required_scope not in envelope.tenant.authorized_scopes:
        raise HTTPException(
            status_code=403,
            detail={"error": "E_3LO_SCOPE_NOT_ENTITLED"},
            headers={"Cache-Control": "no-store"},
        )
    try:
        WorkspacePluginRegistry.verify_oauth_callback_state(
            callback_state=req.oauth_state,
            active_envelope=envelope,
            required_scope=req.required_scope,
        )
    except PermissionError as csrf_exc:
        raise HTTPException(
            status_code=403,
            detail={"error": "E_OAUTH_3LO_CSRF_STATE_MISMATCH"},
            headers={"Cache-Control": "no-store"},
        ) from csrf_exc

    token_handle = AuthManager3LOVault.handle_for_caller(
        tenant_id=envelope.tenant.tenant_id,
        user_sub=envelope.security.sub,
        required_scope=req.required_scope,
    )
    expires_at = int(time.time()) + 3600
    delegated_token = Delegated3LOToken(
        token_handle=token_handle,
        tenant_id=envelope.tenant.tenant_id,
        user_sub=envelope.security.sub,
        provider=req.provider,
        scopes=(req.required_scope,),
        access_token=f"oauth3lo-{secrets.token_urlsafe(24)}",
        expires_at=expires_at,
    )
    vault_3lo = gateway_module().TURN_SERVICES.workspace_plugins.vault_3lo
    try:
        if isinstance(vault_3lo, RemoteBroker3LOVault):
            await asyncio.to_thread(
                vault_3lo.store_3lo_token_for_caller,
                envelope=envelope,
                token=delegated_token,
            )
        else:
            vault_3lo.store_3lo_token(delegated_token)
    except PermissionError as vault_exc:
        raise HTTPException(
            status_code=403,
            detail={"error": public_error_code(vault_exc)},
            headers={"Cache-Control": "no-store"},
        ) from vault_exc

    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "OAUTH_CONSENT_LINKED",
        "token_handle": token_handle,
        "tenant_id": envelope.tenant.tenant_id,
        "provider": req.provider,
        "scopes": [req.required_scope],
        "expires_at": expires_at,
    }
