# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Structural and behavioral unit tests for GCP SRE Advisor."""

import asyncio
import base64
import json
import re
import tokenize
import warnings
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from importlib import reload
from pathlib import Path
from types import SimpleNamespace

import app.config as cfg
import pytest
import yaml
from app import app as adk_app_obj
from app.agent import root_agent
from app.app_utils.profile_loader import (
    PROFILES_ROOT,
    build_profile_drift_contract,
    clear_profile_caches,
    get_enabled_mcp_keys_for_profile,
    list_available_profiles,
    load_active_profile,
    render_live_catalog_for_prompt,
    render_profile_for_prompt,
    resolve_active_target_metadata,
)
from app.prompts import (
    COST_INSTRUCTION,
    OPS_INSTRUCTION,
    ORCHESTRATOR_INSTRUCTION,
    RELIABILITY_INSTRUCTION,
    SECURITY_INSTRUCTION,
)
from app.sub_agents import (
    MAX_MCP_RESPONSE_CHARS,
    PILLAR_SPECS,
    bound_specialist_tool_args,
    build_specialist_agents,
    build_sweep_reviewers,
    cap_specialist_tool_response,
    strip_tool_response_schemas,
)
from app.tools import sweep_tool
from app.tools.catalog_tools import (
    activate_live_catalog_application,
    activate_zero_profile_discovery,
    get_active_profile_drift_baseline,
    list_workload_profiles,
    select_workload_profile,
)
from app.tools.mcp_registry import (
    _OIDC_TOKEN_CACHE,
    MANAGED_GCP_MCP_CATALOG,
    _catalog_mcp_header_provider,
    _cloud_run_oidc_header_provider,
    _gcp_adc_header_provider,
    _normalize_catalog_mcp_endpoints,
    _normalize_toolbox_endpoints,
    _observability_mcp_header_provider,
    build_database_toolbox_mcp,
    build_external_catalog_mcp,
    build_external_observability_mcp,
    build_managed_mcp_toolsets,
    clear_auth_caches,
    get_configured_observability_mcp_specs,
)
from deployment import cli as cli_mod
from deployment.bootstrap_profile import bootstrap_profile
from deployment.check_profile_drift import (
    check_profile_drift,
    classify_asset_item,
)
from deployment.inspect_catalog import inspect_catalog, probe_catalog_mcp
from deployment.setup_gemini_enterprise import (
    DEFAULT_PLACEHOLDER,
    DEFAULT_STARTER_PROMPTS,
    _encode_oauth_scopes,
    _post_idempotent,
)
from deployment.sync_profiles_gcs import sync_profiles
from deployment.validate_profile import validate_profile
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.cli.utils.agent_loader import AgentLoader
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_synthetic_profile(
    root: Path,
    slug: str,
    *,
    projects_by_role: dict[str, str],
    compute: list[str],
    databases: list[str],
    caching_messaging: list[str] | None = None,
    edge_networking: list[str] | None = None,
    region: str = "us-east1",
    zone: str = "us-east1-b",
) -> Path:
    pdir = root / slug
    pdir.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": "1.0",
        "curated_by": "Architecture Team",
        "last_reviewed": "2026-11-24",
        "workload_identity": {
            "id": slug,
            "display_name": f"Workload {slug}",
            "business_domain": "Platform Services",
            "criticality": "mission-critical",
            "criticality_summary": "Core customer API",
            "peak_windows": "08:00-20:00 UTC",
        },
        "environment_and_projects": {
            "environment_tier": "prod",
            "primary_region": region,
            "primary_zone": zone,
            "projects_by_role": projects_by_role,
        },
        "architecture_archetype": "cloud-native-microservices",
        "active_stack": {
            "compute": compute,
            "databases": databases,
            "caching_messaging": caching_messaging or [],
            "edge_networking": edge_networking or [],
        },
        "network_and_protocol_constraints": {
            "egress_static_ips": [],
            "special_protocols": [],
        },
        "finops_and_cost_controls": {
            "required_labels": ["app", "env"],
            "nonprod_cost_saving_policy": "Scale down non-prod off hours",
        },
        "slo_and_resilience_targets": {
            "availability_slo_pct": 99.95,
            "latency_p95_ms": 250,
            "rpo_minutes": 5,
            "rto_minutes": 30,
            "critical_business_windows": "08:00-20:00 UTC",
        },
        "external_boundaries": {
            "identity_providers": [],
            "edge_and_dns": [],
            "external_apis_or_clouds": [],
        },
        "accepted_exceptions": [],
        "change_delivery_model": {
            "delivery_mode": "declarative_iac",
            "tooling": "terraform",
            "remediation_format": "Terraform HCL diff",
        },
    }
    (pdir / "profile.yaml").write_text(
        yaml.safe_dump(doc, sort_keys=False), encoding="utf-8"
    )
    (pdir / "context.md").write_text(
        f"# Context for {slug}\nSynthetic test workload.\n", encoding="utf-8"
    )
    return pdir


def test_adk_app_structure_and_agent_discovery():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        loader = AgentLoader(str(REPO_ROOT))
        discovered = loader.list_agents()
        loaded = loader.load_agent("app")
    dep_warnings = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
    ]
    assert not dep_warnings
    assert discovered == ["app"]
    assert loaded is adk_app_obj
    assert adk_app_obj.name == "app"
    assert adk_app_obj.root_agent is root_agent
    assert root_agent.name == "gcp_sre_advisor"
    assert len(root_agent.sub_agents) == 6
    expected_root_tools = (
        6
        + len(build_managed_mcp_toolsets("resourcemanager"))
        + len(build_external_catalog_mcp())
    )
    assert len(root_agent.tools) == expected_root_tools
    assert any(
        getattr(t, "tool_name_prefix", None) == "resourcemanager"
        for t in root_agent.tools
    )
    assert root_agent.before_model_callback is strip_tool_response_schemas
    assert root_agent.after_tool_callback is cap_specialist_tool_response
    assert cfg.ORCHESTRATOR_MODEL.retry_options.attempts == 5
    assert cfg.SPECIALIST_MODEL.retry_options.attempts == 5
    assert (
        cfg.ORCHESTRATOR_MODEL.client_kwargs["http_options"].timeout == 75_000
    )
    assert cfg.SPECIALIST_MODEL.client_kwargs["http_options"].timeout == 75_000

    wired_mcps = {mcp for spec in PILLAR_SPECS for mcp in spec.mcp_keys}
    assert "cloudasset" in wired_mcps
    assert set(MANAGED_GCP_MCP_CATALOG.keys()) == wired_mcps


def test_repo_contains_only_sample_profile_and_validates(monkeypatch):
    profile_dirs = [p.name for p in PROFILES_ROOT.iterdir() if p.is_dir()]
    assert profile_dirs == ["_sample"]

    validated = validate_profile("_sample")
    assert validated["workload_identity"]["id"] == "sample-commerce-api"

    monkeypatch.setattr(cfg, "PROFILES_GCS_URI", "")
    clear_profile_caches()
    assert list_available_profiles(force_refresh=True) == []


def test_missing_profile_single_project_and_unselected_isolation(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cfg, "PROFILES_GCS_URI", "")
    monkeypatch.setattr(cfg, "WORKLOAD_PROFILE_NAME", "")
    monkeypatch.setattr(cfg, "MULTI_PROFILE_MODE", True)
    monkeypatch.setattr(cfg, "TARGET_PROJECT_ID", "fallback-env-project")
    clear_profile_caches()

    assert (
        load_active_profile(
            "does-not-exist", force_refresh=True, profiles_root=tmp_path
        )
        == {}
    )

    unselected_meta = resolve_active_target_metadata(SimpleNamespace(state={}))
    assert unselected_meta["mode"] == "unselected"
    assert unselected_meta["project_ids"] == []
    assert unselected_meta["primary_project_id"] == ""

    _write_synthetic_profile(
        tmp_path,
        "single-proj-app",
        projects_by_role={"application": "dedicated-app-proj-01"},
        compute=["cloud_run"],
        databases=["cloudsql_postgres"],
        region="europe-west1",
        zone="europe-west1-b",
    )
    monkeypatch.setattr("app.app_utils.profile_loader.PROFILES_ROOT", tmp_path)
    clear_profile_caches()

    profile = load_active_profile("single-proj-app", force_refresh=True)
    rendered = render_profile_for_prompt(profile)
    assert "dedicated-app-proj-01" in rendered
    assert "fallback-env-project" not in rendered
    assert "europe-west1" in rendered
    assert "europe-west1-b" in rendered

    ctx = SimpleNamespace(state={"active_workload_profile": "single-proj-app"})
    ops_prompt = OPS_INSTRUCTION(ctx)
    assert "--scope=projects/dedicated-app-proj-01" in ops_prompt
    assert "europe-west1" in ops_prompt


def test_synthetic_profiles_validate_adapt_mcps_and_switch_sessions(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cfg, "PROFILES_GCS_URI", "")
    monkeypatch.setattr(cfg, "WORKLOAD_PROFILE_NAME", "")
    monkeypatch.setattr("app.app_utils.profile_loader.PROFILES_ROOT", tmp_path)
    clear_profile_caches()

    specs = [
        (
            "serverless-portal",
            ["cloud_run"],
            ["cloudsql_postgres"],
            ["pubsub"],
            "sqladmin",
            "compute",
        ),
        (
            "hybrid-analytics",
            ["cloud_run_jobs"],
            ["bigquery"],
            ["eventarc"],
            "bigquery",
            "compute",
        ),
        (
            "cluster-commerce",
            ["gke"],
            ["cloudsql_mysql"],
            ["memorystore_redis"],
            "compute",
            "bigquery",
        ),
        (
            "vm-legacy-erp",
            ["compute_engine"],
            ["cloudsql_sqlserver"],
            [],
            "compute",
            "cloudrun",
        ),
    ]
    for slug, comp, dbs, msg, expected_mcp, unexpected_mcp in specs:
        _write_synthetic_profile(
            tmp_path,
            slug,
            projects_by_role={"primary": f"prj-{slug}"},
            compute=comp,
            databases=dbs,
            caching_messaging=msg,
        )
        validated = validate_profile(slug, profiles_root=tmp_path)
        mcps = get_enabled_mcp_keys_for_profile(validated)
        assert expected_mcp in mcps
        assert unexpected_mcp not in mcps
        drift = build_profile_drift_contract(validated)
        assert drift["profile_id"] == slug
        assert drift["projects_by_role"] == {"primary": f"prj-{slug}"}

    empty_ctx = SimpleNamespace(state={})
    unselected_prompt = ORCHESTRATOR_INSTRUCTION(empty_ctx)
    assert "NONE SELECTED" in unselected_prompt
    assert "Session target selection rules:" in unselected_prompt

    catalog_res = list_workload_profiles(empty_ctx)
    assert len(catalog_res["available_profiles"]) == 4

    res = select_workload_profile("hybrid-analytics", empty_ctx)
    assert res["switched"] is True
    assert empty_ctx.state["active_workload_profile"] == "hybrid-analytics"
    selected_prompt = ORCHESTRATOR_INSTRUCTION(empty_ctx)
    assert "hybrid-analytics" in selected_prompt
    assert "Session target selection rules:" not in selected_prompt

    bad_disc = activate_zero_profile_discovery(
        "   ", "prod", tool_context=empty_ctx
    )
    assert bad_disc["zero_profile_discovery_active"] is False
    assert empty_ctx.state["active_workload_profile"] == "hybrid-analytics"

    good_disc = activate_zero_profile_discovery(
        "live-sandbox-01",
        "staging",
        region="southamerica-east1",
        tool_context=empty_ctx,
    )
    assert good_disc["zero_profile_discovery_active"] is True
    assert good_disc["primary_region"] == "southamerica-east1"
    assert good_disc["primary_zone"] == "southamerica-east1-a"
    disc_prompt = ORCHESTRATOR_INSTRUCTION(empty_ctx)
    assert "Live Project Discovery Context:" in disc_prompt
    assert "Live Google Cloud Project Discovery" in disc_prompt
    assert "live-sandbox-01" in disc_prompt
    assert "southamerica-east1" in disc_prompt

    baseline_err = get_active_profile_drift_baseline(empty_ctx)
    assert "error" in baseline_err


def test_validate_profile_rejects_legacy_or_malformed_nested_types(tmp_path):
    base_doc = {
        "workload_identity": {
            "id": "x",
            "display_name": "X",
            "business_domain": "D",
            "criticality": "standard",
        },
        "environment_and_projects": {
            "environment_tier": "prod",
            "primary_region": "us-central1",
            "primary_zone": "us-central1-a",
            "projects_by_role": {"primary": "proj-x"},
        },
        "architecture_archetype": "monolith",
        "active_stack": {
            "compute": [],
            "databases": [],
            "caching_messaging": [],
            "edge_networking": [],
        },
        "network_and_protocol_constraints": {},
        "finops_and_cost_controls": {},
        "slo_and_resilience_targets": {
            "availability_slo_pct": 99.9,
            "latency_p95_ms": 400,
            "rpo_minutes": 15,
            "rto_minutes": 60,
        },
        "external_boundaries": {},
        "accepted_exceptions": [],
    }

    legacy_dir = tmp_path / "legacy-only"
    legacy_dir.mkdir()
    legacy_doc = {**base_doc, "gitops_governance": {"iac_tool": "terraform"}}
    (legacy_dir / "profile.yaml").write_text(
        yaml.safe_dump(legacy_doc), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="change_delivery_model"):
        validate_profile("legacy-only", profiles_root=tmp_path)

    bad_nested_dir = tmp_path / "bad-nested"
    bad_nested_dir.mkdir()
    bad_doc = {
        **base_doc,
        "environment_and_projects": {
            "environment_tier": "prod",
            "primary_region": "us-central1",
            "primary_zone": "us-central1-a",
            "projects_by_role": {"primary": "   "},
        },
        "slo_and_resilience_targets": {
            "availability_slo_pct": True,
            "latency_p95_ms": -5,
            "rpo_minutes": 15,
            "rto_minutes": 60,
        },
        "accepted_exceptions": ["not-a-mapping"],
        "change_delivery_model": {
            "delivery_mode": "declarative_iac",
            "tooling": "terraform",
            "remediation_format": "HCL diff",
        },
        "gitops_governance": {"iac_tool": "terraform"},
    }
    (bad_nested_dir / "profile.yaml").write_text(
        yaml.safe_dump(bad_doc), encoding="utf-8"
    )
    with pytest.raises(ValueError) as exc_info:
        validate_profile("bad-nested", profiles_root=tmp_path)
    err_text = str(exc_info.value)
    assert "gitops_governance" in err_text
    assert "projects_by_role" in err_text
    assert "availability_slo_pct" in err_text
    assert "latency_p95_ms" in err_text
    assert "accepted_exceptions[0]" in err_text


def test_parallel_six_pillar_sweep_real_adk_runner_and_error_isolation(
    monkeypatch,
):
    monkeypatch.setattr(cfg, "PROFILES_GCS_URI", "")
    monkeypatch.setattr(cfg, "WORKLOAD_PROFILE_NAME", "")
    monkeypatch.setattr(cfg, "MULTI_PROFILE_MODE", True)
    clear_profile_caches()

    built_tools = sweep_tool.build_sweep_agent_tools()
    assert len(built_tools) == 6
    assert all(t.include_plugins is False for _, t in built_tools)

    unselected_res = asyncio.run(
        sweep_tool.waf_six_pillar_parallel_sweep(
            "Unselected attempt", tool_context=SimpleNamespace(state={})
        )
    )
    assert unselected_res["pillar_count"] == 0
    assert "error" in unselected_res

    class MockSweepLlm(BaseLlm):
        """Mock LLM simulating coordinator sweep tool call and pillars."""

        model: str = "mock-gemini"

        async def generate_content_async(
            self,
            llm_request: LlmRequest,
            stream: bool = False,
        ) -> AsyncGenerator[LlmResponse, None]:
            _ = stream
            sys_inst = str(llm_request.config.system_instruction or "")
            await asyncio.sleep(0.01)
            if "TEST_COORDINATOR" in sys_inst:
                has_fn_resp = any(
                    any(p.function_response for p in (c.parts or []))
                    for c in (llm_request.contents or [])
                )
                if not has_fn_resp:
                    yield LlmResponse(
                        content=types.Content(
                            role="model",
                            parts=[
                                types.Part.from_function_call(
                                    name="waf_six_pillar_parallel_sweep",
                                    args={
                                        "assessment_scope": (
                                            "Full production readiness"
                                        )
                                    },
                                )
                            ],
                        )
                    )
                else:
                    fn_payload = next(
                        p.function_response.response
                        for c in (llm_request.contents or [])
                        for p in (c.parts or [])
                        if p.function_response
                    )
                    done_count = len(fn_payload["completed_pillars"])
                    yield LlmResponse(
                        content=types.Content(
                            role="model",
                            parts=[
                                types.Part.from_text(
                                    text=f"Completed={done_count}"
                                )
                            ],
                        )
                    )
            else:
                tag = sys_inst.splitlines()[0]
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part.from_text(text=f"Diagnosis for {tag}")
                        ],
                    )
                )

    pillar_keys = [spec.pillar_key for spec in PILLAR_SPECS]
    monkeypatch.setattr(
        sweep_tool,
        "build_sweep_agent_tools",
        lambda: [
            (
                k,
                AgentTool(
                    agent=LlmAgent(
                        name=f"rev_{k}",
                        model=MockSweepLlm(),
                        instruction=f"PILLAR::{k}",
                        output_key=f"sweep_out_{k}",
                    ),
                    include_plugins=False,
                ),
            )
            for k in pillar_keys
        ],
    )

    coord = LlmAgent(
        name="test_coord",
        model=MockSweepLlm(),
        instruction="TEST_COORDINATOR",
        tools=[sweep_tool.waf_six_pillar_parallel_sweep],
    )
    runner = InMemoryRunner(app=App(name="app", root_agent=coord))

    async def _execute_runner():
        sess = await runner.session_service.create_session(
            app_name="app",
            user_id="u1",
            state={"zero_profile_project": "proj-sweep-01"},
        )
        final_texts = []
        async for ev in runner.run_async(
            user_id="u1",
            session_id=sess.id,
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(text="run sweep")]
            ),
        ):
            if ev.content and ev.content.parts:
                for part in ev.content.parts:
                    if part.text:
                        final_texts.append(part.text)
        updated = await runner.session_service.get_session(
            app_name="app", user_id="u1", session_id=sess.id
        )
        return final_texts, updated.state

    texts, final_state = asyncio.run(_execute_runner())
    assert any("Completed=6" in t for t in texts)
    for k in pillar_keys:
        assert f"Diagnosis for PILLAR::{k}" in final_state[f"sweep_out_{k}"]

    class OutcomeStub:
        """Stubbed AgentTool returning deterministic success or failure."""

        def __init__(self, mode: str):
            self.mode = mode

        async def run_async(self, *, args, tool_context):
            _ = (args, tool_context)
            if self.mode == "raise":
                raise RuntimeError("synthetic MCP timeout")
            if self.mode == "empty":
                return "   "
            if self.mode == "unresolved":
                return (
                    "Error: agent 'rev' stopped waiting on unresolved "
                    "long-running tool call(s)"
                )
            return "Healthy pillar report"

    modes = ["ok", "raise", "empty", "unresolved", "ok", "ok"]
    monkeypatch.setattr(
        sweep_tool,
        "build_sweep_agent_tools",
        lambda: [
            (k, OutcomeStub(m)) for k, m in zip(pillar_keys, modes, strict=True)
        ],
    )
    ctx = SimpleNamespace(state={"zero_profile_project": "proj-sweep-01"})
    partial = asyncio.run(
        sweep_tool.waf_six_pillar_parallel_sweep(
            "Incident triage", tool_context=ctx
        )
    )
    assert len(partial["completed_pillars"]) == 3
    assert len(partial["failed_pillars"]) == 3

    with pytest.raises(ValueError):
        asyncio.run(
            sweep_tool.waf_six_pillar_parallel_sweep(
                "No context", tool_context=None
            )
        )


def test_auth_header_caching_project_omission_and_db_toolbox_config(
    monkeypatch,
):
    monkeypatch.delenv("CLOUDSDK_CORE_ACCOUNT", raising=False)
    clear_auth_caches()
    refresh_calls = 0

    class FakeCreds:
        def __init__(self):
            self.token = None
            self.expired = False
            self.expiry = None

        def refresh(self, _req):
            nonlocal refresh_calls
            refresh_calls += 1
            self.token = f"adc-token-{refresh_calls}"
            self.expiry = datetime.now(UTC) + timedelta(minutes=50)

    monkeypatch.setattr(
        "google.auth.default", lambda scopes=None: (FakeCreds(), "")
    )
    monkeypatch.setattr(cfg, "RUNTIME_PROJECT_ID", "")
    monkeypatch.setattr(cfg, "REQUIRE_DELEGATED_USER_OAUTH", False)

    h1 = _gcp_adc_header_provider(None)
    h2 = _gcp_adc_header_provider(None)
    assert refresh_calls == 1
    assert h1 == {"Authorization": "Bearer adc-token-1"}
    assert h2 == {"Authorization": "Bearer adc-token-1"}
    assert "X-Goog-User-Project" not in h1

    monkeypatch.setattr(cfg, "RUNTIME_PROJECT_ID", "quota-proj-01")
    h3 = _gcp_adc_header_provider(None)
    assert refresh_calls == 1
    assert h3["X-Goog-User-Project"] == "quota-proj-01"

    delegated_ctx = SimpleNamespace(
        state={
            "gcp-sre-user-oauth": "sample-delegated-oauth-identifier-value-001"
        },
        get_credential=lambda _k: None,
    )
    hd = _gcp_adc_header_provider(delegated_ctx)
    assert (
        hd["Authorization"]
        == "Bearer sample-delegated-oauth-identifier-value-001"
    )

    monkeypatch.setattr(cfg, "REQUIRE_DELEGATED_USER_OAUTH", True)
    with pytest.raises(PermissionError):
        _gcp_adc_header_provider(
            SimpleNamespace(state={}, get_credential=lambda _k: None)
        )

    assert _normalize_toolbox_endpoints(
        "https://toolbox.example.run.app/mcp/"
    ) == (
        "https://toolbox.example.run.app/mcp",
        "https://toolbox.example.run.app",
    )

    monkeypatch.setattr(
        "app.tools.mcp_registry.id_token.fetch_id_token",
        lambda _req, _aud: (_ for _ in ()).throw(
            ValueError("no service account")
        ),
    )
    monkeypatch.setattr(
        cfg, "DATABASE_MCP_TOOLBOX_URL", "https://toolbox.example.run.app/mcp"
    )
    fallback_hdr = _cloud_run_oidc_header_provider()
    assert fallback_hdr == {"Authorization": "Bearer adc-token-1"}
    assert not _OIDC_TOKEN_CACHE

    oidc_calls = 0

    def fake_fetch_id_token(_req, audience):
        nonlocal oidc_calls
        oidc_calls += 1
        return f"oidc-jwt-for-{audience}"

    monkeypatch.setattr(
        "app.tools.mcp_registry.id_token.fetch_id_token", fake_fetch_id_token
    )
    o1 = _cloud_run_oidc_header_provider()
    o2 = _cloud_run_oidc_header_provider()
    assert oidc_calls == 1
    assert (
        o1
        == o2
        == {
            "Authorization": (
                "Bearer oidc-jwt-for-https://toolbox.example.run.app"
            )
        }
    )

    monkeypatch.setenv("DATABASE_MCP_TOOLS", "*")
    reload(cfg)
    monkeypatch.setattr(
        cfg, "DATABASE_MCP_TOOLBOX_URL", "https://toolbox.example.run.app/mcp"
    )
    toolsets = build_database_toolbox_mcp()
    assert len(toolsets) == 1
    assert toolsets[0].tool_filter is None
    assert (
        getattr(toolsets[0], "_connection_params").url
        == "https://toolbox.example.run.app/mcp"
    )


def test_bootstrap_multiproject_drift_sync_prune_and_gemini_enterprise(
    monkeypatch, tmp_path
):
    assert classify_asset_item(
        {"assetType": "compute.googleapis.com/Router"}
    ) == (
        "edge_networking",
        "cloud_nat",
    )
    assert classify_asset_item(
        {"assetType": "dns.googleapis.com/ManagedZone"}
    ) == (
        "edge_networking",
        "cloud_dns",
    )
    assert classify_asset_item(
        {"assetType": "run.googleapis.com/WorkerPool"}
    ) == (
        "compute",
        "cloud_run_worker_pools",
    )
    assert classify_asset_item(
        {"assetType": "compute.googleapis.com/UrlMap", "location": "us-east1"}
    ) == (
        "edge_networking",
        "regional_alb",
    )

    fake_assets_by_scope = {
        "--scope=projects/prj-commerce-01": [
            {
                "assetType": "run.googleapis.com/Service",
                "displayName": "checkout-api",
                "labels": {"app": "shop", "env": "prod"},
            },
            {
                "assetType": "sqladmin.googleapis.com/Instance",
                "displayName": "orders-db",
                "additionalAttributes": {"databaseVersion": "MYSQL_8_0"},
                "labels": {"app": "shop"},
            },
            {
                "assetType": "pubsub.googleapis.com/Topic",
                "displayName": "orders-events",
                "labels": {},
            },
            {
                "assetType": "compute.googleapis.com/Router",
                "displayName": "nat-router",
                "labels": {},
            },
        ],
        "--scope=projects/prj-app": [
            {
                "assetType": "run.googleapis.com/WorkerPool",
                "displayName": "worker-1",
            }
        ],
        "--scope=projects/prj-data": [
            {
                "assetType": "sqladmin.googleapis.com/Instance",
                "displayName": "pg-1",
            }
        ],
        "--scope=projects/prj-net": [
            {
                "assetType": "compute.googleapis.com/Router",
                "displayName": "rtr-1",
            },
            {
                "assetType": "dns.googleapis.com/ManagedZone",
                "displayName": "zone-1",
            },
        ],
    }

    def fake_check_output(cmd, **_kw):
        for flag in cmd:
            if flag in fake_assets_by_scope:
                return json.dumps(fake_assets_by_scope[flag])
        return "[]"

    monkeypatch.setattr("subprocess.check_output", fake_check_output)

    iac_dir = tmp_path / "iac"
    iac_dir.mkdir()
    (iac_dir / "main.tf").write_text("", encoding="utf-8")

    profiles_dir = tmp_path / "profiles"
    sample_copy = profiles_dir / "_sample"
    sample_copy.mkdir(parents=True)
    (sample_copy / "profile.yaml").write_text(
        "schema_version: '1.0'\n", encoding="utf-8"
    )

    out = bootstrap_profile(
        project_id="prj-commerce-01",
        profile_slug="commerce-prod",
        tier="prod",
        iac_dir=str(iac_dir),
        region="us-east4",
        output_root=profiles_dir,
    )
    assert (out / "profile.yaml").exists()
    validated = validate_profile("commerce-prod", profiles_root=profiles_dir)
    assert validated["change_delivery_model"]["tooling"] == "terraform"
    assert validated["active_stack"]["databases"] == ["cloudsql_mysql"]
    assert validated["active_stack"]["edge_networking"] == ["cloud_nat"]
    assert (
        check_profile_drift("commerce-prod", profiles_root=profiles_dir) is True
    )

    _write_synthetic_profile(
        profiles_dir,
        "multi-proj-suite",
        projects_by_role={
            "application": "prj-app",
            "data": "prj-data",
            "networking": "prj-net",
        },
        compute=["cloud_run_worker_pools"],
        databases=["cloudsql_postgres"],
        edge_networking=["cloud_nat", "cloud_dns"],
    )
    assert (
        check_profile_drift("multi-proj-suite", profiles_root=profiles_dir)
        is True
    )

    uploaded_urls: list[str] = []
    deleted_urls: list[str] = []

    class FakeResponse:
        """Fake HTTP response object for profile sync tests."""

        def __init__(self, status_code=200, data=None):
            self.status_code = status_code
            self._data = data or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._data

    class FakeSession:
        """Fake AuthorizedSession capturing GCS uploads and deletions."""

        def __init__(self, _creds=None):
            pass

        def post(self, url, **_kw):
            uploaded_urls.append(url)
            return FakeResponse(200)

        def get(self, _url, **_kw):
            return FakeResponse(
                200,
                {
                    "items": [
                        {"name": "profiles/commerce-prod/profile.yaml"},
                        {"name": "profiles/multi-proj-suite/profile.yaml"},
                        {"name": "profiles/legacy-demo/profile.yaml"},
                        {"name": "profiles/_internal/keep.yaml"},
                    ]
                },
            )

        def delete(self, url, **_kw):
            deleted_urls.append(url)
            return FakeResponse(204)

    monkeypatch.setattr(
        "deployment.sync_profiles_gcs.resolve_credentials", lambda _p: object()
    )
    monkeypatch.setattr(
        "deployment.sync_profiles_gcs.AuthorizedSession", FakeSession
    )

    count = sync_profiles(
        gcs_uri="gs://test-bucket/profiles",
        runtime_project="prj-commerce-01",
        prune=False,
        profiles_root=profiles_dir,
    )
    assert count == 4
    assert not deleted_urls

    sync_profiles(
        gcs_uri="gs://test-bucket/profiles",
        runtime_project="prj-commerce-01",
        prune=True,
        profiles_root=profiles_dir,
    )
    assert len(deleted_urls) == 1
    assert "legacy-demo" in deleted_urls[0]

    patched: list[str] = []

    class ConflictSession:
        """Fake session returning 409 Conflict on POST."""

        def post(self, _url, **_kw):
            return FakeResponse(409)

        def patch(self, url, **_kw):
            patched.append(url)
            return FakeResponse(200)

    _post_idempotent(ConflictSession(), "https://example.com/ds", {}, {})
    assert not patched
    _post_idempotent(
        ConflictSession(),
        "https://example.com/auth",
        {},
        {},
        patch_url_on_conflict="https://example.com/auth/id1",
    )
    assert patched == ["https://example.com/auth/id1"]

    encoded = _encode_oauth_scopes(
        "https://scope.one/read,  https://scope.two/read "
    )
    assert (
        encoded
        == "https%3A%2F%2Fscope.one%2Fread%20https%3A%2F%2Fscope.two%2Fread"
    )
    assert len(DEFAULT_STARTER_PROMPTS) == 4
    assert all(p.get("text", "").strip() for p in DEFAULT_STARTER_PROMPTS)
    assert DEFAULT_PLACEHOLDER.strip()


def test_specialist_mcp_payload_bounding_and_truncation_callbacks():
    metric_args: dict[str, object] = {"name": "projects/example"}
    assert (
        bound_specialist_tool_args(
            SimpleNamespace(name="monitoring_list_metric_descriptors"),
            metric_args,
            None,
        )
        is None
    )
    assert metric_args["activeOnly"] is True
    assert metric_args["pageSize"] == 40

    log_args: dict[str, object] = {"pageSize": 5000}
    bound_specialist_tool_args(
        SimpleNamespace(name="logging_list_log_entries"), log_args, None
    )
    assert log_args["pageSize"] == 40

    small_resp = {
        "content": [{"type": "text", "text": "compact"}],
        "isError": False,
    }
    assert cap_specialist_tool_response(None, {}, None, small_resp) is None

    oversized_text = "M" * (MAX_MCP_RESPONSE_CHARS + 25_000)
    oversized_resp = {
        "content": [{"type": "text", "text": oversized_text}],
        "structuredContent": {"descriptors": [oversized_text]},
        "isError": False,
    }
    capped = cap_specialist_tool_response(None, {}, None, oversized_resp)
    assert capped is not None
    assert "structuredContent" not in capped
    assert len(json.dumps(capped)) < MAX_MCP_RESPONSE_CHARS + 250
    assert "truncated at" in capped["content"][0]["text"]

    decl = types.FunctionDeclaration(
        name="monitoring_list_dashboards",
        parameters_json_schema={
            "type": "object",
            "properties": {"parent": {"type": "string"}},
        },
        response_json_schema={
            "type": "object",
            "$defs": {"RecursiveWidget": {"type": "object"}},
        },
    )
    fake_llm_req = SimpleNamespace(
        config=SimpleNamespace(tools=[types.Tool(function_declarations=[decl])])
    )
    assert strip_tool_response_schemas(None, fake_llm_req) is None
    assert decl.response is None
    assert decl.response_json_schema is None


def test_simplified_cli_positional_commands_and_metadata_resolution(
    monkeypatch, tmp_path
):
    parser = cli_mod.build_parser()
    val_args = parser.parse_args(["validate", "_sample"])
    assert val_args.command == "validate"
    assert val_args.profile_pos == "_sample"

    boot_args = parser.parse_args(
        ["bootstrap", "prj-example-01", "payments-prod"]
    )
    assert boot_args.project_pos == "prj-example-01"
    assert boot_args.profile_pos == "payments-prod"

    drift_args = parser.parse_args(["drift", "payments-prod"])
    assert drift_args.profile_pos == "payments-prod"

    asset_args: dict[str, object] = {"pageSize": 999}
    bound_specialist_tool_args(
        SimpleNamespace(name="cloudasset_list_assets"), asset_args, None
    )
    assert asset_args["pageSize"] == 80

    meta = tmp_path / "deployment_metadata.json"
    meta.write_text('{"reasoning_engine_id": "99887766"}\n', encoding="utf-8")
    monkeypatch.setattr(cli_mod, "ROOT_DIR", tmp_path)
    assert (
        getattr(cli_mod, "_resolve_saved_reasoning_engine_id")() == "99887766"
    )

    cat_args = parser.parse_args(
        ["catalog", "prj-example-01", "--region", "us-east1"]
    )
    assert cat_args.command == "catalog"
    assert cat_args.project_pos == "prj-example-01"
    assert cat_args.region == "us-east1"


def test_automatic_context_resolution_cascade_sources_and_switching(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cfg, "PROFILES_GCS_URI", "")
    monkeypatch.setattr(cfg, "WORKLOAD_PROFILE_NAME", "")
    monkeypatch.setattr(cfg, "MULTI_PROFILE_MODE", True)
    monkeypatch.setattr(cfg, "CATALOG_MCP_URL", "")
    monkeypatch.setattr(cfg, "CATALOG_MCP_PROVIDER_NAME", "")
    monkeypatch.setattr("app.app_utils.profile_loader.PROFILES_ROOT", tmp_path)
    clear_profile_caches()

    _write_synthetic_profile(
        tmp_path,
        "curated-checkout",
        projects_by_role={"application": "prj-curated-app"},
        compute=["cloud_run"],
        databases=["cloudsql_postgres"],
    )

    ctx = SimpleNamespace(state={})
    initial = list_workload_profiles(ctx)
    assert initial["active_context_source"] == "unselected"
    assert initial["active_profile_id"] == "UNSELECTED"
    assert initial["supports_live_project_discovery"] is True
    assert initial["live_catalog_integration"]["apphub_supported"] is True
    assert (
        initial["live_catalog_integration"]["external_catalog_mcp_enabled"]
        is False
    )

    d_res = activate_zero_profile_discovery(
        "prj-greenfield-01", "dev", region="us-west1", tool_context=ctx
    )
    assert d_res["zero_profile_discovery_active"] is True
    assert d_res["context_source"] == "live_project_discovery"
    assert (
        list_workload_profiles(ctx)["active_profile_id"]
        == "discovery:prj-greenfield-01"
    )
    assert (
        list_workload_profiles(ctx)["active_context_source"]
        == "live_project_discovery"
    )

    bad_cat_empty_app = activate_live_catalog_application(
        "  ", "prj-cat-01", tool_context=ctx
    )
    assert bad_cat_empty_app["live_catalog_active"] is False
    assert ctx.state["zero_profile_project"] == "prj-greenfield-01"

    bad_cat_empty_proj = activate_live_catalog_application(
        "orders-core", " , ", tool_context=ctx
    )
    assert bad_cat_empty_proj["live_catalog_active"] is False
    assert "project_id" in bad_cat_empty_proj["error"]
    assert ctx.state["zero_profile_project"] == "prj-greenfield-01"

    monkeypatch.setattr(
        cfg, "CATALOG_MCP_URL", "https://backstage.corp.example.com/api/mcp"
    )
    monkeypatch.setattr(cfg, "CATALOG_MCP_PROVIDER_NAME", "backstage")
    coord_with_cat = ORCHESTRATOR_INSTRUCTION(SimpleNamespace(state={}))
    assert "app_catalog_" in coord_with_cat
    assert "resourcemanager_search_projects" in coord_with_cat
    assert "Priority 1" in coord_with_cat
    assert "Priority 2" in coord_with_cat
    assert "Priority 3" in coord_with_cat

    cat_res = activate_live_catalog_application(
        application_id="orders-core",
        project_id="prj-orders-app, prj-orders-data",
        environment_tier="prod",
        region="us-east4",
        criticality="mission-critical",
        display_name="Orders Core Service",
        owner_team="Commerce SRE",
        apphub_application_id="orders-apphub",
        slo_summary="Availability 99.95% | Latency P95 200ms",
        finops_labels="app,env,cost_center",
        delivery_model_summary="GitOps Terraform in repo org/orders-iac",
        accepted_risks_summary=(
            "RISK-01 single-zone batch exporter accepted until 2027-06-30"
        ),
        architecture_notes="Event-driven order pipeline.",
        tool_context=ctx,
    )
    assert cat_res["live_catalog_active"] is True
    assert cat_res["context_source"] == "live_catalog"
    assert cat_res["catalog_source"] == "backstage"
    assert cat_res["project_ids"] == ["prj-orders-app", "prj-orders-data"]
    assert ctx.state["zero_profile_project"] == ""
    assert ctx.state["active_workload_profile"] == ""

    cat_listing = list_workload_profiles(ctx)
    assert cat_listing["active_context_source"] == "live_catalog"
    assert cat_listing["active_profile_id"] == "catalog:orders-core"
    assert (
        cat_listing["live_catalog_integration"]["external_catalog_mcp_enabled"]
        is True
    )

    meta_cat = resolve_active_target_metadata(ctx)
    assert meta_cat["mode"] == "catalog"
    assert meta_cat["context_source"] == "live_catalog"
    assert meta_cat["project_ids"] == ["prj-orders-app", "prj-orders-data"]
    rendered_cat = render_live_catalog_for_prompt(meta_cat["catalog_context"])
    assert "Live Application Catalog and Google Cloud App Hub" in rendered_cat
    assert "RISK-01" in rendered_cat
    assert "orders-apphub" in rendered_cat

    ops_cat = OPS_INSTRUCTION(ctx)
    assert "gcloud apphub applications describe orders-apphub" in ops_cat
    assert "--project=prj-orders-app" in ops_cat
    assert "`projects/prj-orders-app`, `projects/prj-orders-data`" in ops_cat

    assert "error" in get_active_profile_drift_baseline(ctx)

    prof_res = select_workload_profile("curated-checkout", ctx)
    assert prof_res["switched"] is True
    assert prof_res["context_source"] == "workload_profile"
    assert ctx.state["live_catalog_app_id"] == ""
    assert ctx.state["live_catalog_context"] == {}
    assert (
        list_workload_profiles(ctx)["active_context_source"]
        == "workload_profile"
    )


def test_external_catalog_mcp_endpoints_auth_modes_and_cli_inspector(
    monkeypatch, capsys
):
    monkeypatch.delenv("CLOUDSDK_CORE_ACCOUNT", raising=False)
    clear_auth_caches()
    assert _normalize_catalog_mcp_endpoints("") == ("", "")
    assert _normalize_catalog_mcp_endpoints("https://catalog.run.app") == (
        "https://catalog.run.app/mcp",
        "https://catalog.run.app",
    )
    assert _normalize_catalog_mcp_endpoints("https://catalog.run.app/mcp/") == (
        "https://catalog.run.app/mcp",
        "https://catalog.run.app",
    )
    assert _normalize_catalog_mcp_endpoints(
        "https://backstage.example.com/api/mcp/"
    ) == (
        "https://backstage.example.com/api/mcp",
        "https://backstage.example.com",
    )

    monkeypatch.setattr(cfg, "CATALOG_MCP_URL", "")
    assert not build_external_catalog_mcp()

    monkeypatch.setattr(cfg, "CATALOG_MCP_URL", "https://catalog.run.app")
    monkeypatch.setattr(cfg, "CATALOG_MCP_AUTH_MODE", "oidc")
    monkeypatch.setattr(
        cfg,
        "CATALOG_MCP_TOOLS",
        ["list_catalog_applications", "get_catalog_application"],
    )
    monkeypatch.setattr(
        "app.tools.mcp_registry.id_token.fetch_id_token",
        lambda _req, aud: f"jwt-for-{aud}",
    )
    oidc_hdr = _catalog_mcp_header_provider()
    assert oidc_hdr == {
        "Authorization": "Bearer jwt-for-https://catalog.run.app"
    }
    built_oidc = build_external_catalog_mcp()
    assert len(built_oidc) == 1
    assert built_oidc[0].tool_name_prefix == "app_catalog"
    assert built_oidc[0].tool_filter == [
        "list_catalog_applications",
        "get_catalog_application",
    ]

    monkeypatch.setattr(cfg, "CATALOG_MCP_AUTH_MODE", "bearer")
    monkeypatch.setattr(cfg, "CATALOG_MCP_BEARER_TOKEN", "")
    with pytest.raises(PermissionError):
        _catalog_mcp_header_provider()
    monkeypatch.setattr(cfg, "CATALOG_MCP_BEARER_TOKEN", "catalog-api-key-001")
    assert _catalog_mcp_header_provider() == {
        "Authorization": "Bearer catalog-api-key-001"
    }

    monkeypatch.setattr(cfg, "CATALOG_MCP_AUTH_MODE", "none")
    assert _catalog_mcp_header_provider() == {}
    built_none = build_external_catalog_mcp()
    assert len(built_none) == 1
    assert getattr(built_none[0], "_header_provider") is None

    monkeypatch.setattr(cfg, "CATALOG_MCP_AUTH_MODE", "unsupported-mode")
    with pytest.raises(ValueError, match="Unsupported CATALOG_MCP_AUTH_MODE"):
        build_external_catalog_mcp()
    with pytest.raises(ValueError, match="Unsupported CATALOG_MCP_AUTH_MODE"):
        _catalog_mcp_header_provider()

    monkeypatch.setattr(cfg, "CATALOG_MCP_AUTH_MODE", "oidc")
    monkeypatch.setattr(cfg, "CATALOG_MCP_URL", "https://catalog.run.app/mcp")
    monkeypatch.setenv("CATALOG_MCP_URL", "https://catalog.run.app/mcp")
    monkeypatch.setenv("CATALOG_MCP_AUTH_MODE", "oidc")
    monkeypatch.setattr(
        "deployment.inspect_catalog.list_available_profiles", lambda **_kw: []
    )
    monkeypatch.setattr(
        "deployment.inspect_catalog.subprocess.check_output",
        lambda *_a, **_kw: json.dumps(
            [
                {
                    "name": (
                        "projects/p1/locations/us-central1/"
                        "applications/orders-app"
                    ),
                    "displayName": "Orders App",
                    "attributes": {
                        "criticality": {"type": "MISSION_CRITICAL"},
                        "environment": {"type": "PRODUCTION"},
                    },
                }
            ]
        ),
    )

    class FakeMcpResp:
        """Fake HTTP response for MCP catalog probe tests."""

        def __init__(
            self, payload=None, headers=None, status_code=200, text=""
        ):
            self._payload = payload or {}
            self.headers = headers or {}
            self.status_code = status_code
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    seen_methods: list[str] = []

    def fake_mcp_post(_url, **kwargs):
        body = kwargs.get("json") or {}
        seen_methods.append(body["method"])
        if body["method"] == "initialize":
            return FakeMcpResp(
                {"result": {"serverInfo": {"name": "toolbox"}}},
                headers={"Mcp-Session-Id": "sess-1"},
            )
        if body["method"] == "notifications/initialized":
            return FakeMcpResp(status_code=202)
        return FakeMcpResp(
            {
                "result": {
                    "tools": [
                        {"name": "list_catalog_applications"},
                        {"name": "get_catalog_application"},
                    ]
                }
            }
        )

    monkeypatch.setattr(
        "deployment.inspect_catalog.requests.post", fake_mcp_post
    )
    summary = inspect_catalog("prj-test-01", "us-central1")
    printed = capsys.readouterr().out
    assert "Automatic Context Resolution Cascade:" in printed
    assert "[Priority 1] External Catalog MCP" in printed
    assert "[Priority 1] Google Cloud App Hub" in printed
    assert "[Priority 2] Workload Profiles" in printed
    assert (
        "[Priority 3] Accessible GCP Projects via Service Account / OAuth"
        in printed
    )
    assert seen_methods == [
        "initialize",
        "notifications/initialized",
        "tools/list",
    ]
    assert summary["live_project_discovery_ready"] is True
    assert not summary["workload_profiles"]
    assert summary["apphub_applications"][0]["application_id"] == "orders-app"
    assert summary["external_catalog_mcp"]["tools"] == [
        "list_catalog_applications",
        "get_catalog_application",
    ]


def test_sse_mcp_probe_oidc_user_adc_uri_normalization_and_sweep_rate_limit(
    monkeypatch,
):
    monkeypatch.delenv("CLOUDSDK_CORE_ACCOUNT", raising=False)
    clear_auth_caches()

    class UserAdcCreds:
        """Fake user ADC credentials containing an OIDC ID token."""

        def __init__(self):
            self.token = "ya29-user-access-token"
            self.id_token = "eyJ.user-adc-oidc-jwt.sig"
            self.expired = False
            self.expiry = datetime.now(UTC) + timedelta(minutes=40)

        def refresh(self, _req):
            pass

    monkeypatch.setattr(
        "google.auth.default", lambda scopes=None: (UserAdcCreds(), "prj-user")
    )
    monkeypatch.setattr(
        "app.tools.mcp_registry.id_token.fetch_id_token",
        lambda _req, _aud: (_ for _ in ()).throw(
            ValueError("no metadata server on laptop")
        ),
    )
    monkeypatch.setattr(cfg, "CATALOG_MCP_URL", "https://catalog.run.app/mcp")
    monkeypatch.setattr(cfg, "CATALOG_MCP_AUTH_MODE", "oidc")
    hdr = _catalog_mcp_header_provider()
    assert hdr == {"Authorization": "Bearer eyJ.user-adc-oidc-jwt.sig"}

    sa_cmds: list[list[str]] = []
    monkeypatch.setenv(
        "CLOUDSDK_CORE_ACCOUNT", "sa-bot@prj.iam.gserviceaccount.com"
    )
    clear_auth_caches()
    monkeypatch.setattr(
        "app.tools.mcp_registry.subprocess.check_output",
        lambda cmd, **_kw: sa_cmds.append(cmd) or "sa-jwt-token\n",
    )
    sa_hdr = _catalog_mcp_header_provider()
    assert sa_hdr == {"Authorization": "Bearer sa-jwt-token"}
    assert "--audiences=https://catalog.run.app" in sa_cmds[0]
    monkeypatch.delenv("CLOUDSDK_CORE_ACCOUNT", raising=False)

    for key in (
        "CLOUDSDK_CORE_ACCOUNT",
        "GOOGLE_OAUTH_ACCESS_TOKEN",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "K_SERVICE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "deployment.cli.subprocess.check_output",
        lambda *_a, **_kw: "architect@example.com\n",
    )
    getattr(cli_mod, "_ensure_cli_gcloud_account_alignment")()
    assert (
        cli_mod.os.environ.get("CLOUDSDK_CORE_ACCOUNT")
        == "architect@example.com"
    )
    monkeypatch.delenv("CLOUDSDK_CORE_ACCOUNT", raising=False)

    class SseResp:
        """Fake SSE HTTP response for MCP probe tests."""

        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code
            self.headers = {"Content-Type": "text/event-stream"}

        def raise_for_status(self):
            return None

        def json(self):
            raise AssertionError(
                "json() must not be called on text/event-stream"
            )

    def fake_sse_post(_url, **kwargs):
        body = kwargs.get("json") or {}
        if body["method"] == "initialize":
            return SseResp(
                "event: message\n"
                'data: {"jsonrpc":"2.0","id":1,"result":'
                '{"serverInfo":{"name":"fastmcp-backstage"}}}\n\n'
            )
        if body["method"] == "notifications/initialized":
            return SseResp("", status_code=202)
        return SseResp(
            "event: message\n"
            'data: {"jsonrpc":"2.0","id":2,"result":'
            '{"tools":[{"name":"get_entity"}]}}\n\n'
        )

    clear_auth_caches()
    monkeypatch.setattr(
        "deployment.inspect_catalog.requests.post", fake_sse_post
    )
    sse_res = probe_catalog_mcp("https://backstage.example.com/mcp")
    assert sse_res["server_name"] == "fastmcp-backstage"
    assert sse_res["tools"] == ["get_entity"]

    def fake_rpc_error_post(_url, **kwargs):
        body = kwargs.get("json") or {}
        if body["method"] == "initialize":
            return SseResp(
                'data: {"jsonrpc":"2.0","id":1,'
                '"error":{"code":-32600,"message":"denied"}}\n\n'
            )
        return SseResp("", status_code=202)

    monkeypatch.setattr(
        "deployment.inspect_catalog.requests.post", fake_rpc_error_post
    )
    with pytest.raises(RuntimeError, match="MCP error"):
        probe_catalog_mcp("https://backstage.example.com/mcp")

    ctx = SimpleNamespace(state={})
    d1 = activate_zero_profile_discovery(
        "projects/prj-uri-01/locations/global", tool_context=ctx
    )
    assert d1["target_project_id"] == "prj-uri-01"

    monkeypatch.setattr(cfg, "CATALOG_MCP_URL", "")
    monkeypatch.setattr(cfg, "TARGET_PROJECT_ID", "projects/prj-apphub-host")
    apphub_only = activate_live_catalog_application(
        application_id=(
            "projects/prj-apphub-host/locations/us-central1/"
            "applications/billing-core"
        ),
        tool_context=ctx,
    )
    assert apphub_only["live_catalog_active"] is True
    assert apphub_only["application_id"] == "billing-core"
    assert apphub_only["apphub_application_id"] == "billing-core"
    assert apphub_only["project_ids"] == ["prj-apphub-host"]

    rel_prompt = RELIABILITY_INSTRUCTION(ctx)
    cost_prompt = COST_INSTRUCTION(ctx)
    assert "gcloud apphub applications describe billing-core" in rel_prompt
    assert "gcloud apphub applications describe" not in cost_prompt

    monkeypatch.setattr(cfg, "CATALOG_MCP_URL", "https://catalog.run.app/mcp")
    specialists = build_specialist_agents()
    sweepers = [agent for _, agent in build_sweep_reviewers()]
    assert any(
        getattr(t, "tool_name_prefix", None) == "app_catalog"
        for t in specialists[0].tools
    )
    assert not any(
        getattr(t, "tool_name_prefix", None) == "app_catalog"
        for t in sweepers[0].tools
    )

    active_now = 0
    peak_active = 0
    attempts_by_pillar: dict[str, int] = {}

    class RateLimitedStub:
        """Fake AgentTool simulating transient 429 rate-limit recovery."""

        def __init__(self, key: str):
            self.key = key

        async def run_async(self, *, args, tool_context):
            nonlocal active_now, peak_active
            _ = (args, tool_context)
            active_now += 1
            peak_active = max(peak_active, active_now)
            try:
                await asyncio.sleep(0.005)
                attempts_by_pillar[self.key] = (
                    attempts_by_pillar.get(self.key, 0) + 1
                )
                if (
                    self.key == "reliability"
                    and attempts_by_pillar[self.key] == 1
                ):
                    raise RuntimeError("429 RESOURCE_EXHAUSTED burst")
                return f"Recovered {self.key}"
            finally:
                active_now -= 1

    pillar_keys = [spec.pillar_key for spec in PILLAR_SPECS]
    monkeypatch.setattr(cfg, "SWEEP_CONCURRENCY_LIMIT", 2)
    monkeypatch.setattr(sweep_tool, "_RETRY_DELAY_SECONDS", 0.005)
    monkeypatch.setattr(
        sweep_tool,
        "build_sweep_agent_tools",
        lambda: [(k, RateLimitedStub(k)) for k in pillar_keys],
    )
    recovered = asyncio.run(
        sweep_tool.waf_six_pillar_parallel_sweep("Sweep test", tool_context=ctx)
    )
    assert peak_active <= 2
    assert len(recovered["completed_pillars"]) == 6
    assert recovered["failed_pillars"] == []
    assert attempts_by_pillar["reliability"] == 2


def test_zero_numbered_tiers_and_zero_code_comments():
    expr = "|".join(
        (
            "tier" + r"[_ -]?[123]",
            "context" + r"[_ -]?tier",
            "context-" + "maturity",
            "maturity" + " tier",
        )
    )
    pattern = re.compile(expr, re.IGNORECASE)
    for folder in ("app", "deployment", "tests"):
        for path in sorted((REPO_ROOT / folder).rglob("*")):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or ".terraform" in path.parts
            ):
                continue
            text = path.read_text(encoding="utf-8")
            assert not pattern.search(
                text
            ), f"Forbidden numbered tier reference in {path}"
            if path.suffix == ".py":
                with path.open("rb") as fh:
                    comment_tokens = [
                        tok.string
                        for tok in tokenize.tokenize(fh.readline)
                        if tok.type == tokenize.COMMENT and tok.start[0] > 14
                    ]
                assert (
                    not comment_tokens
                ), f"Code comments found in {path}: {comment_tokens}"


def test_datadog_and_external_observability_mcp_modes(monkeypatch):
    clear_auth_caches()
    monkeypatch.setattr(cfg, "RUNTIME_PROJECT_ID", "prj-sre-host")
    monkeypatch.setattr(
        cfg,
        "OBSERVABILITY_MCP_URL",
        "https://mcp.datadoghq.com/v1/mcp?toolsets=apm,metrics,logs,monitors",
    )
    monkeypatch.setattr(cfg, "OBSERVABILITY_MCP_AUTH_MODE", "bearer")
    monkeypatch.setattr(cfg, "OBSERVABILITY_MCP_BEARER_TOKEN", "")
    monkeypatch.setattr(
        cfg, "OBSERVABILITY_MCP_TOKEN_SECRET_ID", "datadog-readonly-sat"
    )
    monkeypatch.setattr(cfg, "OBSERVABILITY_MCP_PROVIDER_NAME", "datadog")
    monkeypatch.setattr(
        cfg,
        "OBSERVABILITY_MCP_TOOLS",
        ["search_datadog_logs", "list_datadog_monitors"],
    )
    monkeypatch.setattr(
        "app.tools.mcp_registry._get_cached_adc_token_and_project",
        lambda: ("gcp-adc-tok", "prj-sre-host"),
    )

    class FakeSecretResp:
        """Fake Secret Manager REST response for bearer token lookup."""

        def raise_for_status(self):
            return None

        def json(self):
            encoded = base64.b64encode(b"dd_sat_readonly_secret_123\n").decode(
                "ascii"
            )
            return {"payload": {"data": encoded}}

    monkeypatch.setattr(
        "app.tools.mcp_registry.requests.get",
        lambda *_a, **_kw: FakeSecretResp(),
    )

    obs_toolsets = build_external_observability_mcp()
    assert len(obs_toolsets) == 1
    assert obs_toolsets[0].tool_name_prefix == "datadog"
    hdr = _observability_mcp_header_provider(None)
    assert hdr == {"Authorization": "Bearer dd_sat_readonly_secret_123"}

    specialists = build_specialist_agents()
    sweepers = [agent for _, agent in build_sweep_reviewers()]
    assert any(
        getattr(t, "tool_name_prefix", None) == "datadog"
        for t in specialists[0].tools
    )
    assert any(
        getattr(t, "tool_name_prefix", None) == "datadog"
        for t in sweepers[0].tools
    )

    clear_auth_caches()
    monkeypatch.setattr(cfg, "OBSERVABILITY_MCP_AUTH_MODE", "headers")
    monkeypatch.setattr(cfg, "OBSERVABILITY_MCP_TOKEN_SECRET_ID", "")
    monkeypatch.setattr(
        cfg,
        "OBSERVABILITY_MCP_HEADERS_JSON",
        '{"DD-API-KEY":"dd_api_1","DD-APPLICATION-KEY":"dd_app_2"}',
    )
    custom_hdr = _observability_mcp_header_provider(None)
    assert custom_hdr == {
        "DD-API-KEY": "dd_api_1",
        "DD-APPLICATION-KEY": "dd_app_2",
    }

    monkeypatch.setattr(cfg, "OBSERVABILITY_MCP_URL", "")
    monkeypatch.setattr(
        cfg,
        "OBSERVABILITY_MCP_SERVERS_JSON",
        json.dumps(
            [
                {
                    "name": "zabbix",
                    "priority": 2,
                    "url": "https://zabbix-mcp.run.app/mcp",
                    "auth_mode": "none",
                    "pillars": ["reliability"],
                    "layer_role": "Hybrid on-premises hosts and WAN links",
                },
                {
                    "name": "datadog",
                    "priority": 1,
                    "url": "https://mcp.datadoghq.com/v1/mcp",
                    "auth_mode": "bearer",
                    "bearer_token": "dd_tok_direct",
                    "pillars": ["operational_excellence", "reliability"],
                    "layer_role": "In-process APM traces",
                },
                {
                    "name": "wiz",
                    "priority": 1,
                    "url": "https://wiz-mcp.run.app/mcp",
                    "auth_mode": "bearer",
                    "bearer_token": "wiz_tok_direct",
                    "pillars": ["security_compliance"],
                    "layer_role": "Cloud vulnerability graph",
                },
            ]
        ),
    )
    monkeypatch.setattr(
        cfg,
        "CATALOG_MCP_SERVERS_JSON",
        json.dumps(
            [
                {
                    "name": "servicenow",
                    "priority": 2,
                    "url": "https://snow.run.app/mcp",
                    "auth_mode": "none",
                },
                {
                    "name": "backstage",
                    "priority": 1,
                    "url": "https://backstage.run.app/mcp",
                    "auth_mode": "none",
                },
            ]
        ),
    )

    rel_specs = get_configured_observability_mcp_specs("reliability")
    assert [s["tool_name_prefix"] for s in rel_specs] == ["datadog", "zabbix"]
    assert get_configured_observability_mcp_specs("cost_optimization") == []

    scoped_specialists = {a.name: a for a in build_specialist_agents()}
    rel_prefixes = [
        getattr(t, "tool_name_prefix", "")
        for t in scoped_specialists["reliability_agent"].tools
    ]
    sec_prefixes = [
        getattr(t, "tool_name_prefix", "")
        for t in scoped_specialists["security_compliance_agent"].tools
    ]
    cost_prefixes = [
        getattr(t, "tool_name_prefix", "")
        for t in scoped_specialists["cost_optimization_agent"].tools
    ]
    assert (
        "datadog" in rel_prefixes
        and "zabbix" in rel_prefixes
        and "wiz" not in rel_prefixes
    )
    assert "wiz" in sec_prefixes and "datadog" not in sec_prefixes
    assert "datadog" not in cost_prefixes and "wiz" not in cost_prefixes

    rel_prompt = RELIABILITY_INSTRUCTION(SimpleNamespace(state={}))
    assert "Priority 1: `datadog_*`" in rel_prompt
    assert "Priority 2: `zabbix_*`" in rel_prompt
    assert "wiz_*" not in rel_prompt
    assert "External observability priority" not in COST_INSTRUCTION(
        SimpleNamespace(state={})
    )
    assert "Priority 1: `wiz_*`" in SECURITY_INSTRUCTION(
        SimpleNamespace(state={})
    )

    cat_toolsets = build_external_catalog_mcp()
    assert [t.tool_name_prefix for t in cat_toolsets] == [
        "app_catalog_backstage",
        "app_catalog_servicenow",
    ]
    orch_prompt = ORCHESTRATOR_INSTRUCTION(SimpleNamespace(state={}))
    assert (
        "`app_catalog_backstage_*` at priority 1, "
        "`app_catalog_servicenow_*` at priority 2" in orch_prompt
    )
