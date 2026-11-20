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

"""Tests for the 'What Breaks at 2 AM' Failure Modes & Open Agentic Standards (`ADR-0008`).

Verifies every operational failure mode and open protocol highlighted in the updated Multi-Tenant
Agentic AI presentation and Pooled Blueprint:
1. **Control Plane 2 AM Failure Modes**:
   - Tier downgrade immediately invalidates cached Registry entitlements (`Enterprise` ->
     `Standard`).
   - Control Plane Registry outage triggers fail-closed rejection (`503
     E_CONTROL_PLANE_REGISTRY_UNAVAILABLE_FAIL_CLOSED`).
2. **Compute Plane 2 AM Failure Modes**:
   - Mid-turn A2A delegation token expiration halts child sub-agent execution (`401
     E_A2A_DELEGATION_EXPIRED_MID_TURN`).
   - Recursive sub-agent spawn depth cap (`429 E_SUBAGENT_SPAWN_DEPTH_EXCEEDED`) prevents sandbox
     exhaustion.
   - Redis real-time token bucket vs. BigQuery billing truth drift reconciliation.
3. **Data Plane 3-Hop Substrate-Agnostic Pattern & MCP Conditional Rules**:
   - Substrate-agnostic 3-hop isolation across AlloyDB/PostgreSQL, Cloud Spanner, Cloud Firestore,
     and BigQuery RAP.
   - MCP perimeter conditional rules (`mcp.toolName`, `mcp.method`, `mcp.tool.isReadOnly`) & MCP
     circuit breaker.
4. **Cross-Plane Observability & Open Agentic Standards (`OKF v0.2`, `A2UI v1`)**:
   - High-cardinality `user_id` scrubbing prevents metric cardinality explosion.
   - Open Knowledge Format (`OKF v0.2`) provenance, staleness TTL, and SHA-256 digest verification.
   - Declarative `A2UI` (`a2ui/v1`) tenant-scoped card generation with XSS sanitization.
"""

from __future__ import annotations

import time

import pytest
from agents.context import ContextEnvelope, SubscriptionTier
from agents.pooled_resilience_and_standards import (
    A2AAgentCardRegistry,
    A2UITenantCardBuilder,
    AgentPluginLoader,
    ComputePlane2AMGuard,
    ControlPlaneResilienceGuard,
    DynamicModelTierRouter,
    MCPConditionalPerimeterGuard,
    ObservabilityCardinalityGuard,
    OKFKnowledgeVerifier,
    SubstrateAgnostic3HopAdapter,
)


def test_control_plane_tier_downgrade_invalidates_stale_registry_cache_and_fails_closed() -> (
    None
):
    guard = ControlPlaneResilienceGuard()
    initial = guard.get_entitled_agents(tenant_id="tenant-finvault-alpha")
    assert "finvault_regulatory_escalation_agent" in initial

    # Simulate 2 AM tier downgrade from Enterprise -> Standard: cache must invalidate immediately
    guard.update_tenant_tier(
        tenant_id="tenant-finvault-alpha", new_tier=SubscriptionTier.STANDARD
    )
    after_downgrade = guard.get_entitled_agents(
        tenant_id="tenant-finvault-alpha"
    )
    assert "finvault_regulatory_escalation_agent" not in after_downgrade

    # Simulate Control Plane Registry outage: Compute Plane must fail closed
    guard.set_registry_health(healthy=False)
    with pytest.raises(
        PermissionError,
        match="E_CONTROL_PLANE_REGISTRY_UNAVAILABLE_FAIL_CLOSED",
    ):
        guard.get_entitled_agents(tenant_id="tenant-finvault-alpha")


def test_compute_plane_a2a_mid_turn_expiration_and_subagent_depth_cap(
    finvault_envelope: ContextEnvelope,
) -> None:
    now = time.time()
    valid_hop = ComputePlane2AMGuard.verify_a2a_subagent_hop(
        parent_envelope=finvault_envelope,
        delegation_exp_epoch=int(now + 300),
        current_depth=2,
        now_epoch=now,
    )
    assert valid_hop["temp:tenant_id"] == "tenant-finvault-alpha"

    # Expired mid-turn A2A delegation token must be rejected
    with pytest.raises(
        PermissionError, match="E_A2A_DELEGATION_EXPIRED_MID_TURN"
    ):
        ComputePlane2AMGuard.verify_a2a_subagent_hop(
            parent_envelope=finvault_envelope,
            delegation_exp_epoch=int(now - 5),
            current_depth=1,
            now_epoch=now,
        )

    # Recursive sub-agent spawning beyond MAX_SUBAGENT_DEPTH (3) must be blocked
    with pytest.raises(
        PermissionError, match="E_SUBAGENT_SPAWN_DEPTH_EXCEEDED"
    ):
        ComputePlane2AMGuard.verify_a2a_subagent_hop(
            parent_envelope=finvault_envelope,
            delegation_exp_epoch=int(now + 300),
            current_depth=4,
            now_epoch=now,
        )


def test_compute_plane_redis_bigquery_token_bucket_drift_reconciliation() -> (
    None
):
    rec = ComputePlane2AMGuard.reconcile_redis_with_bigquery_truth(
        tenant_id="tenant-retailstream-beta",
        redis_consumed_tokens=32000,
        bigquery_billed_tokens=39500,
        tier_tpm_limit=40000,
    )
    assert rec["authoritative_consumed_tokens"] == 39500
    assert rec["drift_corrected_tokens"] == 7500
    assert rec["remaining_tpm_budget"] == 500
    assert rec["quota_exhausted"] is False


def test_data_plane_substrate_agnostic_3_hop_bindings_and_mcp_conditional_rules(
    finvault_envelope: ContextEnvelope,
    retailstream_envelope: ContextEnvelope,
) -> None:
    for substrate, expected_snippet in [
        (
            "alloydb_postgresql",
            "SET LOCAL app.current_tenant_id = 'tenant-finvault-alpha';",
        ),
        ("cloud_spanner", "request.tag='tenant_id=tenant-finvault-alpha'"),
        (
            "cloud_firestore",
            "/tenants/tenant-finvault-alpha/documents/incidents",
        ),
        ("bigquery_rap", "FILTER USING (tenant_id = 'tenant-finvault-alpha')"),
    ]:
        binding = SubstrateAgnostic3HopAdapter.build_substrate_binding(
            envelope=finvault_envelope, substrate=substrate
        )
        assert expected_snippet in (
            binding["hop3_statement"] + binding["policy_ddl"]
        )

    mcp_guard = MCPConditionalPerimeterGuard()
    allowed = mcp_guard.evaluate_mcp_call(
        envelope=retailstream_envelope,
        server_id="cymbal-mcp-telemetry",
        mcp_tool_name="docs_readonly",
        mcp_method="tools/call",
        is_read_only=True,
    )
    assert allowed["status"] == "MCP_PERIMETER_ALLOWED"

    # Standard tier mutating tool must be blocked when mcp.tool.isReadOnly=False policy is active
    with pytest.raises(
        PermissionError, match="E_MCP_CONDITIONAL_READONLY_POLICY"
    ):
        mcp_guard.evaluate_mcp_call(
            envelope=retailstream_envelope,
            server_id="cymbal-mcp-telemetry",
            mcp_tool_name="send_email",
            mcp_method="tools/call",
            is_read_only=False,
        )

    # MCP server outage opens circuit breaker for graceful degradation
    mcp_guard.set_mcp_server_circuit(
        server_id="cymbal-mcp-telemetry", is_open=True
    )
    with pytest.raises(PermissionError, match="E_MCP_SERVER_CIRCUIT_OPEN"):
        mcp_guard.evaluate_mcp_call(
            envelope=finvault_envelope,
            server_id="cymbal-mcp-telemetry",
            mcp_tool_name="docs_readonly",
            mcp_method="tools/call",
            is_read_only=True,
        )


def test_open_standards_okf_provenance_a2ui_xss_and_otel_cardinality_guard(
    finvault_envelope: ContextEnvelope,
    retailstream_envelope: ContextEnvelope,
) -> None:
    now = time.time()
    artifact = OKFKnowledgeVerifier.create_attested_artifact(
        document_id="DOC-FV-SEC-17A4",
        tenant_id="tenant-finvault-alpha",
        content="SEC 17a-4 WORM retention procedure.",
        freshness_ttl_seconds=3600,
        published_at_epoch=now - 60,
    )
    verified = OKFKnowledgeVerifier.verify_for_tenant(
        artifact=artifact, envelope=finvault_envelope, now_epoch=now
    )
    assert verified["okf_version"] == "0.2"

    # Cross-tenant OKF artifact consumption must fail
    with pytest.raises(PermissionError, match="E_OKF_CROSS_TENANT_PROVENANCE"):
        OKFKnowledgeVerifier.verify_for_tenant(
            artifact=artifact, envelope=retailstream_envelope, now_epoch=now
        )

    # Stale OKF artifact beyond freshness_ttl_seconds must fail
    with pytest.raises(PermissionError, match="E_OKF_ARTIFACT_STALE"):
        OKFKnowledgeVerifier.verify_for_tenant(
            artifact=artifact, envelope=finvault_envelope, now_epoch=now + 7200
        )

    # Observability cardinality guard strips raw user_id and keeps low-cardinality dimensions
    sanitized_attrs = (
        ObservabilityCardinalityGuard.sanitize_otel_metric_attributes(
            {
                "tenant_id": "tenant-finvault-alpha",
                "agent_id": "cymbal_shared_diagnostic_agent",
                "tool_name": "query_telemetry_rls",
                "model_id": "gemini-4-argon",
                "user_id": "alice.personal.pii@finvault.com",
            }
        )
    )
    assert "user_id" not in sanitized_attrs
    assert "user_hash_bucket" in sanitized_attrs

    # A2UI card escapes XSS payloads while binding tenant_id
    card = A2UITenantCardBuilder.build_diagnostic_card(
        envelope=finvault_envelope,
        title="<script>alert('xss')</script>Wire Anomaly",
        incident_id="INC-FV-1001",
        summary="All SSNs redacted.",
    )
    assert card["protocol"] == "a2ui/v1"
    assert "<script>" not in card["props"]["title"]
    assert "&lt;script&gt;" in card["props"]["title"]


def test_dynamic_model_tiering_agent_plugins_and_a2a_cards_endpoints(
    finvault_envelope: ContextEnvelope,
    retailstream_envelope: ContextEnvelope,
) -> None:
    from app.main import app
    from fastapi.testclient import TestClient

    # 1. Dynamic Model Tiering (Hydrogen vs Carbon vs Gemma 3)
    r_routine = DynamicModelTierRouter.route_model(
        envelope=finvault_envelope, task_type="intent_classification"
    )
    assert r_routine["selected_model"] == "gemini-4-hydrogen"

    r_complex_fv = DynamicModelTierRouter.route_model(
        envelope=finvault_envelope, task_type="root_cause_synthesis"
    )
    assert r_complex_fv["selected_model"] == "gemini-4-hydrogen"

    r_complex_rs = DynamicModelTierRouter.route_model(
        envelope=retailstream_envelope, task_type="root_cause_synthesis"
    )
    assert r_complex_rs["selected_model"] == "gemini-4-hydrogen"

    r_sovereign = DynamicModelTierRouter.route_model(
        envelope=finvault_envelope,
        task_type="root_cause_synthesis",
        sovereign_open_weight_required=True,
    )
    assert r_sovereign["selected_model"] == "gemma-3-27b-it"

    # 2. Agent Plugin Bundle Loader & A2A Cards
    fv_plugin = AgentPluginLoader.load_plugin_for_tenant(
        envelope=finvault_envelope
    )
    rs_plugin = AgentPluginLoader.load_plugin_for_tenant(
        envelope=retailstream_envelope
    )
    fv_tools = {t["name"] for t in fv_plugin["entitled_mcp_tools"]}
    rs_tools = {t["name"] for t in rs_plugin["entitled_mcp_tools"]}
    assert "create_jira_incident" in fv_tools
    assert "create_jira_incident" not in rs_tools
    assert "create_servicenow_incident" in rs_tools
    assert "create_servicenow_incident" not in fv_tools

    fv_cards = A2AAgentCardRegistry.build_a2a_agent_cards(
        envelope=finvault_envelope
    )
    rs_cards = A2AAgentCardRegistry.build_a2a_agent_cards(
        envelope=retailstream_envelope
    )
    assert len(fv_cards["agent_cards"]) == 2
    assert len(rs_cards["agent_cards"]) == 1

    # 3. FastAPI /.well-known/agent.json and /api/v1/2am-chaos/{mode} endpoints
    client = TestClient(app)
    from scripts.sandbox_auth import SandboxCaller

    fv = SandboxCaller(
        client, tenant_id="tenant-finvault-alpha", sub="alice@finvault.com"
    )
    a2a_resp = client.get(
        "/.well-known/agent.json",
        headers=fv.headers("GET", fv.url("/.well-known/agent.json")),
    )
    assert a2a_resp.status_code == 200
    assert a2a_resp.json()["a2a_DiscoveryVersion"] == "1.0"
    assert "allowlisted_tools" in a2a_resp.json()["agent_cards"][0]

    for mode in (
        "tier_downgrade_cache",
        "a2a_expiration_and_drift",
        "substrate_agnostic_3hop",
        "open_standards_bundle",
    ):
        resp = client.post(f"/api/v1/2am-chaos/{mode}")
        assert resp.status_code == 200
        assert resp.json()["failure_mode"] == mode
