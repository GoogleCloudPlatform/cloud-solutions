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

# pylint: disable=import-outside-toplevel,inconsistent-quotes,line-too-long
# pylint: disable=missing-class-docstring,protected-access

"""Gateway access tokens bound to the caller's key (RFC 9449 DPoP), issued after Hop 0.

Why: IdP ID tokens (Okta, Entra, Google) cannot carry a key binding, so a stolen ID token would
work with any attacker-made DPoP key. The gateway therefore exchanges a verified IdP token once
for its own short-lived access token whose `cnf.jkt` is the thumbprint of the client's DPoP key:

    POST /api/v1/auth/token   {"subject_token": <IdP ID token>}   + DPoP proof for that URL
      -> {"access_token": <gateway token>, "token_type": "DPoP", "expires_in": 600}

Every data request then sends `Authorization: DPoP <gateway token>` plus a fresh DPoP proof that
(1) is signed by the bound key (`jkt == cnf.jkt`), (2) names this method and URL, (3) carries
`ath = b64url(sha256(token))`, (4) is recent (`iat` within the window), and (5) has an unused `jti`.
Verification is stateless apart from the bounded replay cache, so it works across instances that
share the signing key. Re-exchanging the same IdP token must use the same client key (bounded,
per-instance binding), so an ID token copied after use cannot be bound to an attacker's key.

Limits: by default the replay cache and ID-token binding are in-process; pass a Redis-backed
`SharedReplayStore` before running more than one instance with customer data.

Rolling-Deploy Signing-Key Rotation Runbook (`(active_kid, previous_kid, next_kid)` ring):
1. **Stage 1 (Pre-stage verify-only `next_kid`)**: Add new EC P-256 secret version `B` as
   `identity.gateway_next_signing_secret` while `identity.gateway_signing_secret` remains `A`.
   Roll out across all instances so every replica verifies both `A` and `B` before any replica
   signs with `B`.
2. **Stage 2 (Switch signing to `B`)**: Set `identity.gateway_signing_secret = B`,
   `identity.gateway_previous_signing_secret = A`, and clear `gateway_next_signing_secret`. New
   replicas sign with `B` (accepted by Stage-1 replicas via `next_kid`) while Stage-1 replicas
   still signing with `A` are accepted by Stage-2 replicas via `previous_kid`.
3. **Stage 3 (Retire `A` after TTL drain)**: Wait at least `gateway_token_ttl_seconds + 30s`
   (`630s` at the `600s` default, plus any downstream JWKS cache TTL) after Stage 2 completes
   before removing `gateway_previous_signing_secret` and disabling Secret Manager version `A`.
   Note: pseudonymous user log references (`log_user_ref` / `log_key`) are derived from the active
   signing key and therefore rotate at Stage 2.

Signing key: Secret Manager secret version `identity.gateway_signing_secret` (pinned; PKCS#8 PEM,
EC P-256), read once at startup as the serving identity (secrets never come from environment
variables). In a synthetic sandbox
without it, an ephemeral per-process key is used (one instance only); with customer data and no
secret, config validation and the gateway refuse to run (fail closed).
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import jwt
from agents import context_signing, platform_config
from agents.context import (
    _ACTIVE_TENANT_ENVELOPE,
    AsymmetricDPoPProvider,
    ContextEnvelope,
    EdgeAuthVerifier,
    build_redis_client_from_env,
)
from agents.context_signing import ContextSigningUnavailableError
from agents.platform_config import PlatformConfig, get_platform_config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException, Request
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

GATEWAY_ISSUER = "https://agent-gateway.cymbal.internal"
# Distinct from the audience IdP tokens use, so a gateway token is never accepted as an IdP token
# (and the reverse) even if an issuer were misconfigured.
GATEWAY_TOKEN_AUDIENCE = GATEWAY_ISSUER + "/gateway-api"
_DEFAULT_GATEWAY_TOKEN_TTL_SECONDS = 600
GATEWAY_TOKEN_TTL_SECONDS = _DEFAULT_GATEWAY_TOKEN_TTL_SECONDS
_DEFAULT_DPOP_MAX_AGE_SECONDS = 120
DPOP_MAX_AGE_SECONDS = _DEFAULT_DPOP_MAX_AGE_SECONDS
CLOCK_SKEW_SECONDS = 30
_REPLAY_CACHE_MAX = 100_000


def effective_gateway_token_ttl_seconds() -> int:
    """Returns the active gateway token TTL from platform config/env, honoring test overrides."""
    if GATEWAY_TOKEN_TTL_SECONDS != _DEFAULT_GATEWAY_TOKEN_TTL_SECONDS:
        return GATEWAY_TOKEN_TTL_SECONDS
    return (
        platform_config.resolve_effective_token_policy().gateway_token_ttl_seconds
    )


def effective_dpop_max_age_seconds() -> int:
    """Returns the active DPoP proof freshness window from platform config/env."""
    if DPOP_MAX_AGE_SECONDS != _DEFAULT_DPOP_MAX_AGE_SECONDS:
        return DPOP_MAX_AGE_SECONDS
    return (
        platform_config.resolve_effective_token_policy().dpop_proof_max_age_seconds
    )


class GatewayTokenError(PermissionError):
    """Caller authentication failed. `code` is safe to return; details are not."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def log_user_ref(tenant_id: str, sub: str) -> str:
    """Pseudonymous user reference for logs: an HMAC keyed from the gateway's secret signing key,
    so log readers cannot reverse it by hashing guessed emails. Stable while the key is (one
    user's lines still correlate); ephemeral sandbox keys give per-process references.
    """
    import hmac

    mac = hmac.new(
        get_token_service().log_key, f"log:{tenant_id}:{sub}".encode(), "sha256"
    )
    return "u-" + mac.hexdigest()[:16]


def access_token_hash(token: str) -> str:
    """RFC 9449 `ath`: base64url(SHA-256(ASCII access token)), unpadded."""
    digest = hashlib.sha256(token.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def request_htu(request: Request) -> str:
    """The URL the client called, without query or fragment (RFC 9449 `htu`).

    With `identity.public_origin` set (required for customer data) the origin is fixed by config,
    so client-supplied forwarding headers cannot make a proof minted for another host pass here.
    Otherwise (synthetic sandbox) the `Host` header and the proxy's `X-Forwarded-Proto` are used;
    `X-Forwarded-Host` is never trusted.
    """
    origin = get_platform_config().identity.public_origin
    if origin:
        return origin.rstrip("/") + request.url.path
    proto = (
        request.headers.get("x-forwarded-proto", request.url.scheme)
        .split(",")[0]
        .strip()
    )
    host = request.headers.get("host", "")
    return f"{proto}://{host}{request.url.path}"


_STORE_ERRORS: tuple[type[BaseException], ...] = (
    RedisError,
    OSError,
    TimeoutError,
)


def _nx_inserted(res: object) -> bool:
    """Strict `SET ... NX` result: True = inserted; None/False = key exists; anything else is an
    unexpected client (e.g. a coroutine) and must fail closed, never count as success.
    """
    if res is True:
        return True
    if res is None or res is False:
        return False
    raise OSError("unexpected replay store response")


class FirestoreReplayClient:
    """Firestore-backed `SET ... NX EX` / `GET` adapter for multi-replica DPoP `jti` replay
    protection.
    """

    def __init__(
        self,
        project_id: str | None = None,
        database: str | None = None,
        collection_name: str = "cymbal_jti_replay_v1",
    ) -> None:
        from google.cloud import firestore

        resolved_project = project_id or platform_config.resolve_project_id()
        resolved_db = database or os.getenv(
            "FIRESTORE_DATABASE", "cymbal-memory-bank-prod"
        )
        self._client = firestore.Client(
            project=resolved_project, database=resolved_db
        )
        self._collection = collection_name

    def _doc_id(self, key: str) -> str:
        return "r-" + hashlib.sha256(key.encode("utf-8")).hexdigest()

    def set(
        self, key: str, value: str, *, nx: bool = True, ex: int = 120
    ) -> bool:
        from google.api_core import exceptions as gcp_exceptions

        now = time.time()
        expires_at = now + max(1, int(ex))
        doc_ref = self._client.collection(self._collection).document(
            self._doc_id(key)
        )
        payload = {
            "key": key,
            "value": value,
            "expires_at": expires_at,
            "updated_at": now,
        }
        try:
            if nx:
                try:
                    doc_ref.create(payload)
                    return True
                except gcp_exceptions.AlreadyExists:
                    snap = doc_ref.get()
                    data = snap.to_dict() or {}
                    if float(data.get("expires_at", 0.0)) < now:
                        doc_ref.set(payload)
                        return True
                    return False
            doc_ref.set(payload)
            return True
        except Exception as exc:
            raise OSError(
                f"Firestore replay store error: {type(exc).__name__}"
            ) from exc

    def get(self, key: str) -> str | None:
        now = time.time()
        doc_ref = self._client.collection(self._collection).document(
            self._doc_id(key)
        )
        try:
            snap = doc_ref.get()
            if not snap.exists:
                return None
            data = snap.to_dict() or {}
            if float(data.get("expires_at", 0.0)) < now:
                return None
            val = data.get("value")
            return str(val) if val is not None else None
        except Exception as exc:
            raise OSError(
                f"Firestore replay store error: {type(exc).__name__}"
            ) from exc


class SharedReplayStore:
    """Thread-safe shared replay and subject-token binding store (Redis SET NX EX contract).

    Can be shared across multiple `GatewayTokenService` instances or backed by a Redis client
    implementing `set(key, value, nx=True, ex=ttl)` and `get(key)`. Any backend I/O error raises
    `OSError` so callers fail closed with `E_DPOP_REPLAY_STORE_UNAVAILABLE`.
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        max_entries: int = _REPLAY_CACHE_MAX,
    ) -> None:
        if redis_client is not None:
            # An async client returns a coroutine from `set` (always truthy): every check would
            # pass.
            module = type(redis_client).__module__
            if module.startswith(
                "redis.asyncio"
            ) or inspect.iscoroutinefunction(
                getattr(redis_client, "set", None)
            ):
                raise ValueError(
                    "SharedReplayStore needs a synchronous Redis client"
                )
        self._redis = redis_client
        self._max = max_entries
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._bindings: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock = threading.Lock()

    def set_if_absent(self, key: str, ttl_seconds: int) -> bool:
        """Atomic SET-if-not-exists with TTL (`SET dpop:jti:{key} 1 NX EX {ttl}`)."""
        if self._redis is not None:
            try:
                res = self._redis.set(
                    f"dpop:jti:{key}", "1", nx=True, ex=max(1, int(ttl_seconds))
                )
            except (
                _STORE_ERRORS
            ) as exc:  # redis errors are not OSError: normalize to fail closed
                raise OSError("replay store unavailable") from exc
            return _nx_inserted(res)
        now = time.time()
        with self._lock:
            while self._seen and next(iter(self._seen.values())) < now:
                self._seen.popitem(last=False)
            if key in self._seen:
                return False
            if len(self._seen) >= self._max:
                raise GatewayTokenError("E_DPOP_REPLAY_CACHE_FULL")
            self._seen[key] = now + ttl_seconds
            return True

    def bind_subject_key(
        self, handle: str, jkt: str, expires_at: float
    ) -> bool:
        """Bind a subject token hash to the first DPoP thumbprint (`jkt`) seen until
        `expires_at`.
        """
        now = time.time()
        ttl = max(1, int(expires_at - now))
        if self._redis is not None:
            rkey = f"dpop:sub:{handle}"
            try:
                if _nx_inserted(self._redis.set(rkey, jkt, nx=True, ex=ttl)):
                    return True
                existing = self._redis.get(rkey)
            except (
                _STORE_ERRORS
            ) as exc:  # redis errors are not OSError: normalize to fail closed
                raise OSError("replay store unavailable") from exc
            if isinstance(existing, bytes):
                existing = existing.decode("utf-8")
            if not isinstance(existing, str):
                # None: the binding expired between SET and GET. Never treat that as a match.
                raise OSError("replay store returned no binding")
            return existing == jkt
        with self._lock:
            while (
                self._bindings and next(iter(self._bindings.values()))[1] < now
            ):
                self._bindings.popitem(last=False)
            bound = self._bindings.get(handle)
            if bound is not None:
                return bound[0] == jkt
            if len(self._bindings) >= self._max:
                raise GatewayTokenError("E_SUBJECT_TOKEN_CACHE_FULL")
            self._bindings[handle] = (jkt, expires_at)
            return True


class _ReplayCache:
    """Bounded `jti` cache. Entries expire a fixed time after insertion (longer than any proof
    could still be accepted), so expiry order equals insertion order and eviction from the head
    is exact even when clients choose odd `iat` values. Supports an optional shared store.
    """

    ENTRY_TTL_SECONDS = DPOP_MAX_AGE_SECONDS + CLOCK_SKEW_SECONDS + 1

    def __init__(
        self,
        max_entries: int = _REPLAY_CACHE_MAX,
        shared_store: SharedReplayStore | None = None,
    ) -> None:
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._max = max_entries
        self._shared = shared_store
        self._lock = threading.Lock()

    def check_and_add(self, jti: str) -> None:
        entry_ttl_seconds = (
            effective_dpop_max_age_seconds() + CLOCK_SKEW_SECONDS + 1
        )
        if self._shared is not None:
            try:
                inserted = self._shared.set_if_absent(jti, entry_ttl_seconds)
            except GatewayTokenError:
                raise
            except (OSError, RuntimeError) as exc:
                raise GatewayTokenError(
                    "E_DPOP_REPLAY_STORE_UNAVAILABLE"
                ) from exc
            if not inserted:
                raise GatewayTokenError("E_DPOP_REPLAY")
            return
        now = time.time()
        with self._lock:
            while self._seen and next(iter(self._seen.values())) < now:
                self._seen.popitem(last=False)
            if jti in self._seen:
                raise GatewayTokenError("E_DPOP_REPLAY")
            if len(self._seen) >= self._max:
                # Full of unexpired proofs: refuse rather than forget (fail closed). Only callers
                # who already proved a valid token can add entries, so this needs real tokens.
                raise GatewayTokenError("E_DPOP_REPLAY_CACHE_FULL")
            self._seen[jti] = now + entry_ttl_seconds


def verify_fresh_dpop_proof(
    proof_jwt: str,
    *,
    htm: str,
    htu: str,
    access_token: str | None,
) -> dict[str, Any]:
    """Signature, method, URL, recency and token hash of a DPoP proof (does not consume it)."""
    if not proof_jwt:
        raise GatewayTokenError("E_DPOP_MISSING")
    try:
        proof = AsymmetricDPoPProvider().verify_and_decode_dpop_jwt(
            dpop_jwt=proof_jwt, expected_htm=htm, expected_htu=htu
        )
        raw = jwt.decode(proof_jwt, options={"verify_signature": False})
    except (PermissionError, jwt.PyJWTError, KeyError, ValueError) as exc:
        raise GatewayTokenError("E_DPOP_INVALID") from exc
    now = time.time()
    iat = proof["iat"]
    max_proof_age = effective_dpop_max_age_seconds()
    if iat > now + CLOCK_SKEW_SECONDS or iat < now - max_proof_age:
        raise GatewayTokenError("E_DPOP_STALE")
    if access_token is not None and raw.get("ath") != access_token_hash(
        access_token
    ):
        raise GatewayTokenError("E_DPOP_ATH_MISMATCH")
    if access_token is None and "ath" in raw:
        raise GatewayTokenError(
            "E_DPOP_INVALID"
        )  # a request proof is not an exchange proof
    return proof


def consume_proof(proof: dict[str, Any], replay: _ReplayCache) -> None:
    """Single use: call only after the caller's token has been verified."""
    replay.check_and_add(f"{proof['jkt']}:{proof['jti']}")


class _SubjectTokenBindings:
    """First DPoP key seen per IdP token: a re-exchange must use the same key.

    A thief who copies an ID token after the real client exchanged it gets refused (on this
    instance or across instances when backed by `SharedReplayStore`). Entries expire with the
    IdP token; bounded like the replay cache.
    """

    def __init__(
        self,
        max_entries: int = _REPLAY_CACHE_MAX,
        shared_store: SharedReplayStore | None = None,
    ) -> None:
        self._keys: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max = max_entries
        self._shared = shared_store
        self._lock = threading.Lock()

    def bind(self, subject_token: str, jkt: str, expires_at: float) -> None:
        handle = hashlib.sha256(subject_token.encode()).hexdigest()
        if self._shared is not None:
            try:
                matched = self._shared.bind_subject_key(handle, jkt, expires_at)
            except GatewayTokenError:
                raise
            except (OSError, RuntimeError) as exc:
                raise GatewayTokenError(
                    "E_DPOP_REPLAY_STORE_UNAVAILABLE"
                ) from exc
            if not matched:
                raise GatewayTokenError("E_SUBJECT_TOKEN_BOUND_TO_OTHER_KEY")
            return
        now = time.time()
        with self._lock:
            while self._keys and next(iter(self._keys.values()))[1] < now:
                self._keys.popitem(last=False)
            bound = self._keys.get(handle)
            if bound is not None and bound[0] != jkt:
                raise GatewayTokenError("E_SUBJECT_TOKEN_BOUND_TO_OTHER_KEY")
            if bound is None:
                if len(self._keys) >= self._max:
                    raise GatewayTokenError("E_SUBJECT_TOKEN_CACHE_FULL")
                self._keys[handle] = (jkt, expires_at)


def _load_ec_p256_private_key(pem: str) -> ec.EllipticCurvePrivateKey:
    """Parses a PEM-encoded EC P-256 private key and rejects any other key type or curve."""
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    if (
        not isinstance(key, ec.EllipticCurvePrivateKey)
        or key.curve.name != "secp256r1"
    ):
        raise RuntimeError(
            "gateway signing key must be an EC P-256 private key"
        )
    return key


@dataclass
class GatewayTokenService:
    private_key: ec.EllipticCurvePrivateKey
    kid: str
    ephemeral: bool
    previous_public_key: ec.EllipticCurvePublicKey | None = None
    previous_kid: str | None = None
    next_public_key: ec.EllipticCurvePublicKey | None = None
    next_kid: str | None = None
    replay: _ReplayCache = field(default_factory=_ReplayCache)  # data requests
    exchange_replay: _ReplayCache = field(
        default_factory=_ReplayCache
    )  # /auth/token
    subject_bindings: _SubjectTokenBindings = field(
        default_factory=_SubjectTokenBindings
    )
    _key_lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False
    )

    @classmethod
    def from_config(cls, cfg: PlatformConfig) -> GatewayTokenService:
        secret_id = cfg.identity.gateway_signing_secret
        if secret_id:
            key = _load_ec_p256_private_key(fetch_signing_key_pem(secret_id))
            kid = "gw-" + _public_thumbprint(key)[:16]
            seen_kids: set[str] = {kid}

            previous_public_key: ec.EllipticCurvePublicKey | None = None
            previous_kid: str | None = None
            previous_secret_id = cfg.identity.gateway_previous_signing_secret
            if previous_secret_id:
                previous_key = _load_ec_p256_private_key(
                    fetch_signing_key_pem(previous_secret_id)
                )
                previous_kid = "gw-" + _public_thumbprint(previous_key)[:16]
                if previous_kid in seen_kids:
                    raise RuntimeError(
                        "E_GATEWAY_SIGNING_KEY_DUPLICATE: active and previous signing secrets "
                        "resolved to the same EC P-256 key"
                    )
                seen_kids.add(previous_kid)
                previous_public_key = previous_key.public_key()

            next_public_key: ec.EllipticCurvePublicKey | None = None
            next_kid: str | None = None
            next_secret_id = cfg.identity.gateway_next_signing_secret
            if next_secret_id:
                next_key = _load_ec_p256_private_key(
                    fetch_signing_key_pem(next_secret_id)
                )
                next_kid = "gw-" + _public_thumbprint(next_key)[:16]
                if next_kid in seen_kids:
                    raise RuntimeError(
                        "E_GATEWAY_SIGNING_KEY_DUPLICATE: next signing secret resolved to an "
                        "already-configured EC P-256 key"
                    )
                seen_kids.add(next_kid)
                next_public_key = next_key.public_key()

            logger.info(
                "GatewayTokenService initialized: active_kid=%s previous_kid=%s next_kid=%s",
                kid,
                previous_kid,
                next_kid,
            )
            shared_store: SharedReplayStore | None = None
            redis_client = build_redis_client_from_env()
            if redis_client is not None:
                shared_store = SharedReplayStore(redis_client=redis_client)
            elif (
                platform_config.is_live_mode()
                and not context_signing._PYTEST_MODE
            ):
                shared_store = SharedReplayStore(
                    FirestoreReplayClient(project_id=cfg.gcp.project_id)
                )
            return cls(
                private_key=key,
                kid=kid,
                ephemeral=False,
                previous_public_key=previous_public_key,
                previous_kid=previous_kid,
                next_public_key=next_public_key,
                next_kid=next_kid,
                replay=_ReplayCache(shared_store=shared_store),
                exchange_replay=_ReplayCache(shared_store=shared_store),
                subject_bindings=_SubjectTokenBindings(
                    shared_store=shared_store
                ),
            )
        if cfg.data_classification != "synthetic":
            raise RuntimeError(
                "E_GATEWAY_SIGNING_KEY_MISSING: set identity.gateway_signing_secret; an ephemeral "
                "key is allowed only for synthetic sandboxes"
            )
        logger.warning(
            "Gateway token key is EPHEMERAL (per process): run one instance or set "
            "identity.gateway_signing_secret."
        )
        key = ec.generate_private_key(ec.SECP256R1())
        ephemeral_kid = "gw-ephemeral-" + uuid.uuid4().hex[:8]
        logger.info(
            (
                "GatewayTokenService initialized (ephemeral): active_kid=%s "
                "previous_kid=None next_kid=None"
            ),
            ephemeral_kid,
        )
        ephemeral_redis = build_redis_client_from_env()
        ephemeral_shared = (
            SharedReplayStore(redis_client=ephemeral_redis)
            if ephemeral_redis is not None
            else None
        )
        return cls(
            private_key=key,
            kid=ephemeral_kid,
            ephemeral=True,
            replay=_ReplayCache(shared_store=ephemeral_shared),
            exchange_replay=_ReplayCache(shared_store=ephemeral_shared),
            subject_bindings=_SubjectTokenBindings(
                shared_store=ephemeral_shared
            ),
        )

    @property
    def verification_keys(self) -> dict[str, ec.EllipticCurvePublicKey]:
        """Returns the `(active_kid, previous_kid, next_kid)` public-key verification ring."""
        with self._key_lock:
            ring: dict[str, ec.EllipticCurvePublicKey] = {
                self.kid: self.private_key.public_key()
            }
            if (
                self.previous_kid is not None
                and self.previous_public_key is not None
            ):
                ring[self.previous_kid] = self.previous_public_key
            if self.next_kid is not None and self.next_public_key is not None:
                ring[self.next_kid] = self.next_public_key
            return ring

    def rotate_signing_key(
        self,
        new_private_key: ec.EllipticCurvePrivateKey,
        new_kid: str | None = None,
    ) -> dict[str, str | None]:
        """SANDBOX / TEST-ONLY: rotates the in-process ES256 signing key (`active -> previous`).

        Do not call on a single replica of a multi-instance deployment (which would diverge key
        rings across instances); multi-instance production uses the 3-step Secret Manager config
        rollout (`gateway_next_signing_secret` -> `gateway_signing_secret` ->
        `gateway_previous_signing_secret`).

        Args:
            new_private_key: Replacement EC P-256 (`secp256r1`) private key.
            new_kid: Optional explicit key identifier; defaults to `gw-<thumbprint[:16]>`.

        Returns:
            Dictionary containing `active_kid` and `previous_kid` after rotation.

        Raises:
            ValueError: If `new_private_key` is not an EC P-256 key or matches the active key.
        """
        if (
            not isinstance(new_private_key, ec.EllipticCurvePrivateKey)
            or new_private_key.curve.name != "secp256r1"
        ):
            raise ValueError(
                "new_private_key must be an EC P-256 (secp256r1) private key"
            )
        new_thumbprint = _public_thumbprint(new_private_key)
        resolved_kid = (
            new_kid.strip() if new_kid else ""
        ) or f"gw-{new_thumbprint[:16]}"
        with self._key_lock:
            current_thumbprint = _public_thumbprint(self.private_key)
            if resolved_kid == self.kid or new_thumbprint == current_thumbprint:
                raise ValueError(
                    "E_KEY_ROTATION_DUPLICATE_KID: new signing key must differ from active key"
                )
            self.previous_public_key = self.private_key.public_key()
            self.previous_kid = self.kid
            self.private_key = new_private_key
            self.kid = resolved_kid
            self.next_public_key = None
            self.next_kid = None
            return {
                "active_kid": self.kid,
                "previous_kid": self.previous_kid,
            }

    @property
    def log_key(self) -> bytes:
        """Key for pseudonymous log references, derived from (never equal to) the active signing
        key.

        Note: pseudonymous user log references (`u-<hmac>`) rotate when the active signing key
        rotates; log correlation holds within a signing-key epoch.
        """
        with self._key_lock:
            secret = self.private_key.private_numbers().private_value.to_bytes(
                32, "big"
            )
        return hashlib.sha256(b"cymbal-log-ref-v1:" + secret).digest()

    def issue(self, envelope: ContextEnvelope) -> tuple[str, int]:
        """A gateway token that never outlives the IdP token it came from."""
        now = int(time.time())
        gateway_ttl_seconds = effective_gateway_token_ttl_seconds()
        exp = min(int(envelope.security.exp), now + gateway_ttl_seconds)
        if exp <= now:
            raise GatewayTokenError("E_SUBJECT_TOKEN_EXPIRED")
        claims = {
            "iss": GATEWAY_ISSUER,
            "aud": GATEWAY_TOKEN_AUDIENCE,
            "sub": envelope.security.sub,
            "tenant_id": envelope.tenant.tenant_id,
            "user_role": envelope.security.user_role,
            "idp_provider": envelope.security.idp_provider,
            "idp_iss": envelope.security.iss,
            "cnf": {"jkt": envelope.security.dpop_jkt},
            "iat": now,
            "exp": exp,
            "jti": f"gw-{uuid.uuid4().hex}",
        }
        with self._key_lock:
            signing_key = self.private_key
            active_kid = self.kid
        token = jwt.encode(
            claims,
            signing_key,
            algorithm="ES256",
            headers={"kid": active_kid, "typ": "at+jwt"},
        )
        return token, exp - now

    def verify_request(
        self, *, authorization: str, dpop: str, htm: str, htu: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Claims of a valid, key-bound gateway token and its fresh proof for this request."""
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "dpop" or not token.strip():
            raise GatewayTokenError("E_TOKEN_MISSING")
        token = token.strip()
        try:
            header = jwt.get_unverified_header(token)
            token_kid = header.get("kid")
            verification_key = (
                self.verification_keys.get(token_kid)
                if isinstance(token_kid, str)
                else None
            )
            if header.get("typ") != "at+jwt" or verification_key is None:
                raise GatewayTokenError("E_TOKEN_INVALID")
            claims = jwt.decode(
                token,
                verification_key,
                algorithms=["ES256"],
                audience=GATEWAY_TOKEN_AUDIENCE,
                issuer=GATEWAY_ISSUER,
                options={"require": ["exp", "iat", "sub", "jti", "cnf"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise GatewayTokenError("E_TOKEN_EXPIRED") from exc
        except jwt.PyJWTError as exc:
            raise GatewayTokenError("E_TOKEN_INVALID") from exc
        proof = verify_fresh_dpop_proof(
            dpop, htm=htm, htu=htu, access_token=token
        )
        if proof["jkt"] != (claims.get("cnf") or {}).get("jkt"):
            raise GatewayTokenError("E_DPOP_KEY_MISMATCH")
        consume_proof(proof, self.replay)
        return claims, proof


def fetch_signing_key_pem(secret_version: str) -> str:
    """The pinned signing-key secret version, read with the serving identity's credentials."""
    import google.auth
    import google.auth.transport.requests
    import httpx
    from agents.platform_config import resolve_project_id

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(google.auth.transport.requests.Request())
    project = resolve_project_id()
    resp = httpx.get(
        f"https://secretmanager.googleapis.com/v1/projects/{project}/secrets/{secret_version}"
        ":access",
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return base64.b64decode(resp.json()["payload"]["data"]).decode()


def _public_thumbprint(key: ec.EllipticCurvePrivateKey) -> str:
    jwk = AsymmetricDPoPProvider.public_key_to_jwk(key.public_key())
    return AsymmetricDPoPProvider.compute_rfc7638_jwk_thumbprint(jwk)


_SERVICES: dict[str, GatewayTokenService] = {}
_LOCK = threading.Lock()


def get_token_service() -> GatewayTokenService:
    """One service (signing key + replay cache) per environment. Customer environments build it at
    import time (`app.main`), so a missing or unreadable key fails startup, not requests.
    """
    cfg = get_platform_config()
    with _LOCK:
        if cfg.environment not in _SERVICES:
            _SERVICES[cfg.environment] = GatewayTokenService.from_config(cfg)
        return _SERVICES[cfg.environment]


# Backend outages are not the caller's fault: 503, never 401 "invalid token".
UNAVAILABLE_CODES = frozenset(
    {
        "E_DPOP_REPLAY_STORE_UNAVAILABLE",
        "E_DPOP_REPLAY_CACHE_FULL",
        "E_SUBJECT_TOKEN_CACHE_FULL",
    }
)


def gateway_error(code: str) -> HTTPException:
    """401 for token problems; 503 when the server can't check replay (store down or full).

    A 401 with `error="invalid_token"` would make clients discard a valid token and retry.
    """
    if code in UNAVAILABLE_CODES:
        return HTTPException(
            status_code=503,
            detail={"error": code},
            headers={"Retry-After": "10"},
        )
    return unauthorized(code)


def unauthorized(code: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": code},
        headers={
            "WWW-Authenticate": 'DPoP algs="ES256", error="invalid_token"'
        },
    )


def _session_id_for_request(gateway_token_jti: str) -> str:
    """Session identifier bound to the verified gateway token's `jti`.

    All requests using the same gateway token share `sess-{jti}`, so `TokenBucketBulkhead` can
    enforce `max_turns_per_session` across sequential HTTP calls. Nothing the caller sends (such as
    an `X-Session-ID` header) changes it: a caller-chosen key would let a client start a fresh turn
    counter at will.
    """
    return f"sess-{gateway_token_jti}"


def make_require_caller(
    verifier: EdgeAuthVerifier,
) -> Callable[[Request], AsyncIterator[ContextEnvelope]]:
    """FastAPI dependency: the caller's verified envelope, built only from the gateway token.

    Nothing about identity is read from the body, query, or tenancy headers. The request's
    context variable is cleared when the request ends.
    """

    async def require_caller(
        request: Request,
    ) -> AsyncIterator[ContextEnvelope]:
        try:
            claims, proof = get_token_service().verify_request(
                authorization=request.headers.get("authorization", ""),
                dpop=request.headers.get("dpop", ""),
                htm=request.method,
                htu=request_htu(request),
            )
            session_id = _session_id_for_request(claims["jti"])
            # Off the event loop: a cache miss calls KMS (bounded, but up to its deadline). The
            # context variable set inside the worker thread does not propagate back, so it is set
            # again below in this request's own context.
            envelope = await run_in_threadpool(
                verifier.exchange_obo_token,
                verified_idp_claims={
                    "iss": claims["idp_iss"],
                    "sub": claims["sub"],
                    "tenant_id": claims["tenant_id"],
                    "user_role": claims["user_role"],
                    "idp_provider": claims["idp_provider"],
                    "exp": claims["exp"],
                    "jti": claims["jti"],
                },
                dpop_proof={"jkt": proof["jkt"], "jti": proof["jti"]},
                raw_client_headers=dict(request.headers),
                session_id=session_id,
                replay_checked=True,
            )
            _ACTIVE_TENANT_ENVELOPE.set(envelope)
        except GatewayTokenError as exc:
            raise gateway_error(exc.code) from exc
        except (
            ContextSigningUnavailableError
        ) as exc:  # KMS down or slow: 503, no local fallback
            raise HTTPException(
                status_code=503,
                detail={"error": ContextSigningUnavailableError.code},
                headers={"Retry-After": "10"},
            ) from exc
        except (
            PermissionError
        ) as exc:  # e.g. tenant offboarded since the token was issued
            raise unauthorized("E_CALLER_NOT_AUTHORIZED") from exc
        # Logs carry a pseudonymous user reference, never the raw subject or email.
        logger.debug(
            "caller tenant=%s user=%s role=%s",
            envelope.tenant.tenant_id,
            log_user_ref(envelope.tenant.tenant_id, envelope.security.sub),
            envelope.security.user_role,
        )
        try:
            yield envelope
        finally:
            _ACTIVE_TENANT_ENVELOPE.set(None)

    return require_caller


def make_optional_caller(
    verifier: EdgeAuthVerifier,
) -> Callable[[Request], AsyncIterator[ContextEnvelope | None]]:
    """Like `make_require_caller`, but no `Authorization` header yields None (the endpoint then
    answers in its own protocol, e.g. JSON-RPC -32001). A present but invalid token is a 401.
    """
    require = make_require_caller(verifier)

    async def optional_caller(
        request: Request,
    ) -> AsyncIterator[ContextEnvelope | None]:
        if not request.headers.get("authorization"):
            yield None
            return
        inner = require(request)
        envelope = await inner.__anext__()
        try:
            yield envelope
        finally:
            await inner.aclose()

    return optional_caller
