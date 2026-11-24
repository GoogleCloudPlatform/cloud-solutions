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

# pylint: disable=import-outside-toplevel,line-too-long,protected-access

"""Pool / silo / hybrid topology: config validation and routing refusals (plan track C1).

Covers:
1. Slide 7 & 8 alignment: FinVault's 3LO Google Workspace tools + Jira (unchanged pooled behaviour).
2. `topology:` config is validated fail-closed (unknown pattern, missing or foreign fields, shared
   endpoints/projects, silo in the pooled project). Sandbox tenants stay `pool`.
3. `agents.topology_router`: pool stays in process; silo and hybrid get a routing decision plus a
   derived context token bound to the tenant's own audience. Refusals: unknown pattern, missing
   endpoint, audience mismatch, tenant mismatch, offboarded tenant, and tenant A routed to (or
   accepted by) tenant B's silo.
No network calls are made: the router only returns decisions.
"""

from __future__ import annotations

from typing import Any

import pytest
from agents import context_token as ct
from agents import platform_config as pc
from agents.agent_alpha import build_agent_alpha
from agents.context import TENANT_DIRECTORY, ContextEnvelope
from agents.context_exchange import ContextTokenExchange, ExchangeRefused
from agents.interceptors import (
    OTelAuditSink,
    enforce_tenant_isolation_interceptor,
)
from agents.registry import AgentRegistryPDP
from agents.testing_fakes import MockADKCallbackContext
from agents.topology_router import (
    IN_PROCESS,
    TopologyRefused,
    TopologyRouter,
    verify_forwarded_context_token,
)
from mcp_server.server import schedule_calendar_postmortem

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"

FV_SILO = {
    "pattern": "silo",
    "runtime_url": "https://runtime.finvault-silo.example",
    "project_id": "finvault-silo-example",
    "audience": "https://runtime.finvault-silo.example",
}
RS_SILO = {
    "pattern": "silo",
    "runtime_url": "https://runtime.retailstream-silo.example",
    "project_id": "retailstream-silo-example",
    "audience": "https://runtime.retailstream-silo.example",
}
FV_HYBRID = {
    "pattern": "hybrid",
    "data_endpoint": "https://data.finvault-psc.example",
    "data_project_id": "finvault-data-example",
    "mcp_audience": "https://mcp.finvault-psc.example/mcp",
}


@pytest.fixture(autouse=True)
def _fresh_gateway_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture envelopes reuse one cached context token across tests; give each test its own
    rate-limit bucket so per-token limits never leak between tests."""
    import agents.topology_router as tr

    monkeypatch.setattr(tr, "get_context_token_exchange", ContextTokenExchange)


def _router(topologies: dict[str, dict[str, Any]], **kw: Any) -> TopologyRouter:
    return TopologyRouter(topology_for_tenant=topologies.get, **kw)


def _sandbox_with(
    tenant_index: int, topology: dict[str, Any]
) -> dict[str, Any]:
    data = pc.load_platform_config("sandbox").model_dump()
    data["tenants"][tenant_index]["topology"] = topology
    return data


# --- 1. pooled tool surface (unchanged) -----------------------------------------------------------


async def test_slide_7_and_8_finvault_drive_calendar_gmail_jira_3lo_completeness(
    finvault_envelope: ContextEnvelope,
    retailstream_envelope: ContextEnvelope,
    registry_pdp: AgentRegistryPDP,
    otel_sink: OTelAuditSink,
) -> None:
    alpha = build_agent_alpha()
    fv_ctx = MockADKCallbackContext(
        state=finvault_envelope.to_adk_state(), agent=alpha
    )
    await enforce_tenant_isolation_interceptor(
        fv_ctx, registry_pdp=registry_pdp, otel_sink=otel_sink
    )

    tool_names = {
        getattr(t, "name", getattr(t, "__name__", ""))
        for t in fv_ctx.active_tools
    }
    assert tool_names == {
        "query_telemetry_rls",
        "read_runbook",
        "execute_diagnostic_sandbox",
        "create_jira_incident",
        "send_gmail_brief",
        "schedule_calendar_postmortem",
        "escalate_regulatory_filing",
    }

    cal_res = await schedule_calendar_postmortem(
        incident_id="INC-FV-1001",
        title="Post-Mortem for SSN 123-45-6789 wire delay",
        tool_context=fv_ctx,
    )
    assert cal_res["status"] == "scheduled"
    assert "[REDACTED_BANKING_SSN]" in cal_res["title"]

    rs_ctx = MockADKCallbackContext(
        state=retailstream_envelope.to_adk_state(), agent=alpha
    )
    with pytest.raises(PermissionError, match="403 Forbidden"):
        await schedule_calendar_postmortem(
            incident_id="INC-FV-1001", tool_context=rs_ctx
        )


# --- 2. config validation ------------------------------------------------------------------------


def test_sandbox_tenants_stay_pooled() -> None:
    cfg = pc.load_platform_config("sandbox")
    assert {t.tenant_id: t.topology.pattern for t in cfg.tenants} == {
        FV: "pool",
        RS: "pool",
    }
    assert TENANT_DIRECTORY[FV]["topology"] == {"pattern": "pool"}


@pytest.mark.parametrize(
    "topology", [FV_SILO, FV_HYBRID, {"pattern": "pool"}, {}]
)
def test_valid_topologies_load(topology: dict[str, Any]) -> None:
    cfg = pc.PlatformConfig.model_validate(_sandbox_with(0, topology))
    assert cfg.tenants[0].topology.pattern == topology.get("pattern", "pool")


@pytest.mark.parametrize("pattern", ["mesh", "POOL", "", "silo-lite"])
def test_config_refuses_unknown_pattern(pattern: str) -> None:
    with pytest.raises(ValueError, match="pattern"):
        pc.PlatformConfig.model_validate(_sandbox_with(0, {"pattern": pattern}))


@pytest.mark.parametrize(
    ("base", "drop"),
    [
        (FV_SILO, "runtime_url"),
        (FV_SILO, "project_id"),
        (FV_SILO, "audience"),
        (FV_HYBRID, "data_endpoint"),
        (FV_HYBRID, "data_project_id"),
        (FV_HYBRID, "mcp_audience"),
    ],
)
def test_config_refuses_missing_required_field(
    base: dict[str, Any], drop: str
) -> None:
    topology = {k: v for k, v in base.items() if k != drop}
    with pytest.raises(ValueError, match=f"requires \\['{drop}'\\]"):
        pc.PlatformConfig.model_validate(_sandbox_with(0, topology))


@pytest.mark.parametrize(
    "topology",
    [
        {
            "pattern": "pool",
            "runtime_url": "https://runtime.finvault-silo.example",
        },
        {**FV_SILO, "data_endpoint": "https://data.finvault-psc.example"},
        {**FV_HYBRID, "audience": "https://runtime.finvault-silo.example"},
    ],
)
def test_config_refuses_fields_of_another_pattern(
    topology: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="does not allow"):
        pc.PlatformConfig.model_validate(_sandbox_with(0, topology))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime_url", "http://runtime.finvault-silo.example"),
        ("audience", "runtime"),
        ("audience", "https://user:pw@runtime.finvault-silo.example"),
        ("project_id", "Not_A_Project"),
    ],
)
def test_config_refuses_malformed_silo_fields(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=f"topology.{field}"):
        pc.PlatformConfig.model_validate(
            _sandbox_with(0, {**FV_SILO, field: value})
        )


def test_config_refuses_unknown_topology_key() -> None:
    with pytest.raises(ValueError, match="extra"):
        pc.PlatformConfig.model_validate(
            _sandbox_with(0, {**FV_SILO, "spiffe_san": "x"})
        )


def test_config_refuses_endpoint_shared_by_two_tenants() -> None:
    data = _sandbox_with(0, FV_SILO)
    data["tenants"][1]["topology"] = {
        **RS_SILO,
        "audience": FV_SILO["audience"],
    }
    with pytest.raises(ValueError, match="shared by multiple tenants"):
        pc.PlatformConfig.model_validate(data)


def test_config_refuses_topology_audience_registered_to_another_tenant() -> (
    None
):
    data = _sandbox_with(
        1, {**RS_SILO, "audience": "https://mcp.finvault.example/mcp"}
    )
    with pytest.raises(ValueError, match="shared by multiple tenants"):
        pc.PlatformConfig.model_validate(data)


def test_config_refuses_topology_audience_equal_to_own_external_mcp_audience() -> (
    None
):
    data = _sandbox_with(
        0, {**FV_SILO, "audience": "https://mcp.finvault.example/mcp"}
    )
    with pytest.raises(ValueError, match="overlap external_mcp_audiences"):
        pc.PlatformConfig.model_validate(data)


def test_config_refuses_project_shared_by_two_tenants() -> None:
    data = _sandbox_with(0, FV_SILO)
    data["tenants"][1]["topology"] = {
        **RS_SILO,
        "project_id": FV_SILO["project_id"],
    }
    with pytest.raises(ValueError, match="projects shared by multiple tenants"):
        pc.PlatformConfig.model_validate(data)


def test_config_refuses_silo_in_the_pooled_project() -> None:
    data = _sandbox_with(0, FV_SILO)
    data["tenants"][0]["topology"]["project_id"] = data["gcp"]["project_id"]
    with pytest.raises(ValueError, match="pooled project"):
        pc.PlatformConfig.model_validate(data)


# --- 3. routing ----------------------------------------------------------------------------------


def test_pool_routes_in_process_without_a_forwarded_token(
    finvault_envelope: ContextEnvelope,
) -> None:
    decision = TopologyRouter().route(finvault_envelope.context_token)
    assert decision.pattern == "pool"
    assert decision.tenant_id == FV
    assert (decision.runtime_target, decision.data_target) == (
        IN_PROCESS,
        IN_PROCESS,
    )
    assert decision.forwarded_token is None
    assert decision.token_audience is None


def test_silo_forwards_with_a_token_bound_to_the_silo_audience(
    finvault_envelope: ContextEnvelope,
) -> None:
    decision = _router({FV: FV_SILO}).route(finvault_envelope.context_token)
    assert decision.pattern == "silo"
    assert decision.runtime_target == FV_SILO["runtime_url"]
    assert decision.token_audience == FV_SILO["audience"]
    assert decision.forwarded_token
    assert decision.forwarded_token not in repr(decision)
    assert "forwarded_token" not in decision.public_view()
    claims = verify_forwarded_context_token(
        decision.forwarded_token, audience=FV_SILO["audience"], tenant_id=FV
    )
    assert claims["tenant_id"] == FV
    assert claims["sub"] == "alice@finvault.com"
    assert claims["exp"] - claims["iat"] <= ct.DERIVED_TOKEN_MAX_TTL_SECONDS
    # The derived token is not an internal token: the pooled runtime/MCP refuse it.
    with pytest.raises(ct.ContextTokenError):
        ct.get_context_verifier().verify(
            decision.forwarded_token, audience=ct.AUDIENCE_RUNTIME
        )


def test_hybrid_keeps_pooled_runtime_and_targets_the_psc_endpoint(
    finvault_envelope: ContextEnvelope,
) -> None:
    decision = _router({FV: FV_HYBRID}).route(finvault_envelope.context_token)
    assert decision.pattern == "hybrid"
    assert decision.runtime_target == IN_PROCESS
    assert decision.data_target == FV_HYBRID["data_endpoint"]
    assert decision.token_audience == FV_HYBRID["mcp_audience"]
    assert decision.forwarded_token is not None
    verify_forwarded_context_token(
        decision.forwarded_token,
        audience=FV_HYBRID["mcp_audience"],
        tenant_id=FV,
    )


def test_router_refuses_unknown_pattern(
    finvault_envelope: ContextEnvelope,
) -> None:
    with pytest.raises(TopologyRefused) as info:
        _router({FV: {"pattern": "mesh"}}).route(
            finvault_envelope.context_token
        )
    assert info.value.code == "E_TOPOLOGY_UNKNOWN_PATTERN"


@pytest.mark.parametrize(
    ("topology", "drop"),
    [(FV_SILO, "runtime_url"), (FV_SILO, "audience"), (FV_HYBRID, "data_endpoint"),
     (FV_HYBRID, "mcp_audience")],
)  # fmt: skip
def test_router_refuses_missing_endpoint(
    finvault_envelope: ContextEnvelope, topology: dict[str, Any], drop: str
) -> None:
    broken = {k: v for k, v in topology.items() if k != drop}
    with pytest.raises(TopologyRefused) as info:
        _router({FV: broken}).route(finvault_envelope.context_token)
    assert info.value.code == "E_TOPOLOGY_ENDPOINT_MISSING"


def test_router_refuses_offboarded_tenant(
    finvault_envelope: ContextEnvelope,
) -> None:
    with pytest.raises(TopologyRefused) as info:
        _router({}).route(finvault_envelope.context_token)
    assert info.value.code == "E_TOPOLOGY_TENANT_OFFBOARDED"


def test_router_refuses_non_internal_tokens(
    finvault_envelope: ContextEnvelope,
) -> None:
    router = _router({FV: FV_SILO})
    derived = router.route(finvault_envelope.context_token).forwarded_token
    assert derived is not None
    for token in (derived, "not.a.token", ""):
        with pytest.raises(TopologyRefused) as info:
            router.route(token)
        assert info.value.code.startswith("E_CONTEXT_TOKEN_")


def test_router_refuses_derived_token_with_wrong_audience(
    finvault_envelope: ContextEnvelope,
) -> None:
    class WrongAudienceExchange(ContextTokenExchange):
        def exchange(
            self, context_token: str, *, audience: str
        ) -> tuple[str, dict[str, Any]]:
            return "tok", {
                "aud": RS_SILO["audience"],
                "tenant_id": FV,
                "exp": 0,
            }

    router = _router({FV: FV_SILO}, exchange=WrongAudienceExchange())
    with pytest.raises(TopologyRefused) as info:
        router.route(finvault_envelope.context_token)
    assert info.value.code == "E_TOPOLOGY_TOKEN_AUDIENCE_MISMATCH"


def test_router_refuses_derived_token_for_another_tenant(
    finvault_envelope: ContextEnvelope,
) -> None:
    class WrongTenantExchange(ContextTokenExchange):
        def exchange(
            self, context_token: str, *, audience: str
        ) -> tuple[str, dict[str, Any]]:
            return "tok", {"aud": audience, "tenant_id": RS, "exp": 0}

    router = _router({FV: FV_SILO}, exchange=WrongTenantExchange())
    with pytest.raises(TopologyRefused) as info:
        router.route(finvault_envelope.context_token)
    assert info.value.code == "E_TOPOLOGY_TOKEN_AUDIENCE_MISMATCH"


# --- tenant A can never reach tenant B's silo -----------------------------------------------------


def test_tenant_a_is_routed_only_to_its_own_silo(
    finvault_envelope: ContextEnvelope, retailstream_envelope: ContextEnvelope
) -> None:
    router = _router({FV: FV_SILO, RS: RS_SILO})
    fv = router.route(finvault_envelope.context_token)
    rs = router.route(retailstream_envelope.context_token)
    assert (fv.tenant_id, fv.runtime_target, fv.token_audience) == (
        FV,
        FV_SILO["runtime_url"],
        FV_SILO["audience"],
    )
    assert (rs.tenant_id, rs.runtime_target, rs.token_audience) == (
        RS,
        RS_SILO["runtime_url"],
        RS_SILO["audience"],
    )


def test_tenant_a_token_with_tenant_b_session_is_refused(
    finvault_envelope: ContextEnvelope,
) -> None:
    router = _router({FV: FV_SILO, RS: RS_SILO})
    with pytest.raises(TopologyRefused) as info:
        router.route(finvault_envelope.context_token, expected_tenant_id=RS)
    assert info.value.code == "E_TOPOLOGY_TENANT_MISMATCH"


def test_tenant_a_cannot_get_a_token_for_tenant_b_silo_audience(
    finvault_envelope: ContextEnvelope,
) -> None:
    router = _router({FV: FV_SILO, RS: RS_SILO})
    with pytest.raises(ExchangeRefused) as info:
        router._exchange.exchange(
            finvault_envelope.context_token, audience=RS_SILO["audience"]
        )
    assert info.value.code == "E_EXCHANGE_AUDIENCE_NOT_REGISTERED"


def test_tenant_b_silo_refuses_tenant_a_forwarded_token(
    finvault_envelope: ContextEnvelope,
) -> None:
    token = (
        _router({FV: FV_SILO})
        .route(finvault_envelope.context_token)
        .forwarded_token
    )
    assert token is not None
    # RetailStream's silo checks its own audience: FinVault's token has the wrong audience.
    with pytest.raises(TopologyRefused) as info:
        verify_forwarded_context_token(
            token, audience=RS_SILO["audience"], tenant_id=RS
        )
    assert info.value.code == "E_CONTEXT_TOKEN_AUDIENCE"
    # Even a receiver misconfigured with FinVault's audience still checks the tenant.
    with pytest.raises(TopologyRefused) as info:
        verify_forwarded_context_token(
            token, audience=FV_SILO["audience"], tenant_id=RS
        )
    assert info.value.code == "E_TOPOLOGY_TENANT_MISMATCH"


def test_router_exchange_never_issues_external_mcp_or_broker_audiences(
    finvault_envelope: ContextEnvelope,
) -> None:
    """The router's exchange issues only the tenant's topology audience (plus the exchange's
    built-in broker audience, which the router never requests)."""
    router = _router({FV: FV_SILO})
    with pytest.raises(ExchangeRefused) as info:
        router._exchange.exchange(
            finvault_envelope.context_token,
            audience="https://mcp.finvault.example/mcp",
        )
    assert info.value.code == "E_EXCHANGE_AUDIENCE_NOT_REGISTERED"


def test_router_exchange_never_issues_the_broker_audience(
    finvault_envelope: ContextEnvelope,
) -> None:
    router = _router({FV: FV_SILO})
    with pytest.raises(ExchangeRefused) as info:
        router._exchange.exchange(
            finvault_envelope.context_token, audience=ct.AUDIENCE_BROKER
        )
    assert info.value.code == "E_EXCHANGE_AUDIENCE_NOT_REGISTERED"
    # The gateway's own exchange still issues broker tokens (default unchanged).
    _, claims = ContextTokenExchange().exchange(
        finvault_envelope.context_token, audience=ct.AUDIENCE_BROKER
    )
    assert claims["aud"] == ct.AUDIENCE_BROKER


def test_router_exchange_shares_gateway_user_ref_and_rate_limit(
    finvault_envelope: ContextEnvelope, monkeypatch: pytest.MonkeyPatch
) -> None:
    import agents.topology_router as tr

    gateway = ContextTokenExchange(user_ref=lambda tenant, sub: "u-gateway-ref")
    monkeypatch.setattr(tr, "get_context_token_exchange", lambda: gateway)
    router = _router({FV: FV_SILO})
    assert router._exchange.user_ref is gateway.user_ref
    token = finvault_envelope.context_token
    for _ in range(gateway._max_per_source):
        gateway.exchange(token, audience=ct.AUDIENCE_BROKER)
    with pytest.raises(TopologyRefused) as info:
        router.route(token)
    assert info.value.code == "E_EXCHANGE_RATE_LIMITED"


@pytest.mark.parametrize(
    "audience",
    [
        ct.AUDIENCE_MCP,
        ct.AUDIENCE_RUNTIME,
        ct.AUDIENCE_BROKER,
        "http://runtime.finvault-silo.example",
    ],
)
def test_receiver_refuses_internal_or_non_https_audience(
    finvault_envelope: ContextEnvelope, audience: str
) -> None:
    with pytest.raises(TopologyRefused) as info:
        verify_forwarded_context_token(
            finvault_envelope.context_token, audience=audience, tenant_id=FV
        )
    assert info.value.code == "E_TOPOLOGY_RECEIVER_AUDIENCE"
    # Internal audiences are refused by name (checked first), not only by the https rule.
    expected = "internal" if ct.is_internal_audience(audience) else "https"
    assert expected in str(info.value)


def test_fastapi_interactive_3_pattern_topology_endpoints() -> None:
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    for pat_id in ("pattern_a_pooled", "pattern_b_silo", "pattern_c_hybrid"):
        r = client.post(f"/api/v1/topology-deltas/{pat_id}")
        assert r.status_code == 200
        body = r.json()
        assert "plain_english_summary" in body
        assert "eyJ" not in r.text  # no token values in the demo response
    assert client.post("/api/v1/topology-deltas/pattern_z").status_code == 404


def test_invoke_agent_includes_topology_route_receipt() -> None:
    from app.main import app
    from fastapi.testclient import TestClient
    from scripts.sandbox_auth import SandboxCaller

    client = TestClient(app)
    caller = SandboxCaller(
        client, tenant_id=FV, sub="alice@finvault.com", role="sre_admin"
    )
    path = "/api/v1/invoke-agent"
    resp = client.post(
        path,
        json={
            "agent_id": "cymbal_shared_diagnostic_agent",
            "tool_name": "query_telemetry_rls",
            "requested_thinking_tokens": 1000,
        },
        headers=caller.headers("POST", caller.url(path)),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["topology_route"] == {
        "tenant_id": FV,
        "pattern": "pool",
        "runtime_target": IN_PROCESS,
        "data_target": IN_PROCESS,
        "token_audience": None,
        "token_exp": None,
        "forwarded_token_present": False,
    }
    assert "forwarded_token" not in body["topology_route"]
