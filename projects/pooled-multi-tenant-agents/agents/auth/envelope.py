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

"""Immutable 3-dimension `ContextEnvelope`, tenancy tiers, memory scopes, and ADK user IDs."""

from __future__ import annotations

import contextvars
import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

_ACTIVE_TENANT_ENVELOPE: contextvars.ContextVar[ContextEnvelope | None] = (
    contextvars.ContextVar("active_tenant_envelope", default=None)
)

# Delegation depth is a loop limit, not an access grant (ADR-0014 D1): it is tracked in-process and
# bound to the context token with a random per-process key that is never configured, never leaves
# this process, and is never checked across process boundaries (MCP ignores depth).
_DELEGATION_DEPTH_KEY = secrets.token_bytes(32)


class SubscriptionTier(StrEnum):
    """Commercial and operational tenancy tiers in Cymbal SaaS."""

    STANDARD = "standard"  # RetailStream Corp (4,000 thinking budget, max 5 turns/session)
    ENTERPRISE = "enterprise"  # FinVault Bank (8,000 thinking budget, max 12 turns/session)


class MemoryScope(StrEnum):
    """The 5 Logical Memory Levels of Gemini Memory Bank."""

    GLOBAL = "global"  # Level 1: Platform-wide heuristics & shared ontology
    TENANT = "tenant"  # Level 2: Organization-wide guidelines & RAG indices
    STRATEGY = (
        "strategy"  # Level 3: Sub-agent task execution heuristics & workflows
    )
    USER = "user"  # Level 4: Personalized user preferences & past history
    SESSION = "session"  # Level 5: Ephemeral turn-by-turn conversational state


@dataclass(frozen=True)
class SecurityContext:
    """Dimension 1 of Context Envelope: Cryptographic identity claims."""

    iss: str
    sub: str
    aud: str
    exp: int
    jti: str
    kid: str
    dpop_jkt: str  # RFC 9449 DPoP JWK thumbprint bound to the OBO token
    user_role: str = (
        "sre_admin"  # Intra-tenant RBAC role (Hop 0 maps it from IdP roles/groups)
    )
    idp_provider: str = "google_workspace_oidc"  # Hop 0 federated IdP family


@dataclass(frozen=True)
class TenantContext:
    """Dimension 2 of Context Envelope: Immutable tenancy & entitlement claims."""

    tenant_id: str
    subscription_tier: SubscriptionTier
    org_unit: str
    authorized_scopes: tuple[str, ...]
    thinking_token_budget: int
    cmek_key_name: str


@dataclass(frozen=True)
class RequestContext:
    """Dimension 3 of Context Envelope: Dynamic execution & telemetry metadata."""

    trace_id: str
    correlation_id: str
    session_id: str
    region: str = "us-central1"


@dataclass(frozen=True)
class ContextEnvelope:
    """The 3-Dimension Cryptographic Context Envelope minted at Hop 1/2."""

    security: SecurityContext
    tenant: TenantContext
    request: RequestContext
    # ES256 `ctx+jwt` signed by the gateway (KMS) over every access-deciding field below.
    context_token: str = ""
    delegation_sig: str = (
        ""  # in-process depth tag (depth 0); see propagate_to_subagent
    )
    agent_id: str | None = (
        None  # routed agent bound in `context_token` (ADR-0016)
    )

    def to_adk_state(self) -> dict[str, Any]:
        """Serializes immutable tenant claims into ADK `temp:` invocation state."""
        state: dict[str, Any] = {
            "temp:tenant_id": self.tenant.tenant_id,
            "temp:tier": str(self.tenant.subscription_tier),
            "temp:org_unit": self.tenant.org_unit,
            "temp:thinking_budget": self.tenant.thinking_token_budget,
            "temp:authorized_scopes": list(self.tenant.authorized_scopes),
            "temp:cmek_key_name": self.tenant.cmek_key_name,
            "temp:iss": self.security.iss,
            "temp:user_sub": self.security.sub,
            "temp:user_role": self.security.user_role,
            "temp:idp_provider": self.security.idp_provider,
            "temp:jti": self.security.jti,
            "temp:dpop_jkt": self.security.dpop_jkt,
            "temp:trace_id": self.request.trace_id,
            "temp:correlation_id": self.request.correlation_id,
            "temp:session_id": self.request.session_id,
            "temp:context_token": self.context_token,
            "temp:delegation_depth": 0,
            "temp:delegation_sig": self.delegation_sig,
        }
        if self.agent_id:
            state["temp:agent_id"] = self.agent_id
        return state


def tenant_qualified_user_id(tenant_id: str, sub: str) -> str:
    """ADK `user_id` for a caller: IdP subjects are unique only within one IdP, so qualify them."""
    if not tenant_id or ":" in tenant_id or not sub or not sub.strip():
        raise ValueError(
            "A colon-free tenant_id and a non-empty sub are required for a session user_id."
        )
    return f"{tenant_id}:{sub}"
