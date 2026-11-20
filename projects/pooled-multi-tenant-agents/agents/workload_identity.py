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

"""Workload (caller) identity and agent binding: the agent layer of ADR-0016.

Two questions, answered without trusting anything the caller says about itself:

1. **Who is calling?** The caller's ID token is verified (signature, issuer, audience, expiry) and
   reduced to a normalized `CallerPrincipal`:

   - **Service account** (today's runtime): Google-issued token (`iss` = accounts.google.com),
     principal = the verified `email`.
   - **Cloud Run Agent Identity** (confirmed in the A0 spike, 2026-11-06): token issued by the
     organization's agent STS pool, `iss` =
     ``https://sts.googleapis.com/v1/organizations/<ORG_ID>/locations/global/workloadIdentityPools/agents.global.org-<ORG_ID>.system.id.goog``,
     `sub` = ``spiffe://agents.global.org-<ORG_ID>.system.id.goog/resources/run/projects/<N>/locations/<R>/services/<S>``,
     `aud` = a list, no `email`. The issuer is pinned to the configured org; the SPIFFE ID is
     normalized to the IAM member form used in bindings and allow-lists::

         principal://agents.global.org-<ORG_ID>.system.id.goog/resources/run/projects/<N>/locations/<R>/services/<S>

   Request headers are never a source of identity.

2. **Is it the agent the gateway routed to, and may it do this?** `check_agent_binding` compares the
   caller principal with the principal registered for the context token's signed `agent_id`, and
   checks that the agent is allowed the purpose (`broker:access_token`, `mcp:<tool>`, ...).

Framework-free apart from PyJWT (used only by `agent_identity_token_verifier`), so the credential
broker can import it.
"""

from __future__ import annotations

import os
import re
import threading
import time
import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

GOOGLE_ISSUERS = frozenset(
    {"https://accounts.google.com", "accounts.google.com"}
)

_TRUST_DOMAIN = r"agents\.global\.org-(?P<org>[0-9]{1,20})\.system\.id\.goog"
_RUN_PATH = (
    r"/resources/run/projects/[0-9]{1,20}/locations/[a-z][a-z0-9-]{1,30}"
    r"/services/[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
)
AGENT_PRINCIPAL_RE = re.compile(r"principal://" + _TRUST_DOMAIN + _RUN_PATH)
AGENT_SPIFFE_RE = re.compile(r"spiffe://" + _TRUST_DOMAIN + _RUN_PATH)
SERVICE_ACCOUNT_RE = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?@[a-z0-9][a-z0-9.-]{0,98}\.gserviceaccount\.com"
)
AGENT_ID_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
PURPOSE_RE = re.compile(r"(?:broker|mcp):[a-z][a-z0-9_]{0,63}")
ORG_ID_RE = re.compile(r"[0-9]{1,20}")

AGENT_PRINCIPAL_CLAIM_ENV = "WORKLOAD_IDENTITY_AGENT_PRINCIPAL_CLAIM"
SA_PRINCIPAL_CLAIM_ENV = "WORKLOAD_IDENTITY_SA_PRINCIPAL_CLAIM"


class CallerIdentityError(PermissionError):
    """The caller's identity could not be established (refuse; safe code only)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AgentAuthorizationError(PermissionError):
    """The caller is not the routed agent, or the agent is not allowed this purpose."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CallerPrincipal:
    kind: Literal["service_account", "agent"]
    value: str


@dataclass(frozen=True)
class PrincipalClaimConfig:
    """Which verified ID-token claim carries each principal kind (A0: `sub` and `email`)."""

    agent_claim: str = "sub"
    service_account_claim: str = "email"

    @classmethod
    def from_env(cls) -> PrincipalClaimConfig:
        return cls(
            agent_claim=(os.getenv(AGENT_PRINCIPAL_CLAIM_ENV) or "sub").strip(),
            service_account_claim=(
                os.getenv(SA_PRINCIPAL_CLAIM_ENV) or "email"
            ).strip(),
        )


@dataclass(frozen=True)
class AgentBinding:
    """The expected workload principal of one agent, and what that agent may do."""

    agent_id: str
    workload_principal: str
    allowed_purposes: frozenset[str]


def flag_enabled(name: str) -> bool:
    """Feature flags are on only when explicitly `1` (default off)."""
    return os.getenv(name, "").strip() == "1"


def agent_identity_issuer(org_id: str) -> str:
    """The OIDC issuer of Cloud Run Agent Identity tokens for an organization (A0)."""
    if not isinstance(org_id, str) or not ORG_ID_RE.fullmatch(org_id):
        raise ValueError("org_id must be digits")
    return (
        f"https://sts.googleapis.com/v1/organizations/{org_id}/locations/global/"
        f"workloadIdentityPools/agents.global.org-{org_id}.system.id.goog"
    )


def normalize_principal(value: str) -> CallerPrincipal | None:
    """A configured principal (allowed caller or binding), or None if malformed.

    `spiffe://<trust-domain>/...` and `principal://<trust-domain>/...` name the same agent; both
    normalize to the `principal://` (IAM member) form.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if AGENT_PRINCIPAL_RE.fullmatch(candidate):
        return CallerPrincipal("agent", candidate)
    if AGENT_SPIFFE_RE.fullmatch(candidate):
        return CallerPrincipal(
            "agent", "principal://" + candidate[len("spiffe://") :]
        )
    lowered = candidate.lower()
    if SERVICE_ACCOUNT_RE.fullmatch(lowered):
        return CallerPrincipal("service_account", lowered)
    return None


def principal_org(principal: str) -> str | None:
    """The org id of an Agent Identity principal, else None."""
    match = AGENT_PRINCIPAL_RE.fullmatch(principal or "")
    return match.group("org") if match else None


def _audience_ok(aud: Any, audience: str) -> bool:
    return aud == audience or (isinstance(aud, list) and audience in aud)


def principal_from_verified_claims(
    claims: Mapping[str, Any],
    *,
    audience: str | None = None,
    agent_org_id: str | None = None,
    claim_config: PrincipalClaimConfig | None = None,
) -> CallerPrincipal:
    """Principal from claims whose signature was already verified (Cloud Run IAM or a verifier).

    - Agent Identity: only if `agent_org_id` is configured and `iss` is exactly that org's agent
      pool issuer; the configured claim (default `sub`) must be a SPIFFE ID in the same org.
    - Service account: `iss` is Google, the configured claim (default `email`) is a verified SA.
    When `audience` is given, `aud` must equal it (or, as a list, contain it).
    """
    cfg = claim_config or PrincipalClaimConfig()
    if not isinstance(claims, Mapping):
        raise CallerIdentityError("E_CALLER_ISSUER")
    iss = claims.get("iss")
    agent_issuer = agent_identity_issuer(agent_org_id) if agent_org_id else None
    if iss not in GOOGLE_ISSUERS and (
        agent_issuer is None or iss != agent_issuer
    ):
        raise CallerIdentityError("E_CALLER_ISSUER")
    if audience and not _audience_ok(claims.get("aud"), audience):
        raise CallerIdentityError("E_CALLER_AUDIENCE")
    if agent_issuer is not None and iss == agent_issuer:
        value = claims.get(cfg.agent_claim)
        principal = (
            normalize_principal(value)
            if isinstance(value, str) and AGENT_SPIFFE_RE.fullmatch(value)
            else None
        )
        if principal is None or principal_org(principal.value) != agent_org_id:
            raise CallerIdentityError("E_CALLER_PRINCIPAL_UNRECOGNIZED")
        return principal
    sa_value = claims.get(cfg.service_account_claim)
    if (
        isinstance(sa_value, str)
        and claims.get("email_verified") in (True, "true")
        and SERVICE_ACCOUNT_RE.fullmatch(sa_value.lower())
    ):
        return CallerPrincipal("service_account", sa_value.lower())
    raise CallerIdentityError("E_CALLER_PRINCIPAL_UNRECOGNIZED")


def verify_caller_identity(
    id_token: str,
    audience: str,
    *,
    verify_signature: Callable[[str, str], Mapping[str, Any]],
    agent_org_id: str | None = None,
    claim_config: PrincipalClaimConfig | None = None,
) -> CallerPrincipal:
    """Verifies a caller ID token and returns its normalized principal.

    `verify_signature(token, audience)` must check signature, issuer, expiry and audience (for
    example `routing_signature_verifier`); any exception from it is a refusal.
    """
    if not audience:
        raise ValueError("audience is required")
    if not isinstance(id_token, str) or id_token.count(".") != 2:
        raise CallerIdentityError("E_CALLER_TOKEN_MALFORMED")
    try:
        claims = verify_signature(id_token, audience)
    except Exception as exc:
        raise CallerIdentityError("E_CALLER_TOKEN_UNVERIFIED") from exc
    return principal_from_verified_claims(
        claims,
        audience=audience,
        agent_org_id=agent_org_id,
        claim_config=claim_config,
    )


def agent_identity_token_verifier(
    org_id: str,
    *,
    jwk_client: Any | None = None,
) -> Callable[[str, str], dict[str, Any]]:
    """Verifies an Agent Identity ID token: RS256 against `<issuer>/openid/jwks`, issuer pinned to
    the org's agent pool, `aud` contains the audience, `exp` required. `jwk_client` (anything with
    `get_signing_key_from_jwt`) is injectable for tests."""
    import jwt

    issuer = agent_identity_issuer(org_id)
    # Bounded JWKS fetch: a slow key endpoint is a refusal (503 upstream), never a hang.
    client = jwk_client or jwt.PyJWKClient(
        f"{issuer}/openid/jwks", cache_keys=True, timeout=5
    )

    def verify(token: str, audience: str) -> dict[str, Any]:
        key = client.get_signing_key_from_jwt(token).key
        return dict(
            jwt.decode(
                token,
                key,
                algorithms=["RS256"],  # pinned: never HS256 / none
                audience=audience,
                issuer=issuer,
                leeway=30,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
            )
        )

    return verify


def routing_signature_verifier(
    *,
    google_verifier: Callable[[str, str], dict[str, Any]],
    agent_verifier: Callable[[str, str], dict[str, Any]] | None,
    agent_org_id: str | None,
) -> Callable[[str, str], dict[str, Any]]:
    """Picks the verifier by the token's (unverified) `iss`; each verifier pins its own issuer, so
    a forged `iss` only selects a verifier that then rejects the signature."""
    import jwt

    agent_issuer = agent_identity_issuer(agent_org_id) if agent_org_id else None

    def verify(token: str, audience: str) -> dict[str, Any]:
        iss = jwt.decode(token, options={"verify_signature": False}).get("iss")
        if (
            agent_verifier is not None
            and agent_issuer is not None
            and iss == agent_issuer
        ):
            return agent_verifier(token, audience)
        return google_verifier(token, audience)

    return verify


@dataclass(frozen=True)
class SuspendedAgentRecord:
    """Immutable audit record for an emergency control-plane agent suspension (`C17`)."""

    agent_id: str
    reason: str
    suspended_at: float


_REVOCATION_LOCK = threading.Lock()
_SUSPENDED_AGENTS: dict[str, SuspendedAgentRecord] = {}
_REVOKED_TENANTS: set[str] = set()
_AGENT_EVICTION_TARGETS: weakref.WeakSet[Any] = weakref.WeakSet()
_EXTERNAL_REVOCATION_STORE: Any | None = None


class FirestoreRevocationStore:
    """Multi-replica control-plane revocation store backed by Google Cloud Firestore."""

    def __init__(
        self,
        *,
        project_id: str | None = None,
        database: str | None = None,
        collection_name: str = "cymbal_control_plane_revocations_v1",
        firestore_client: Any | None = None,
    ) -> None:
        if firestore_client is not None:
            self._client = firestore_client
        else:
            from agents import platform_config
            from agents.kms_rest import build_firestore_client

            resolved_project = (
                project_id or platform_config.resolve_project_id()
            )
            resolved_db = database or os.getenv(
                "FIRESTORE_DATABASE", "cymbal-memory-bank-prod"
            )
            self._client = build_firestore_client(
                project_id=resolved_project, database=resolved_db
            )
        self._collection = collection_name

    def _agent_doc_id(self, agent_id: str) -> str:
        return f"agent:{agent_id}"

    def _tenant_doc_id(self, tenant_id: str) -> str:
        return f"tenant:{tenant_id}"

    def suspend_agent(self, agent_id: str, *, reason: str) -> None:
        self._client.collection(self._collection).document(
            self._agent_doc_id(agent_id)
        ).set(
            {
                "kind": "agent_suspension",
                "agent_id": agent_id,
                "suspended": True,
                "reason": reason,
                "updated_at": time.time(),
            }
        )

    def resume_agent(self, agent_id: str) -> bool:
        doc_ref = self._client.collection(self._collection).document(
            self._agent_doc_id(agent_id)
        )
        snap = doc_ref.get()
        existed = bool(getattr(snap, "exists", False))
        if existed:
            doc_ref.delete()
        return existed

    def is_agent_suspended(self, agent_id: str) -> bool:
        snap = (
            self._client.collection(self._collection)
            .document(self._agent_doc_id(agent_id))
            .get()
        )
        if not getattr(snap, "exists", False):
            return False
        data = snap.to_dict() or {}
        return bool(data.get("suspended", False))

    def mark_tenant_revoked(self, tenant_id: str) -> None:
        self._client.collection(self._collection).document(
            self._tenant_doc_id(tenant_id)
        ).set(
            {
                "kind": "tenant_revocation",
                "tenant_id": tenant_id,
                "revoked": True,
                "updated_at": time.time(),
            }
        )

    def clear_tenant_revoked(self, tenant_id: str) -> bool:
        doc_ref = self._client.collection(self._collection).document(
            self._tenant_doc_id(tenant_id)
        )
        snap = doc_ref.get()
        existed = bool(getattr(snap, "exists", False))
        if existed:
            doc_ref.delete()
        return existed

    def is_tenant_revoked(self, tenant_id: str) -> bool:
        snap = (
            self._client.collection(self._collection)
            .document(self._tenant_doc_id(tenant_id))
            .get()
        )
        if not getattr(snap, "exists", False):
            return False
        data = snap.to_dict() or {}
        return bool(data.get("revoked", False))


def _resolve_external_revocation_store() -> Any | None:
    global _EXTERNAL_REVOCATION_STORE
    with _REVOCATION_LOCK:
        if _EXTERNAL_REVOCATION_STORE is not None:
            return _EXTERNAL_REVOCATION_STORE
        if not flag_enabled("FIRESTORE_REVOCATION_STORE"):
            return None
        _EXTERNAL_REVOCATION_STORE = FirestoreRevocationStore()
        return _EXTERNAL_REVOCATION_STORE


def install_revocation_store(store: Any | None) -> None:
    """Installs an optional shared control-plane revocation store (Redis / Firestore)."""
    global _EXTERNAL_REVOCATION_STORE
    with _REVOCATION_LOCK:
        _EXTERNAL_REVOCATION_STORE = store


def register_agent_eviction_target(target: Any) -> None:
    """Registers a runtime cache or sandbox manager for synchronous eviction on `suspend_agent`."""
    with _REVOCATION_LOCK:
        _AGENT_EVICTION_TARGETS.add(target)


def suspend_agent(
    agent_id: str,
    *,
    reason: str = "operator_emergency_suspension",
) -> SuspendedAgentRecord:
    """Suspends `agent_id` immediately across gateway, runtime, sandboxes, and credential broker."""
    if not isinstance(agent_id, str) or not AGENT_ID_RE.fullmatch(agent_id):
        raise ValueError(f"Invalid agent_id for suspension: {agent_id!r}")
    clean_reason = (reason or "operator_emergency_suspension").strip()[:256]
    record = SuspendedAgentRecord(
        agent_id=agent_id,
        reason=clean_reason,
        suspended_at=time.time(),
    )
    with _REVOCATION_LOCK:
        _SUSPENDED_AGENTS[agent_id] = record
        targets = list(_AGENT_EVICTION_TARGETS)
    ext = _resolve_external_revocation_store()
    if ext is not None and hasattr(ext, "suspend_agent"):
        ext.suspend_agent(agent_id, reason=clean_reason)
    for target in targets:
        evict_fn = getattr(target, "evict_agent", None)
        if callable(evict_fn):
            evict_fn(agent_id)
    return record


def resume_agent(agent_id: str) -> bool:
    """Lifts an active suspension on `agent_id`."""
    if not isinstance(agent_id, str) or not AGENT_ID_RE.fullmatch(agent_id):
        raise ValueError(f"Invalid agent_id for resume: {agent_id!r}")
    with _REVOCATION_LOCK:
        removed = _SUSPENDED_AGENTS.pop(agent_id, None) is not None
    ext = _resolve_external_revocation_store()
    if ext is not None and hasattr(ext, "resume_agent"):
        removed = bool(ext.resume_agent(agent_id)) or removed
    return removed


def is_agent_suspended(agent_id: Any) -> bool:
    """Returns True if `agent_id` is currently suspended in the control-plane registry."""
    if not isinstance(agent_id, str) or not agent_id:
        return False
    with _REVOCATION_LOCK:
        if agent_id in _SUSPENDED_AGENTS:
            return True
    ext = _resolve_external_revocation_store()
    if ext is not None and hasattr(ext, "is_agent_suspended"):
        return bool(ext.is_agent_suspended(agent_id))
    return False


def list_suspended_agents() -> dict[str, SuspendedAgentRecord]:
    """Returns a snapshot of currently suspended agents in this process."""
    with _REVOCATION_LOCK:
        return dict(_SUSPENDED_AGENTS)


def mark_tenant_revoked(tenant_id: str) -> None:
    """Marks `tenant_id` dynamically revoked across gateway, runtime, and credential broker."""
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        return
    clean = tenant_id.strip()
    with _REVOCATION_LOCK:
        _REVOKED_TENANTS.add(clean)
    ext = _resolve_external_revocation_store()
    if ext is not None and hasattr(ext, "mark_tenant_revoked"):
        ext.mark_tenant_revoked(clean)


def clear_tenant_revoked(tenant_id: str) -> bool:
    """Clears a dynamic tenant revocation flag when re-onboarding a tenant."""
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        return False
    clean = tenant_id.strip()
    with _REVOCATION_LOCK:
        removed = clean in _REVOKED_TENANTS
        _REVOKED_TENANTS.discard(clean)
    ext = _resolve_external_revocation_store()
    if ext is not None and hasattr(ext, "clear_tenant_revoked"):
        removed = bool(ext.clear_tenant_revoked(clean)) or removed
    return removed


def is_tenant_revoked(tenant_id: Any) -> bool:
    """Returns True if `tenant_id` has been dynamically offboarded/revoked."""
    if not isinstance(tenant_id, str) or not tenant_id:
        return False
    with _REVOCATION_LOCK:
        if tenant_id in _REVOKED_TENANTS:
            return True
    ext = _resolve_external_revocation_store()
    if ext is not None and hasattr(ext, "is_tenant_revoked"):
        return bool(ext.is_tenant_revoked(tenant_id))
    return False


def reset_control_plane_revocations() -> None:
    """Clears in-process dynamic agent suspensions and tenant revocations (test hygiene)."""
    with _REVOCATION_LOCK:
        _SUSPENDED_AGENTS.clear()
        _REVOKED_TENANTS.clear()
        ext = _EXTERNAL_REVOCATION_STORE
    if ext is not None and hasattr(ext, "reset"):
        ext.reset()


def check_agent_binding(
    *,
    agent_id: Any,
    caller: CallerPrincipal | None,
    purpose: str,
    bindings: Mapping[str, AgentBinding],
) -> AgentBinding:
    """Allowed only if the caller IS the routed agent and that agent may do `purpose`.

    Fails closed: no `agent_id`, a suspended agent (`E_AGENT_SUSPENDED`), an agent with no
    registered principal, no verified caller, a principal mismatch or a missing purpose are all
    refusals.
    """
    if not isinstance(agent_id, str) or not AGENT_ID_RE.fullmatch(agent_id):
        raise AgentAuthorizationError("E_AGENT_ID_MISSING")
    if is_agent_suspended(agent_id):
        raise AgentAuthorizationError("E_AGENT_SUSPENDED")
    binding = bindings.get(agent_id)
    if binding is None or not binding.workload_principal:
        raise AgentAuthorizationError("E_AGENT_NOT_BOUND")
    if caller is None:
        raise AgentAuthorizationError("E_AGENT_CALLER_MISSING")
    if caller.value != binding.workload_principal:
        raise AgentAuthorizationError("E_AGENT_PRINCIPAL_MISMATCH")
    if purpose not in binding.allowed_purposes:
        raise AgentAuthorizationError("E_AGENT_PURPOSE_NOT_ALLOWED")
    return binding


def agent_org_id_from_config(cfg: Any) -> str | None:
    section = getattr(cfg, "agent_identity", None)
    return getattr(section, "org_id", None)


def _resolve_principal_template(
    raw_value: str, *, cfg: Any, org_id: str | None
) -> str:
    if "{" not in raw_value and "}" not in raw_value:
        return raw_value
    from agents.platform_config import resolve_project_number

    resolved = raw_value
    if "{org_id}" in resolved:
        if not org_id:
            raise ValueError(
                "agent_identity.org_id is required to resolve {org_id}"
            )
        resolved = resolved.replace("{org_id}", org_id)
    if "{project_number}" in resolved:
        project_number = resolve_project_number(
            cfg if hasattr(cfg, "gcp") else None
        )
        if not project_number:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT_NUMBER, gcp.project_number, or metadata server is required "
                "to resolve {project_number}"
            )
        resolved = resolved.replace("{project_number}", project_number)
    if "{region}" in resolved:
        gcp = getattr(cfg, "gcp", None)
        region = (
            getattr(gcp, "region", None)
            or os.getenv("GOOGLE_CLOUD_REGION")
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or ""
        ).strip()
        if not region:
            raise ValueError(
                "gcp.region or GOOGLE_CLOUD_REGION is required to resolve {region}"
            )
        resolved = resolved.replace("{region}", region)
    return resolved


def bindings_from_config(cfg: Any) -> dict[str, AgentBinding]:
    """`agent_identity.bindings` of a `PlatformConfig` as normalized `AgentBinding`s."""
    section = getattr(cfg, "agent_identity", None)
    raw = getattr(section, "bindings", None) or {}
    org_id = getattr(section, "org_id", None)
    out: dict[str, AgentBinding] = {}
    for agent_id, spec in raw.items():
        candidate = _resolve_principal_template(
            spec.workload_principal, cfg=cfg, org_id=org_id
        )
        if "{" in candidate or "}" in candidate:
            raise ValueError(
                f"agent_identity.bindings[{agent_id!r}]: unresolved workload_principal template"
            )
        principal = normalize_principal(candidate)
        if principal is None:  # the config schema validates this too
            raise ValueError(
                f"agent_identity.bindings[{agent_id!r}]: malformed workload_principal"
            )
        out[agent_id] = AgentBinding(
            agent_id=agent_id,
            workload_principal=principal.value,
            allowed_purposes=frozenset(spec.allowed_purposes),
        )
    return out
