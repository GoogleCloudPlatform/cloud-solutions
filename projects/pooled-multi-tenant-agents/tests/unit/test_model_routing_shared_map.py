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

# pylint: disable=line-too-long,protected-access

"""Verification suite for Hop 3 Model Routing: Shared Map and First Move (ADR-0015).

Tests Track 1 FastSearch harness trimming, AskPro mid-task advisor escalation caps,
cross-family `<thought>` sanitization, TTL policy cache expiry, synchronous tenant
offboarding eviction, and end-to-end FastAPI DPoP HTTP boundaries with zero mocks.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from agents.context import (
    ContextEnvelope,
    EdgeAuthVerifier,
    SubscriptionTier,
    offboard_tenant,
    register_tenant,
    reset_dynamic_tenants,
)
from agents.model_routing import (
    CrossFamilySessionSanitizer,
    FastSearchHarnessTrimmer,
    ModelRoutingMode,
    SharedModelRoutingPDP,
    TaskComplexityClass,
)
from app.main import MODEL_ROUTING_PDP, app
from fastapi.testclient import TestClient
from scripts.sandbox_auth import SandboxCaller

FINVAULT_TENANT = "tenant-finvault-alpha"
RETAILSTREAM_TENANT = "tenant-retailstream-beta"

client = TestClient(app)


def _mint_envelope(
    tenant_id: str = FINVAULT_TENANT,
    sub: str = "alice@finvault.com",
    user_role: str = "sre_admin",
    iss: str = "https://accounts.google.com",
) -> ContextEnvelope:
    """Mints a verified ContextEnvelope via EdgeAuthVerifier for unit tests."""
    verifier = EdgeAuthVerifier()
    return verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": iss,
            "sub": sub,
            "tenant_id": tenant_id,
            "user_role": user_role,
            "exp": int(time.time()) + 600,
        },
        dpop_proof={
            "jkt": f"jkt-{tenant_id}",
            "jti": f"jti-{uuid.uuid4().hex}",
            "htm": "POST",
            "htu": "https://cymbal.internal/api/v1/invoke-agent",
        },
    )


def _caller(tenant_id: str, sub: str, role: str = "sre_admin") -> SandboxCaller:
    """Builds a real RFC 9449 DPoP-authenticated sandbox caller."""
    return SandboxCaller(client, tenant_id=tenant_id, sub=sub, role=role)


def _post_dpop(
    caller: SandboxCaller, path: str, payload: dict[str, Any]
) -> Any:
    """Sends a DPoP-bound POST request to the FastAPI gateway."""
    return client.post(
        path,
        json=payload,
        headers=caller.headers("POST", caller.url(path)),
    )


def _get_dpop(caller: SandboxCaller, path: str) -> Any:
    """Sends a DPoP-bound GET request to the FastAPI gateway."""
    return client.get(
        path,
        headers=caller.headers("GET", caller.url(path)),
    )


def test_fast_search_harness_trimmer_prunes_write_tools_and_saves_schema_tokens() -> (
    None
):
    """Track 1 FastSearch routes lookup queries to Flash and strips mutating tools."""
    finvault_envelope = _mint_envelope()
    routing_pdp = SharedModelRoutingPDP()
    entitled_tools = (
        "query_telemetry_rls",
        "read_runbook",
        "create_jira_incident",
        "schedule_calendar_postmortem",
        "send_gmail_brief",
    )

    decision = routing_pdp.decide_route(
        envelope=finvault_envelope,
        agent_id="cymbal_shared_diagnostic_agent",
        tool_name="query_telemetry_rls",
        prompt="Lookup P1 latency telemetry and show incident runbook status.",
        entitled_tools=entitled_tools,
        requested_thinking_budget=8000,
    )

    assert decision.task_complexity == TaskComplexityClass.FAST_SEARCH_LOOKUP
    assert decision.selected_model == "gemini-4-hydrogen"
    assert decision.pruned_active_tools == (
        "query_telemetry_rls",
        "read_runbook",
    )
    assert decision.trimmed_write_tools_count == 3
    assert decision.allow_subagent_delegation is False
    assert decision.effective_thinking_budget == 2048
    assert decision.schema_tokens_saved == 1400
    assert decision.estimated_turn_usd_saved > 0.0


def test_mutating_prompt_or_regulatory_agent_preserves_full_entitled_harness() -> (
    None
):
    """Mutating prompts or regulatory escalations do not trim write tools."""
    finvault_envelope = _mint_envelope()
    routing_pdp = SharedModelRoutingPDP()
    entitled_tools = (
        "query_telemetry_rls",
        "read_runbook",
        "create_jira_incident",
    )

    standard_decision = routing_pdp.decide_route(
        envelope=finvault_envelope,
        agent_id="cymbal_shared_diagnostic_agent",
        tool_name="create_jira_incident",
        prompt="Create a P1 Jira incident and schedule postmortem for wire settlement.",
        entitled_tools=entitled_tools,
        requested_thinking_budget=8000,
        requested_mode=ModelRoutingMode.DETERMINISTIC,
    )
    assert (
        standard_decision.task_complexity
        == TaskComplexityClass.STANDARD_DIAGNOSTIC
    )
    assert standard_decision.selected_model == "gemini-4-hydrogen"
    assert standard_decision.pruned_active_tools == entitled_tools
    assert standard_decision.trimmed_write_tools_count == 0
    assert standard_decision.allow_subagent_delegation is True

    regulatory_decision = routing_pdp.decide_route(
        envelope=finvault_envelope,
        agent_id="finvault_regulatory_escalation_agent",
        tool_name="escalate_regulatory_filing",
        prompt="Escalate OCC 12 CFR Part 30 filing.",
        entitled_tools=("escalate_regulatory_filing",),
        requested_thinking_budget=8000,
    )
    assert (
        regulatory_decision.task_complexity
        == TaskComplexityClass.REGULATORY_ESCALATION
    )
    assert regulatory_decision.selected_model == "claude-3-7-sonnet@20250219"


def test_cross_family_session_sanitizer_strips_thoughts_and_verifies_state() -> (
    None
):
    """Switching between Claude and Gemini strips <thought> tags and guards state identity."""
    finvault_envelope = _mint_envelope()
    history = (
        "<thought>Internal Claude reasoning trace step 1</thought>Settlement delay confirmed.",
        "<thinking>Second hidden block</thinking>Escalation ticket drafted.",
    )

    sanitized, stripped_count = (
        CrossFamilySessionSanitizer.sanitize_history_for_target_model(
            previous_model_id="claude-3-7-sonnet@20250219",
            target_model_id="gemini-4-hydrogen",
            session_history=history,
            envelope=finvault_envelope,
            expected_agent_id="cymbal_shared_diagnostic_agent",
            session_state={
                "temp:tenant_id": FINVAULT_TENANT,
                "temp:agent_id": "cymbal_shared_diagnostic_agent",
            },
        )
    )
    assert stripped_count == 2
    assert sanitized == (
        "Settlement delay confirmed.",
        "Escalation ticket drafted.",
    )

    # Same-family transition preserves history without stripping.
    same_family_history, same_stripped = (
        CrossFamilySessionSanitizer.sanitize_history_for_target_model(
            previous_model_id="gemini-4-carbon",
            target_model_id="gemini-4-hydrogen",
            session_history=history,
            envelope=finvault_envelope,
            expected_agent_id="cymbal_shared_diagnostic_agent",
        )
    )
    assert same_stripped == 0
    assert same_family_history == history

    # Cross-tenant session state spoof raises PermissionError.
    with pytest.raises(PermissionError, match="E_CROSS_TENANT_SESSION_STATE"):
        CrossFamilySessionSanitizer.sanitize_history_for_target_model(
            previous_model_id="claude-3-7-sonnet@20250219",
            target_model_id="gemini-4-hydrogen",
            session_history=history,
            envelope=finvault_envelope,
            expected_agent_id="cymbal_shared_diagnostic_agent",
            session_state={"temp:tenant_id": RETAILSTREAM_TENANT},
        )

    # Agent identity drift raises PermissionError.
    with pytest.raises(PermissionError, match="E_AGENT_IDENTITY_DRIFT"):
        CrossFamilySessionSanitizer.sanitize_history_for_target_model(
            previous_model_id="claude-3-7-sonnet@20250219",
            target_model_id="gemini-4-hydrogen",
            session_history=history,
            envelope=finvault_envelope,
            expected_agent_id="cymbal_shared_diagnostic_agent",
            session_state={
                "temp:agent_id": "finvault_regulatory_escalation_agent"
            },
        )


def test_askpro_mid_task_escalation_enforces_one_consultation_per_turn_cap() -> (
    None
):
    """AskPro allows 1 consultation per (tenant_id, trace_id) and rejects the 2nd with 429."""
    finvault_envelope = _mint_envelope()
    routing_pdp = SharedModelRoutingPDP()

    first_receipt = routing_pdp.escalate_to_advisor(
        envelope=finvault_envelope,
        trace_id="trace-askpro-001",
        escalation_reason="ambiguous_evidence",
        compact_evidence_digest="AlloyDB p99 spike 1420ms; two candidate runbooks match.",
    )
    assert first_receipt["status"] == "ASKPRO_ADVISOR_COMPLETED"
    assert first_receipt["executor_model"] == "gemini-4-hydrogen"
    assert first_receipt["advisor_model"] == "gemini-4-carbon"
    assert first_receipt["consultation_index"] == 1
    assert first_receipt["incremental_usd_saved_vs_full_pro_loop"] > 0.0

    with pytest.raises(
        PermissionError, match="429 E_ASKPRO_CONSULTATION_CAP_EXCEEDED"
    ):
        routing_pdp.escalate_to_advisor(
            envelope=finvault_envelope,
            trace_id="trace-askpro-001",
            escalation_reason="tool_error_retry",
            compact_evidence_digest="Second attempt on same trace must fail closed.",
        )


def test_policy_ttl_expiry_and_synchronous_offboarding_eviction() -> None:
    """Policy cache expires at t + ttl + 1 and offboard_tenant immediately evicts all state."""
    try:
        register_tenant(
            tenant_id="tenant-routing-temp",
            display_name="Routing Temp Corp",
            tier=SubscriptionTier.STANDARD,
        )
        temp_envelope = _mint_envelope(
            tenant_id="tenant-routing-temp",
            sub="ops@routingtemp.com",
        )
        routing_pdp = SharedModelRoutingPDP(policy_ttl_seconds=30.0)

        # Standard tier cannot request ADAPTIVE_BANDIT_GUARDED.
        with pytest.raises(
            PermissionError, match="403 E_ROUTING_MODE_FORBIDDEN"
        ):
            routing_pdp.resolve_tenant_policy(
                temp_envelope,
                requested_mode=ModelRoutingMode.ADAPTIVE_BANDIT_GUARDED,
            )

        policy_t0 = routing_pdp.resolve_tenant_policy(temp_envelope, now=100.0)
        assert policy_t0.routing_mode == ModelRoutingMode.TRACK1_FAST_SEARCH
        assert "tenant-routing-temp" in routing_pdp._policy_cache

        # At t + ttl + 1 (131.0), the expired cache entry is replaced.
        policy_expired = routing_pdp.resolve_tenant_policy(
            temp_envelope, now=131.0
        )
        assert policy_expired.tenant_id == "tenant-routing-temp"
        expires_at, _ = routing_pdp._policy_cache["tenant-routing-temp"]
        assert expires_at == pytest.approx(161.0)

        # Record a decision and an AskPro consultation, then offboard the tenant.
        routing_pdp.decide_route(
            envelope=temp_envelope,
            agent_id="cymbal_shared_diagnostic_agent",
            tool_name="query_telemetry_rls",
            prompt="Lookup incident status",
            entitled_tools=("query_telemetry_rls",),
            requested_thinking_budget=4000,
        )
        assert (
            routing_pdp.ledger.get_tenant_summary(temp_envelope)["turns_routed"]
            == 1
        )

        offboard_tenant("tenant-routing-temp")

        # Synchronous check before cache lookup must reject offboarded tenant with 403.
        with pytest.raises(PermissionError, match="403 E_TENANT_OFFBOARDED"):
            routing_pdp.resolve_tenant_policy(temp_envelope, now=132.0)
        with pytest.raises(PermissionError, match="403 E_TENANT_OFFBOARDED"):
            routing_pdp.ledger.get_tenant_summary(temp_envelope)
    finally:
        reset_dynamic_tenants()


def test_http_endpoints_enforce_dpop_auth_and_tenant_isolated_telemetry() -> (
    None
):
    """Traces /api/v1/model-routing/* and /api/v1/invoke-agent from FastAPI Request to HTTP
    status.
    """
    # 1. Unauthenticated callers are rejected with HTTP 401 + DPoP challenge.
    assert (
        client.post("/api/v1/model-routing/decide", json={}).status_code == 401
    )
    assert (
        client.post(
            "/api/v1/model-routing/escalate-askpro",
            json={"trace_id": "t-1", "compact_evidence_digest": "digest"},
        ).status_code
        == 401
    )
    assert client.get("/api/v1/model-routing/telemetry").status_code == 401

    finvault_caller = _caller(
        FINVAULT_TENANT, "alice@finvault.com", "sre_admin"
    )
    retail_caller = _caller(
        RETAILSTREAM_TENANT, "bob@retailstream.com", "sre_admin"
    )

    # 2. Live /api/v1/invoke-agent includes Hop 3 model_routing receipt.
    invoke_response = _post_dpop(
        finvault_caller,
        "/api/v1/invoke-agent",
        {
            "agent_id": "cymbal_shared_diagnostic_agent",
            "tool_name": "query_telemetry_rls",
            "prompt": "Lookup P1 telemetry status and summarize runbook.",
        },
    )
    assert invoke_response.status_code == 200
    invoke_body = invoke_response.json()
    assert invoke_body["model_routing"]["selected_model"] == "gemini-4-hydrogen"
    assert (
        invoke_body["model_routing"]["task_complexity"] == "fast_search_lookup"
    )
    assert invoke_body["model_routing"]["schema_tokens_saved"] == 1400

    # 3. /api/v1/model-routing/decide strips cross-family <thought> tags and blocks cross-tenant
    # Agent Alpha.
    decide_response = _post_dpop(
        finvault_caller,
        "/api/v1/model-routing/decide",
        {
            "agent_id": "cymbal_shared_diagnostic_agent",
            "tool_name": "query_telemetry_rls",
            "prompt": "Search runbook telemetry for incident status.",
            "previous_model_id": "claude-3-7-sonnet@20250219",
            "session_history": [
                "<thought>Secret Claude chain</thought>Prior turn summary."
            ],
        },
    )
    assert decide_response.status_code == 200
    decide_data = decide_response.json()
    assert decide_data["cross_family_thoughts_stripped"] == 1
    assert decide_data["sanitized_session_history"] == ["Prior turn summary."]

    blocked_alpha = _post_dpop(
        retail_caller,
        "/api/v1/model-routing/decide",
        {
            "agent_id": "finvault_regulatory_escalation_agent",
            "tool_name": "escalate_regulatory_filing",
            "prompt": "Escalate OCC filing",
        },
    )
    assert blocked_alpha.status_code == 403

    # 4. /api/v1/model-routing/escalate-askpro enforces 1 consultation per trace_id (HTTP 200 then
    # HTTP 429).
    trace_id = "http-trace-askpro-99"
    first_esc = _post_dpop(
        finvault_caller,
        "/api/v1/model-routing/escalate-askpro",
        {
            "trace_id": trace_id,
            "escalation_reason": "ambiguous_evidence",
            "compact_evidence_digest": "Conflicting p99 telemetry across 2 shards.",
        },
    )
    assert first_esc.status_code == 200
    assert first_esc.json()["status"] == "ASKPRO_ADVISOR_COMPLETED"

    second_esc = _post_dpop(
        finvault_caller,
        "/api/v1/model-routing/escalate-askpro",
        {
            "trace_id": trace_id,
            "escalation_reason": "tool_error_retry",
            "compact_evidence_digest": "Second escalation in same turn.",
        },
    )
    assert second_esc.status_code == 429
    assert (
        second_esc.json()["detail"]["error"]
        == "E_ASKPRO_CONSULTATION_CAP_EXCEEDED"
    )

    # 5. /api/v1/model-routing/telemetry is strictly tenant-scoped.
    fv_telemetry = _get_dpop(
        finvault_caller, "/api/v1/model-routing/telemetry"
    ).json()
    rs_telemetry = _get_dpop(
        retail_caller, "/api/v1/model-routing/telemetry"
    ).json()
    assert fv_telemetry["tenant_id"] == FINVAULT_TENANT
    assert fv_telemetry["turns_routed"] >= 2
    assert fv_telemetry["askpro_escalations"] >= 1
    assert rs_telemetry["tenant_id"] == RETAILSTREAM_TENANT
    assert rs_telemetry["askpro_escalations"] == 0
    assert MODEL_ROUTING_PDP.ledger is not None
    assert FastSearchHarnessTrimmer is not None
