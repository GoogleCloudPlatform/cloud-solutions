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

"""Context-token public keys from the gateway's internal JWKS route (ADR-0014 B5, plan S1).

The agent runtime services verify context tokens with public keys only. By default they read the
public key of the configured KMS signing key (`KmsPublicKeySource`, needs `viewPublicKey`). If an
agent-identity service can't call KMS, set `CONTEXT_JWKS_URL` instead: keys then come from the
gateway's `/internal/v1/context-jwks`, called with this service's own ID token.

Public keys are not secret; the caller check on that route is defence in depth. A JWKS outage is a
`ContextKeyUnavailableError` (HTTP 503), never an accepted token.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agents.context_token import ContextKeyUnavailableError
from cryptography.hazmat.primitives.asymmetric import ec
from mcp_server.external_verifier import (
    JwksCache,
    JwksUnavailable,
    parse_max_age,
)

CONTEXT_JWKS_URL_ENV = "CONTEXT_JWKS_URL"
CALLER_TOKEN_HEADER = "X-Cymbal-Caller-Token"


def authenticated_jwks_fetcher(
    id_token_provider: Callable[[str], str],
    *,
    audience: str,
    http_get: Callable[..., Any] | None = None,
    timeout: float = 5.0,
) -> Callable[[str], tuple[dict[str, Any], int]]:
    """GET the JWKS with this service's ID token (audience = the gateway's JWKS audience)."""

    def fetch(url: str) -> tuple[dict[str, Any], int]:
        get = http_get
        if get is None:
            import httpx

            get = httpx.get
        token = id_token_provider(audience)
        resp = get(
            url,
            headers={CALLER_TOKEN_HEADER: f"Bearer {token}"},
            timeout=timeout,
            follow_redirects=False,
        )
        resp.raise_for_status()
        return resp.json(), parse_max_age(
            resp.headers.get("cache-control"), 300
        )

    return fetch


class JwksPublicKeySource:
    """`PublicKeySource` backed by a `JwksCache` (single-flight refresh, bounded staleness).

    Not cacheable by the verifier: `JwksCache` already caches per the JWKS `max-age`, so a kid the
    gateway stops publishing stops verifying when that cache refreshes."""

    cacheable = False

    def __init__(self, cache: JwksCache) -> None:
        self._cache = cache

    def known_kids(self) -> tuple[str, ...]:
        return ()

    def jwks_kids(self) -> tuple[str, ...]:
        return ()

    def accepts(self, kid: str) -> bool:
        return isinstance(kid, str) and 0 < len(kid) <= 512

    def fetch(self, kid: str) -> ec.EllipticCurvePublicKey | None:
        try:
            return self._cache.get(kid)
        except JwksUnavailable as exc:
            raise ContextKeyUnavailableError(
                f"context JWKS unavailable ({exc})"
            ) from exc
