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

"""Hop 1 & Hop 2 edge auth verifier, OBO + DPoP exchange, and signed ADK state verification."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import threading
import time
import uuid
from dataclasses import replace
from typing import Any

from agents.auth.dpop import AsymmetricDPoPProvider
from agents.auth.envelope import (
    _ACTIVE_TENANT_ENVELOPE,
    _DELEGATION_DEPTH_KEY,
    ContextEnvelope,
    RequestContext,
    SecurityContext,
    TenantContext,
)
from agents.auth.tenant_directory import (
    ROLE_PLATFORM_SCOPES,
    TENANT_DIRECTORY,
    USER_ROLE_ALLOWED_SCOPES,
)
from agents.context_token import DEFAULT_MAX_DELEGATION_DEPTH
from agents.platform_config import PLATFORM_SCOPES

# ADK `temp:` state key -> signed context-token claim. Every access-deciding field is listed;
# `trace_id`, `correlation_id` and `requested_thinking_budget` are deliberately absent (unsigned,
# per-turn, never used for access decisions).
_STATE_CLAIM_BINDINGS: tuple[tuple[str, str], ...] = (
    ("temp:tenant_id", "tenant_id"),
    ("temp:tier", "tier"),
    ("temp:org_unit", "org_unit"),
    ("temp:thinking_budget", "thinking_budget"),
    ("temp:authorized_scopes", "scopes"),
    ("temp:cmek_key_name", "cmek_key_name"),
    ("temp:iss", "idp_iss"),
    ("temp:user_sub", "sub"),
    ("temp:user_role", "user_role"),
    ("temp:idp_provider", "idp_provider"),
    ("temp:jti", "src_jti"),
    ("temp:dpop_jkt", "cnf.jkt"),
    ("temp:session_id", "session_id"),
)


def _claim(claims: dict[str, Any], name: str) -> Any:
    if name == "cnf.jkt":
        return (claims.get("cnf") or {}).get("jkt")
    return claims.get(name)


def _normalize_state_value(key: str, value: Any) -> Any:
    """Coerces a state value for comparison with its claim; raises on malformed types."""
    if key == "temp:authorized_scopes":
        if isinstance(value, (str, bytes)) or not isinstance(
            value, (list, tuple, set, frozenset)
        ):
            raise PermissionError(
                "E_SUBAGENT_STATE_TAMPERING: Malformed temp:authorized_scopes type."
            )
        return sorted(str(s) for s in value)
    if key == "temp:thinking_budget":
        if isinstance(value, bool):
            raise TypeError("bool budget")
        return int(value)
    return value


def _delegation_tag(context_token: str, depth: int) -> str:
    """Binds a delegation depth to this context token, so an in-process hop cannot lower it."""
    digest = hashlib.sha256(context_token.encode()).hexdigest()
    return hmac.new(
        _DELEGATION_DEPTH_KEY, f"{digest}:{int(depth)}".encode(), hashlib.sha256
    ).hexdigest()


def _context_verifier(verifier: Any | None) -> Any:
    from agents.context_token import get_context_verifier

    return verifier if verifier is not None else get_context_verifier()


class EdgeAuthVerifier:
    """Hop 1 & Hop 2: Cloud Armor + IAP Edge Verifier & RFC 8693 OBO + DPoP Token Exchange."""

    def __init__(
        self,
        *,
        context_issuer: Any | None = None,
        context_verifier: Any | None = None,
    ) -> None:
        """`context_issuer` / `context_verifier` default to the process-wide ones
        (`agents.context_signing.get_context_token_issuer`, resolved at first use).
        """
        self._context_issuer = context_issuer
        self._context_verifier = context_verifier
        self._seen_dpop_jtis: set[str] = set()
        self._jti_lock = threading.Lock()
        self.crypto_provider = AsymmetricDPoPProvider()

    @staticmethod
    def strip_untrusted_headers(headers: dict[str, str]) -> dict[str, str]:
        """Hop 1 (Cloud Armor / IAP): Unconditionally strips client-supplied tenancy headers."""
        forbidden_prefixes = (
            "x-tenant-id",
            "x-org-unit",
            "x-subscription-tier",
            "x-obo-",
        )
        return {
            k: v
            for k, v in headers.items()
            if not k.lower().startswith(forbidden_prefixes)
        }

    def exchange_asymmetric_jwt_obo(
        self,
        *,
        inbound_oidc_jwt: str,
        dpop_proof_jwt: str,
        expected_htm: str = "POST",
        expected_htu: str = "https://agent-gateway.cymbal.internal/api/v1/invoke-agent",
        raw_client_headers: dict[str, str] | None = None,
        session_id: str | None = None,
    ) -> ContextEnvelope:
        """Full Asymmetric ES256 RFC 8693 + RFC 9449 + RFC 7638 Token Exchange."""
        verified_claims = self.crypto_provider.verify_idp_jwt(inbound_oidc_jwt)
        decoded_dpop = self.crypto_provider.verify_and_decode_dpop_jwt(
            dpop_jwt=dpop_proof_jwt,
            expected_htm=expected_htm,
            expected_htu=expected_htu,
        )
        return self.exchange_obo_token(
            verified_idp_claims=verified_claims,
            dpop_proof=decoded_dpop,
            raw_client_headers=raw_client_headers,
            session_id=session_id,
        )

    def exchange_federated_idp_token(
        self,
        *,
        inbound_idp_jwt: str,
        dpop_proof_jwt: str,
        hop0_gate: Any,
        expected_htm: str = "POST",
        expected_htu: str = "https://agent-gateway.cymbal.internal/api/v1/invoke-agent",
        raw_client_headers: dict[str, str] | None = None,
        session_id: str | None = None,
    ) -> ContextEnvelope:
        """Hop 0 -> Hop 1: Okta / Entra ID / Google token federation, then DPoP-bound OBO exchange.

        `hop0_gate` is an `agents.hop0_idp_federation.HopZeroFederationGate`. It verifies the
        token against the issuer's JWKS and derives `tenant_id`, `user_role`, and `idp_provider`
        from the issuer binding; the caller cannot assert them.
        """
        normalized_claims = hop0_gate.verify_and_normalize(inbound_idp_jwt)
        decoded_dpop = self.crypto_provider.verify_and_decode_dpop_jwt(
            dpop_jwt=dpop_proof_jwt,
            expected_htm=expected_htm,
            expected_htu=expected_htu,
        )
        return self.exchange_obo_token(
            verified_idp_claims=normalized_claims,
            dpop_proof=decoded_dpop,
            raw_client_headers=raw_client_headers,
            session_id=session_id,
        )

    def exchange_obo_token(
        self,
        *,
        verified_idp_claims: dict[str, Any],
        dpop_proof: dict[str, Any] | None,
        raw_client_headers: dict[str, str] | None = None,
        session_id: str | None = None,
        replay_checked: bool = False,
        issue_context_token: bool = True,
    ) -> ContextEnvelope:
        """Hop 2 (Ingress PEP): Performs RFC 8693 OBO token exchange with RFC 9449 DPoP binding.

        `replay_checked=True` means the caller already enforced single use of the proof in a
        bounded cache (`app.gateway_tokens`), so its `jti` is not added to the legacy set.

        The envelope carries a context token signed once per source token (`jti`) and claims, with
        `exp` no later than the source token's `exp` (the gateway token on data requests).
        `issue_context_token=False` (the `/auth/token` exchange, which only needs identity to issue
        the gateway token) skips signing; such an envelope is refused by every verifier.
        A signing outage raises `ContextSigningUnavailableError` (HTTP 503), never a fallback.
        """
        _ = self.strip_untrusted_headers(raw_client_headers or {})

        tenant_id = verified_idp_claims.get("tenant_id")
        if (
            not isinstance(tenant_id, str)
            or not tenant_id
            or "\x00" in tenant_id
            or tenant_id != tenant_id.strip()
            or tenant_id not in TENANT_DIRECTORY
        ):
            raise PermissionError(
                "E_UNAUTHENTICATED_TENANT: Missing, malformed, or unknown verified tenant_id."
            )

        tenant_meta = TENANT_DIRECTORY[tenant_id]
        expected_issuer = tenant_meta["iss"]
        actual_issuer = verified_idp_claims.get("iss")
        if actual_issuer != expected_issuer:
            raise PermissionError(
                "E_IDP_ISSUER_MISMATCH: the token issuer is not the IdP onboarded for this tenant."
            )

        exp = int(verified_idp_claims.get("exp", 0))
        if exp <= int(time.time()):
            raise PermissionError(
                "E_EXPIRED_IDENTITY_TOKEN: Inbound OIDC token has expired."
            )

        if (
            not dpop_proof
            or not dpop_proof.get("jkt")
            or not dpop_proof.get("jti")
        ):
            raise PermissionError(
                "E_MISSING_DPOP_PROOF: RFC 9449 DPoP proof is required."
            )

        if not replay_checked:
            dpop_jti = str(dpop_proof["jti"])
            with self._jti_lock:
                if dpop_jti in self._seen_dpop_jtis:
                    raise PermissionError(
                        "E_DPOP_REPLAY_DETECTED: DPoP proof jti has already been consumed."
                    )
                self._seen_dpop_jtis.add(dpop_jti)

        user_role = str(
            verified_idp_claims.get("user_role", "sre_admin")
        ).strip()
        if user_role not in USER_ROLE_ALLOWED_SCOPES:
            raise PermissionError(
                f"403 E_UNKNOWN_USER_ROLE: Unrecognized intra-tenant RBAC role '{user_role}'."
            )
        role_allowed = USER_ROLE_ALLOWED_SCOPES[user_role]
        effective_scopes = tuple(
            s
            for s in tenant_meta["authorized_scopes"]
            if s not in PLATFORM_SCOPES
            and ("*" in role_allowed or s in role_allowed)
        ) + (
            # Platform capabilities (e.g. writing tenant-shared memory) require a role the IdP
            # actually asserted. A token without `user_role` never receives them.
            ROLE_PLATFORM_SCOPES.get(user_role, ())
            if "user_role" in verified_idp_claims
            else ()
        )

        security = SecurityContext(
            iss=actual_issuer,
            sub=str(verified_idp_claims["sub"]),
            aud="https://agent-gateway.cymbal.internal",
            exp=exp,
            jti=str(verified_idp_claims.get("jti", uuid.uuid4())),
            kid=str(verified_idp_claims.get("kid", "iap-key-1")),
            dpop_jkt=str(dpop_proof["jkt"]),
            user_role=user_role,
            idp_provider=str(
                verified_idp_claims.get("idp_provider", "google_workspace_oidc")
            ),
        )
        tenant = TenantContext(
            tenant_id=tenant_id,
            subscription_tier=tenant_meta["tier"],
            org_unit=tenant_meta["org_unit"],
            authorized_scopes=effective_scopes,
            thinking_token_budget=int(tenant_meta["thinking_budget"]),
            cmek_key_name=tenant_meta["cmek_key_name"],
        )
        request = RequestContext(
            trace_id=str(verified_idp_claims.get("trace_id", uuid.uuid4().hex)),
            correlation_id=str(
                verified_idp_claims.get("correlation_id", uuid.uuid4())
            ),
            session_id=session_id or f"sess-{uuid.uuid4().hex[:10]}",
        )
        context_token = (
            self._sign_envelope(security, tenant, request)
            if issue_context_token
            else ""
        )
        envelope = ContextEnvelope(
            security=security,
            tenant=tenant,
            request=request,
            context_token=context_token,
            delegation_sig=(
                _delegation_tag(context_token, 0) if context_token else ""
            ),
        )
        _ACTIVE_TENANT_ENVELOPE.set(envelope)
        return envelope

    def verify_obo_envelope(
        self, envelope: ContextEnvelope, presented_dpop_jkt: str
    ) -> bool:
        """Hop 4/5: Verifies the context token (public key) and the sender DPoP thumbprint."""
        from agents.context_token import (
            AGENT_ID_CLAIM,
            AUDIENCE_RUNTIME,
            ContextTokenError,
        )

        try:
            claims = _context_verifier(self._context_verifier).verify(
                envelope.context_token, audience=AUDIENCE_RUNTIME
            )
            state = envelope.to_adk_state()
            for key, claim in _STATE_CLAIM_BINDINGS:
                if _normalize_state_value(key, state[key]) != _claim(
                    claims, claim
                ):
                    raise PermissionError(key)
            if (
                AGENT_ID_CLAIM in claims
                and state.get("temp:agent_id") != claims[AGENT_ID_CLAIM]
            ):
                raise PermissionError("temp:agent_id")
        except ContextTokenError as exc:
            raise PermissionError(
                f"E_INVALID_OBO_SIGNATURE: Envelope context token rejected ({exc.code})."
            ) from exc
        except (PermissionError, TypeError, ValueError) as exc:
            raise PermissionError(
                "E_INVALID_OBO_SIGNATURE: Envelope fields do not match the signed context token."
            ) from exc
        if not hmac.compare_digest(
            envelope.security.dpop_jkt, presented_dpop_jkt
        ):
            raise PermissionError(
                "E_DPOP_BINDING_MISMATCH: Sender DPoP thumbprint does not match token."
            )
        return True

    def verify_dpop_for_tool_call(
        self,
        *,
        envelope: ContextEnvelope,
        dpop_proof: dict[str, Any],
        target_tool_name: str,
        expected_method: str = "POST",
    ) -> bool:
        """Edge Case #8: Verifies RFC 9449 DPoP `htu` (tool URI), `htm` (HTTP method), `jkt`, and
        `jti`.
        """
        self.verify_obo_envelope(envelope, str(dpop_proof.get("jkt", "")))

        jti = str(dpop_proof.get("jti", ""))
        if not jti or jti in self._seen_dpop_jtis:
            raise PermissionError(
                "E_DPOP_REPLAY_DETECTED: Tool DPoP proof jti missing or replayed."
            )
        self._seen_dpop_jtis.add(jti)

        expected_htu = f"mcp://cymbal.internal/tools/{target_tool_name}"
        actual_htu = str(dpop_proof.get("htu", ""))
        if actual_htu != expected_htu:
            raise PermissionError(
                f"E_DPOP_HTU_MISMATCH: DPoP proof bound to '{actual_htu}' cannot be replayed "
                f"against tool '{expected_htu}'."
            )

        actual_htm = str(dpop_proof.get("htm", "POST")).upper()
        if actual_htm != expected_method.upper():
            raise PermissionError(
                "E_DPOP_HTM_MISMATCH: Expected HTTP method '"
                f"{expected_method}', got '{actual_htm}'."
            )
        return True

    def bind_routed_agent(
        self, envelope: ContextEnvelope, agent_id: str
    ) -> ContextEnvelope:
        """ADR-0016: a copy of `envelope` whose context token also signs `agent_id`.

        Call only after the registry has entitled the caller to `agent_id` (the gateway signs
        only agents it actually routed to). The new token keeps every other claim and the same
        source token and expiry; the delegation tag is re-bound to it.
        """
        from agents.context_token import _AGENT_ID_RE

        if not isinstance(agent_id, str) or not _AGENT_ID_RE.fullmatch(
            agent_id
        ):
            raise PermissionError(
                "E_AGENT_ID_INVALID: cannot bind a malformed agent id."
            )
        if not envelope.context_token:
            raise PermissionError(
                "E_UNSIGNED_STATE: envelope carries no context token."
            )
        token = self._sign_envelope(
            envelope.security,
            envelope.tenant,
            envelope.request,
            agent_id=agent_id,
        )
        bound = replace(
            envelope,
            context_token=token,
            delegation_sig=_delegation_tag(token, 0),
            agent_id=agent_id,
        )
        _ACTIVE_TENANT_ENVELOPE.set(
            bound
        )  # later hops in this request see the bound token
        return bound

    def _sign_envelope(
        self,
        security: SecurityContext,
        tenant: TenantContext,
        request: RequestContext,
        *,
        agent_id: str | None = None,
    ) -> str:
        if self._context_issuer is None:
            from agents.context_signing import get_context_token_issuer

            self._context_issuer = get_context_token_issuer()
        extra = {"agent_id": agent_id} if agent_id else {}
        token, _ = self._context_issuer.issue(
            source_jti=security.jti,
            not_after=security.exp,
            sub=security.sub,
            cnf={"jkt": security.dpop_jkt},
            tenant_id=tenant.tenant_id,
            tier=str(tenant.subscription_tier),
            org_unit=tenant.org_unit,
            thinking_budget=int(tenant.thinking_token_budget),
            scopes=sorted(tenant.authorized_scopes),
            cmek_key_name=tenant.cmek_key_name,
            user_role=security.user_role,
            idp_provider=security.idp_provider,
            idp_iss=security.iss,
            session_id=request.session_id,
            max_delegation_depth=DEFAULT_MAX_DELEGATION_DEPTH,
            **extra,
        )
        return token


def get_active_envelope() -> ContextEnvelope:
    """Retrieves the immutable thread-local ContextEnvelope (prevents sub-agent principal drop)."""
    env = _ACTIVE_TENANT_ENVELOPE.get()
    if env is None:
        raise PermissionError(
            "E_BROKEN_PRINCIPAL_CHAIN: No active ContextEnvelope in contextvars."
        )
    return env


def verify_signed_adk_state(
    state: dict[str, Any],
    *,
    audience: str = "runtime",
    verifier: Any | None = None,
    check_delegation: bool = True,
) -> dict[str, Any]:
    """Re-verifies the context token carried in ADK `temp:` state; returns its verified claims.

    Used by the ADK interceptor and sub-agent hops (`audience="runtime"`) and the MCP wire handler
    (`audience="mcp"`). All of them currently run in the gateway process and also check the
    in-process delegation-depth tag (`check_delegation=True`: depth and tag must both be present).
    A separately deployed MCP server (ADR-0014 B3) would pass `check_delegation=False`: it cannot
    check the per-process tag and never decides access on depth.

    Every access-deciding field (tenant, tier, org unit, scopes, CMEK key, identity, role, IdP)
    must equal the signed claim; state without a verifiable token or with malformed field types is
    refused (`PermissionError`). A key outage raises `ContextKeyUnavailableError` (HTTP 503).
    Verification uses public keys only.
    """
    from agents.context_token import (
        AGENT_ID_CLAIM,
        ContextTokenError,
        agent_id_required,
    )

    if not state.get("temp:tenant_id"):
        raise PermissionError("E_UNSIGNED_STATE: State carries no tenant.")
    token = state.get("temp:context_token")
    if not (token and isinstance(token, str)):
        raise PermissionError(
            "E_SUBAGENT_UNSIGNED_STATE: Parent state carries no verifiable context token."
        )
    try:
        claims = _context_verifier(verifier).verify(token, audience=audience)
    except ContextTokenError as exc:
        raise PermissionError(
            f"E_SUBAGENT_STATE_TAMPERING: Context token rejected ({exc.code})."
        ) from exc
    try:
        for key, claim in _STATE_CLAIM_BINDINGS:
            if _normalize_state_value(key, state.get(key)) != _claim(
                claims, claim
            ):
                raise PermissionError(
                    f"E_SUBAGENT_STATE_TAMPERING: {key} does not match the signed context token."
                )
        if AGENT_ID_CLAIM in claims:
            signed_agent_id = claims[AGENT_ID_CLAIM]
            if "temp:agent_id" in state:
                if state.get("temp:agent_id") != signed_agent_id:
                    raise PermissionError(
                        "E_SUBAGENT_STATE_TAMPERING: temp:agent_id does not match the "
                        "signed context token."
                    )
            elif agent_id_required():
                raise PermissionError(
                    "E_SUBAGENT_STATE_TAMPERING: temp:agent_id is missing for signed "
                    "agent_id token."
                )
        if check_delegation:
            if (
                "temp:delegation_depth" not in state
                or "temp:delegation_sig" not in state
            ):
                raise PermissionError(
                    "E_SUBAGENT_STATE_TAMPERING: Delegation depth or its tag is missing."
                )
            raw_depth = state["temp:delegation_depth"]
            if isinstance(raw_depth, bool) or int(raw_depth) < 0:
                raise ValueError("bad depth")
            if not hmac.compare_digest(
                _delegation_tag(token, int(raw_depth)),
                str(state["temp:delegation_sig"]),
            ):
                raise PermissionError(
                    "E_SUBAGENT_STATE_TAMPERING: Delegation depth is not bound to the "
                    "context token."
                )
    except (TypeError, ValueError) as exc:
        raise PermissionError(
            "E_SUBAGENT_STATE_TAMPERING: Malformed numeric or collection field in state."
        ) from exc
    return claims


async def averify_signed_adk_state(
    state: dict[str, Any],
    *,
    audience: str = "runtime",
    verifier: Any | None = None,
    check_delegation: bool = True,
) -> dict[str, Any]:
    """`verify_signed_adk_state` for async callers: runs in a worker thread only when the key may
    have to be fetched from KMS, so a slow KMS never stalls the event loop."""
    resolved = _context_verifier(verifier)
    token = state.get("temp:context_token")
    kwargs = {
        "audience": audience,
        "verifier": resolved,
        "check_delegation": check_delegation,
    }
    if isinstance(token, str) and resolved.may_block(token):
        return await asyncio.to_thread(verify_signed_adk_state, state, **kwargs)
    return verify_signed_adk_state(state, **kwargs)


def propagate_to_subagent(
    parent_state: dict[str, Any],
    *,
    max_delegation_depth: int = DEFAULT_MAX_DELEGATION_DEPTH,
    verifier: Any | None = None,
) -> dict[str, Any]:
    """Propagates and cryptographically re-verifies tenant state across in-process sub-agent hops.

    The depth limit is the smaller of `max_delegation_depth` and the token's signed
    `max_delegation_depth`. Remote (cross-process) delegation is unsupported until the gateway can
    issue a fresh token with a decremented limit (ADR-0014 D1).
    """
    if not parent_state.get("temp:tenant_id"):
        raise PermissionError(
            "E_SUBAGENT_PRINCIPAL_DROP: Refusing to fall back to default runtime service account."
        )
    claims = verify_signed_adk_state(
        parent_state, verifier=verifier, check_delegation=True
    )
    token = str(parent_state["temp:context_token"])
    parent_depth = int(parent_state["temp:delegation_depth"])
    limit = min(int(max_delegation_depth), int(claims["max_delegation_depth"]))
    depth = parent_depth + 1
    if depth > limit:
        raise PermissionError(
            f"E_SUBAGENT_MAX_DEPTH_EXCEEDED: Delegation depth ({depth}) exceeds limit ({limit})."
        )

    child_state = {
        k: v for k, v in parent_state.items() if k.startswith("temp:")
    }
    child_state["temp:delegation_depth"] = depth
    child_state["temp:delegation_sig"] = _delegation_tag(token, depth)
    return child_state
