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
# pylint: disable=missing-class-docstring,unused-import

"""Tenant blast-radius containment: per-tenant runtime identities and tenant-scoped credentials.

Problem this solves: the pooled gateway used one service account with project-wide rights on
every tenant's Cloud KMS key, Secret Manager secret, and Cloud Storage object. A single
compromised request, container, or credential therefore reached every tenant, and per-tenant
keys did not contain it.

Model:
1. **One service account per tenant** (`ct-<sha256(tenant_id)[:24]>@<project>`). Terraform
   (`terraform/tenant_isolation.tf`) grants it access to *only* that tenant's KMS key, secrets, and
   runbook folder. The shared gateway identity keeps no project-wide KMS, Secret Manager, or
   Storage role; it may only mint short-lived tokens for tenant service accounts.
2. **Tenant-scoped credentials are minted from the verified `ContextEnvelope` only.** The broker
   never accepts a free-form tenant argument, so a request can only act as the tenant Hop 0/1
   verified.
3. **Two independent controls per call.** `TenantIsolationPolicy` rejects a cross-tenant
   resource in code *before* any network call, and IAM on the tenant service account rejects it
   again at the Google API.
4. `LocalKMS` is an IAM-enforcing stand-in for Cloud KMS, so the blast-radius guarantees are
   tested hermetically.
"""

from __future__ import annotations

import contextlib
import contextvars
import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from agents import platform_config
from agents.context import TENANT_DIRECTORY, ContextEnvelope
from agents.platform_config import is_live_mode
from agents.tenant_identity import TENANT_SA_PREFIX  # noqa: F401 - re-exported
from agents.tenant_identity import (
    tenant_service_account_email,
    tenant_service_account_id,
)
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
MAX_CREDENTIAL_LIFETIME_SECONDS = 300
DEFAULT_CREDENTIAL_LIFETIME_SECONDS = MAX_CREDENTIAL_LIFETIME_SECONDS
DEFAULT_REFRESH_MARGIN_SECONDS = 60

# Secret Manager secrets owned by each tenant, from `secret_ids` in config/tenants/<env>/*.yaml
# (mirrors `local.tenant_isolation` in Terraform). Dynamic tenants register theirs via
# `register_tenant(secret_ids=...)`; the policy always reads TENANT_DIRECTORY, so this snapshot is
# informational.
TENANT_SECRET_IDS: dict[str, tuple[str, ...]] = {
    tenant_id: tuple(meta.get("secret_ids", ()))
    for tenant_id, meta in TENANT_DIRECTORY.items()
}


# ---------------------------------------------------------------------------------------------
# Policy: which tenant principal may use which resource
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TenantResourceGrants:
    tenant_id: str
    principal: str
    kms_keys: frozenset[str]
    secret_ids: frozenset[str]
    object_prefixes: frozenset[tuple[str, str]]  # (bucket, prefix)


class TenantIsolationPolicy:
    """Code-level mirror of the per-tenant IAM bindings in `terraform/tenant_isolation.tf`."""

    def __init__(
        self, *, project_id: str, runbook_bucket: str | None = None
    ) -> None:
        self.project_id = project_id
        self.runbook_bucket = runbook_bucket or f"{project_id}-runbooks"

    def grants_for(self, tenant_id: str) -> TenantResourceGrants:
        meta = TENANT_DIRECTORY.get(tenant_id)
        if meta is None:
            raise PermissionError("E_TENANT_NOT_ONBOARDED: Unknown tenant.")
        return TenantResourceGrants(
            tenant_id=tenant_id,
            principal=tenant_service_account_email(tenant_id, self.project_id),
            kms_keys=frozenset({str(meta["cmek_key_name"])}),
            secret_ids=frozenset(meta.get("secret_ids", ())),
            object_prefixes=frozenset({(self.runbook_bucket, f"{tenant_id}/")}),
        )

    @staticmethod
    def _key_matches(granted: str, requested: str) -> bool:
        # A key version (`.../cryptoKeyVersions/N`) belongs to its parent key.
        return requested == granted or requested.startswith(
            f"{granted}/cryptoKeyVersions/"
        )

    def assert_kms_key(self, tenant_id: str, kms_key_name: str) -> None:
        if not any(
            self._key_matches(k, kms_key_name)
            for k in self.grants_for(tenant_id).kms_keys
        ):
            raise PermissionError(
                "E_TENANT_RESOURCE_SCOPE_VIOLATION: KMS key is not owned by the calling tenant."
            )

    def assert_secret(self, tenant_id: str, secret_id: str) -> None:
        if secret_id not in self.grants_for(tenant_id).secret_ids:
            raise PermissionError(
                "E_TENANT_RESOURCE_SCOPE_VIOLATION: Secret is not owned by the calling tenant."
            )

    def assert_object(
        self, tenant_id: str, bucket: str, object_path: str
    ) -> None:
        if ".." in object_path.split("/"):
            raise PermissionError(
                "E_TENANT_RESOURCE_SCOPE_VIOLATION: Path traversal rejected."
            )
        allowed = any(
            bucket == b and object_path.startswith(prefix)
            for b, prefix in self.grants_for(tenant_id).object_prefixes
        )
        if not allowed:
            raise PermissionError(
                "E_TENANT_RESOURCE_SCOPE_VIOLATION: Object is not owned by the calling tenant."
            )

    def tenants_with_kms_access(self, kms_key_name: str) -> set[str]:
        return {
            t
            for t in TENANT_DIRECTORY
            if any(
                self._key_matches(k, kms_key_name)
                for k in self.grants_for(t).kms_keys
            )
        }

    def blast_radius(self, compromised_tenant_id: str) -> set[str]:
        """Tenants whose keys, secrets, or objects a compromised tenant principal could reach."""
        grants = self.grants_for(compromised_tenant_id)
        reached: set[str] = set()
        for other in TENANT_DIRECTORY:
            other_grants = self.grants_for(other)
            if (
                grants.kms_keys & other_grants.kms_keys
                or grants.secret_ids & other_grants.secret_ids
                or grants.object_prefixes & other_grants.object_prefixes
            ):
                reached.add(other)
        return reached


# ---------------------------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TenantScopedCredential:
    tenant_id: str
    principal: str
    token: str
    expires_at: float

    def bearer_headers(self, project_id: str) -> dict[str, str]:
        """Authorization header only.

        No `X-Goog-User-Project`: Cloud Storage treats it as a billing-project override that needs
        `serviceusage.services.use`, a project-level permission tenant service accounts deliberately
        lack. Tenant service accounts live in the same project, so quota attribution is unchanged.
        `project_id` is kept for call-site symmetry with the shared-identity helper.
        """
        del project_id
        return {"Authorization": f"Bearer {self.token}"}


class TenantCredentialBackend(Protocol):
    def mint(
        self, *, tenant_id: str, principal: str, lifetime_seconds: int
    ) -> TenantScopedCredential: ...


class LocalTenantCredentialBackend:
    """Hermetic backend: opaque per-tenant tokens with no cloud access (tests, local sandbox)."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self.minted: list[TenantScopedCredential] = []

    def mint(
        self, *, tenant_id: str, principal: str, lifetime_seconds: int
    ) -> TenantScopedCredential:
        cred = TenantScopedCredential(
            tenant_id=tenant_id,
            principal=principal,
            token=f"local-{tenant_service_account_id(tenant_id)}-{uuid.uuid4().hex}",
            expires_at=self._clock() + lifetime_seconds,
        )
        self.minted.append(cred)
        return cred


class ImpersonatedTenantCredentialBackend:
    """Live backend: the gateway identity impersonates the tenant service account.

    Uses `google.auth.impersonated_credentials` (IAM Credentials `generateAccessToken`). The
    gateway needs `roles/iam.serviceAccountTokenCreator` on each tenant service account only.
    """

    def mint(
        self, *, tenant_id: str, principal: str, lifetime_seconds: int
    ) -> TenantScopedCredential:
        import google.auth
        import google.auth.transport.requests
        from google.auth import impersonated_credentials

        source, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
        target = impersonated_credentials.Credentials(
            source_credentials=source,
            target_principal=principal,
            target_scopes=[CLOUD_PLATFORM_SCOPE],
            lifetime=lifetime_seconds,
        )
        target.refresh(google.auth.transport.requests.Request())
        expiry = (
            target.expiry.timestamp()
            if target.expiry
            else time.time() + lifetime_seconds
        )
        return TenantScopedCredential(
            tenant_id=tenant_id,
            principal=principal,
            token=str(target.token),
            expires_at=expiry,
        )


class TenantCredentialUnavailable(RuntimeError):
    """Credentials could not be obtained right now (broker or IAM outage). Not a denial: 503."""


BROKER_CONTEXT_TOKEN_HEADER = "X-Cymbal-Context-Token"
BROKER_CREDENTIAL_PATH = "/internal/v1/tenant-credential"


def _fetch_cloud_run_id_token(audience: str) -> str:
    """Google-signed ID token for calling Cloud Run services (`*.run.app` `run.invoker`).

    `bind_id_token=False` requests an unbound S2S ID token (`GET .../identity`) even on Cloud Run
    Agent Identity (`--identity-certificate`), because `*.run.app` GFE edges do not terminate
    workload mTLS client certificates (unlike `*.mtls.googleapis.com`).
    """
    import google.auth.transport.requests
    import google.oauth2.id_token

    req = google.auth.transport.requests.Request()
    try:
        return str(
            google.oauth2.id_token.fetch_id_token(
                req, audience, bind_id_token=False
            )
        )
    except (
        TypeError
    ):  # pragma: no cover - older google-auth without bind_id_token kwarg
        return str(google.oauth2.id_token.fetch_id_token(req, audience))


# ADR-0014 B5: a forwarded turn carries a broker-audience token the gateway pre-minted, because the
# agent runtime service holds no signer and cannot run the exchange itself.
_TURN_BROKER_TOKEN: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "cymbal_turn_broker_token", default=None
)


@contextlib.contextmanager
def turn_broker_token(token: str | None) -> Iterator[None]:
    """Makes `token` the broker token for mints in this turn (the runtime service sets it)."""
    reset = _TURN_BROKER_TOKEN.set(token or None)
    try:
        yield
    finally:
        _TURN_BROKER_TOKEN.reset(reset)


class RemoteBrokerBackend:
    """Live backend after ADR-0014 B4: the runtime asks the credential broker service to mint.

    Per mint: (1) exchange the turn's internal context token for a fresh broker-audience token
    (`agents.context_exchange`, new `jti` each time), (2) get a Cloud Run IAM ID token for the
    broker URL, (3) `POST /internal/v1/tenant-credential` with the ID token in
    `X-Serverless-Authorization` and the broker token in `X-Cymbal-Context-Token`. The broker
    takes the tenant from the token; the runtime cannot name it. The runtime needs no
    `serviceAccountTokenCreator` on tenant service accounts.
    """

    needs_context_token = True

    def __init__(
        self,
        broker_url: str,
        *,
        exchange: Any | None = None,
        id_token_provider: Callable[[str], str] = _fetch_cloud_run_id_token,
        http_post: Callable[..., Any] | None = None,
        timeout_seconds: float = 10.0,
        allow_exchange: bool = True,
    ) -> None:
        """`allow_exchange=False` (the agent runtime service): only the turn's pre-minted broker
        token is used; without one the mint is refused, never exchanged locally.
        """
        self._allow_exchange = allow_exchange
        # Plain http only for the in-process test server or an injected transport (tests).
        if not (
            broker_url.startswith("https://")
            or broker_url == "http://testserver"
            or http_post is not None
        ):
            raise ValueError(
                "E_BROKER_URL: the credential broker URL must be https://"
            )
        self.broker_url = broker_url.rstrip("/")
        self._exchange = exchange
        self._id_token_provider = id_token_provider
        self._http_post = http_post
        self._timeout = timeout_seconds

    def mint(
        self,
        *,
        tenant_id: str,
        principal: str,
        lifetime_seconds: int,
        context_token: str = "",
    ) -> TenantScopedCredential:
        from agents.context_exchange import get_context_token_exchange

        if not context_token:
            raise PermissionError(
                "E_BROKER_NO_CONTEXT_TOKEN: a signed context token is required."
            )
        pre_minted = _TURN_BROKER_TOKEN.get()
        if pre_minted:
            broker_token = (
                pre_minted  # minted by the gateway for this turn (B5)
            )
        elif self._allow_exchange:
            exchange = self._exchange or get_context_token_exchange()
            broker_token, _ = exchange.exchange(
                context_token, audience="broker"
            )
        else:
            raise PermissionError(
                "E_BROKER_NO_BROKER_TOKEN: this turn carries no pre-minted broker token."
            )
        policy_max_ttl = min(
            platform_config.resolve_effective_token_policy().tenant_sa_token_ttl_seconds,
            MAX_CREDENTIAL_LIFETIME_SECONDS,
        )
        clamped_lifetime = max(60, min(int(lifetime_seconds), policy_max_ttl))
        try:
            id_token = self._id_token_provider(self.broker_url)
            post = self._http_post
            if post is None:
                import httpx

                post = httpx.post
            resp = post(
                self.broker_url + BROKER_CREDENTIAL_PATH,
                headers={
                    "X-Serverless-Authorization": f"Bearer {id_token}",
                    BROKER_CONTEXT_TOKEN_HEADER: broker_token,
                },
                json={
                    "kind": "access_token",
                    "lifetime_seconds": clamped_lifetime,
                },
                timeout=self._timeout,
            )
        except (
            Exception
        ) as exc:  # transport / metadata server: an outage, not a denial
            raise TenantCredentialUnavailable(
                f"E_BROKER_UNAVAILABLE: {type(exc).__name__}"
            ) from exc
        if resp.status_code in (400, 401, 403, 409, 422, 429):
            code = "E_BROKER_REFUSED"
            with contextlib.suppress(
                Exception
            ):  # keep the generic code if the body is odd
                code = str(resp.json().get("detail", {}).get("error", code))
            raise PermissionError(
                f"{code}: credential broker refused the mint."
            )
        if resp.status_code != 200:
            raise TenantCredentialUnavailable(
                f"E_BROKER_UNAVAILABLE: HTTP {resp.status_code}"
            )
        try:
            body = resp.json()
            token = body["access_token"]
            expires_at = float(body["expires_at"])
            if not isinstance(token, str) or not token:
                raise ValueError("empty token")
        except (
            Exception
        ) as exc:  # a 200 we can't use is a broker fault, not a denial
            raise TenantCredentialUnavailable(
                "E_BROKER_MALFORMED_RESPONSE"
            ) from exc
        if (
            body.get("tenant_id") != tenant_id
            or body.get("principal") != principal
        ):
            raise PermissionError(
                "E_CREDENTIAL_TENANT_MISMATCH: broker minted the wrong principal."
            )
        return TenantScopedCredential(
            tenant_id=tenant_id,
            principal=principal,
            token=token,
            expires_at=expires_at,
        )


class TenantCredentialBroker:
    """Mints and caches short-lived credentials for the tenant in a verified `ContextEnvelope`."""

    def __init__(
        self,
        *,
        project_id: str,
        backend: TenantCredentialBackend,
        lifetime_seconds: int | None = None,
        refresh_margin_seconds: int | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        token_policy = (
            platform_config.resolve_effective_token_policy()
            if (lifetime_seconds is None or refresh_margin_seconds is None)
            else None
        )
        resolved_lifetime = (
            lifetime_seconds
            if lifetime_seconds is not None
            else token_policy.tenant_sa_token_ttl_seconds  # type: ignore[union-attr]
        )
        resolved_margin = (
            refresh_margin_seconds
            if refresh_margin_seconds is not None
            else token_policy.tenant_sa_refresh_margin_seconds  # type: ignore[union-attr]
        )
        if not 60 <= resolved_lifetime <= MAX_CREDENTIAL_LIFETIME_SECONDS:
            raise ValueError(
                "E_CREDENTIAL_LIFETIME: lifetime must be between 60 and "
                f"{MAX_CREDENTIAL_LIFETIME_SECONDS} seconds."
            )
        if not 0 <= resolved_margin < resolved_lifetime:
            raise ValueError(
                "E_CREDENTIAL_REFRESH_MARGIN: refresh_margin_seconds must be >= 0 and < "
                "lifetime_seconds."
            )
        from agents.context import register_tenant_eviction_target
        from agents.workload_identity import register_agent_eviction_target

        self.project_id = project_id
        self.backend = backend
        self.lifetime_seconds = resolved_lifetime
        self.refresh_margin_seconds = resolved_margin
        self._clock = clock
        self._cache: dict[
            tuple[str, str, tuple[str, ...]], TenantScopedCredential
        ] = {}
        self._eviction_generation: dict[str, int] = {}
        self._agent_eviction_generation: dict[str, int] = {}
        self._lock = threading.Lock()
        register_tenant_eviction_target(self)
        register_agent_eviction_target(self)

    @staticmethod
    def _cache_key_for_envelope(
        envelope: ContextEnvelope,
    ) -> tuple[str, str, tuple[str, ...]]:
        """Partitions cached 2LO credentials by `(tenant_id, agent_id, normalized_scopes)`."""
        tenant_id = envelope.tenant.tenant_id
        agent_id = (envelope.agent_id or "").strip()
        normalized_scopes = tuple(
            sorted(set(envelope.tenant.authorized_scopes))
        )
        return (tenant_id, agent_id, normalized_scopes)

    def evict_tenant(self, tenant_id: str) -> bool:
        """Evicts all cached credentials for `tenant_id` across every agent and scope at once."""
        with self._lock:
            self._eviction_generation[tenant_id] = (
                self._eviction_generation.get(tenant_id, 0) + 1
            )
            matching_keys = [key for key in self._cache if key[0] == tenant_id]
            for key in matching_keys:
                self._cache.pop(key, None)
            return bool(matching_keys)

    def evict_agent(self, agent_id: str) -> bool:
        """Evicts all cached 2LO credentials bound to `agent_id` upon agent suspension (`C17`)."""
        with self._lock:
            self._agent_eviction_generation[agent_id] = (
                self._agent_eviction_generation.get(agent_id, 0) + 1
            )
            matching_keys = [key for key in self._cache if key[1] == agent_id]
            for key in matching_keys:
                self._cache.pop(key, None)
            return bool(matching_keys)

    def credential_for(
        self, envelope: ContextEnvelope
    ) -> TenantScopedCredential:
        from agents.workload_identity import (
            is_agent_suspended,
            is_tenant_revoked,
        )

        if not isinstance(envelope, ContextEnvelope):
            raise PermissionError(
                "E_UNVERIFIED_ENVELOPE: A verified ContextEnvelope is required."
            )
        tenant_id = envelope.tenant.tenant_id
        if tenant_id not in TENANT_DIRECTORY or is_tenant_revoked(tenant_id):
            raise PermissionError("E_TENANT_NOT_ONBOARDED: Unknown tenant.")
        bound_agent = (envelope.agent_id or "").strip()
        if bound_agent and is_agent_suspended(bound_agent):
            raise PermissionError(
                f"403 Forbidden: E_AGENT_SUSPENDED: Agent '{bound_agent}' is suspended."
            )
        cache_key = self._cache_key_for_envelope(envelope)
        principal = tenant_service_account_email(tenant_id, self.project_id)
        with self._lock:
            generation_before = self._eviction_generation.get(tenant_id, 0)
            agent_gen_before = self._agent_eviction_generation.get(
                bound_agent, 0
            )
            cached = self._cache.get(cache_key)
            if (
                cached
                and cached.expires_at - self.refresh_margin_seconds
                > self._clock()
            ):
                return cached
        extra: dict[str, Any] = {}
        if getattr(self.backend, "needs_context_token", False):
            extra["context_token"] = (
                envelope.context_token
            )  # RemoteBrokerBackend (ADR-0014 B4)
        cred = self.backend.mint(
            tenant_id=tenant_id,
            principal=principal,
            lifetime_seconds=self.lifetime_seconds,
            **extra,
        )
        if cred.tenant_id != tenant_id or cred.principal != principal:
            raise PermissionError(
                "E_CREDENTIAL_TENANT_MISMATCH: Backend minted the wrong principal."
            )
        with self._lock:
            if (
                self._eviction_generation.get(tenant_id, 0) != generation_before
                or tenant_id not in TENANT_DIRECTORY
                or is_tenant_revoked(tenant_id)
            ):
                raise PermissionError(
                    "E_TENANT_OFFBOARDED_DURING_MINT: Tenant was offboarded during credential mint."
                )
            if bound_agent and (
                is_agent_suspended(bound_agent)
                or self._agent_eviction_generation.get(bound_agent, 0)
                != agent_gen_before
            ):
                raise PermissionError(
                    f"403 Forbidden: E_AGENT_SUSPENDED: Agent '{bound_agent}' was suspended."
                )
            self._cache[cache_key] = cred
        return cred

    def headers_for(self, envelope: ContextEnvelope) -> dict[str, str]:
        return self.credential_for(envelope).bearer_headers(self.project_id)


def tenant_scoped_credentials_enabled() -> bool:
    """On by default. `CYMBAL_TENANT_SCOPED_CREDENTIALS=0` is a migration escape hatch only."""
    return os.getenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", "1") != "0"


_DEFAULT_BROKER: TenantCredentialBroker | None = None
_DEFAULT_BROKER_LOCK = threading.Lock()
_LOCAL_EXCHANGE_ALLOWED = True


def disable_local_exchange() -> None:
    """Agent runtime service (B5): it holds no signer, so the default broker backend uses only
    the turn's pre-minted broker token and never runs the exchange itself."""
    global _LOCAL_EXCHANGE_ALLOWED, _DEFAULT_BROKER
    with _DEFAULT_BROKER_LOCK:
        _LOCAL_EXCHANGE_ALLOWED = False
        _DEFAULT_BROKER = None


def get_default_broker(project_id: str) -> TenantCredentialBroker:
    """Process-wide broker. Offline: local tokens. Live mode needs an explicit choice:
    `CREDENTIAL_BROKER_URL` (the credential broker, ADR-0014 B4) or
    `CYMBAL_DIRECT_IMPERSONATION=1` (pre-B4: the runtime impersonates tenant SAs itself).
    With neither, it refuses (fail closed) instead of silently picking one."""
    global _DEFAULT_BROKER
    with _DEFAULT_BROKER_LOCK:
        if _DEFAULT_BROKER is None or _DEFAULT_BROKER.project_id != project_id:
            backend: TenantCredentialBackend
            broker_url = os.getenv("CREDENTIAL_BROKER_URL", "").strip()
            if not is_live_mode():
                backend = LocalTenantCredentialBackend()
            elif broker_url:
                backend = RemoteBrokerBackend(
                    broker_url, allow_exchange=_LOCAL_EXCHANGE_ALLOWED
                )
            elif os.getenv("CYMBAL_DIRECT_IMPERSONATION") == "1":
                backend = ImpersonatedTenantCredentialBackend()
            else:
                raise TenantCredentialUnavailable(
                    "E_CREDENTIAL_BACKEND_UNCONFIGURED: live mode needs CREDENTIAL_BROKER_URL "
                    "(credential broker) or CYMBAL_DIRECT_IMPERSONATION=1 (pre-B4)"
                )
            _DEFAULT_BROKER = TenantCredentialBroker(
                project_id=project_id, backend=backend
            )
        return _DEFAULT_BROKER


def set_default_broker(broker: TenantCredentialBroker | None) -> None:
    """Test hook: install (or clear) the process-wide broker."""
    global _DEFAULT_BROKER
    with _DEFAULT_BROKER_LOCK:
        _DEFAULT_BROKER = broker


def evict_tenant_credentials(tenant_id: str) -> bool:
    """Evicts `tenant_id` from the process-wide credential broker cache if initialized."""
    with _DEFAULT_BROKER_LOCK:
        broker = _DEFAULT_BROKER
    if broker is None:
        return False
    return broker.evict_tenant(tenant_id)


# ---------------------------------------------------------------------------------------------
# IAM-enforcing local KMS (hermetic stand-in for Cloud KMS)
# ---------------------------------------------------------------------------------------------


class LocalKMS:
    """Cloud KMS stand-in that enforces the per-tenant IAM model.

    Each key has random, non-exportable material. `encrypt`/`decrypt` succeed only when the
    caller's credential principal is the tenant service account bound to that key, mirroring
    `roles/cloudkms.cryptoKeyEncrypterDecrypter` on the key resource.
    """

    def __init__(self, policy: TenantIsolationPolicy) -> None:
        self.policy = policy
        self._material: dict[str, bytes] = {}

    def _authorize(
        self, credential: TenantScopedCredential | None, kms_key_name: str
    ) -> bytes:
        if credential is None:
            raise PermissionError(
                "E_KMS_IAM_DENIED: Caller has no tenant-scoped credential."
            )
        expected = tenant_service_account_email(
            credential.tenant_id, self.policy.project_id
        )
        if credential.principal != expected:
            raise PermissionError(
                "E_KMS_IAM_DENIED: Credential principal does not match tenant."
            )
        try:
            self.policy.assert_kms_key(credential.tenant_id, kms_key_name)
        except PermissionError as exc:
            raise PermissionError(
                "E_KMS_IAM_DENIED: Principal lacks cryptoKeyEncrypterDecrypter on this key."
            ) from exc
        return self._material.setdefault(kms_key_name, os.urandom(32))

    def encrypt(
        self,
        *,
        kms_key_name: str,
        plaintext: bytes,
        aad: bytes,
        credential: TenantScopedCredential | None,
    ) -> bytes:
        key = self._authorize(credential, kms_key_name)
        nonce = os.urandom(12)
        return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)

    def decrypt(
        self,
        *,
        kms_key_name: str,
        ciphertext: bytes,
        aad: bytes,
        credential: TenantScopedCredential | None,
    ) -> bytes:
        key = self._authorize(credential, kms_key_name)
        try:
            return AESGCM(key).decrypt(ciphertext[:12], ciphertext[12:], aad)
        except InvalidTag as exc:
            raise PermissionError(
                "E_KMS_DECRYPT_FAILED: Wrong key or AAD."
            ) from exc


def describe_blast_radius(policy: TenantIsolationPolicy) -> dict[str, Any]:
    """Machine-readable blast-radius report used by tests and docs."""
    return {
        tenant: sorted(policy.blast_radius(tenant))
        for tenant in sorted(TENANT_DIRECTORY)
    }
