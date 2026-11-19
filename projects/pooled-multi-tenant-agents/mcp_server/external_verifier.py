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

# pylint: disable=broad-exception-caught,import-outside-toplevel,line-too-long

"""Reference verifier for customer-hosted (Hop 5 BYO) MCP servers (ADR-0014 D3).

A customer MCP server receives `Authorization: Bearer <token>` where the token is a context token
the gateway issued for **this server's URL** through its token exchange. The server verifies it
with the gateway's published public keys (JWKS) and then applies its own row-level isolation using
`tenant_id`. No shared secret and no private key are involved anywhere.

This module is deliberately standalone: it imports only PyJWT, `cryptography` and `httpx` (no
`agents.*`), so a customer can copy it as is. Checks:

- header: `typ = ctx+jwt`, `alg = ES256`, a `kid`, and nothing else (no embedded `jwk`/`jku`);
- signature with the JWKS key for that `kid` (P-256 public keys only);
- `iss` = the gateway's context issuer; `aud` = exactly this server's URL (a token for the
  gateway's internal audiences or for another server is refused); `exp` (30 s leeway);
  lifetime <= 5 min + skew; `sub`, `jti`, `tenant_id` present.

JWKS caching honours `Cache-Control: max-age` (capped), refetches on an unknown `kid` at most once
per `min_refetch_seconds`, and serves the last good key set for up to `max_stale_seconds` if the
JWKS endpoint is unreachable; after that verification fails closed (`JwksUnavailable`).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections.abc import Callable
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

logger = logging.getLogger(__name__)

CONTEXT_TOKEN_TYP = "ctx+jwt"
CONTEXT_TOKEN_ISSUER = "https://context.cymbal.internal"
MAX_LIFETIME_SECONDS = 300
CLOCK_SKEW_SECONDS = 30
_ALLOWED_HEADER = frozenset({"alg", "typ", "kid"})
_MAX_AGE_RE = re.compile(r"max-age=(\d+)")


class ExternalTokenRejected(PermissionError):
    """The token is not valid for this server. Answer 401; `code` is safe to return."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class JwksUnavailable(RuntimeError):
    """No usable key set (JWKS unreachable beyond the stale window). Answer 503."""


def parse_max_age(cache_control: str | None, default: int) -> int:
    match = _MAX_AGE_RE.search(cache_control or "")
    return int(match.group(1)) if match else default


def http_jwks_fetcher(
    url: str, *, timeout: float = 5.0
) -> tuple[dict[str, Any], int]:
    """GET the JWKS: (document, max-age seconds)."""
    import httpx

    resp = httpx.get(url, timeout=timeout, follow_redirects=False)
    resp.raise_for_status()
    return resp.json(), parse_max_age(resp.headers.get("cache-control"), 300)


def _load_jwk(jwk: dict[str, Any]) -> ec.EllipticCurvePublicKey | None:
    if (
        not isinstance(jwk, dict)
        or jwk.get("kty") != "EC"
        or jwk.get("crv") != "P-256"
        or "d" in jwk
        or jwk.get("alg", "ES256") != "ES256"
        or not isinstance(jwk.get("kid"), str)
    ):
        return None
    key = jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(jwk))
    return key if isinstance(key, ec.EllipticCurvePublicKey) else None


class JwksCache:
    """kid -> public key, from the gateway's JWKS URL (https only).

    Fetches run outside the lock and are single-flight: while one thread refreshes, others keep
    using the current key set (or wait for the first fetch if there is none yet). One malformed
    JWK is skipped without breaking the rest of the set.
    """

    def __init__(
        self,
        jwks_url: str,
        *,
        fetch: Callable[[str], tuple[dict[str, Any], int]] = http_jwks_fetcher,
        min_refetch_seconds: float = 30.0,
        max_age_cap_seconds: int = 3600,
        max_stale_seconds: float = 600.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not jwks_url.startswith("https://"):
            raise ValueError("the JWKS URL must be https://")
        self._url = jwks_url
        self._fetch = fetch
        self._min_refetch = min_refetch_seconds
        self._cap = max_age_cap_seconds
        self._max_stale = max_stale_seconds
        self._clock = clock
        self._keys: dict[str, ec.EllipticCurvePublicKey] = {}
        self._expires = float("-inf")
        self._last_fetch = float("-inf")
        self._cond = threading.Condition()
        self._fetching = False
        self.fetches = 0

    @staticmethod
    def _parse(doc: Any) -> dict[str, ec.EllipticCurvePublicKey]:
        keys: dict[str, ec.EllipticCurvePublicKey] = {}
        for jwk in doc.get("keys", []) if isinstance(doc, dict) else []:
            try:
                key = _load_jwk(jwk)
            except Exception as exc:
                logger.warning(
                    "skipping malformed JWK (%s)", type(exc).__name__
                )
                continue
            if key is not None:
                keys[jwk["kid"]] = key
        return keys

    def get(self, kid: str) -> ec.EllipticCurvePublicKey | None:
        with self._cond:
            now = self._clock()
            expired = now >= self._expires
            want = (
                expired or kid not in self._keys
            ) and now - self._last_fetch >= self._min_refetch
            if want and not self._fetching:
                self._fetching = True
                self._last_fetch = now
                leader = True
            else:
                leader = False
                while (
                    self._fetching and not self._keys
                ):  # first fetch in flight: wait for it
                    self._cond.wait(timeout=10.0)
        if leader:
            error: Exception | None = None
            keys: dict[str, ec.EllipticCurvePublicKey] = {}
            max_age = 0
            try:
                try:
                    doc, max_age = self._fetch(self._url)  # outside the lock
                    keys = self._parse(doc)
                    if not keys:
                        raise ValueError("JWKS has no usable keys")
                except Exception as exc:
                    error = exc
                with self._cond:
                    self.fetches += 1
                    if error is None:
                        self._keys = keys
                        self._expires = now + min(
                            max(int(max_age), 0), self._cap
                        )
            finally:  # even on BaseException (e.g. KeyboardInterrupt): never leave waiters stuck
                with self._cond:
                    self._fetching = False
                    self._cond.notify_all()
            if error is not None and (
                not self._keys or now >= self._expires + self._max_stale
            ):
                raise JwksUnavailable(
                    f"JWKS unavailable ({type(error).__name__})"
                ) from error
        with self._cond:
            now = self._clock()
            if not self._keys or now >= self._expires + self._max_stale:
                raise JwksUnavailable("JWKS too stale or never loaded")
            return self._keys.get(kid)


class ExternalContextTokenVerifier:
    """What a customer MCP server runs on every request."""

    def __init__(
        self,
        *,
        audience: str,
        jwks: JwksCache,
        issuer: str = CONTEXT_TOKEN_ISSUER,
    ) -> None:
        if not audience:
            raise ValueError(
                "audience (this server's registered URL) is required"
            )
        self.audience = audience
        self._jwks = jwks
        self._issuer = issuer

    def verify(self, token: str) -> dict[str, Any]:
        if (
            not isinstance(token, str)
            or token.count(".") != 2
            or len(token) > 16384
        ):
            raise ExternalTokenRejected("E_TOKEN_MALFORMED")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise ExternalTokenRejected("E_TOKEN_MALFORMED") from exc
        if header.get("typ") != CONTEXT_TOKEN_TYP:
            raise ExternalTokenRejected("E_TOKEN_TYPE")
        if header.get("alg") != "ES256":
            raise ExternalTokenRejected("E_TOKEN_ALG")
        if set(header) - _ALLOWED_HEADER or not isinstance(
            header.get("kid"), str
        ):
            raise ExternalTokenRejected("E_TOKEN_HEADER")
        key = self._jwks.get(header["kid"])
        if key is None:
            raise ExternalTokenRejected("E_TOKEN_UNKNOWN_KID")
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=["ES256"],
                audience=self.audience,
                issuer=self._issuer,
                leeway=CLOCK_SKEW_SECONDS,
                options={
                    "require": [
                        "iss",
                        "sub",
                        "aud",
                        "iat",
                        "exp",
                        "jti",
                        "tenant_id",
                    ]
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExternalTokenRejected("E_TOKEN_EXPIRED") from exc
        except jwt.InvalidAudienceError as exc:
            raise ExternalTokenRejected("E_TOKEN_AUDIENCE") from exc
        except jwt.PyJWTError as exc:
            raise ExternalTokenRejected("E_TOKEN_INVALID") from exc
        aud = claims["aud"]
        if aud != self.audience and aud != [self.audience]:
            raise ExternalTokenRejected(
                "E_TOKEN_AUDIENCE"
            )  # exactly one audience: this server
        try:
            lifetime = int(claims["exp"]) - int(claims["iat"])
        except (TypeError, ValueError) as exc:
            raise ExternalTokenRejected("E_TOKEN_INVALID") from exc
        if not 0 < lifetime <= MAX_LIFETIME_SECONDS + CLOCK_SKEW_SECONDS:
            raise ExternalTokenRejected("E_TOKEN_LIFETIME")
        if not isinstance(claims["tenant_id"], str) or not claims["tenant_id"]:
            raise ExternalTokenRejected("E_TOKEN_INVALID")
        return dict(claims)

    def verify_authorization(self, authorization: str) -> dict[str, Any]:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise ExternalTokenRejected("E_TOKEN_MISSING")
        return self.verify(token.strip())
