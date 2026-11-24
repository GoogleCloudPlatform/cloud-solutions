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

"""Config-driven topology routing: pool, silo or hybrid per tenant (plan track C1).

The tenant comes from the verified internal context token, never from the caller. The tenant's
`topology` block (`config/tenants/*.yaml`, validated in `agents.platform_config.TenantTopology`)
decides where the turn runs:

- `pool`: in process, exactly as today. No extra token.
- `silo`: forward to the tenant's own runtime (`runtime_url`). The forwarded request carries a
  derived context token whose only audience is the silo's `audience`; the silo verifies it with the
  gateway's public keys (JWKS) via `verify_forwarded_context_token`.
- `hybrid`: the pooled runtime runs the turn; data and MCP calls go to the tenant's Private Service
  Connect endpoint (`data_endpoint`) with a derived token whose only audience is `mcp_audience`.

Derived tokens come from the ADR-0014 per-audience exchange (`agents.context_exchange`), with a
router-owned exchange that issues only the tenant's own topology audience (never `broker` or an
external MCP audience). It shares the gateway exchange's audit `user_ref` and per-token rate limit.
This module makes routing
decisions only: it never calls a silo or PSC endpoint. Refusals raise `TopologyRefused` with a
stable `E_TOPOLOGY_*` (or underlying `E_EXCHANGE_*` / `E_CONTEXT_TOKEN_*`) code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from agents import context_token as ct
from agents.context_exchange import (
    ContextTokenExchange,
    ExchangeRefused,
    get_context_token_exchange,
)

IN_PROCESS = "in-process"
KNOWN_PATTERNS = ("pool", "silo", "hybrid")


class TopologyRefused(PermissionError):
    """Routing was refused. `code` is a stable error code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class RoutingDecision:
    """Where one turn goes. `forwarded_token` is never included in `repr` or `public_view`."""

    tenant_id: str
    pattern: str
    runtime_target: str  # IN_PROCESS (pool, hybrid) or the silo runtime URL
    data_target: str  # IN_PROCESS (pool), the silo runtime URL (silo) or the PSC endpoint (hybrid)
    token_audience: str | None = None
    token_exp: int | None = None
    forwarded_token: str | None = field(default=None, repr=False)

    def public_view(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "pattern": self.pattern,
            "runtime_target": self.runtime_target,
            "data_target": self.data_target,
            "token_audience": self.token_audience,
            "token_exp": self.token_exp,
            "forwarded_token_present": self.forwarded_token is not None,
        }


def configured_topology(tenant_id: str) -> Mapping[str, Any] | None:
    """The tenant's topology block from the live tenant directory; None if not onboarded."""
    from agents.context import TENANT_DIRECTORY

    meta = TENANT_DIRECTORY.get(tenant_id)
    if meta is None:
        return None
    return meta.get("topology") or {"pattern": "pool"}


def topology_audience(topology: Mapping[str, Any]) -> str | None:
    """The single derived-token audience a topology allows (None for pool or unknown)."""
    pattern = topology.get("pattern", "pool")
    if pattern == "silo":
        return topology.get("audience") or None
    if pattern == "hybrid":
        return topology.get("mcp_audience") or None
    return None


def _require(topology: Mapping[str, Any], name: str, tenant_id: str) -> str:
    value = topology.get(name)
    if not isinstance(value, str) or not value:
        raise TopologyRefused(
            "E_TOPOLOGY_ENDPOINT_MISSING",
            f"{tenant_id}: topology.pattern={topology.get('pattern')} has no {name}",
        )
    return value


class TopologyRouter:
    """Decides pool / silo / hybrid routing for a verified context token."""

    def __init__(
        self,
        *,
        topology_for_tenant: Callable[
            [str], Mapping[str, Any] | None
        ] = configured_topology,
        verifier: ct.ContextTokenVerifier | None = None,
        exchange: ContextTokenExchange | None = None,
    ) -> None:
        self._topology_for_tenant = topology_for_tenant
        self._verifier = verifier
        if exchange is None:
            # Same audit user_ref and per-source-token rate bucket as the gateway's exchange, but
            # only this tenant's topology audience (no broker, no external MCP audiences).
            gateway_exchange = get_context_token_exchange()
            exchange = ContextTokenExchange(
                verifier=verifier,
                audiences_for_tenant=self._audiences_for_tenant,
                is_onboarded=lambda tid: self._topology_for_tenant(tid)
                is not None,
                user_ref=gateway_exchange.user_ref,
                allow_broker=False,
                rate_limit_from=gateway_exchange,
            )
        self._exchange = exchange

    def _audiences_for_tenant(self, tenant_id: str) -> tuple[str, ...]:
        topology = self._topology_for_tenant(tenant_id)
        audience = topology_audience(topology) if topology is not None else None
        return (audience,) if audience else ()

    def route(
        self, context_token: str, *, expected_tenant_id: str | None = None
    ) -> RoutingDecision:
        """Routing decision for this turn. Raises `TopologyRefused`; makes no network calls.

        `expected_tenant_id` (optional) is the tenant the caller believes it serves, e.g. the
        gateway session's tenant; a mismatch with the signed token is refused.
        """
        verifier = self._verifier or ct.get_context_verifier()
        try:
            source = verifier.verify(
                context_token, audience=ct.AUDIENCE_RUNTIME
            )
        except ct.ContextTokenError as exc:
            raise TopologyRefused(
                exc.code, "an internal context token is required"
            ) from exc
        tenant_id = str(source["tenant_id"])
        if expected_tenant_id is not None and expected_tenant_id != tenant_id:
            raise TopologyRefused(
                "E_TOPOLOGY_TENANT_MISMATCH",
                "the context token is for a different tenant",
            )
        topology = self._topology_for_tenant(tenant_id)
        if topology is None:
            raise TopologyRefused(
                "E_TOPOLOGY_TENANT_OFFBOARDED", "tenant is not onboarded"
            )
        pattern = topology.get("pattern", "pool")
        if pattern not in KNOWN_PATTERNS:
            raise TopologyRefused(
                "E_TOPOLOGY_UNKNOWN_PATTERN", f"{tenant_id}: {pattern!r}"
            )

        if pattern == "pool":
            return RoutingDecision(
                tenant_id=tenant_id,
                pattern=pattern,
                runtime_target=IN_PROCESS,
                data_target=IN_PROCESS,
            )
        if pattern == "silo":
            runtime_target = _require(topology, "runtime_url", tenant_id)
            data_target = runtime_target
            audience = _require(topology, "audience", tenant_id)
        else:
            runtime_target = IN_PROCESS
            data_target = _require(topology, "data_endpoint", tenant_id)
            audience = _require(topology, "mcp_audience", tenant_id)

        token, claims = self._derive(
            context_token, audience=audience, tenant_id=tenant_id
        )
        return RoutingDecision(
            tenant_id=tenant_id,
            pattern=pattern,
            runtime_target=runtime_target,
            data_target=data_target,
            token_audience=audience,
            token_exp=int(claims["exp"]),
            forwarded_token=token,
        )

    def _derive(
        self, context_token: str, *, audience: str, tenant_id: str
    ) -> tuple[str, dict[str, Any]]:
        try:
            token, claims = self._exchange.exchange(
                context_token, audience=audience
            )
        except ExchangeRefused as exc:
            raise TopologyRefused(exc.code, "derived token refused") from exc
        aud = claims.get("aud")
        if (
            aud not in (audience, [audience])
            or claims.get("tenant_id") != tenant_id
        ):
            raise TopologyRefused(
                "E_TOPOLOGY_TOKEN_AUDIENCE_MISMATCH",
                "derived token is not bound to this tenant's topology audience",
            )
        return token, claims


# --- SIMULATED example topologies (sandbox demo and breach simulation only) -----------------------
# Example values in the reserved `.example` domain. Nothing is deployed at these URLs and the
# configured sandbox tenants stay `pool`; the demo builds a router over these mappings explicitly.

SIMULATED_SILO_TOPOLOGIES: dict[str, dict[str, str]] = {
    "tenant-finvault-alpha": {
        "pattern": "silo",
        "runtime_url": "https://runtime.finvault-silo.example",
        "project_id": "finvault-silo-example",
        "audience": "https://runtime.finvault-silo.example",
    },
    "tenant-retailstream-beta": {
        "pattern": "silo",
        "runtime_url": "https://runtime.retailstream-silo.example",
        "project_id": "retailstream-silo-example",
        "audience": "https://runtime.retailstream-silo.example",
    },
}
SIMULATED_HYBRID_TOPOLOGIES: dict[str, dict[str, str]] = {
    "tenant-finvault-alpha": {
        "pattern": "hybrid",
        "data_endpoint": "https://data.finvault-psc.example",
        "data_project_id": "finvault-data-example",
        "mcp_audience": "https://mcp.finvault-psc.example/mcp",
    },
    "tenant-retailstream-beta": {
        "pattern": "hybrid",
        "data_endpoint": "https://data.retailstream-psc.example",
        "data_project_id": "retailstream-data-example",
        "mcp_audience": "https://mcp.retailstream-psc.example/mcp",
    },
}


def verify_forwarded_context_token(
    token: str,
    *,
    audience: str,
    tenant_id: str,
    verifier: ct.ContextTokenVerifier | None = None,
) -> dict[str, Any]:
    """Receiving side (silo runtime or PSC data plane): accept only its own audience and tenant.

    `audience` and `tenant_id` are the receiver's own configuration, never taken from the request.
    """
    from agents.platform_config import _is_plain_https_url

    if not isinstance(audience, str) or ct.is_internal_audience(audience):
        raise TopologyRefused(
            "E_TOPOLOGY_RECEIVER_AUDIENCE",
            "a receiver never accepts internal audiences",
        )
    if not _is_plain_https_url(audience):
        raise TopologyRefused(
            "E_TOPOLOGY_RECEIVER_AUDIENCE",
            "receiver audience must be a plain https URL",
        )
    v = verifier or ct.get_context_verifier()
    try:
        claims = v.verify(token, audience=audience)
    except ct.ContextTokenError as exc:
        raise TopologyRefused(
            exc.code, "forwarded context token rejected"
        ) from exc
    if claims.get("tenant_id") != tenant_id:
        raise TopologyRefused(
            "E_TOPOLOGY_TENANT_MISMATCH",
            "forwarded token is for a different tenant",
        )
    return claims
