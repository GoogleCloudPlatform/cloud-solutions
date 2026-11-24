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

"""Tests for the 30-Prompt Inspectable JSONL Batch Dataset & MCP JSON-RPC 2.0 Wire Endpoint."""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient
from scripts.run_extended_golden_e2e import run_extended_golden_suite
from scripts.run_verifiable_batch_audit import run_batch_dataset_audit


async def test_40_case_extended_golden_e2e_suite_passes() -> None:
    """Proves all 55 Golden E2E cases + sandbox & near-boundary benign telemetry pass."""
    report = await run_extended_golden_suite()
    assert report["status"] == "PASS"
    assert report["score"] == "55/55 PASS"
    assert report["total_golden_cases"] == 55
    assert report["passed_golden_cases"] == 55
    for c in report["cases"]:
        assert c["passed"] is True, f"Golden case failed: {c}"
    sbx_tel = report["sandbox_and_boundary_telemetry"]
    assert sbx_tel["batch_total_cases"] == 45
    assert sbx_tel["batch_passed_cases"] == 45
    assert sbx_tel["sandbox_and_boundary_cases"] >= 10
    assert (
        sbx_tel["sandbox_and_boundary_passed"]
        == sbx_tel["sandbox_and_boundary_cases"]
    )
    assert sbx_tel["confusion_matrix"]["fp_rate"] == 0.0
    assert sbx_tel["confusion_matrix"]["fnr"] == 0.0


def test_30_prompt_jsonl_batch_dataset_passes_with_zero_bleed() -> None:
    """Runs all 45 cases in `adversarial_batch_dataset.jsonl` and verifies 45/45 PASS + CM."""
    report = run_batch_dataset_audit()
    assert report["status"] == "PASS"
    assert report["total_cases"] == 45
    assert report["passed_cases"] == 45
    assert report["mcp_jsonrpc_wire_verified"] is True
    assert report["confusion_matrix"]["fp_rate"] == 0.0
    assert report["confusion_matrix"]["fnr"] == 0.0
    assert report["confusion_matrix"]["refusal_accuracy"] == 1.0
    for r in report["results"]:
        assert r["passed"] is True, f"Batch case failed: {r}"
        assert r["zero_pii_leak"] is True
        assert r["zero_cross_tenant_bleed"] is True


def test_mcp_jsonrpc_2_0_wire_protocol_enforces_tenant_and_3lo_boundaries() -> (
    None
):
    """Proves `POST /mcp/v1/jsonrpc` enforces ContextEnvelope auth, RLS, and 3LO scopes over
    HTTP.
    """
    from scripts.sandbox_auth import SandboxCaller

    client = TestClient(app)
    fv = SandboxCaller(
        client,
        tenant_id="tenant-finvault-alpha",
        sub="alice@finvault.com",
        role="sre_admin",
    )
    rs = SandboxCaller(
        client,
        tenant_id="tenant-retailstream-beta",
        sub="bob@retailstream.com",
        role="sre_admin",
    )

    def mcp(
        caller: SandboxCaller, body: dict[str, object]
    ) -> dict[str, object]:
        url = "/mcp/v1/jsonrpc"
        return client.post(
            url, json=body, headers=caller.headers("POST", caller.url(url))
        ).json()

    # 1. Missing ContextEnvelope -> JSON-RPC error -32001 (401 Unauthorized)
    unauth = client.post(
        "/mcp/v1/jsonrpc",
        json={"jsonrpc": "2.0", "id": 10, "method": "tools/list"},
    ).json()
    assert unauth["error"]["code"] == -32001

    # 2. FinVault tools/list -> includes Jira/Gmail/Calendar, excludes ServiceNow/SharePoint
    fv_list = mcp(fv, {"jsonrpc": "2.0", "id": 11, "method": "tools/list"})
    fv_tool_names = {t["name"] for t in fv_list["result"]["tools"]}
    assert "create_jira_incident" in fv_tool_names
    assert "schedule_calendar_postmortem" in fv_tool_names
    assert "create_servicenow_incident" not in fv_tool_names

    # 3. RetailStream tools/call on `query_telemetry_rls` -> returns only RetailStream rows with
    # redacted PAN
    rs_call = mcp(
        rs,
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "query_telemetry_rls",
                "arguments": {"severity": "P1"},
            },
        },
    )
    content = rs_call["result"]["content"]
    assert content["tenant_id"] == "tenant-retailstream-beta"
    assert len(content["incidents"]) == 1
    assert content["incidents"][0]["incident_id"] == "INC-RS-2001"
    assert "[REDACTED_PAYMENT_PAN]" in content["incidents"][0]["pii_notes"]

    # 4. RetailStream attempting `create_jira_incident` over MCP JSON-RPC -> error -32003 (403
    # Forbidden)
    rs_forbidden = mcp(
        rs,
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "create_jira_incident",
                "arguments": {"summary": "Forbidden Jira call"},
            },
        },
    )
    assert rs_forbidden["error"]["code"] == -32003
    assert "403 Forbidden" in rs_forbidden["error"]["message"]

    # 5. Claiming a tenant in the payload is refused, even with a valid token.
    claimed = mcp(
        rs,
        {
            "jsonrpc": "2.0",
            "id": 14,
            "authenticated_tenant_id": "tenant-finvault-alpha",
            "method": "tools/list",
        },
    )
    assert claimed["error"]["code"] == -32600


async def test_intra_tenant_rbac_blocks_analyst_from_write_tools_and_agent_alpha() -> (
    None
):
    """Proves Level 2 Intra-Tenant User RBAC: Dave (`read_only_analyst` at FinVault) cannot write
    Jira or call Agent Alpha.
    """
    import time
    import uuid

    import pytest
    from agents.context import EdgeAuthVerifier
    from agents.interceptors import enforce_tenant_isolation_interceptor
    from agents.registry import AgentRegistryPDP
    from agents.shared_diagnostic_agent import build_shared_diagnostic_agent
    from agents.testing_fakes import MockADKCallbackContext
    from mcp_server.server import create_jira_incident

    verifier = EdgeAuthVerifier()
    registry = AgentRegistryPDP()

    # Dave is a valid FinVault Bank employee, but his JWT carries `user_role="read_only_analyst"`
    dave_env = verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://accounts.google.com",
            "sub": "dave@finvault.com",
            "tenant_id": "tenant-finvault-alpha",
            "user_role": "read_only_analyst",
            "exp": int(time.time()) + 3600,
            "jti": f"jwt-dave-{uuid.uuid4().hex[:8]}",
        },
        dpop_proof={
            "jkt": "thumb-dave",
            "jti": f"dpop-dave-{uuid.uuid4().hex}",
        },
        session_id="sess-dave-ro",
    )

    # 1. Hop 2: Shared Agent prunes `create_jira_incident`, `send_gmail_brief`,
    # `schedule_calendar_postmortem` for Dave
    shared_agent = build_shared_diagnostic_agent()
    dave_ctx = MockADKCallbackContext(
        state=dave_env.to_adk_state(), agent=shared_agent
    )
    await enforce_tenant_isolation_interceptor(dave_ctx, registry_pdp=registry)
    dave_tools = {
        getattr(t, "name", getattr(t, "__name__", ""))
        for t in dave_ctx.active_tools
    }
    assert "query_telemetry_rls" in dave_tools
    assert "read_runbook" in dave_tools
    assert "create_jira_incident" not in dave_tools
    assert "send_gmail_brief" not in dave_tools
    assert "schedule_calendar_postmortem" not in dave_tools

    # 2. Hop 2: Dave is blocked with 403 Forbidden if he tries to invoke FinVault's private `Agent
    # Alpha`
    with pytest.raises(PermissionError, match="403 Forbidden"):
        registry.verify_agent_access(
            tenant_id="tenant-finvault-alpha",
            agent_id="finvault_regulatory_escalation_agent",
            caller_scopes=dave_env.tenant.authorized_scopes,
        )

    # 3. Hop 5: Dave is blocked with 403 Forbidden if he tries to call `create_jira_incident`
    # directly at the MCP server
    with pytest.raises(PermissionError, match="403 Forbidden"):
        await create_jira_incident(
            summary="Unauthorized ticket by read-only analyst",
            tool_context=dave_ctx,
        )
