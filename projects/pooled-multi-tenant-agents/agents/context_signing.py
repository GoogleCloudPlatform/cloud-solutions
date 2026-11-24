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

"""Context token signing: gateway side only (ADR-0014 D1).

The gateway signs one ES256 context token (`typ = ctx+jwt`) per gateway token; verifiers in
`agents.context_token` hold public keys only. Two signers implement `ContextTokenSigner`:

- `KmsContextSigner`: Cloud KMS `asymmetricSign` with a non-exportable `EC_SIGN_P256_SHA256` key.
  `kid` is the key-version resource name. Every call has a hard deadline; any KMS error or timeout
  raises `ContextSigningUnavailableError`, which the gateway answers with HTTP 503. There is no
  fallback to a local key.
- `LocalTestSigner`: a P-256 key generated in memory per process. Allowed only
  (a) under pytest (installed by the test suite's `pytest_configure` hook), or
  (b) for offline local runs (`make serve`, demo and simulation scripts) when
      `CYMBAL_LOCAL_CONTEXT_SIGNER=1` *and* the config is the synthetic `sandbox` environment *and*
      the process is not on a managed runtime (none of `MANAGED_RUNTIME_ENV`: `K_SERVICE`,
      `CLOUD_RUN_JOB`, `KUBERNETES_SERVICE_HOST`; the same list `app.auth` uses).
  Anything else refuses to start, so the hosted service always signs with KMS.

Which signer: an explicitly installed one (tests), else the local signer if requested and allowed
(a refused request is a startup error, never a silent downgrade), else KMS if
`identity.context_signing_kms_key` / `CONTEXT_SIGNING_KMS_KEY` is set, else startup fails
(`E_CONTEXT_SIGNING_KEY_MISSING`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, Protocol

from agents import context_token as ct
from agents import kms_rest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

logger = logging.getLogger(__name__)

LOCAL_CONTEXT_SIGNER_ENV = "CYMBAL_LOCAL_CONTEXT_SIGNER"


class ContextSigningUnavailableError(RuntimeError):
    """The context-signing key could not be used (KMS error or timeout). Maps to HTTP 503.

    Deliberately not a `PermissionError`: it is an outage, not a denial of the caller.
    """

    code = "E_CONTEXT_SIGNING_UNAVAILABLE"


class ContextTokenSigner(Protocol):
    @property
    def kid(self) -> str: ...

    def sign(self, signing_input: bytes) -> bytes:
        """JWS ES256 signature (raw `r || s`, 64 bytes) over `signing_input`."""
        ...


class KmsContextSigner:
    """Signs with a Cloud KMS asymmetric key version (EC_SIGN_P256_SHA256). Holds no key
    material.
    """

    def __init__(
        self,
        key_version: str,
        *,
        client: kms_rest.KmsClient | None = None,
        timeout: float = kms_rest.DEFAULT_KMS_TIMEOUT_SECONDS,
    ) -> None:
        if not ct._KMS_VERSION_RE.fullmatch(key_version):
            raise ValueError(
                "key_version must be a KMS cryptoKeyVersions resource name"
            )
        self._kid = key_version
        self._timeout = timeout
        # No network at construction: the service starts even before KMS is reachable.
        self._client = client or kms_rest.KmsRestClient(timeout=timeout)

    @property
    def kid(self) -> str:
        return self._kid

    def sign(self, signing_input: bytes) -> bytes:
        digest = hashlib.sha256(signing_input).digest()
        try:
            der = kms_rest.run_with_deadline(
                lambda: self._client.asymmetric_sign(
                    name=self._kid, digest_sha256=digest
                ),
                self._timeout,
            )
            return ct.der_to_raw_signature(der)
        except (
            Exception
        ) as exc:  # any failure: fail closed, never fall back to a local key
            logger.error(
                "ALERT context signing failed via KMS (%s): requests get 503",
                type(exc).__name__,
            )
            raise ContextSigningUnavailableError(
                f"{ContextSigningUnavailableError.code}: {type(exc).__name__}"
            ) from exc


# --- Local signer gating --------------------------------------------------------------------------

_PYTEST_MODE = False


def _local_offline_run_allowed() -> tuple[bool, str]:
    from agents.platform_config import MANAGED_RUNTIME_ENV, get_platform_config

    cfg = get_platform_config()
    managed = [v for v in MANAGED_RUNTIME_ENV if os.getenv(v)]
    if managed:
        return (
            False,
            f"running on a managed runtime (Cloud Run / GKE: {', '.join(managed)})",
        )
    if cfg.environment != "sandbox" or cfg.data_classification != "synthetic":
        return (
            False,
            f"environment {cfg.environment!r} is not the synthetic sandbox",
        )
    return True, ""


def local_signer_allowed() -> bool:
    return _PYTEST_MODE or (
        os.getenv("CYMBAL_LOCAL_CONTEXT_SIGNER") == "1"
        and _local_offline_run_allowed()[0]
    )


class LocalTestSigner:
    """TESTS / OFFLINE SANDBOX ONLY: an in-memory P-256 key generated per process.

    Supports `rotate()` and `retire()` so tests can exercise kid overlap and removal.
    """

    def __init__(self) -> None:
        if not local_signer_allowed():
            raise RuntimeError(
                "E_LOCAL_CONTEXT_SIGNER_REFUSED: the local context signer is allowed only under "
                "pytest or with "
                f"{LOCAL_CONTEXT_SIGNER_ENV}"
                "=1 in the synthetic sandbox off Cloud Run"
            )
        self.public_keys = ct.StaticPublicKeySource()
        self._lock = threading.Lock()
        self._key, self._kid = self._new_key()

    def _new_key(self) -> tuple[ec.EllipticCurvePrivateKey, str]:
        key = ec.generate_private_key(ec.SECP256R1())
        kid = f"local-test-{uuid.uuid4().hex[:12]}"
        self.public_keys.add(kid, key.public_key())
        return key, kid

    @property
    def kid(self) -> str:
        return self._kid

    def sign(self, signing_input: bytes) -> bytes:
        with self._lock:
            key = self._key
        return ct.der_to_raw_signature(
            key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        )

    def rotate(self) -> str:
        """Signs with a new key from now on; the old kid stays trusted until `retire()`."""
        with self._lock:
            self._key, self._kid = self._new_key()
            return self._kid

    def retire(self, kid: str) -> None:
        if kid == self._kid:
            raise ValueError("cannot retire the active signing kid")
        self.public_keys.remove(kid)


# --- Issuer: claims, JWS assembly and the per-gateway-token cache --------------------------------


class ContextTokenIssuer:
    """Builds and signs context tokens; caches one per (gateway-token jti, signed claims).

    Context tokens cannot be revoked once signed, so each token's lifetime stays capped at
    `min(gateway_exp, now + max_ttl_seconds)` (`600` s default, ADR-0014 D1 / Amendment A1). When a
    gateway session token lasts longer than `600` s, `issue()` transparently signs a fresh context
    token once the cached one nears expiry.
    """

    def __init__(
        self,
        signer: ContextTokenSigner,
        *,
        issuer: str = ct.CONTEXT_TOKEN_ISSUER,
        max_ttl_seconds: int = ct.CONTEXT_TOKEN_MAX_TTL_SECONDS,
        cache_max_entries: int = 4096,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not 1 <= int(max_ttl_seconds) <= ct.CONTEXT_TOKEN_MAX_TTL_SECONDS:
            raise ValueError(
                f"max_ttl_seconds must be between 1 and {ct.CONTEXT_TOKEN_MAX_TTL_SECONDS}"
            )
        self.signer = signer
        self._issuer = issuer
        self._max_ttl = int(max_ttl_seconds)
        self._cache_max = cache_max_entries
        self._clock = clock
        self._cache: OrderedDict[str, tuple[str, dict[str, Any]]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()
        self.sign_count = 0

    @property
    def max_ttl_seconds(self) -> int:
        """Hard upper bound (`<= 600` s) applied to every issued internal context token."""
        return self._max_ttl

    def issue(
        self, *, source_jti: str, not_after: int, **claims: Any
    ) -> tuple[str, dict[str, Any]]:
        """(token, claims). `exp <= min(not_after, now + CONTEXT_TOKEN_MAX_TTL_SECONDS)`.

        Tenant config changes alter the signed claims and therefore the cache key, so a stale
        token is never reused for changed claims.
        """
        core = {
            **claims,
            "src_jti": source_jti,
            "aud": list(ct.DEFAULT_CONTEXT_AUDIENCES),
        }
        canonical = json.dumps(core, sort_keys=True, separators=(",", ":"))
        kid = self.signer.kid
        cache_key = hashlib.sha256(
            f"{kid}\x00{source_jti}\x00{canonical}".encode()
        ).hexdigest()
        now = int(self._clock())
        with self._lock:
            hit = self._cache.get(cache_key)
            if hit and int(hit[1]["exp"]) - now > ct.CLOCK_SKEW_SECONDS // 6:
                self._cache.move_to_end(cache_key)
                return hit
        effective_cap = min(self._max_ttl, ct.CONTEXT_TOKEN_MAX_TTL_SECONDS)
        exp = min(int(not_after), now + effective_cap)
        if exp <= now:
            raise PermissionError(
                "E_CONTEXT_TOKEN_SOURCE_EXPIRED: the source token has expired"
            )
        token, full = self._sign_claims(
            core, kid=kid, now=now, exp=exp, jti_prefix="ctx"
        )
        with self._lock:
            self.sign_count += 1
            self._cache[cache_key] = (token, full)
            self._cache.move_to_end(cache_key)
            for key in [
                k for k, (_, c) in self._cache.items() if int(c["exp"]) <= now
            ]:
                self._cache.pop(key, None)
            while len(self._cache) > self._cache_max:
                self._cache.popitem(last=False)
        return token, full

    def issue_derived(
        self,
        *,
        audience: str,
        not_after: int,
        max_ttl_seconds: int,
        **claims: Any,
    ) -> tuple[str, dict[str, Any]]:
        """A single-audience derived token (ADR-0014 D3 exchange): fresh `jti`, never cached.

        `exp = min(not_after, now + max_ttl_seconds)`. Internal audiences are refused here too.
        """
        if not audience or ct.is_internal_audience(audience):
            raise PermissionError(
                "E_EXCHANGE_AUDIENCE_INTERNAL: derived tokens never get aud=runtime/mcp"
            )
        now = int(self._clock())
        exp = min(int(not_after), now + int(max_ttl_seconds))
        if exp <= now:
            raise PermissionError(
                "E_CONTEXT_TOKEN_SOURCE_EXPIRED: the source token has expired"
            )
        token, full = self._sign_claims(
            {**claims, "aud": audience},
            kid=self.signer.kid,
            now=now,
            exp=exp,
            jti_prefix="xctx",
        )
        with self._lock:
            self.sign_count += 1
        return token, full

    def _sign_claims(
        self,
        core: dict[str, Any],
        *,
        kid: str,
        now: int,
        exp: int,
        jti_prefix: str,
    ) -> tuple[str, dict[str, Any]]:
        full = {
            **core,
            "iss": self._issuer,
            "jti": f"{jti_prefix}-{uuid.uuid4().hex}",
            "iat": now,
            "exp": exp,
        }
        header = {
            "alg": ct.CONTEXT_TOKEN_ALG,
            "kid": kid,
            "typ": ct.CONTEXT_TOKEN_TYP,
        }
        signing_input = (
            ct.b64url(
                json.dumps(
                    header, separators=(",", ":"), sort_keys=True
                ).encode()
            )
            + "."
            + ct.b64url(
                json.dumps(full, separators=(",", ":"), sort_keys=True).encode()
            )
        )
        signature = self.signer.sign(signing_input.encode("ascii"))
        if len(signature) != 64:
            raise ContextSigningUnavailableError(
                f"{ContextSigningUnavailableError.code}: signer returned a malformed signature"
            )
        return f"{signing_input}.{ct.b64url(signature)}", full


# --- Process-wide default issuer -----------------------------------------------------------------

_ISSUER_LOCK = threading.Lock()
_ISSUER: ContextTokenIssuer | None = None


def install_context_signer(
    signer: ContextTokenSigner | None,
) -> ContextTokenIssuer | None:
    """Sets (or clears) the process signer. A `LocalTestSigner`'s public keys become trusted."""
    global _ISSUER
    with _ISSUER_LOCK:
        _ISSUER = ContextTokenIssuer(signer) if signer is not None else None
        ct.install_public_key_source(
            signer.public_keys if isinstance(signer, LocalTestSigner) else None
        )
        return _ISSUER


def install_local_test_signer_for_pytest() -> LocalTestSigner:
    """Called from the test suite's `pytest_configure` hook only (never on a plain import)."""
    global _PYTEST_MODE
    _PYTEST_MODE = True
    signer = LocalTestSigner()
    install_context_signer(signer)
    return signer


def enable_offline_local_signer() -> None:
    """Offline demo/simulation scripts: request the local signer (still gated at first use) and
    opt in to local sandbox mode (dev issuer, demo endpoints: `app.auth.sandbox_mode_active`).
    """
    from agents.platform_config import LOCAL_SANDBOX_ENV

    os.environ.setdefault("CYMBAL_LOCAL_CONTEXT_SIGNER", "1")
    os.environ.setdefault(LOCAL_SANDBOX_ENV, "1")


def _build_default_issuer() -> ContextTokenIssuer:
    if os.getenv("CYMBAL_LOCAL_CONTEXT_SIGNER") == "1":
        allowed, why = _local_offline_run_allowed()
        if not allowed:
            raise RuntimeError(
                f"E_LOCAL_CONTEXT_SIGNER_REFUSED: {LOCAL_CONTEXT_SIGNER_ENV}=1 but {why}; unset "
                "it and configure identity.context_signing_kms_key"
            )
        logger.warning(
            "LOCAL CONTEXT SIGNER (offline synthetic sandbox): ephemeral per-process key; "
            "the hosted service signs with Cloud KMS."
        )
        signer = LocalTestSigner()
        ct.install_public_key_source(signer.public_keys)
        return ContextTokenIssuer(signer)
    resolved = ct.resolve_context_signing_kms_key()
    if resolved is None:
        raise RuntimeError(
            "E_CONTEXT_SIGNING_KEY_MISSING: set identity.context_signing_kms_key (or "
            f"{ct.CONTEXT_SIGNING_KMS_KEY_ENV}); there is no built-in context-signing key"
        )
    logger.info("Context tokens signed with KMS key version %s", resolved[1])
    return ContextTokenIssuer(KmsContextSigner(resolved[1]))


def get_context_token_issuer() -> ContextTokenIssuer:
    """The process issuer. Raises at first use (startup in `app.main`) if misconfigured."""
    global _ISSUER
    with _ISSUER_LOCK:
        if _ISSUER is None:
            _ISSUER = _build_default_issuer()
        return _ISSUER
