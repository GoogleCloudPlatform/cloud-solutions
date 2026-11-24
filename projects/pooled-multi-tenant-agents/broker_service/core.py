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

"""Credential broker core (ADR-0014 D2 / B4): framework-free, no ADK or agent imports.

The broker is the only identity that holds `roles/iam.serviceAccountTokenCreator` on tenant
service accounts (`ct-<sha256(tenant_id)[:24]>`). The runtime calls it with a broker-audience
context token from the gateway's exchange (B3) plus a Cloud Run IAM ID token. Per request it:

1. checks the **caller** (the Cloud Run-verified ID token) is an allowed caller: a runtime SA email
   or a Cloud Run Agent Identity principal (`principal://...`; ADR-0016);
2. verifies the **broker token** with public keys only: `typ=ctx+jwt`, ES256, issuer, `aud` is
   exactly `broker`, `exp`, lifetime <= 300 s;
3. takes the **tenant from the token** (the request body cannot name one) and refuses tenants
   that are not onboarded in the platform config (re-checked on every mint);
4. allows only listed **kinds** (`access_token`, `id_token`) and, for ID tokens, only audiences
   configured for that tenant;
5. refuses **replays**: one mint per (`jti`, kind, audience) and at most a few mints per `jti`;
6. mints only for that tenant's own service account, and writes one **audit** line per mint
   or refusal (tenant, kind, token `jti`, caller; never token values).

With `require_agent_binding` (`BROKER_REQUIRE_AGENT_BINDING=1`, ADR-0016) it also requires the
broker token's signed `agent_id`, a caller principal equal to that agent's registered principal,
and that the agent is allowed `broker:<kind>`. Off by default.

Limits: the replay store is in process, so the broker runs with `max-instances=1` until a shared
store is wired (same as the gateway's DPoP replay cache).
"""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from agents import context_token as ct
from agents.tenant_identity import tenant_service_account_email
from agents.workload_identity import (
    AgentAuthorizationError,
    AgentBinding,
    CallerIdentityError,
    PrincipalClaimConfig,
    check_agent_binding,
    is_agent_suspended,
    is_tenant_revoked,
    normalize_principal,
    principal_from_verified_claims,
    principal_org,
)

audit_logger = logging.getLogger("cymbal.audit.broker")

ALLOWED_KINDS = frozenset({"access_token", "id_token"})
MAX_ACCESS_TOKEN_LIFETIME_SECONDS = 300
MAX_3LO_TOKEN_LIFETIME_SECONDS = 3600
MAX_MINTS_PER_TOKEN = 3


@dataclass(frozen=True)
class Stored3LOCredential:
    """Per-user delegated 3LO credential stored in the out-of-process broker vault (`C6`)."""

    token_handle: str
    tenant_id: str
    user_sub: str
    provider: str
    scopes: tuple[str, ...]
    access_token: str
    expires_at: int


class BrokerRefused(PermissionError):
    """Refusal with an HTTP status and a stable code (safe to return to the caller)."""

    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


class BrokerUnavailable(RuntimeError):
    """IAM / KMS / store outage: 503, not the caller's fault."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class MintedCredential:
    kind: str
    token: str
    expires_at: float
    principal: str


class MintBackend(Protocol):
    def access_token(
        self, *, principal: str, lifetime_seconds: int
    ) -> MintedCredential: ...

    def id_token(
        self, *, principal: str, audience: str
    ) -> MintedCredential: ...


SIGNATURE_REMOVED = "SIGNATURE_REMOVED_BY_GOOGLE"


def caller_email_from_header(
    value: str | None,
    *,
    verify_signature: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Claims of the caller's Google ID token (the header Cloud Run IAM verified).

    Cloud Run IAM verifies the token before the request reaches the container and replaces its
    signature with `SIGNATURE_REMOVED_BY_GOOGLE`; with `--no-allow-unauthenticated` and
    `run.invoker` granted only to the runtime SA, other callers never get here. If the signature
    is still present (unexpected deployment), it is verified with `verify_signature` and the
    request is refused if that fails or no verifier is configured. Never trusts unsigned claims
    that Cloud Run did not mark as verified.
    """
    scheme, _, token = (value or "").partition(" ")
    if scheme.lower() != "bearer" or token.count(".") != 2:
        raise BrokerRefused(401, "E_BROKER_CALLER_MISSING")
    if token.rsplit(".", 1)[1] != SIGNATURE_REMOVED:
        if verify_signature is None:
            raise BrokerRefused(403, "E_BROKER_CALLER_UNVERIFIED")
        try:
            verified = verify_signature(token)
        except Exception as exc:
            raise BrokerRefused(403, "E_BROKER_CALLER_UNVERIFIED") from exc
        if not isinstance(verified, dict):
            raise BrokerRefused(403, "E_BROKER_CALLER_UNVERIFIED")
        return verified
    try:
        payload = token.split(".")[1]
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
    except (ValueError, TypeError) as exc:
        raise BrokerRefused(401, "E_BROKER_CALLER_MISSING") from exc
    if not isinstance(claims, dict):
        raise BrokerRefused(401, "E_BROKER_CALLER_MISSING")
    return claims


class _ReplayStore:
    """(jti, kind, audience) -> exp, plus mints per jti. Bounded; full -> fail closed (503)."""

    def __init__(
        self,
        *,
        max_entries: int = 100_000,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._seen: dict[tuple[str, str, str], float] = {}
        self._per_jti: dict[str, tuple[int, float]] = {}
        self._max = max_entries
        self._clock = clock
        self._lock = threading.Lock()

    def claim(self, jti: str, kind: str, audience: str, exp: float) -> None:
        now = self._clock()
        with self._lock:
            if len(self._seen) >= self._max:
                self._seen = {k: e for k, e in self._seen.items() if e > now}
                self._per_jti = {
                    k: v for k, v in self._per_jti.items() if v[1] > now
                }
                if len(self._seen) >= self._max:
                    raise BrokerUnavailable("E_BROKER_REPLAY_STORE_FULL")
            key = (jti, kind, audience)
            if key in self._seen:
                raise BrokerRefused(409, "E_BROKER_TOKEN_REPLAYED")
            count, _ = self._per_jti.get(jti, (0, exp))
            if count >= MAX_MINTS_PER_TOKEN:
                raise BrokerRefused(429, "E_BROKER_TOKEN_MINT_LIMIT")
            self._seen[key] = exp
            self._per_jti[jti] = (count + 1, exp)


class CredentialBroker:
    def __init__(
        self,
        *,
        project_id: str,
        allowed_callers: frozenset[str],
        backend: MintBackend,
        tenants: Callable[[], Mapping[str, tuple[str, ...]]],
        verifier: Callable[
            [], ct.ContextTokenVerifier
        ] = ct.get_context_verifier,
        expected_caller_audience: str | None = None,
        caller_signature_verifier: (
            Callable[[str], dict[str, Any]] | None
        ) = None,
        max_access_token_lifetime_seconds: int = MAX_ACCESS_TOKEN_LIFETIME_SECONDS,
        clock: Callable[[], float] = time.time,
        require_agent_binding: bool = False,
        agent_bindings: Callable[[], Mapping[str, AgentBinding]] | None = None,
        principal_claims: PrincipalClaimConfig | None = None,
        agent_org_id: str | None = None,
    ) -> None:
        """`tenants()` returns onboarded tenant_id -> allowed ID-token audiences (re-read per mint).

        `allowed_callers` holds SA emails and/or Agent Identity principals. With
        `require_agent_binding`, `agent_bindings()` (agent_id -> binding) is required.
        """
        if not allowed_callers:
            raise ValueError(
                "E_BROKER_CONFIG: at least one allowed caller is required"
            )
        normalized = {normalize_principal(c) for c in allowed_callers}
        if None in normalized:
            raise ValueError(
                "E_BROKER_CONFIG: allowed callers must be SA emails or Agent Identity principals"
            )
        if any(
            p is not None
            and p.kind == "agent"
            and principal_org(p.value) != agent_org_id
            for p in normalized
        ):
            raise ValueError(
                "E_BROKER_CONFIG: agent-identity callers need agent_identity.org_id of their org"
            )
        if require_agent_binding and agent_bindings is None:
            raise ValueError(
                "E_BROKER_CONFIG: agent binding is on but no agent bindings are set"
            )
        if not project_id:
            raise ValueError("E_BROKER_CONFIG: project_id is required")
        if (
            not 60
            <= max_access_token_lifetime_seconds
            <= MAX_ACCESS_TOKEN_LIFETIME_SECONDS
        ):
            raise ValueError(
                "E_BROKER_CONFIG: max_access_token_lifetime_seconds must be between "
                f"60 and {MAX_ACCESS_TOKEN_LIFETIME_SECONDS}"
            )
        self._project_id = project_id
        self._allowed_callers = frozenset(
            p.value for p in normalized if p is not None
        )
        self._require_agent_binding = require_agent_binding
        self._agent_bindings = agent_bindings
        self._principal_claims = principal_claims or PrincipalClaimConfig()
        self._agent_org_id = agent_org_id
        self._backend = backend
        self._tenants = tenants
        self._verifier = verifier
        self._expected_aud = expected_caller_audience
        self._verify_caller_signature = caller_signature_verifier
        self._max_access_token_lifetime = max_access_token_lifetime_seconds
        self._clock = clock
        self._replay = _ReplayStore(clock=clock)
        self._vault_3lo: dict[str, Stored3LOCredential] = {}
        self._vault_3lo_lock = threading.Lock()

    def _audit(self, event: str, **fields: Any) -> None:
        audit_logger.info(
            json.dumps({"event": event, **fields}, sort_keys=True, default=str)
        )

    def _verify_caller_and_broker_token(
        self,
        *,
        caller_header: str | None,
        context_token: str | None,
        purpose: str,
        known: dict[str, Any],
    ) -> dict[str, Any]:
        """Verifies caller workload identity, `aud=broker` `ctx+jwt`, suspension, and onboarding."""
        caller = caller_email_from_header(
            caller_header, verify_signature=self._verify_caller_signature
        )
        try:
            principal = principal_from_verified_claims(
                caller,
                audience=self._expected_aud,
                agent_org_id=self._agent_org_id,
                claim_config=self._principal_claims,
            )
        except CallerIdentityError as exc:
            known["caller"] = str(caller.get("email", ""))[:254] or None
            raise BrokerRefused(403, "E_BROKER_CALLER_NOT_ALLOWED") from exc
        known["caller"] = principal.value
        if principal.value not in self._allowed_callers:
            raise BrokerRefused(403, "E_BROKER_CALLER_NOT_ALLOWED")
        if not context_token:
            raise BrokerRefused(401, "E_BROKER_TOKEN_MISSING")
        try:
            claims = self._verifier().verify(
                context_token, audience=ct.AUDIENCE_BROKER
            )
        except ct.ContextTokenError as exc:
            raise BrokerRefused(403, exc.code) from exc
        except ct.ContextKeyUnavailableError as exc:
            raise BrokerUnavailable(exc.code) from exc
        tenant_id = str(claims["tenant_id"])
        known.update(
            tenant_id=tenant_id,
            token_jti=claims["jti"],
            src_jti=claims.get("src_jti"),
        )
        bound_agent = claims.get(ct.AGENT_ID_CLAIM)
        if bound_agent is not None:
            known["agent_id"] = bound_agent
            if is_agent_suspended(bound_agent):
                raise BrokerRefused(403, "E_AGENT_SUSPENDED")
        if self._require_agent_binding:
            bindings = self._agent_bindings() if self._agent_bindings else {}
            try:
                check_agent_binding(
                    agent_id=bound_agent,
                    caller=principal,
                    purpose=purpose,
                    bindings=bindings,
                )
            except AgentAuthorizationError as exc:
                raise BrokerRefused(403, exc.code) from exc
        if is_tenant_revoked(tenant_id):
            raise BrokerRefused(403, "E_BROKER_TENANT_REVOKED")
        onboarded = self._tenants()
        if tenant_id not in onboarded:
            raise BrokerRefused(403, "E_BROKER_TENANT_NOT_ONBOARDED")
        return dict(claims)

    def mint(
        self,
        *,
        caller_header: str | None,
        context_token: str | None,
        kind: str,
        audience: str | None = None,
        lifetime_seconds: int | None = None,
    ) -> tuple[MintedCredential, str]:
        """(credential, tenant_id). Raises `BrokerRefused` / `BrokerUnavailable`."""
        requested_lifetime = (
            self._max_access_token_lifetime
            if lifetime_seconds is None
            else int(lifetime_seconds)
        )
        known: dict[str, Any] = {"kind": str(kind)[:32]}
        try:
            cred, tenant_id = self._mint(
                caller_header,
                context_token,
                kind,
                audience,
                requested_lifetime,
                known,
            )
        except (BrokerRefused, BrokerUnavailable) as exc:
            self._audit("tenant_credential_refused", code=exc.code, **known)
            raise
        self._audit(
            "tenant_credential_mint",
            principal=cred.principal,
            expires_at=int(cred.expires_at),
            **known,
        )
        return cred, tenant_id

    def _mint(
        self,
        caller_header: str | None,
        context_token: str | None,
        kind: str,
        audience: str | None,
        lifetime_seconds: int,
        known: dict[str, Any],
    ) -> tuple[MintedCredential, str]:
        if kind not in ALLOWED_KINDS:
            # Verify caller & token first so unauthenticated probes still get 401/403 caller errors,
            # while keeping purpose syntactically valid before rejecting unknown `kind`.
            claims = self._verify_caller_and_broker_token(
                caller_header=caller_header,
                context_token=context_token,
                purpose="broker:access_token",
                known=known,
            )
            raise BrokerRefused(403, "E_BROKER_KIND_NOT_ALLOWED")
        claims = self._verify_caller_and_broker_token(
            caller_header=caller_header,
            context_token=context_token,
            purpose=f"broker:{kind}",
            known=known,
        )
        tenant_id = str(claims["tenant_id"])
        onboarded = self._tenants()
        if kind == "id_token":
            if not audience or audience not in onboarded[tenant_id]:
                raise BrokerRefused(403, "E_BROKER_AUDIENCE_NOT_ALLOWED")
        elif audience:
            raise BrokerRefused(400, "E_BROKER_AUDIENCE_NOT_ALLOWED")
        known["audience"] = audience
        self._replay.claim(
            str(claims["jti"]), kind, audience or "", float(claims["exp"])
        )
        principal = tenant_service_account_email(tenant_id, self._project_id)
        try:
            if kind == "access_token":
                effective_ceiling = min(
                    self._max_access_token_lifetime,
                    MAX_ACCESS_TOKEN_LIFETIME_SECONDS,
                )
                lifetime = max(
                    60, min(int(lifetime_seconds), effective_ceiling)
                )
                cred = self._backend.access_token(
                    principal=principal, lifetime_seconds=lifetime
                )
            else:
                cred = self._backend.id_token(
                    principal=principal, audience=str(audience)
                )
        except BrokerRefused:
            raise
        except (
            Exception
        ) as exc:  # IAM outage or misconfiguration: never the caller's fault
            raise BrokerUnavailable(
                f"E_BROKER_MINT_FAILED_{type(exc).__name__}"
            ) from exc
        if cred.principal != principal or cred.kind != kind:
            raise BrokerUnavailable("E_BROKER_BACKEND_MISMATCH")
        return cred, tenant_id

    def store_3lo_credential(
        self,
        *,
        caller_header: str | None,
        context_token: str | None,
        token_handle: str,
        provider: str,
        scopes: tuple[str, ...],
        access_token: str,
        expires_at: int,
    ) -> Stored3LOCredential:
        """Stores a per-user 3LO token bound strictly to `(claims.tenant_id, claims.sub)`."""
        known: dict[str, Any] = {
            "op": "store_3lo",
            "token_handle": token_handle[:64],
            "provider": provider[:64],
        }
        try:
            claims = self._verify_caller_and_broker_token(
                caller_header=caller_header,
                context_token=context_token,
                purpose="broker:oauth_3lo",
                known=known,
            )
            tenant_id = str(claims["tenant_id"])
            user_sub = str(claims.get("sub") or "").strip()
            if not user_sub:
                raise BrokerRefused(403, "E_BROKER_SUB_MISSING")
            clean_handle = token_handle.strip()
            clean_provider = provider.strip()
            clean_secret = access_token.strip()
            normalized_scopes = tuple(
                sorted({s.strip() for s in scopes if s and s.strip()})
            )
            if (
                not clean_handle
                or not clean_provider
                or not clean_secret
                or not normalized_scopes
            ):
                raise BrokerRefused(400, "E_3LO_INVALID_PAYLOAD")
            now_int = int(self._clock())
            if int(expires_at) <= now_int:
                raise BrokerRefused(400, "E_3LO_TOKEN_EXPIRED")
            capped_exp = min(
                int(expires_at), now_int + MAX_3LO_TOKEN_LIFETIME_SECONDS
            )
            self._replay.claim(
                str(claims["jti"]),
                "store_3lo",
                clean_handle,
                float(claims["exp"]),
            )
            stored = Stored3LOCredential(
                token_handle=clean_handle,
                tenant_id=tenant_id,
                user_sub=user_sub,
                provider=clean_provider,
                scopes=normalized_scopes,
                access_token=clean_secret,
                expires_at=capped_exp,
            )
            with self._vault_3lo_lock:
                existing = self._vault_3lo.get(clean_handle)
                if existing is not None and (
                    existing.tenant_id != tenant_id
                    or existing.user_sub != user_sub
                ):
                    raise BrokerRefused(403, "E_3LO_CONFUSED_DEPUTY_BLOCKED")
                self._vault_3lo[clean_handle] = stored
        except (BrokerRefused, BrokerUnavailable) as exc:
            self._audit("3lo_credential_refused", code=exc.code, **known)
            raise
        self._audit(
            "3lo_credential_stored",
            expires_at=stored.expires_at,
            scopes_count=len(stored.scopes),
            **known,
        )
        return stored

    def checkout_3lo_credential(
        self,
        *,
        caller_header: str | None,
        context_token: str | None,
        token_handle: str,
        required_scope: str,
    ) -> Stored3LOCredential:
        """Checks out a 3LO token only when `(tenant_id, sub)` in `ctx+jwt` matches the owner."""
        known: dict[str, Any] = {
            "op": "checkout_3lo",
            "token_handle": token_handle[:64],
            "required_scope": required_scope[:128],
        }
        try:
            claims = self._verify_caller_and_broker_token(
                caller_header=caller_header,
                context_token=context_token,
                purpose="broker:oauth_3lo",
                known=known,
            )
            tenant_id = str(claims["tenant_id"])
            user_sub = str(claims.get("sub") or "").strip()
            if not user_sub:
                raise BrokerRefused(403, "E_BROKER_SUB_MISSING")
            clean_handle = token_handle.strip()
            self._replay.claim(
                str(claims["jti"]),
                "checkout_3lo",
                clean_handle,
                float(claims["exp"]),
            )
            with self._vault_3lo_lock:
                stored = self._vault_3lo.get(clean_handle)
            if stored is None:
                raise BrokerRefused(404, "E_3LO_TOKEN_NOT_FOUND")
            if stored.tenant_id != tenant_id or stored.user_sub != user_sub:
                raise BrokerRefused(403, "E_3LO_CONFUSED_DEPUTY_BLOCKED")
            if stored.expires_at <= int(self._clock()):
                raise BrokerRefused(403, "E_3LO_TOKEN_EXPIRED")
            if required_scope not in stored.scopes:
                raise BrokerRefused(403, "E_3LO_INSUFFICIENT_SCOPE")
        except (BrokerRefused, BrokerUnavailable) as exc:
            self._audit("3lo_credential_refused", code=exc.code, **known)
            raise
        self._audit(
            "3lo_credential_checkout", provider=stored.provider, **known
        )
        return stored

    def evict_tenant_3lo_credentials(
        self,
        *,
        caller_header: str | None,
        context_token: str | None,
    ) -> tuple[str, int]:
        """Evicts all stored 3LO tokens belonging to the `ctx+jwt` tenant."""
        known: dict[str, Any] = {"op": "evict_3lo"}
        try:
            claims = self._verify_caller_and_broker_token(
                caller_header=caller_header,
                context_token=context_token,
                purpose="broker:oauth_3lo",
                known=known,
            )
            tenant_id = str(claims["tenant_id"])
            self._replay.claim(
                str(claims["jti"]), "evict_3lo", tenant_id, float(claims["exp"])
            )
            evicted = self.evict_tenant_3lo_local(tenant_id)
        except (BrokerRefused, BrokerUnavailable) as exc:
            self._audit("3lo_credential_refused", code=exc.code, **known)
            raise
        self._audit("3lo_credential_evicted", evicted_count=evicted, **known)
        return tenant_id, evicted

    def evict_tenant_3lo_local(self, tenant_id: str) -> int:
        """Purges all stored 3LO credentials for `tenant_id` (used on tenant offboarding)."""
        with self._vault_3lo_lock:
            handles = [
                h
                for h, tok in self._vault_3lo.items()
                if tok.tenant_id == tenant_id
            ]
            for handle in handles:
                self._vault_3lo.pop(handle, None)
            return len(handles)


def google_id_token_signature_verifier(
    audience: str,
) -> Callable[[str], dict[str, Any]]:
    """Verifies a Google-signed ID token (signature, issuer, expiry, `aud == audience`)."""

    def verify(token: str) -> dict[str, Any]:
        import google.auth.transport.requests
        import google.oauth2.id_token

        return dict(
            google.oauth2.id_token.verify_token(
                token,
                google.auth.transport.requests.Request(),
                audience=audience,
            )
        )

    return verify
