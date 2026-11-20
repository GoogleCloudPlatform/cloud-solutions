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

"""Wire contract between the gateway and an agent runtime service (ADR-0014 B5, plan S1).

The gateway admits a turn (Hop 0-2) and forwards it to the agent's own Cloud Run service:

    POST /internal/v1/turn
    X-Serverless-Authorization: Bearer <gateway's Google ID token, audience = the service URL>
    {
      "context_token": "<KMS-signed ctx+jwt with agent_id bound>",
      "broker_token": "<broker-audience derived token, pre-minted by the gateway>" | null,
      "turn": {agent_id, prompt, tool_name, requested_thinking_tokens, raw_sql_override,
          live_cloud},
      "admission": {hops, finops, estimated_tokens, prompt_cache_hit, identity_source,
                    trace_id, correlation_id}
    }

Turn outcomes are HTTP 200 with `outcome` = `ok` | `blocked` | `http_error`, so the gateway can
reproduce exactly the response the in-process path gives. Authentication and token failures are
plain 401 / 403 / 503 from the runtime.

Everything that decides access in the runtime comes from the verified context token (tenant, user,
role, scopes, session, agent). `admission` is the gateway's bookkeeping for the response (hops so
far, metered tokens); it is accepted only from the authenticated gateway and never widens access.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Mapping
from typing import Any, Literal

from agents.context import (
    TENANT_DIRECTORY,
    ContextEnvelope,
    RequestContext,
    SecurityContext,
    SubscriptionTier,
    TenantContext,
    _delegation_tag,
)
from agents.context_token import AUDIENCE_RUNTIME
from agents.workload_identity import CallerIdentityError
from pydantic import BaseModel, Field

TURN_PATH = "/internal/v1/turn"
SANDBOX_PAUSE_PATH = "/internal/v1/sandboxes/session/pause"
SANDBOX_RELEASE_PATH = "/internal/v1/sandboxes/session/release"
SIGNATURE_REMOVED = "SIGNATURE_REMOVED_BY_GOOGLE"
TURN_FIELDS = (
    "agent_id",
    "prompt",
    "tool_name",
    "requested_thinking_tokens",
    "raw_sql_override",
    "live_cloud",
)


class SandboxLifecycleRequest(BaseModel):
    """B5 runtime request to pause or permanently destroy the session's agent sandbox in Gemini."""

    model_config = {"extra": "forbid"}

    context_token: str | None = Field(default=None, max_length=16384)
    agent_id: str = Field(max_length=64)
    language: Literal["python", "javascript", "bash"] | None = None
    trace_id: str = Field(default="", max_length=128)
    correlation_id: str = Field(default="", max_length=128)


def turn_payload(req: Any) -> dict[str, Any]:
    """The turn request fields the runtime needs (nothing identity-bearing)."""
    payload = {name: getattr(req, name) for name in TURN_FIELDS}
    sandbox_code = getattr(req, "sandbox_code", None)
    if sandbox_code is not None:
        payload["sandbox_code"] = sandbox_code
        payload["sandbox_language"] = str(
            getattr(req, "sandbox_language", "python") or "python"
        )
    return payload


def verified_claims_from_cloud_run_header(
    value: str | None,
    *,
    verify_signature: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Claims of the caller's ID token from the header Cloud Run IAM verified.

    Same rule as the broker: Cloud Run IAM verifies the token before the request reaches the
    container and replaces its signature with `SIGNATURE_REMOVED_BY_GOOGLE`. If the signature is
    still present (unexpected deployment), it must verify with `verify_signature`, else refuse.
    """
    scheme, _, token = (value or "").partition(" ")
    if scheme.lower() != "bearer" or token.count(".") != 2:
        raise CallerIdentityError("E_CALLER_TOKEN_MISSING")
    if token.rsplit(".", 1)[1] != SIGNATURE_REMOVED:
        if verify_signature is None:
            raise CallerIdentityError("E_CALLER_TOKEN_UNVERIFIED")
        try:
            verified = verify_signature(token)
        except Exception as exc:
            raise CallerIdentityError("E_CALLER_TOKEN_UNVERIFIED") from exc
        if not isinstance(verified, Mapping):
            raise CallerIdentityError("E_CALLER_TOKEN_UNVERIFIED")
        return dict(verified)
    try:
        payload = token.split(".")[1]
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
    except (ValueError, TypeError) as exc:
        raise CallerIdentityError("E_CALLER_TOKEN_MISSING") from exc
    if not isinstance(claims, dict):
        raise CallerIdentityError("E_CALLER_TOKEN_MISSING")
    return claims


def envelope_from_claims(
    claims: Mapping[str, Any],
    context_token: str,
    *,
    trace_id: str,
    correlation_id: str,
) -> ContextEnvelope:
    """Rebuilds the request envelope from VERIFIED context-token claims only.

    Every access-deciding field comes from the signed claims; the per-turn telemetry ids are the
    only unsigned inputs (they never drive an access decision). The tenant must still be onboarded
    in this process (offboarding is honoured by the runtime too).
    """
    tenant_id = str(claims["tenant_id"])
    if tenant_id not in TENANT_DIRECTORY:
        raise PermissionError(
            "E_RUNTIME_TENANT_NOT_ONBOARDED: tenant is not onboarded."
        )
    security = SecurityContext(
        iss=str(claims["idp_iss"]),
        sub=str(claims["sub"]),
        aud=AUDIENCE_RUNTIME,
        exp=int(claims["exp"]),
        jti=str(claims["src_jti"]),
        kid="",
        dpop_jkt=str((claims.get("cnf") or {}).get("jkt", "")),
        user_role=str(claims["user_role"]),
        idp_provider=str(claims["idp_provider"]),
    )
    tenant = TenantContext(
        tenant_id=tenant_id,
        subscription_tier=SubscriptionTier(str(claims["tier"])),
        org_unit=str(claims["org_unit"]),
        authorized_scopes=tuple(claims["scopes"]),
        thinking_token_budget=int(claims["thinking_budget"]),
        cmek_key_name=str(claims["cmek_key_name"]),
    )
    request = RequestContext(
        trace_id=str(trace_id)[:128],
        correlation_id=str(correlation_id)[:128],
        session_id=str(claims["session_id"]),
    )
    raw_agent_id = claims.get("agent_id")
    return ContextEnvelope(
        security=security,
        tenant=tenant,
        request=request,
        context_token=context_token,
        delegation_sig=_delegation_tag(context_token, 0),
        agent_id=(
            str(raw_agent_id)
            if isinstance(raw_agent_id, str) and raw_agent_id
            else None
        ),
    )
