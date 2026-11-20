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

"""Per-audience context-token exchange (ADR-0014 D3): gateway side, in process only.

Contract (fixed here so the B5 split needs no redesign):

- The caller presents a valid **internal** context token (`aud = [runtime, mcp]`), verified with
  the public key. Derived tokens, gateway access tokens and forged tokens are refused.
- `tenant_id` and `sub` are copied **from that token**; the caller cannot name them.
- The requested audience is either `broker` (credential broker, B4) or an external MCP URL that is
  registered for **that** tenant (`external_mcp_audiences` in the tenant config). Internal
  audiences (`runtime`, `mcp`) are never issued.
- `exp <= min(now + 300 s, the presented token's exp)`; every issuance gets a fresh `jti`.
- `max_delegation_depth` (and `agent_id`, when the source has it; ADR-0016) is carried over. The
  tenant must still be onboarded (any audience).
- At most 20 derived tokens per presented context token per minute.
- Each issuance and each refusal writes one audit line with a pseudonymous user reference (no
  token values).

Reachability: this is a Python API, not an HTTP route. In phase 3a the runtime and the gateway are
one process, so the runtime calls it directly; the public app exposes nothing under `/internal/`
(`app.main` returns 404 for that prefix). Phase 3b (B5) serves it on the internal-only gateway
service (ingress `internal`, Cloud Run IAM `run.invoker` for the runtime SA only).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from typing import Any

from agents import context_token as ct
from agents.context_signing import ContextTokenIssuer, get_context_token_issuer

audit_logger = logging.getLogger("cymbal.audit.context_exchange")

DERIVED_TOKEN_MAX_TTL_SECONDS = ct.DERIVED_TOKEN_MAX_TTL_SECONDS


class ExchangeRefused(PermissionError):
    """The exchange was refused. `code` is a stable `E_EXCHANGE_*` / `E_CONTEXT_TOKEN_*` code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def registered_external_audiences(tenant_id: str) -> tuple[str, ...]:
    """External MCP URLs registered for a currently onboarded tenant (empty if offboarded)."""
    from agents.context import TENANT_DIRECTORY

    meta = TENANT_DIRECTORY.get(tenant_id)
    return tuple(meta.get("external_mcp_audiences", ())) if meta else ()


def tenant_onboarded(tenant_id: str) -> bool:
    from agents.context import TENANT_DIRECTORY

    return tenant_id in TENANT_DIRECTORY


_PROCESS_REF_KEY = secrets.token_bytes(32)


def default_user_ref(tenant_id: str, sub: str) -> str:
    """Pseudonymous user reference (HMAC with a per-process random key; not reversible by hashing
    guessed emails). The gateway installs `app.gateway_tokens.log_user_ref` instead, so exchange
    audit lines correlate with the gateway's own logs."""
    mac = hmac.new(
        _PROCESS_REF_KEY, f"log:{tenant_id}:{sub}".encode(), hashlib.sha256
    )
    return "u-" + mac.hexdigest()[:16]


class ContextTokenExchange:
    """Issues derived, single-audience tokens from a verified internal context token.

    Bounded: at most `max_per_source_per_minute` derived tokens per presented context token
    (`E_EXCHANGE_RATE_LIMITED`). Every issuance and every refusal writes one audit line with a
    pseudonymous user reference; token values are never logged.
    """

    _MAX_TRACKED_SOURCES = 10_000

    def __init__(
        self,
        issuer: ContextTokenIssuer | None = None,
        verifier: ct.ContextTokenVerifier | None = None,
        *,
        max_ttl_seconds: int = DERIVED_TOKEN_MAX_TTL_SECONDS,
        max_per_source_per_minute: int = 20,
        audiences_for_tenant: Callable[
            [str], tuple[str, ...]
        ] = registered_external_audiences,
        is_onboarded: Callable[[str], bool] = tenant_onboarded,
        user_ref: Callable[[str, str], str] = default_user_ref,
        clock: Callable[[], float] = time.time,
        allow_broker: bool = True,
        rate_limit_from: ContextTokenExchange | None = None,
    ) -> None:
        """`allow_broker=False`: issue only `audiences_for_tenant` (no built-in broker audience).
        `rate_limit_from`: share that exchange's per-source-token bucket (one budget per token).
        """
        self._issuer = issuer
        self._verifier = verifier
        self._max_ttl = min(int(max_ttl_seconds), DERIVED_TOKEN_MAX_TTL_SECONDS)
        self._max_per_source = int(max_per_source_per_minute)
        self._audiences_for_tenant = audiences_for_tenant
        self._is_onboarded = is_onboarded
        self.user_ref = user_ref
        self._clock = clock
        self._allow_broker = allow_broker
        if rate_limit_from is not None:
            self._lock = rate_limit_from._lock
            self._by_source = rate_limit_from._by_source
            self._max_per_source = rate_limit_from._max_per_source
        else:
            self._lock = threading.Lock()
            self._by_source: OrderedDict[str, deque[float]] = OrderedDict()
        self.issued = 0

    def _take_slot(self, src_jti: str) -> bool:
        now = self._clock()
        with self._lock:
            window = self._by_source.get(src_jti)
            if window is None:
                window = self._by_source[src_jti] = deque()
            self._by_source.move_to_end(src_jti)
            while window and now - window[0] >= 60.0:
                window.popleft()
            if len(window) >= self._max_per_source:
                return False
            window.append(now)
            while len(self._by_source) > self._MAX_TRACKED_SOURCES:
                self._by_source.popitem(last=False)
            return True

    def _refund_slot(self, src_jti: str) -> None:
        """Gives back the slot taken for an issuance that did not happen."""
        with self._lock:
            window = self._by_source.get(src_jti)
            if window:
                window.pop()

    def _audit(self, event: str, **fields: Any) -> None:
        audit_logger.info(
            json.dumps({"event": event, **fields}, sort_keys=True)
        )

    def exchange(
        self, context_token: str, *, audience: str
    ) -> tuple[str, dict[str, Any]]:
        """(derived token, its claims). Raises `ExchangeRefused`; KMS outages raise 503 errors."""
        known: dict[str, Any] = {}
        try:
            token, claims = self._exchange(context_token, audience, known)
        except ExchangeRefused as exc:
            self._audit(
                "context_token_exchange_refused",
                code=exc.code,
                audience=str(audience)[:200],
                **known,
            )
            raise
        self._audit(
            "context_token_exchange",
            audience=audience,
            jti=claims["jti"],
            exp=claims["exp"],
            **known,
        )
        return token, claims

    def _exchange(
        self, context_token: str, audience: str, known: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        if (
            not isinstance(audience, str)
            or not audience
            or ct.is_internal_audience(audience)
        ):
            raise ExchangeRefused(
                "E_EXCHANGE_AUDIENCE_INTERNAL",
                "internal audiences are never issued",
            )
        verifier = self._verifier or ct.get_context_verifier()
        try:
            source = verifier.verify(
                context_token, audience=ct.AUDIENCE_RUNTIME
            )
        except ct.ContextTokenError as exc:
            raise ExchangeRefused(
                exc.code, "an internal context token is required"
            ) from exc
        tenant_id = str(source["tenant_id"])
        known.update(
            tenant_id=tenant_id,
            user_ref=self.user_ref(tenant_id, str(source["sub"])),
            src_jti=source["jti"],
        )
        if not self._is_onboarded(tenant_id):  # every audience, broker included
            raise ExchangeRefused(
                "E_EXCHANGE_TENANT_OFFBOARDED", "tenant is not onboarded"
            )
        broker_ok = self._allow_broker and audience == ct.AUDIENCE_BROKER
        if not broker_ok and audience not in self._audiences_for_tenant(
            tenant_id
        ):
            raise ExchangeRefused(
                "E_EXCHANGE_AUDIENCE_NOT_REGISTERED",
                "audience is not an external MCP server registered for this tenant",
            )
        if not self._take_slot(str(source["jti"])):
            raise ExchangeRefused(
                "E_EXCHANGE_RATE_LIMITED",
                "too many derived tokens for this context token",
            )
        issuer = self._issuer or get_context_token_issuer()
        # ADR-0016: the routed agent stays bound to the derived token (broker / MCP check that the
        # calling workload is that agent). Copied only from the verified source token.
        agent_claim = (
            {ct.AGENT_ID_CLAIM: source[ct.AGENT_ID_CLAIM]}
            if ct.AGENT_ID_CLAIM in source
            else {}
        )
        try:
            token, claims = issuer.issue_derived(
                audience=audience,
                not_after=int(source["exp"]),
                max_ttl_seconds=self._max_ttl,
                sub=source["sub"],
                tenant_id=tenant_id,
                max_delegation_depth=int(source["max_delegation_depth"]),
                src_jti=source["jti"],
                **agent_claim,
            )
        except (
            PermissionError
        ) as exc:  # e.g. the presented token expired meanwhile
            self._refund_slot(str(source["jti"]))
            raise ExchangeRefused(
                "E_EXCHANGE_SOURCE_EXPIRED", str(exc)
            ) from exc
        except (
            Exception
        ) as exc:  # signing outage (KMS -> 503): refund the slot, audit, re-raise
            self._refund_slot(str(source["jti"]))
            self._audit(
                "context_token_exchange_failed",
                code=getattr(exc, "code", type(exc).__name__),
                audience=audience,
                **known,
            )
            raise
        with self._lock:
            self.issued += 1
        return token, claims


_EXCHANGE_LOCK = threading.Lock()
_EXCHANGE: ContextTokenExchange | None = None


def get_context_token_exchange() -> ContextTokenExchange:
    """The process exchange (uses the process issuer and verifier, resolved lazily)."""
    global _EXCHANGE
    with _EXCHANGE_LOCK:
        if _EXCHANGE is None:
            _EXCHANGE = ContextTokenExchange()
        return _EXCHANGE
