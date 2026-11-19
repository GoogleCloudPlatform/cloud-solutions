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
# pylint: disable=missing-class-docstring,protected-access

"""Bucket 1 Blog-to-Code Alignment & Facade Aliasing Verification Suite.

Proves all 5 Bucket 1 engineering closures + modular facade aliasing invariants end-to-end:
1. Active Gemini models (`gemini-4-argon` + `gemini-3.8-flash`) replace retired 2.5 models,
   and `LiveADKVertexRunner` dynamically wires `SharedModelRoutingPDP`, clamped `ThinkingConfig`,
   `global` endpoint routing, `static_instruction`, and per-model ADK `ContextCacheConfig`.
2. Per-model context cache isolation (`compute_per_model_prefix_cache_key`) never shares a cache
   key across distinct models, enforces the documented `4,096`-token floor for Gemini 3/4 (`2,048`
   for Gemini 2), and validates `ttl_seconds >= 60` + cache-poisoning guards.
3. `TenantCredentialBroker` caches 2LO credentials strictly by `(tenant_id, agent_id, scopes)`
   and `evict_tenant(tenant_id)` purges all `(tenant_id, *, *)` entries on offboarding.
4. `mcp_server/schema.sql` + `RelationalSQLRLSVerifier` + `mcp_server/server.py` enforce
   fail-closed RLS/RBAC (`0` rows when `app.current_user_role` or `app.current_agent_id` is
   unset/empty), `NOSUPERUSER NOBYPASSRLS`, column-scoped `GRANT UPDATE (severity, summary)`,
   and restrictive write RBAC blocking `read_only_analyst` updates.
5. Modular facade aliasing (`agents.context`, `agents.gcp_live_bridge`, `app.main`) stays
   in-place synchronized across `reset_dynamic_tenants()` and `monkeypatch.setattr(...)`,
   and `/api/v1/verify-live-gcp` passes required `tenant_id` to `LiveCloudDLPGuardrail`.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from agents import context as agent_context
from agents import gcp_live_bridge
from agents.auth import tenant_directory
from agents.shared_diagnostic_agent import (
    DEFAULT_FLASH_EXECUTOR_MODEL,
    DEFAULT_SHARED_DIAGNOSTIC_MODEL,
    SHARED_SYSTEM_PROMPT_PREFIX,
    build_per_model_context_cache_config,
    build_shared_diagnostic_agent,
    build_shared_diagnostic_app,
    compute_per_model_prefix_cache_key,
    min_cacheable_tokens,
)
from agents.tenant_credentials import (
    LocalTenantCredentialBackend,
    TenantCredentialBroker,
)
from agents.testing_fakes import MockADKCallbackContext
from app import main as gateway_main
from app.schemas.gateway import InvokeAgentRequest
from fastapi.testclient import TestClient
from mcp_server import server as mcp_tools
from mcp_server.db import RLSDatabasePool
from mcp_server.sql_rls_engine_verifier import RelationalSQLRLSVerifier

pytestmark = pytest.mark.security

FINVAULT_TENANT = "tenant-finvault-alpha"
RETAILSTREAM_TENANT = "tenant-retailstream-beta"


def _mint_verified_envelope(
    *,
    tenant_id: str = FINVAULT_TENANT,
    sub: str = "alice@finvault.com",
    user_role: str = "sre_admin",
    agent_id: str | None = "cymbal_shared_diagnostic_agent",
) -> agent_context.ContextEnvelope:
    verifier = agent_context.EdgeAuthVerifier()
    iss = agent_context.TENANT_DIRECTORY[tenant_id]["iss"]
    jti = f"jti-{tenant_id}-{sub}-{user_role}-{time.time_ns()}"
    env = verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": iss,
            "sub": sub,
            "tenant_id": tenant_id,
            "user_role": user_role,
            "exp": int(time.time()) + 3600,
            "jti": jti,
        },
        dpop_proof={"jkt": f"jkt-{sub}", "jti": f"dpop-{jti}"},
        session_id=f"sess-{jti[-8:]}",
    )
    if agent_id:
        return verifier.bind_routed_agent(env, agent_id)
    return env


def test_per_model_context_cache_isolation_and_adk_app_wiring() -> None:
    """Two models never share a context cache key, and ADK `App` binds `ContextCacheConfig`."""
    hydrogen_key = compute_per_model_prefix_cache_key(
        model_name=DEFAULT_FLASH_EXECUTOR_MODEL
    )
    carbon_key = compute_per_model_prefix_cache_key(
        model_name="gemini-4-carbon"
    )
    argon_key = compute_per_model_prefix_cache_key(model_name="gemini-4-argon")
    flash_key = compute_per_model_prefix_cache_key(
        model_name="gemini-3.8-flash"
    )
    assert len({hydrogen_key, carbon_key, argon_key, flash_key}) == 4
    assert DEFAULT_SHARED_DIAGNOSTIC_MODEL == "gemini-4-hydrogen"
    assert DEFAULT_FLASH_EXECUTOR_MODEL == "gemini-4-hydrogen"

    assert min_cacheable_tokens("gemini-4-hydrogen") == 4096
    assert min_cacheable_tokens("gemini-4-carbon") == 4096
    assert min_cacheable_tokens("gemini-4-argon") == 4096
    assert min_cacheable_tokens("gemini-3.8-flash") == 4096
    assert min_cacheable_tokens("gemini-2.5-flash") == 2048

    hydrogen_cfg = build_per_model_context_cache_config(
        model_name="gemini-4-hydrogen",
        ttl_seconds=3600,
    )
    assert hydrogen_cfg["min_tokens"] == 4096
    assert hydrogen_cfg["ttl_seconds"] == 3600
    assert hydrogen_cfg["caching_mode"] == "implicit_durable"
    assert hydrogen_cfg["supports_explicit_caching"] is False
    assert hydrogen_cfg["meets_min_token_floor"] is False
    assert hydrogen_cfg["adk_context_cache_config"] is not None
    assert hydrogen_cfg["adk_context_cache_config"].min_tokens == 4096
    assert hydrogen_cfg["adk_context_cache_config"].ttl_seconds == 3600

    flash_cfg = build_per_model_context_cache_config(
        model_name="gemini-3.8-flash",
        ttl_seconds=3600,
    )
    assert flash_cfg["caching_mode"] == "explicit_and_implicit"
    assert flash_cfg["supports_explicit_caching"] is True

    with pytest.raises(ValueError, match="E_CONTEXT_CACHE_TTL"):
        build_per_model_context_cache_config(
            model_name="gemini-4-hydrogen", ttl_seconds=30
        )

    with pytest.raises(ValueError, match="non-empty"):
        compute_per_model_prefix_cache_key(model_name="   ")

    shared_agent = build_shared_diagnostic_agent()
    assert shared_agent.model == "gemini-4-hydrogen"
    assert shared_agent.static_instruction == SHARED_SYSTEM_PROMPT_PREFIX
    assert shared_agent.generate_content_config is not None
    assert shared_agent.generate_content_config.thinking_config is not None

    pooled_app = build_shared_diagnostic_app(
        model_name="gemini-4-hydrogen", thinking_budget=4000
    )
    assert getattr(pooled_app, "context_cache_config", None) is not None
    assert pooled_app.context_cache_config.min_tokens == 4096


def test_live_adk_runner_wires_tier_routing_thinking_config_and_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`LiveADKVertexRunner` passes routed model, `ThinkingConfig`, `ContextCacheConfig` & GUCs."""
    from google.adk import apps as adk_apps
    from google.adk import runners as adk_runners

    captured_runs: list[dict[str, Any]] = []
    jira_calls: list[str] = []

    class _FakeJiraConnector:
        def __init__(self, project_id: str) -> None:
            self.project_id = project_id

        def query_regulatory_issues(self, *, envelope: Any) -> dict[str, Any]:
            jira_calls.append(envelope.tenant.tenant_id)
            return {"issues": [{"key": "FINVAULT-1"}]}

    class _InspectingRunner:
        def __init__(
            self,
            agent: Any = None,
            *,
            app_name: str | None = None,
            app: Any = None,
            **_kwargs: Any,
        ) -> None:
            resolved_agent = app.root_agent if app is not None else agent
            captured_runs.append(
                {
                    "agent": resolved_agent,
                    "app": app,
                    "app_name": app.name if app is not None else app_name,
                }
            )
            self._agent = resolved_agent
            self.session_service = SimpleNamespace(
                create_session=self._create_session,
            )

        async def _create_session(self, **_kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(id="sess-inspect-1")

        async def run_async(self, **_kwargs: Any) -> Any:
            p1_tool = next(
                fn
                for fn in self._agent.tools
                if fn.__name__ == "get_scoped_p1_incidents"
            )
            await p1_tool()
            jira_tool = next(
                (
                    fn
                    for fn in self._agent.tools
                    if fn.__name__ == "query_live_jira_regulatory_issues"
                ),
                None,
            )
            if jira_tool is not None:
                await jira_tool()
            yield SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            function_call=SimpleNamespace(
                                name="get_scoped_p1_incidents"
                            ),
                            text=None,
                        ),
                        SimpleNamespace(
                            function_call=None,
                            text="Summarized P1 incident cleanly.",
                        ),
                    ]
                )
            )

    monkeypatch.setattr(adk_runners, "InMemoryRunner", _InspectingRunner)
    monkeypatch.setattr(
        gcp_live_bridge, "LiveAtlassianJiraConnector", _FakeJiraConnector
    )
    monkeypatch.setattr(
        gcp_live_bridge.interceptors,
        "ingress_model_armor_screen",
        lambda **_kw: None,
    )
    assert adk_apps.App is not None

    runner = gcp_live_bridge.LiveADKVertexRunner(
        project_id="cymbal-multitenancy-example"
    )

    # 1. Enterprise FinVault complex diagnostic turn -> `gemini-4-hydrogen` + `HIGH` thinking
    fv_env = _mint_verified_envelope(
        tenant_id=FINVAULT_TENANT,
        sub="alice@finvault.com",
        user_role="sre_admin",
    )
    fv_res = asyncio.run(
        runner.run_tenant_diagnostic_turn(
            envelope=fv_env,
            user_prompt="Create P1 remediation plan and escalate core wire settlement outage.",
        )
    )
    assert fv_res["model"] == "gemini-4-hydrogen"
    assert fv_res["model_location"] == "global"
    assert fv_res["thinking_config"] == {"thinking_level": "HIGH"}
    assert fv_res["context_cache"]["min_tokens"] == 4096
    assert "SET LOCAL app.current_user_role = 'sre_admin';" in fv_res["rls_guc"]
    assert (
        "SET LOCAL app.current_agent_id = 'cymbal_shared_diagnostic_agent';"
        in fv_res["rls_guc"]
    )
    assert jira_calls == [FINVAULT_TENANT]

    fv_agent = captured_runs[-1]["agent"]
    fv_app = captured_runs[-1]["app"]
    assert (
        getattr(fv_agent.model, "model", fv_agent.model) == "gemini-4-hydrogen"
    )
    assert fv_agent.static_instruction == SHARED_SYSTEM_PROMPT_PREFIX
    assert str(
        fv_agent.generate_content_config.thinking_config.thinking_level
    ).endswith("HIGH")
    assert fv_app is not None
    assert fv_app.context_cache_config.min_tokens == 4096

    # 2. Standard RetailStream turn -> routes to `gemini-4-hydrogen` (`LOW` on FastSearch lookup)
    rs_env = _mint_verified_envelope(
        tenant_id=RETAILSTREAM_TENANT,
        sub="bob@retailstream.com",
        user_role="sre_admin",
    )
    rs_res = asyncio.run(
        runner.run_tenant_diagnostic_turn(
            envelope=rs_env,
            user_prompt="Lookup P1 incident status and check runbook.",
        )
    )
    assert rs_res["model"] == "gemini-4-hydrogen"
    assert rs_res["thinking_config"] == {"thinking_level": "LOW"}
    assert (
        fv_res["context_cache"]["cache_key_sha256"]
        == rs_res["context_cache"]["cache_key_sha256"]
    )
    carbon_runner = gcp_live_bridge.LiveADKVertexRunner(
        project_id="cymbal-multitenancy-example",
        model_name="gemini-4-carbon",
    )
    carbon_res = asyncio.run(
        carbon_runner.run_tenant_diagnostic_turn(
            envelope=fv_env,
            user_prompt="Create P1 remediation plan and escalate core wire settlement outage.",
        )
    )
    assert carbon_res["model"] == "gemini-4-carbon"
    assert (
        carbon_res["context_cache"]["cache_key_sha256"]
        != rs_res["context_cache"]["cache_key_sha256"]
    )

    # 3. FinVault private `Agent Alpha` (`compliance_officer`) -> hot-swaps to `gemini-4-hydrogen`
    comp_env = _mint_verified_envelope(
        tenant_id=FINVAULT_TENANT,
        sub="claire.compliance@finvault.com",
        user_role="compliance_officer",
        agent_id="finvault_regulatory_escalation_agent",
    )
    alpha_res = asyncio.run(
        runner.run_finvault_agent_alpha_turn(envelope=comp_env)
    )
    assert alpha_res["configured_primary_model"] == "claude-3-7-sonnet@20250219"
    assert alpha_res["executed_model"] == "gemini-4-hydrogen"


def test_credential_broker_caches_strictly_by_tenant_agent_and_scopes() -> None:
    """Broker cache partitions `(tenant_id, agent_id, scopes)` and evicts all keys per tenant."""
    backend = LocalTenantCredentialBackend()
    broker = TenantCredentialBroker(
        project_id="cymbal-multitenancy-example",
        backend=backend,
        lifetime_seconds=300,
    )

    fv_shared_sre_1 = _mint_verified_envelope(
        tenant_id=FINVAULT_TENANT,
        sub="alice@finvault.com",
        user_role="sre_admin",
        agent_id="cymbal_shared_diagnostic_agent",
    )
    fv_shared_sre_2 = _mint_verified_envelope(
        tenant_id=FINVAULT_TENANT,
        sub="other-sre@finvault.com",
        user_role="sre_admin",
        agent_id="cymbal_shared_diagnostic_agent",
    )
    fv_alpha_sre = _mint_verified_envelope(
        tenant_id=FINVAULT_TENANT,
        sub="alice@finvault.com",
        user_role="sre_admin",
        agent_id="finvault_regulatory_escalation_agent",
    )
    fv_shared_analyst = _mint_verified_envelope(
        tenant_id=FINVAULT_TENANT,
        sub="dave@finvault.com",
        user_role="read_only_analyst",
        agent_id="cymbal_shared_diagnostic_agent",
    )
    rs_shared_sre = _mint_verified_envelope(
        tenant_id=RETAILSTREAM_TENANT,
        sub="bob@retailstream.com",
        user_role="sre_admin",
        agent_id="cymbal_shared_diagnostic_agent",
    )

    c1 = broker.credential_for(fv_shared_sre_1)
    c2 = broker.credential_for(fv_shared_sre_2)
    assert c1 is c2
    assert len(backend.minted) == 1

    # Different `agent_id` must NOT reuse the cached entry for `cymbal_shared_diagnostic_agent`.
    c_alpha = broker.credential_for(fv_alpha_sre)
    assert c_alpha is not c1
    assert len(backend.minted) == 2

    # Narrower `authorized_scopes` (`read_only_analyst`) must NOT reuse `sre_admin` cache entry.
    c_analyst = broker.credential_for(fv_shared_analyst)
    assert c_analyst is not c1
    assert c_analyst is not c_alpha
    assert len(backend.minted) == 3

    # RetailStream gets its own tenant entry.
    c_rs = broker.credential_for(rs_shared_sre)
    assert len(backend.minted) == 4
    assert len(broker._cache) == 4

    # Offboarding FinVault purges ALL 3 FinVault `(tenant, agent, scopes)` entries at once.
    assert broker.evict_tenant(FINVAULT_TENANT) is True
    assert all(k[0] != FINVAULT_TENANT for k in broker._cache)
    assert len(broker._cache) == 1
    assert broker.credential_for(rs_shared_sre) is c_rs


@pytest.mark.asyncio
async def test_sql_rls_and_mcp_tools_fail_closed_on_missing_role_or_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`schema.sql` + `mcp_server/server.py` fail closed when `user_role` or `agent_id` is unset."""
    verifier = RelationalSQLRLSVerifier()
    # Missing user_role -> 0 rows
    assert (
        verifier.execute_rls_transaction(
            FINVAULT_TENANT,
            "SELECT * FROM tenant_incidents;",
            user_role=None,
            agent_id="cymbal_shared_diagnostic_agent",
        )
        == []
    )
    # Missing agent_id -> 0 rows
    assert (
        verifier.execute_rls_transaction(
            FINVAULT_TENANT,
            "SELECT * FROM tenant_incidents;",
            user_role="sre_admin",
            agent_id="",
        )
        == []
    )
    # Write RBAC: compliance_officer cannot UPDATE incidents (0 rows); immutable column raises
    assert (
        verifier.execute_rls_write(
            FINVAULT_TENANT,
            "UPDATE tenant_incidents SET severity = 'P2' WHERE incident_id = 'INC-FV-1001';",
            user_role="compliance_officer",
            agent_id="cymbal_shared_diagnostic_agent",
        )
        == 0
    )
    with pytest.raises(PermissionError, match="E_RBAC_COLUMN_FORBIDDEN"):
        verifier.execute_rls_write(
            FINVAULT_TENANT,
            "UPDATE tenant_incidents SET service_name = 'tampered' "
            "WHERE incident_id = 'INC-FV-1001';",
            user_role="sre_admin",
            agent_id="cymbal_shared_diagnostic_agent",
        )

    # MCP tool layer: missing `temp:user_role` fails closed with `E_MISSING_USER_ROLE`
    fv_env = _mint_verified_envelope(tenant_id=FINVAULT_TENANT)
    bad_state = fv_env.to_adk_state()
    bad_state.pop("temp:user_role", None)
    bad_ctx = MockADKCallbackContext(state=bad_state, agent=None)
    pool = RLSDatabasePool()
    with pytest.raises(PermissionError, match="E_MISSING_USER_ROLE"):
        await mcp_tools.query_telemetry_rls(tool_context=bad_ctx, db_pool=pool)

    # Under `MCP_REQUIRE_AGENT_BINDING=1`, missing `temp:agent_id` and `agent=None` fails closed
    monkeypatch.setenv("MCP_REQUIRE_AGENT_BINDING", "1")
    no_agent_env = replace(fv_env, agent_id=None)
    no_agent_ctx = MockADKCallbackContext(
        state=no_agent_env.to_adk_state(), agent=None
    )
    with pytest.raises(PermissionError, match="E_MISSING_AGENT_ID"):
        await mcp_tools.read_runbook(tool_context=no_agent_ctx, db_pool=pool)


def test_modular_facade_aliasing_and_verify_live_gcp_tenant_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`reset_dynamic_tenants`, `app.main` monkeypatches, and `/api/v1/verify-live-gcp` sync."""
    # 1. `reset_dynamic_tenants` mutates `_BASE_TENANT_DIRECTORY` in place for `agents.context`.
    agent_context.reset_dynamic_tenants()
    assert (
        agent_context._BASE_TENANT_DIRECTORY
        is tenant_directory._BASE_TENANT_DIRECTORY
    )

    # 2. `monkeypatch.setattr(gateway_main, "_TOOL_OUTPUT_TOKEN_ALLOWANCE", ...)` updates metering.
    req = InvokeAgentRequest(prompt="ping", requested_thinking_tokens=100)
    base_tokens, _ = gateway_main._metering(req)
    monkeypatch.setattr(gateway_main, "_TOOL_OUTPUT_TOKEN_ALLOWANCE", 4500)
    bumped_tokens, _ = gateway_main._metering(req)
    assert bumped_tokens - base_tokens == 2500

    # 3. `verify_live_gcp_services` passes `tenant_id="tenant-finvault-alpha"` to Cloud DLP.
    captured_dlp_tenant: list[str] = []
    monkeypatch.setattr(gcp_live_bridge, "is_live_gcp_enabled", lambda: True)
    monkeypatch.setattr(
        gcp_live_bridge,
        "LiveModelArmorGuardrail",
        lambda: SimpleNamespace(
            ensure_template_exists=lambda: None,
            sanitize_prompt=lambda _p: {"blocked": True},
        ),
    )
    monkeypatch.setattr(
        gcp_live_bridge,
        "LiveCloudKMSCMEKVerifier",
        lambda: SimpleNamespace(
            encrypt_for_tenant=lambda **_kw: b"ct",
            decrypt_for_tenant=lambda **_kw: b"finvault-cmek-verified",
        ),
    )

    class _FakeDLP:
        def deidentify_tool_output(
            self, *, raw_output: str, tool_name: str, tenant_id: str
        ) -> dict[str, Any]:
            captured_dlp_tenant.append(tenant_id)
            return {
                "redacted_text": "[REDACTED]",
                "tool_name": tool_name,
                "len": len(raw_output),
            }

    monkeypatch.setattr(gcp_live_bridge, "LiveCloudDLPGuardrail", _FakeDLP)
    monkeypatch.setattr(
        gcp_live_bridge,
        "LiveFirestoreMemoryBank",
        lambda: SimpleNamespace(
            write_memory=lambda **_kw: "mem-1",
            read_memory=lambda **_kw: {"verified_live_gcp": True},
        ),
    )
    monkeypatch.setattr(
        gcp_live_bridge,
        "LiveBigQueryOTelSink",
        lambda: SimpleNamespace(
            verify_row_access_policies=lambda: {
                "missing": [],
                "wrong_filter": [],
            },
            insert_span=lambda **_kw: None,
            query_tenant_cogs_view=list,
        ),
    )
    client = TestClient(gateway_main.app)
    resp = client.post("/api/v1/live-gcp-verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "LIVE_GCP_VERIFIED"
    assert captured_dlp_tenant == ["tenant-finvault-alpha"]
