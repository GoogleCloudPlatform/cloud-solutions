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

"""Tests for Vertex AI ReasoningEngine Multi-Tenant Adapter & Relational SQL RLS Engine Verifier."""

from __future__ import annotations

import pytest
from agents.reasoning_engine_app import (
    CymbalMultiTenantReasoningEngineApp,
    sanitize_before_model_callback,
    sanitize_gcp_project_id,
)
from mcp_server.sql_rls_engine_verifier import RelationalSQLRLSVerifier


def test_relational_sql_rls_engine_executes_schema_and_enforces_policies() -> (
    None
):
    """Proves `mcp_server/schema.sql` compiles and enforces fail-closed RLS in a real SQL engine."""
    verifier = RelationalSQLRLSVerifier()
    report = verifier.run_verification_suite()

    assert report["status"] == "PASS"
    assert report["unset_guc_row_count"] == 0
    assert report["unset_role_row_count"] == 0
    assert report["unset_agent_row_count"] == 0
    assert report["finvault_incident_ids"] == ["INC-FV-1001", "INC-FV-1002"]
    assert report["retailstream_incident_ids"] == ["INC-RS-2001"]
    assert report["rbac_unauthorized_role_row_count"] == 0
    assert report["rbac_unauthorized_agent_row_count"] == 0
    assert report["write_rbac_analyst_updated_rows"] == 0
    assert report["write_rbac_sre_updated_rows"] == 1
    assert report["column_rbac_immutable_blocked"] is True
    assert report["post_tx_reset_row_count"] == 0
    assert report["guc_tampering_blocked"] is True
    assert "tenant_incidents" in report["compiled_policies"]
    assert "tenant_runbooks" in report["compiled_policies"]


@pytest.mark.asyncio
async def test_rls_database_pool_sets_user_role_and_agent_id_session_gucs() -> (
    None
):
    """Verifies `RLSDatabasePool` binds `app.current_user_role` and `app.current_agent_id`
    alongside `app.current_tenant_id`.
    """
    from mcp_server.db import RLSDatabasePool

    pool = RLSDatabasePool()
    rows = await pool.query_incidents(
        tenant_id="tenant-finvault-alpha",
        user_role="sre_admin",
        agent_id="sre_diagnostic_agent",
    )
    assert len(rows) == 2
    assert pool.last_executed_guc == (
        "SET LOCAL app.current_tenant_id = 'tenant-finvault-alpha'; "
        "SET LOCAL app.current_user_role = 'sre_admin'; "
        "SET LOCAL app.current_agent_id = 'sre_diagnostic_agent';"
    )

    # Positive allowlist blocks any arbitrary unlisted role or agent at the database pool RBAC check
    blocked_role = await pool.query_incidents(
        tenant_id="tenant-finvault-alpha",
        user_role="guest_intern",
        agent_id="sre_diagnostic_agent",
    )
    assert blocked_role == []

    blocked_agent = await pool.query_runbooks(
        tenant_id="tenant-finvault-alpha",
        user_role="sre_admin",
        agent_id="rogue_external_agent",
    )
    assert blocked_agent == []

    # Identifier regex validation blocks malformed/injected user_role or agent_id values
    with pytest.raises(PermissionError, match="E_RLS_TAMPERING_DETECTED"):
        await pool.query_incidents(
            tenant_id="tenant-finvault-alpha",
            user_role="sre_admin'; DROP TABLE--",
        )

    # SQL tampering attempting to override app.current_user_role or app.current_agent_id is rejected
    with pytest.raises(PermissionError, match="E_RLS_TAMPERING_DETECTED"):
        pool.validate_sql_safety(
            "SELECT set_config('app.current_user_role', 'sre_admin', true);"
        )
    with pytest.raises(PermissionError, match="E_RLS_TAMPERING_DETECTED"):
        pool.validate_sql_safety(
            "SET LOCAL app.current_agent_id = 'sre_diagnostic_agent';"
        )


def test_reasoning_engine_sanitizes_double_projects_prefix_and_pre_model_pii() -> (
    None
):
    """Verifies Cloud Trace `projects/projects/...` fix and pre-model PII callback."""
    assert sanitize_gcp_project_id("projects/123456789012") == "123456789012"
    assert (
        sanitize_gcp_project_id("projects/projects/cymbal-multitenancy-example")
        == "cymbal-multitenancy-example"
    )

    cleaned, findings = sanitize_before_model_callback(
        "Customer SSN 123-45-6789 and card 4532-0151-1283-0366 failed."
    )
    assert "123-45-6789" not in cleaned
    assert "4532-0151-1283-0366" not in cleaned
    assert "US_SSN" in findings
    assert "CREDIT_CARD" in findings


def test_reasoning_engine_enforces_5_hops_and_blocks_cross_tenant_agent_alpha() -> (
    None
):
    """Verifies `CymbalMultiTenantReasoningEngineApp.query()` enforces all 5 hops."""
    app = CymbalMultiTenantReasoningEngineApp(
        project_id="projects/cymbal-multitenancy-example"
    )
    app.set_up()

    # 1. Valid FinVault turn with spoofed RetailStream header -> spoofed header stripped, 8000
    # budget, 2 RLS rows
    fv = app.query(
        prompt="Inspect wire settlement incidents.",
        authorization_bearer="Bearer mock-finvault-oidc-jwt",
        spoofed_headers={"X-Tenant-ID": "tenant-retailstream-beta"},
        requested_thinking_tokens=16000,
    )
    assert fv["tenant_id"] == "tenant-finvault-alpha"
    assert fv["clamped_thinking_budget"] == 8000
    assert fv["rls_incidents_returned"] == 2
    assert "create_jira_incident" in fv["pruned_active_tools"]
    assert "create_servicenow_incident" not in fv["pruned_active_tools"]

    # 2. Valid RetailStream turn -> 4000 budget clamp, 1 RLS row, Jira pruned
    rs = app.query(
        prompt="Inspect checkout incidents for card 4532-0151-1283-0366.",
        authorization_bearer="Bearer mock-retailstream-entra-jwt",
        requested_thinking_tokens=16000,
    )
    assert rs["tenant_id"] == "tenant-retailstream-beta"
    assert rs["clamped_thinking_budget"] == 4000
    assert rs["rls_incidents_returned"] == 1
    assert "create_servicenow_incident" in rs["pruned_active_tools"]
    assert "create_jira_incident" not in rs["pruned_active_tools"]

    # 3. RetailStream attempting to invoke FinVault's private Agent Alpha -> PermissionError (403)
    with pytest.raises(PermissionError, match="403 Forbidden"):
        app.query(
            prompt="Run FinVault regulatory escalation.",
            authorization_bearer="Bearer mock-retailstream-entra-jwt",
            target_agent_id="finvault_regulatory_escalation_agent",
        )
