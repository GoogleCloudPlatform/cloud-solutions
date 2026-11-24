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

# pylint: disable=broad-exception-caught,import-outside-toplevel
# pylint: disable=inconsistent-quotes,line-too-long,unidiomatic-typecheck

"""Context token verification: public keys only (ADR-0014 D1).

The gateway signs one compact JWS per gateway token (`agents.context_signing`). Every in-process
verifier (the ADK interceptor, sub-agent hops, the MCP wire handler) checks it here with **public
keys only**: this module never imports the signing module and never holds private key material.

Token format::

    header  {"alg": "ES256", "typ": "ctx+jwt", "kid": <key id>}     (no other header fields)
    claims  iss, sub, jti, cnf.jkt, tenant_id, tier, org_unit, thinking_budget, scopes,
            cmek_key_name, user_role, idp_provider, idp_iss, src_jti, session_id,
            max_delegation_depth,
            aud = ["runtime", "mcp"], iat, exp (exp <= the gateway token's exp, <= 10 min)
            optional: agent_id (the agent the gateway routed to; ADR-0016)

`agent_id` is optional while agent-level enforcement is off. With
`CONTEXT_TOKEN_REQUIRE_AGENT_ID=1`, every verifier in that process refuses an internal or derived
token without it. When present it must be a well-formed agent id, on any token.

A verifier requires `typ`, `alg = ES256`, `iss`, its own audience in `aud`, and an unexpired
`exp`. Gateway access tokens (`typ = at+jwt`, gateway key) are never accepted here. Per-turn values
(`trace_id`, `correlation_id`, the requested thinking budget) are not signed and must never drive
an access decision.

Key ring: `kid` is the Cloud KMS key-version resource name. Keys come from KMS `getPublicKey`,
only for versions of the configured key (at most `configured + 2`). Trusted kids refresh on their
own budget and are served stale through KMS blips; unknown kids have a separate, capped budget; a
definitive NOT_FOUND / DISABLED evicts (see `ContextTokenVerifier`).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

logger = logging.getLogger(__name__)

CONTEXT_TOKEN_TYP = "ctx+jwt"
CONTEXT_TOKEN_ALG = "ES256"
CONTEXT_TOKEN_ISSUER = "https://context.cymbal.internal"
AUDIENCE_RUNTIME = "runtime"
AUDIENCE_MCP = "mcp"
DEFAULT_CONTEXT_AUDIENCES = (AUDIENCE_RUNTIME, AUDIENCE_MCP)
CONTEXT_TOKEN_MAX_TTL_SECONDS = (
    600  # hard irrevocable ceiling (ADR-0014 D1 / Amendment A1)
)
# Derived tokens (ADR-0014 D3 exchange): one audience each, never an internal one.
AUDIENCE_BROKER = "broker"
DERIVED_TOKEN_MAX_TTL_SECONDS = 300
# Published at /.well-known/cymbal-context-jwks.json. Rotation overlap must be at least this +
# the max token lifetime (see docs/configuration_reference.md).
JWKS_MAX_AGE_SECONDS = 300
CLOCK_SKEW_SECONDS = 30
DEFAULT_MAX_DELEGATION_DEPTH = 3

# Config: `identity.context_signing_kms_key` (+ `_version`), overridable per deployment.
CONTEXT_SIGNING_KMS_KEY_ENV = "CONTEXT_SIGNING_KMS_KEY"
CONTEXT_SIGNING_KMS_KEY_VERSION_ENV = "CONTEXT_SIGNING_KMS_KEY_VERSION"
_KMS_KEY_RE = re.compile(
    r"projects/[^/]+/locations/[^/]+/keyRings/[^/]+/cryptoKeys/[^/]+"
)
_KMS_VERSION_RE = re.compile(
    _KMS_KEY_RE.pattern + r"/cryptoKeyVersions/[1-9][0-9]{0,8}"
)

_ALLOWED_HEADER_FIELDS = frozenset({"alg", "typ", "kid"})
_REQUIRED_CLAIMS = (
    "iss",
    "sub",
    "aud",
    "iat",
    "exp",
    "jti",
    "cnf",
    "tenant_id",
    "tier",
    "thinking_budget",
    "scopes",
    "cmek_key_name",
    "org_unit",
    "user_role",
    "idp_provider",
    "idp_iss",
    "src_jti",
    "session_id",
    "max_delegation_depth",
)


# Checked by PyJWT for every token, before the audience-specific profile below.
_BASE_REQUIRED_CLAIMS = ("iss", "sub", "aud", "iat", "exp", "jti", "tenant_id")

# Derived (exchanged) tokens carry only what a downstream verifier needs.
_DERIVED_REQUIRED_CLAIMS = (
    "iss",
    "sub",
    "aud",
    "iat",
    "exp",
    "jti",
    "tenant_id",
    "src_jti",
    "max_delegation_depth",
)


AGENT_ID_CLAIM = "agent_id"
REQUIRE_AGENT_ID_ENV = "CONTEXT_TOKEN_REQUIRE_AGENT_ID"
_AGENT_ID_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")


def agent_id_required() -> bool:
    """ADR-0016: verifiers require the signed `agent_id` claim only when this flag is `1`."""
    return os.getenv(REQUIRE_AGENT_ID_ENV, "").strip() == "1"


def _check_agent_id_claim(claims: Mapping[str, Any]) -> None:
    if AGENT_ID_CLAIM not in claims:
        if agent_id_required():
            raise ContextTokenError(
                "E_CONTEXT_TOKEN_AGENT_ID_MISSING", "agent_id is required"
            )
        return
    value = claims[AGENT_ID_CLAIM]
    if not isinstance(value, str) or not _AGENT_ID_RE.fullmatch(value):
        raise ContextTokenError("E_CONTEXT_TOKEN_CLAIMS", "malformed agent_id")


def is_internal_audience(audience: str) -> bool:
    return audience in DEFAULT_CONTEXT_AUDIENCES


class ContextTokenError(PermissionError):
    """A context token was rejected. `code` is a stable `E_CONTEXT_TOKEN_*` code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


# --- JWS helpers (public) -----------------------------------------------------------------------


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def der_to_raw_signature(der: bytes, *, size: int = 32) -> bytes:
    """DER ECDSA signature (what KMS and `cryptography` return) -> JWS raw `r || s` (RFC 7518)."""
    r, s = decode_dss_signature(der)
    if r >= 1 << (8 * size) or s >= 1 << (8 * size):
        raise ValueError("signature component too large for the curve")
    return r.to_bytes(size, "big") + s.to_bytes(size, "big")


def raw_to_der_signature(raw: bytes, *, size: int = 32) -> bytes:
    """JWS raw `r || s` -> DER ECDSA signature."""
    if len(raw) != 2 * size:
        raise ValueError(f"raw ES256 signature must be {2 * size} bytes")
    return encode_dss_signature(
        int.from_bytes(raw[:size], "big"), int.from_bytes(raw[size:], "big")
    )


def load_p256_public_key_pem(pem: str) -> ec.EllipticCurvePublicKey:
    key = serialization.load_pem_public_key(pem.encode())
    if (
        not isinstance(key, ec.EllipticCurvePublicKey)
        or key.curve.name != "secp256r1"
    ):
        raise ValueError("context-signing public key must be EC P-256")
    return key


# --- Config ---------------------------------------------------------------------------------------


def resolve_context_signing_kms_key() -> tuple[str, str] | None:
    """(crypto key, key version) for context signing, or None if none is configured.

    `CONTEXT_SIGNING_KMS_KEY` (env) overrides `identity.context_signing_kms_key`. Either may name a
    key (`.../cryptoKeys/<k>`, version from `CONTEXT_SIGNING_KMS_KEY_VERSION` or
    `identity.context_signing_kms_key_version`, default 1) or a full key version.
    """
    from agents.platform_config import get_platform_config

    ident = get_platform_config().identity
    raw = (
        os.getenv("CONTEXT_SIGNING_KMS_KEY") or ""
    ).strip() or ident.context_signing_kms_key
    if not raw:
        return None
    if _KMS_VERSION_RE.fullmatch(raw):
        return raw.split("/cryptoKeyVersions/")[0], raw
    if not _KMS_KEY_RE.fullmatch(raw):
        raise RuntimeError(
            "E_CONTEXT_SIGNING_KEY_INVALID: context signing key must be "
            "'projects/<p>/locations/<l>/keyRings/<r>/cryptoKeys/<k>[/cryptoKeyVersions/<n>]'"
        )
    version_raw = (os.getenv("CONTEXT_SIGNING_KMS_KEY_VERSION") or "").strip()
    version = (
        int(version_raw)
        if version_raw
        else int(ident.context_signing_kms_key_version)
    )
    if version < 1:
        raise RuntimeError(
            "E_CONTEXT_SIGNING_KEY_INVALID: key version must be >= 1"
        )
    return raw, f"{raw}/cryptoKeyVersions/{version}"


# --- Public key sources ---------------------------------------------------------------------------


class PublicKeySource(Protocol):
    #: False for in-memory sources: the verifier asks them on every lookup (no stale cache).
    cacheable: bool

    def fetch(self, kid: str) -> ec.EllipticCurvePublicKey | None:
        """The public key for `kid`; None if the source definitively does not know (or no longer
        trusts) it. Raises `ContextKeyUnavailableError` when it cannot tell right now.
        """
        ...


class StaticPublicKeySource:
    """An in-memory kid -> public key map (tests, local runs). Holds public keys only."""

    cacheable = False

    def __init__(
        self, keys: Mapping[str, ec.EllipticCurvePublicKey] | None = None
    ) -> None:
        self._keys: dict[str, ec.EllipticCurvePublicKey] = {}
        self._lock = threading.Lock()
        for kid, key in (keys or {}).items():
            self.add(kid, key)

    def add(self, kid: str, key: ec.EllipticCurvePublicKey) -> None:
        if (
            not isinstance(key, ec.EllipticCurvePublicKey)
            or key.curve.name != "secp256r1"
        ):
            raise TypeError(
                "StaticPublicKeySource accepts EC P-256 public keys only"
            )
        with self._lock:
            self._keys[kid] = key

    def remove(self, kid: str) -> None:
        with self._lock:
            self._keys.pop(kid, None)

    def kids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._keys)

    def fetch(self, kid: str) -> ec.EllipticCurvePublicKey | None:
        with self._lock:
            return self._keys.get(kid)


class KmsPublicKeySource:
    """Public keys of one KMS crypto key's versions, via `getPublicKey` (no list permission needed).

    Only kids of the form `<configured key>/cryptoKeyVersions/<n>` with `n <= configured version +
    version_window` are ever fetched, so a token cannot make the verifier fetch arbitrary resources
    or walk unbounded version numbers.

    `fetch` returns None on a definitive answer (version not found, DISABLED or DESTROYED, wrong
    algorithm) and raises `ContextKeyUnavailableError` when KMS is unreachable, slow or refuses
    the caller (IAM); the verifier keeps serving a cached key through the latter.
    """

    cacheable = True

    def __init__(
        self,
        crypto_key: str,
        *,
        configured_version: int | None = None,
        version_window: int = 2,
        client: Any | None = None,
        timeout: float | None = None,
    ) -> None:
        from agents import kms_rest

        if not _KMS_KEY_RE.fullmatch(crypto_key):
            raise ValueError(
                "crypto_key must be a KMS crypto key resource name"
            )
        self.crypto_key = crypto_key
        self.configured_version = configured_version
        self.version_window = version_window
        self._timeout = timeout or kms_rest.DEFAULT_KMS_TIMEOUT_SECONDS
        self._client = client or kms_rest.KmsRestClient(timeout=self._timeout)

    def known_kids(self) -> tuple[str, ...]:
        """The configured signing version: pre-warmed at startup, refreshed on its own budget."""
        if self.configured_version is None:
            return ()
        return (
            f"{self.crypto_key}/cryptoKeyVersions/{self.configured_version}",
        )

    def jwks_kids(self) -> tuple[str, ...]:
        """Versions published in the JWKS: configured - 1 .. configured + 2 (rotation window).

        Listing ENABLED versions would need `cloudkms.cryptoKeyVersions.list`, which
        `roles/cloudkms.signerVerifier` lacks; probing this window needs only `viewPublicKey`.
        """
        if self.configured_version is None:
            return ()
        lo = max(1, self.configured_version - 1)
        hi = self.configured_version + self.version_window
        return tuple(
            f"{self.crypto_key}/cryptoKeyVersions/{n}"
            for n in range(lo, hi + 1)
        )

    def accepts(self, kid: str) -> bool:
        """Checked before any rate limit, so junk kids never consume a fetch budget."""
        if not (
            _KMS_VERSION_RE.fullmatch(kid)
            and kid.startswith(self.crypto_key + "/")
        ):
            return False
        if self.configured_version is None:
            return True
        version = int(kid.rsplit("/", 1)[1])
        return version <= self.configured_version + self.version_window

    def fetch(self, kid: str) -> ec.EllipticCurvePublicKey | None:
        from agents import kms_rest

        if not self.accepts(kid):
            return None
        try:
            pem, algorithm = kms_rest.run_with_deadline(
                lambda: self._client.get_public_key(name=kid), self._timeout
            )
        except kms_rest.KmsKeyRejectedError as exc:
            logger.warning(
                "context key %s rejected by KMS (%s): evicting", kid, exc
            )
            return None
        except kms_rest.KmsUnavailableError as exc:
            raise ContextKeyUnavailableError(
                f"public key fetch for {kid} failed ({exc})"
            ) from exc
        if algorithm != kms_rest.EC_SIGN_P256_SHA256:
            logger.error(
                "context key %s has algorithm %s, refusing it", kid, algorithm
            )
            return None
        try:
            return load_p256_public_key_pem(pem)
        except ValueError:
            logger.error(
                "context key %s is not an EC P-256 public key, refusing it", kid
            )
            return None


# --- Verifier -------------------------------------------------------------------------------------


class ContextKeyUnavailableError(RuntimeError):
    """The verifier could not obtain a trusted public key right now (KMS outage). HTTP 503.

    Not a `PermissionError`: an outage is not a forgery, and callers must not report it as one.
    """

    code = "E_CONTEXT_KEY_UNAVAILABLE"

    def __init__(self, detail: str = "") -> None:
        super().__init__(f"{self.code}: {detail}" if detail else self.code)


class ContextTokenVerifier:
    """Verifies context tokens with a kid -> public key ring. Cannot sign.

    Key ring policy (cacheable sources such as KMS):
    - A cached key is fresh for `key_cache_ttl_seconds`; after that it is refreshed on demand.
    - **Serve-stale:** if a refresh fails transiently, the cached key keeps verifying for up to
      `max_stale_seconds` beyond the TTL. Only a definitive answer (not found / DISABLED /
      DESTROYED) evicts a kid.
    - **Separate budgets:** kids the verifier already trusts (cached) or is configured to trust
      (`source.known_kids()`) refresh on a per-kid interval only, so a flood of unknown kids can
      never starve them. Unknown kids are limited per kid and by a global per-minute cap.
    - The per-kid attempt table is pruned and bounded.
    """

    _MAX_ATTEMPT_ENTRIES = 1024

    def __init__(
        self,
        source: PublicKeySource,
        *,
        issuer: str = CONTEXT_TOKEN_ISSUER,
        key_cache_ttl_seconds: float = 300.0,
        max_stale_seconds: float = 600.0,
        refetch_interval_seconds: float = 30.0,
        max_fetches_per_minute: int = 10,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._source = source
        self._issuer = issuer
        self._ttl = key_cache_ttl_seconds
        self._max_stale = max_stale_seconds
        self._refetch_interval = refetch_interval_seconds
        self._max_unknown_fetches = max_fetches_per_minute
        self._clock = clock
        self._ring: dict[str, tuple[ec.EllipticCurvePublicKey, float]] = {}
        self._last_attempt: OrderedDict[str, float] = OrderedDict()
        self._unknown_fetch_times: list[float] = []
        self._lock = threading.Lock()

    @property
    def source(self) -> PublicKeySource:
        return self._source

    def _known(self, kid: str) -> bool:
        known = getattr(self._source, "known_kids", None)
        return kid in self._ring or (known is not None and kid in known())

    def _record_attempt(self, kid: str, now: float) -> None:
        self._last_attempt.pop(kid, None)
        self._last_attempt[kid] = now
        while self._last_attempt:
            oldest_kid, oldest = next(iter(self._last_attempt.items()))
            if now - oldest < self._refetch_interval and (
                len(self._last_attempt) <= self._MAX_ATTEMPT_ENTRIES
            ):
                break
            self._last_attempt.pop(oldest_kid)

    def _may_fetch(self, kid: str, now: float) -> bool:
        """Rate limits, under the lock. Known kids: per-kid interval only. Unknown: + global cap."""
        if (
            now - self._last_attempt.get(kid, float("-inf"))
            < self._refetch_interval
        ):
            return False
        if not self._known(kid):
            self._unknown_fetch_times = [
                t for t in self._unknown_fetch_times if now - t < 60.0
            ]
            if len(self._unknown_fetch_times) >= self._max_unknown_fetches:
                logger.warning(
                    "unknown-kid refetch limit reached; refusing kid %s", kid
                )
                return False
            self._unknown_fetch_times.append(now)
        self._record_attempt(kid, now)
        return True

    def _key_for(self, kid: str) -> ec.EllipticCurvePublicKey | None:
        if not getattr(self._source, "cacheable", True):
            return self._source.fetch(kid)
        accepts = getattr(self._source, "accepts", None)
        if accepts is not None and not accepts(kid):
            return None  # junk kids never consume a fetch budget
        now = self._clock()
        with self._lock:
            cached = self._ring.get(kid)
            if cached and now - cached[1] < self._ttl:
                return cached[0]
            stale_ok = (
                cached is not None
                and now - cached[1] < self._ttl + self._max_stale
            )
            known = self._known(kid)
            if not self._may_fetch(kid, now):
                if stale_ok:
                    return cached[0]  # type: ignore[index]
                if known:
                    raise ContextKeyUnavailableError(
                        f"refresh of {kid} is rate-limited"
                    )
                return None
        try:
            key = self._source.fetch(kid)
        except ContextKeyUnavailableError:
            if stale_ok:
                logger.warning(
                    "context key refresh failed for %s; serving the cached key",
                    kid,
                )
                return cached[0]  # type: ignore[index]
            raise
        with self._lock:
            if key is None:
                self._ring.pop(
                    kid, None
                )  # definitive: not found / disabled / destroyed
            else:
                self._ring[kid] = (key, now)
                self._last_attempt.pop(kid, None)
        return key

    def may_block(self, token: str) -> bool:
        """True if verifying `token` could need a network fetch (its kid is not freshly cached).

        Async callers offload only those verifications to a worker thread; the common case (a
        fresh cached key, or an in-memory source) stays on the event loop with no thread hop.
        """
        if not getattr(self._source, "cacheable", True):
            return False
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except (jwt.PyJWTError, AttributeError, TypeError):
            return False  # malformed: rejected without any fetch
        with self._lock:
            cached = self._ring.get(kid) if isinstance(kid, str) else None
            return cached is None or self._clock() - cached[1] >= self._ttl

    def published_keys(self) -> dict[str, ec.EllipticCurvePublicKey]:
        """Every currently usable signing key, for the JWKS endpoint (public keys only).

        In-memory sources: all their kids. KMS: the source's JWKS window (no list permission
        needed); other versions that are missing or DISABLED are omitted. If the configured
        (signing) version is unavailable, missing or DISABLED, `ContextKeyUnavailableError`
        propagates (fail closed: 503). Probing the window uses the unknown-kid fetch budget
        (bounded: per-kid interval + global cap).
        """
        source = self._source
        if not getattr(source, "cacheable", True):
            kids = getattr(source, "kids", lambda: ())()
            return {
                kid: key
                for kid in kids
                if (key := source.fetch(kid)) is not None
            }
        known = set(getattr(source, "known_kids", lambda: ())())
        out: dict[str, ec.EllipticCurvePublicKey] = {}
        for kid in getattr(source, "jwks_kids", lambda: tuple(known))():
            try:
                key = self._key_for(kid)
            except ContextKeyUnavailableError:
                if kid in known:
                    raise
                continue
            if key is not None:
                out[kid] = key
            elif (
                kid in known
            ):  # the signing version is missing or DISABLED: misconfigured
                raise ContextKeyUnavailableError(
                    f"configured context key {kid} is not usable"
                )
        return out

    def is_warm(self) -> bool:
        """True once every configured kid has been loaded at least once (or nothing to warm)."""
        known = getattr(self._source, "known_kids", None)
        kids = (
            known()
            if known is not None and getattr(self._source, "cacheable", True)
            else ()
        )
        with self._lock:
            return all(kid in self._ring for kid in kids)

    def prewarm(self, *, quiet: bool = False) -> bool:
        """Fetches the configured kid(s) now; True if all loaded. Never raises.

        Best effort only: a failure is logged at WARNING (DEBUG when `quiet`, for retries) and does
        **not** consume the kid's refetch budget, so the first request that needs the key fetches
        it on demand immediately. Verification stays fail-closed either way. A definitive answer
        (version not found / DISABLED) is a misconfiguration and is logged at ERROR.
        """
        known = getattr(self._source, "known_kids", None)
        ok = True
        for kid in known() if known is not None else ():
            try:
                if self._key_for(kid) is None:
                    ok = False
                    logger.error(
                        "context key %s is not usable (not found or disabled)",
                        kid,
                    )
            except Exception as exc:
                ok = False
                with self._lock:
                    if kid not in self._ring:
                        self._last_attempt.pop(
                            kid, None
                        )  # leave the budget to on-demand fetch
                logger.log(
                    logging.DEBUG if quiet else logging.WARNING,
                    "context key prewarm did not complete for %s (%s); verification will fetch "
                    "the key on demand (still fail-closed)",
                    kid,
                    exc,
                )
        return ok

    def verify(self, token: str, *, audience: str) -> dict[str, Any]:
        """Claims of a valid context token for `audience`.

        Raises `ContextTokenError` (a `PermissionError`) for a bad token and
        `ContextKeyUnavailableError` when the key cannot be obtained right now.
        """
        if not audience:
            raise ValueError("audience is required")
        internal = is_internal_audience(audience)
        if (
            not isinstance(token, str)
            or token.count(".") != 2
            or len(token) > 16384
        ):
            raise ContextTokenError("E_CONTEXT_TOKEN_MALFORMED")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise ContextTokenError("E_CONTEXT_TOKEN_MALFORMED") from exc
        if header.get("typ") != CONTEXT_TOKEN_TYP:
            raise ContextTokenError(
                "E_CONTEXT_TOKEN_TYPE", f"typ {header.get('typ')!r}"
            )
        if header.get("alg") != CONTEXT_TOKEN_ALG:
            raise ContextTokenError(
                "E_CONTEXT_TOKEN_ALG", f"alg {header.get('alg')!r}"
            )
        if set(header) - _ALLOWED_HEADER_FIELDS:
            raise ContextTokenError(
                "E_CONTEXT_TOKEN_HEADER", "unexpected header fields"
            )
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid or len(kid) > 512:
            raise ContextTokenError("E_CONTEXT_TOKEN_UNKNOWN_KID")
        key = self._key_for(kid)
        if key is None:
            raise ContextTokenError("E_CONTEXT_TOKEN_UNKNOWN_KID")
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[CONTEXT_TOKEN_ALG],
                audience=audience,
                issuer=self._issuer,
                leeway=CLOCK_SKEW_SECONDS,
                options={"require": list(_BASE_REQUIRED_CLAIMS)},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ContextTokenError("E_CONTEXT_TOKEN_EXPIRED") from exc
        except jwt.InvalidAudienceError as exc:
            raise ContextTokenError("E_CONTEXT_TOKEN_AUDIENCE") from exc
        except jwt.InvalidIssuerError as exc:
            raise ContextTokenError("E_CONTEXT_TOKEN_ISSUER") from exc
        except jwt.InvalidSignatureError as exc:
            raise ContextTokenError("E_CONTEXT_TOKEN_SIGNATURE") from exc
        except jwt.PyJWTError as exc:
            raise ContextTokenError(
                "E_CONTEXT_TOKEN_INVALID", type(exc).__name__
            ) from exc
        # Audience was checked by PyJWT above; now the claim profile for that kind of audience.
        required = _REQUIRED_CLAIMS if internal else _DERIVED_REQUIRED_CLAIMS
        if any(name not in claims for name in required):
            raise ContextTokenError(
                "E_CONTEXT_TOKEN_CLAIMS", "missing required claims"
            )
        if internal:
            _check_claim_shapes(claims)
        else:
            _check_derived_claim_shapes(claims, audience)
        _check_agent_id_claim(claims)
        return dict(claims)


class ContextKeyWarmer:
    """Opportunistic, non-blocking prewarm of the configured context key.

    Cloud Run throttles CPU outside requests, so the startup prewarm can time out. `kick()` is
    called at startup and on incoming requests (while CPU is allocated): until the key has loaded
    once, it starts at most one background attempt per `min_interval_seconds`. Only the first
    failure is logged at WARNING; retries log at DEBUG. Once warm it does nothing. It never blocks
    the caller and never changes verification (on-demand fetch stays fail-closed).
    """

    def __init__(
        self,
        get_verifier: Callable[[], ContextTokenVerifier],
        *,
        min_interval_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        spawn: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self._get_verifier = get_verifier
        self._interval = min_interval_seconds
        self._clock = clock
        self._spawn = spawn or (
            lambda fn: threading.Thread(
                target=fn, name="ctx-key-prewarm", daemon=True
            ).start()
        )
        self._lock = threading.Lock()
        self._warm = False
        self._in_flight = False
        self._last = float("-inf")
        self.attempts = 0

    @property
    def warm(self) -> bool:
        return self._warm

    def kick(self) -> None:
        if self._warm:
            return
        with self._lock:
            now = self._clock()
            if (
                self._warm
                or self._in_flight
                or now - self._last < self._interval
            ):
                return
            self._in_flight = True
            self._last = now
        self._spawn(self._run)

    def _run(self) -> None:
        try:
            verifier = self._get_verifier()
            ok = verifier.prewarm(quiet=self.attempts > 0) or verifier.is_warm()
        except Exception as exc:
            ok = False
            logger.log(
                logging.DEBUG if self.attempts else logging.WARNING,
                "context key prewarm skipped (%s); verification will fetch on demand",
                exc,
            )
        with self._lock:
            self.attempts += 1
            self._warm = ok
            self._in_flight = False


def _check_claim_shapes(claims: Mapping[str, Any]) -> None:
    try:
        lifetime = int(claims["exp"]) - int(claims["iat"])
        ok = (
            0 < lifetime <= CONTEXT_TOKEN_MAX_TTL_SECONDS + CLOCK_SKEW_SECONDS
            and isinstance(claims["tenant_id"], str)
            and bool(claims["tenant_id"])
            and isinstance(claims["scopes"], list)
            and all(isinstance(s, str) for s in claims["scopes"])
            and type(claims["thinking_budget"]) is int
            and type(claims["max_delegation_depth"]) is int
            and isinstance(claims["cnf"], dict)
            and isinstance(claims["cnf"].get("jkt"), str)
        )
    except (KeyError, TypeError, ValueError):
        ok = False
    if not ok:
        raise ContextTokenError("E_CONTEXT_TOKEN_CLAIMS", "malformed claims")


def _check_derived_claim_shapes(
    claims: Mapping[str, Any], audience: str
) -> None:
    """Exchanged tokens: exactly one audience (the requested one), at most 5 minutes."""
    try:
        lifetime = int(claims["exp"]) - int(claims["iat"])
        aud = claims["aud"]
        ok = (
            0 < lifetime <= DERIVED_TOKEN_MAX_TTL_SECONDS + CLOCK_SKEW_SECONDS
            and (aud == audience or aud == [audience])
            and isinstance(claims["tenant_id"], str)
            and bool(claims["tenant_id"])
            and type(claims["max_delegation_depth"]) is int
        )
    except (KeyError, TypeError, ValueError):
        ok = False
    if not ok:
        raise ContextTokenError(
            "E_CONTEXT_TOKEN_CLAIMS", "malformed derived-token claims"
        )


def public_key_to_jwk(
    kid: str, key: ec.EllipticCurvePublicKey
) -> dict[str, str]:
    """RFC 7517 JWK for a P-256 public key (never includes private material)."""
    numbers = key.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": b64url(numbers.x.to_bytes(32, "big")),
        "y": b64url(numbers.y.to_bytes(32, "big")),
        "kid": kid,
        "alg": CONTEXT_TOKEN_ALG,
        "use": "sig",
    }


# --- Process-wide default verifier ---------------------------------------------------------------

_DEFAULT_LOCK = threading.Lock()
_DEFAULT_VERIFIER: ContextTokenVerifier | None = None
_INSTALLED_SOURCE: PublicKeySource | None = None


def install_public_key_source(source: PublicKeySource | None) -> None:
    """Sets the process's trusted context-signing public keys (local/test signer wiring).

    Production leaves this unset and trusts the configured KMS key's versions.
    """
    global _DEFAULT_VERIFIER, _INSTALLED_SOURCE
    with _DEFAULT_LOCK:
        _INSTALLED_SOURCE = source
        _DEFAULT_VERIFIER = None


def get_context_verifier() -> ContextTokenVerifier:
    """The process verifier: an installed public-key source, else the configured KMS key."""
    global _DEFAULT_VERIFIER
    with _DEFAULT_LOCK:
        if _DEFAULT_VERIFIER is None:
            if _INSTALLED_SOURCE is not None:
                _DEFAULT_VERIFIER = ContextTokenVerifier(_INSTALLED_SOURCE)
            else:
                resolved = resolve_context_signing_kms_key()
                if resolved is None:
                    raise ContextTokenError(
                        "E_CONTEXT_VERIFIER_UNCONFIGURED",
                        "no context-signing key configured",
                    )
                key, version = resolved
                _DEFAULT_VERIFIER = ContextTokenVerifier(
                    KmsPublicKeySource(
                        key, configured_version=int(version.rsplit("/", 1)[1])
                    )
                )
        return _DEFAULT_VERIFIER


def unverified_claims(token: str) -> dict[str, Any]:
    """Claims WITHOUT verification: for logs and display only, never for access decisions."""
    payload = token.split(".")[1]
    return dict(
        json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
    )
