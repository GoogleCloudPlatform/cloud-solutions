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

# pylint: disable=line-too-long

"""Breach Simulation 1: Catalog & Visibility Isolation (Governance Pillar 1 — Hop 2).

Verifies:
1. RetailStream Corp (Standard Tier) cannot see FinVault Bank's private `Agent Alpha` in
   ARD catalog discovery (`/.well-known/ai-catalog.json`).
2. Direct API invocation of `finvault_regulatory_escalation_agent` by RetailStream raises
   `403 Forbidden`.
3. ADK `before_agent_callback` dynamically prunes FinVault-only 3LO tools (`create_jira_incident`,
   `send_gmail_brief`) from RetailStream's active prompt and vice versa.
"""

from __future__ import annotations

import pytest
from agents.agent_alpha import build_agent_alpha
from agents.context import ContextEnvelope
from agents.interceptors import (
    OTelAuditSink,
    enforce_tenant_isolation_interceptor,
)
from agents.registry import AgentRegistryPDP
from agents.shared_diagnostic_agent import build_shared_diagnostic_agent
from agents.testing_fakes import MockADKCallbackContext
from mcp_server.server import (
    create_jira_incident,
    create_servicenow_incident,
    read_runbook,
    read_sharepoint_runbook,
    send_gmail_brief,
)


def test_ard_catalog_hides_agent_alpha_from_retailstream(
    registry_pdp: AgentRegistryPDP,
) -> None:
    finvault_catalog = registry_pdp.discover_ai_catalog("tenant-finvault-alpha")
    retailstream_catalog = registry_pdp.discover_ai_catalog(
        "tenant-retailstream-beta"
    )

    fv_agents = {a["agent_id"] for a in finvault_catalog["agents"]}
    rs_agents = {a["agent_id"] for a in retailstream_catalog["agents"]}

    assert "cymbal_shared_diagnostic_agent" in fv_agents
    assert "finvault_regulatory_escalation_agent" in fv_agents

    assert rs_agents == {"cymbal_shared_diagnostic_agent"}
    assert "finvault_regulatory_escalation_agent" not in rs_agents


async def test_retailstream_direct_call_to_agent_alpha_returns_403(
    retailstream_envelope: ContextEnvelope,
    registry_pdp: AgentRegistryPDP,
    otel_sink: OTelAuditSink,
) -> None:
    private_agent = build_agent_alpha()
    ctx = MockADKCallbackContext(
        state=retailstream_envelope.to_adk_state(),
        agent=private_agent,
    )
    with pytest.raises(PermissionError, match="403 Forbidden"):
        await enforce_tenant_isolation_interceptor(
            ctx, registry_pdp=registry_pdp, otel_sink=otel_sink
        )


async def test_before_agent_callback_prunes_unentitled_3lo_tools(
    finvault_envelope: ContextEnvelope,
    retailstream_envelope: ContextEnvelope,
    registry_pdp: AgentRegistryPDP,
    otel_sink: OTelAuditSink,
) -> None:
    shared_agent = build_shared_diagnostic_agent()

    # FinVault Bank turn: should receive Jira & Gmail 3LO tools, NOT ServiceNow/SharePoint
    fv_ctx = MockADKCallbackContext(
        state=finvault_envelope.to_adk_state(),
        agent=shared_agent,
    )
    await enforce_tenant_isolation_interceptor(
        fv_ctx, registry_pdp=registry_pdp, otel_sink=otel_sink
    )
    fv_tool_names = {
        getattr(t, "name", getattr(t, "__name__", ""))
        for t in fv_ctx.active_tools
    }
    assert fv_tool_names == {
        "query_telemetry_rls",
        "read_runbook",
        "execute_diagnostic_sandbox",
        "create_jira_incident",
        "send_gmail_brief",
    }

    # RetailStream Corp turn: should receive ServiceNow & SharePoint 3LO tools, NOT Jira/Gmail
    rs_ctx = MockADKCallbackContext(
        state=retailstream_envelope.to_adk_state(),
        agent=shared_agent,
    )
    await enforce_tenant_isolation_interceptor(
        rs_ctx, registry_pdp=registry_pdp, otel_sink=otel_sink
    )
    rs_tool_names = {
        getattr(t, "name", getattr(t, "__name__", ""))
        for t in rs_ctx.active_tools
    }
    assert rs_tool_names == {
        "query_telemetry_rls",
        "read_runbook",
        "execute_diagnostic_sandbox",
        "create_servicenow_incident",
        "read_sharepoint_runbook",
    }

    # Direct MCP tool call by RetailStream to FinVault's Jira tool must fail closed with 403
    with pytest.raises(PermissionError, match="403 Forbidden"):
        await create_jira_incident("Spoofed Jira ticket", tool_context=rs_ctx)

    # Direct MCP tool call by FinVault to RetailStream's ServiceNow tool must fail closed with 403
    with pytest.raises(PermissionError, match="403 Forbidden"):
        await create_servicenow_incident(
            "Spoofed ServiceNow ticket", tool_context=fv_ctx
        )

    # Positive invocations for entitled tools succeed with DLP redaction & RLS scoping
    fv_rb = await read_runbook(tool_context=fv_ctx)
    assert fv_rb["runbooks"][0]["runbook_id"] == "RB-FV-01"
    fv_jira = await create_jira_incident(
        "Wire alert SSN 123-45-6789", tool_context=fv_ctx
    )
    assert "[REDACTED_BANKING_SSN]" in fv_jira["summary"]
    fv_mail = await send_gmail_brief(
        "exec@finvault.com", "Wire brief ABA: 021000021", tool_context=fv_ctx
    )
    assert "[REDACTED_ABA_ROUTING]" in fv_mail["body"]

    rs_snow = await create_servicenow_incident(
        "Cart 503 PAN 4532-0151-1283-0366", tool_context=rs_ctx
    )
    assert "[REDACTED_PAYMENT_PAN]" in rs_snow["short_description"]
    rs_sp = await read_sharepoint_runbook(
        "/sites/ops/runbook.md", tool_context=rs_ctx
    )
    assert rs_sp["provider"] == "microsoft-entra-sharepoint-3lo"
