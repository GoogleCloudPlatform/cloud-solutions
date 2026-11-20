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
# pylint: disable=use-implicit-booleaness-not-comparison

"""The gateway trusts only verified callers (roadmap step 1, PR 2b; closes sweep finding P0).

Before this change, invoke-agent, invoke-agent-live, MCP and the catalogs took tenant, user and
role from the request body or query, so any caller allowed through Cloud Run could act as any
tenant's admin. Proves:
- every data endpoint refuses callers without a gateway token;
- tenant, user and role come only from the token; identity fields in the body are rejected;
- spoofed tenancy headers are ignored (and reported as stripped);
- role-based tool pruning follows the token's role;
- demo / simulation endpoints exist only in the synthetic sandbox.
"""

from __future__ import annotations

from typing import Any

import pytest
from agents import platform_config as pc
from app import main
from app.main import app
from fastapi.testclient import TestClient
from scripts.sandbox_auth import SandboxCaller

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
client = TestClient(app)


def _as(tenant: str, sub: str, role: str = "sre_admin") -> SandboxCaller:
    return SandboxCaller(client, tenant_id=tenant, sub=sub, role=role)


def _post(
    caller: SandboxCaller, path: str, body: dict[str, Any], **extra: str
) -> Any:
    return client.post(
        path,
        json=body,
        headers={**extra, **caller.headers("POST", caller.url(path))},
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/invoke-agent"),
        ("POST", "/api/v1/invoke-agent-live"),
        ("GET", "/.well-known/ai-catalog.json"),
        ("GET", "/.well-known/agent.json"),
    ],
)
def test_data_endpoints_refuse_callers_without_a_token(
    method: str, path: str
) -> None:
    resp = client.request(method, path, json={} if method == "POST" else None)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("DPoP")


def test_mcp_without_a_token_is_a_json_rpc_auth_error() -> None:
    body = client.post(
        "/mcp/v1/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert body.json()["error"]["code"] == -32001


def test_tenant_and_user_come_from_the_token() -> None:
    resp = _post(_as(RS, "bob@retailstream.com"), "/api/v1/invoke-agent", {})
    assert resp.status_code == 200
    data = resp.json()
    assert (data["tenant_id"], data["identity_source"]) == (RS, "HOP0_VERIFIED")


@pytest.mark.parametrize(
    "field",
    [
        {"authenticated_tenant_id": FV},
        {"user_sub": "alice@finvault.com"},
        {"user_role": "sre_admin"},
        {"idp_issuer": "https://accounts.google.com"},
        {"spoofed_headers": {"X-Tenant-ID": FV}},
    ],
)
def test_identity_fields_in_the_body_are_rejected(
    field: dict[str, Any],
) -> None:
    caller = _as(RS, "bob@retailstream.com", "read_only_analyst")
    for path in ("/api/v1/invoke-agent", "/api/v1/invoke-agent-live"):
        assert _post(caller, path, field).status_code == 422


def test_spoofed_tenancy_headers_are_ignored_and_reported() -> None:
    resp = _post(
        _as(RS, "bob@retailstream.com"),
        "/api/v1/invoke-agent",
        {},
        **{"X-Tenant-ID": FV, "X-Subscription-Tier": "enterprise"},
    )
    data = resp.json()
    assert data["tenant_id"] == RS
    assert data["tier"].endswith("standard")
    hop1 = data["hops"][0]["detail"]
    assert "x-tenant-id" in hop1
    assert "x-subscription-tier" in hop1


def test_role_from_the_token_drives_tool_pruning() -> None:
    """A read-only analyst cannot reach write tools, whatever the request asks for."""
    analyst = _as(FV, "dave@finvault.com", "read_only_analyst")
    blocked = _post(
        analyst, "/api/v1/invoke-agent", {"tool_name": "create_jira_incident"}
    )
    assert blocked.status_code == 403
    admin = _as(FV, "alice@finvault.com", "sre_admin")
    allowed = _post(
        admin, "/api/v1/invoke-agent", {"tool_name": "query_telemetry_rls"}
    )
    assert allowed.status_code == 200
    assert "create_jira_incident" in allowed.json()["entitled_tools"]


def test_catalog_is_the_tokens_tenant_whatever_the_query_says() -> None:
    caller = _as(RS, "bob@retailstream.com")
    path = "/.well-known/ai-catalog.json"
    resp = client.get(
        path,
        params={"tenant_id": FV},
        headers=caller.headers("GET", caller.url(path)),
    )
    agents = {a["agent_id"] for a in resp.json()["agents"]}
    assert agents == {"cymbal_shared_diagnostic_agent"}


SANDBOX_ONLY = [
    ("POST", "/api/v1/breach-simulations/catalog_spoof"),
    ("POST", "/api/v1/topology-deltas/pattern_a_pooled"),
    ("GET", "/api/v1/finops-telemetry"),
    ("POST", "/api/v1/2am-chaos/tier_downgrade_cache"),
    ("POST", "/api/v1/breach-matrix-10"),
    ("POST", "/api/v1/live-gcp-verify"),
    ("POST", "/api/v1/live-3p-connectors/verify"),
    ("POST", "/api/v1/live-3p-connectors/create-ticket/jira"),
    ("POST", "/api/v1/prerequisites-check/sandbox"),
    ("POST", "/api/v1/golden-e2e-suite"),
    # The 3LO callback records a synthetic grant without a provider code exchange.
    ("POST", "/api/v1/oauth/3lo/authorize"),
    ("POST", "/api/v1/oauth/3lo/callback"),
]


@pytest.mark.parametrize(("method", "path"), SANDBOX_ONLY)
def test_demo_endpoints_do_not_exist_outside_the_sandbox(
    method: str, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    customer = pc.load_platform_config("customer.example")
    monkeypatch.setattr(main, "get_platform_config", lambda *a, **k: customer)
    assert client.request(method, path).status_code == 404


def test_scripted_breach_scenarios_still_run_in_the_sandbox() -> None:
    resp = client.post("/api/v1/breach-simulations/header_forging")
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "BREACH_BLOCKED"


# --- Review hardening -------------------------------------------------------------------------


def test_sandbox_config_in_another_project_exposes_no_demo_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-production-project")
    for method, path in SANDBOX_ONLY:
        assert client.request(method, path).status_code == 404, path


@pytest.mark.parametrize("metadata_project", ["some-production-project", None])
def test_on_cloud_run_only_the_metadata_server_decides(
    monkeypatch: pytest.MonkeyPatch, metadata_project: str | None
) -> None:
    """A copied sandbox overlay on Cloud Run, with GOOGLE_CLOUD_PROJECT unset or forged."""
    from app import auth

    monkeypatch.setenv("K_SERVICE", "cymbal-pooled-gateway")
    monkeypatch.setattr(auth, "_metadata_cache", [])
    monkeypatch.setattr(auth, "_metadata_project", lambda: metadata_project)
    sandbox = pc.load_platform_config("sandbox")
    for env_value in (
        None,
        sandbox.gcp.project_id,
    ):  # unset, or forged to the sandbox project
        if env_value is None:
            monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        else:
            monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", env_value)
        assert not auth.sandbox_mode_active(sandbox)
        assert auth.build_hop0(sandbox).dev_issuer is None
        for method, path in SANDBOX_ONLY:
            assert client.request(method, path).status_code == 404, path


def test_on_cloud_run_in_the_sandbox_project_sandbox_mode_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import auth

    sandbox = pc.load_platform_config("sandbox")
    monkeypatch.setenv("K_SERVICE", "cymbal-pooled-gateway")
    monkeypatch.setattr(auth, "_metadata_cache", [])
    monkeypatch.setattr(
        auth, "_metadata_project", lambda: sandbox.gcp.project_id
    )
    assert auth.sandbox_mode_active(sandbox)


def test_on_cloud_run_the_local_opt_in_flag_is_irrelevant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Managed runtime: the metadata server alone decides, with or without the local flag."""
    from app import auth

    sandbox = pc.load_platform_config("sandbox")
    monkeypatch.setenv("K_SERVICE", "cymbal-pooled-gateway")
    monkeypatch.setattr(auth, "_metadata_cache", [])
    for flag in (None, "1"):
        if flag is None:
            monkeypatch.delenv(pc.LOCAL_SANDBOX_ENV, raising=False)
        else:
            monkeypatch.setenv(pc.LOCAL_SANDBOX_ENV, flag)
        monkeypatch.setattr(
            auth, "_metadata_project", lambda: sandbox.gcp.project_id
        )
        monkeypatch.setattr(auth, "_metadata_cache", [])
        assert auth.sandbox_mode_active(sandbox)
        monkeypatch.setattr(
            auth, "_metadata_project", lambda: "some-production-project"
        )
        monkeypatch.setattr(auth, "_metadata_cache", [])
        assert not auth.sandbox_mode_active(sandbox)


@pytest.mark.parametrize("flag", [None, "0", "true", ""])
def test_local_run_without_the_explicit_opt_in_exposes_no_sandbox_surface(
    monkeypatch: pytest.MonkeyPatch, flag: str | None
) -> None:
    """Off a managed runtime `CYMBAL_ENV` defaults to sandbox and the running project is only the
    config's own value, so a bare `uvicorn app.main:app` (or the image on a VM) must fail closed:
    no token mint, no dev issuer, no demo endpoint. Only `CYMBAL_LOCAL_SANDBOX=1` opts in.
    """
    from app import auth

    for managed in pc.MANAGED_RUNTIME_ENV:
        monkeypatch.delenv(managed, raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    if flag is None:
        monkeypatch.delenv(pc.LOCAL_SANDBOX_ENV, raising=False)
    else:
        monkeypatch.setenv(pc.LOCAL_SANDBOX_ENV, flag)
    sandbox = pc.load_platform_config("sandbox")
    assert not auth.sandbox_mode_active(sandbox)
    assert not auth.dev_issuer_allowed(sandbox)
    assert auth.build_hop0(sandbox).dev_issuer is None
    # The process-wide wiring was built with the flag on (conftest); the route still refuses.
    resp = client.post(
        "/api/v1/sandbox/token",
        json={
            "tenant_id": FV,
            "sub": "alice@finvault.com",
            "role": "sre_admin",
        },
    )
    assert resp.status_code == 404
    assert "id_token" not in resp.text
    for method, path in SANDBOX_ONLY:
        assert client.request(method, path).status_code == 404, path
    for doc_path in ("/openapi.json", "/docs", "/redoc"):
        assert client.get(doc_path).status_code == 404


def test_local_run_with_the_explicit_opt_in_mints_sandbox_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import auth

    for managed in pc.MANAGED_RUNTIME_ENV:
        monkeypatch.delenv(managed, raising=False)
    monkeypatch.setenv(pc.LOCAL_SANDBOX_ENV, "1")
    sandbox = pc.load_platform_config("sandbox")
    assert auth.sandbox_mode_active(sandbox)
    assert auth.build_hop0(sandbox).dev_issuer is not None
    resp = client.post(
        "/api/v1/sandbox/token",
        json={
            "tenant_id": FV,
            "sub": "alice@finvault.com",
            "role": "sre_admin",
        },
    )
    assert resp.status_code == 200
    # The opt-in does not override the project check.
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-production-project")
    assert not auth.sandbox_mode_active(sandbox)
    assert (
        client.post(
            "/api/v1/sandbox/token",
            json={
                "tenant_id": FV,
                "sub": "alice@finvault.com",
                "role": "sre_admin",
            },
        ).status_code
        == 404
    )


# Routes that intentionally carry no caller identity. Everything else must depend on Caller,
# OptionalCaller, or SandboxOnly.
PUBLIC_ROUTES = {
    "/healthz",
    "/api/v1/health",
    "/",
    "/demos",
    "/tuesday",
    "/visualizer",
    "/assets/cymbal_architecture_walkthrough.mp4",
    "/diagrams/{diagram_name}.svg",
    "/api/v1/sandbox/token",  # 404 unless the dev issuer is allowed
    "/api/v1/auth/token",  # verifies the IdP token itself
    "/.well-known/cymbal-context-jwks.json",  # public keys only (ADR-0014 D3)
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


def test_every_route_is_authenticated_sandbox_only_or_explicitly_public() -> (
    None
):
    from fastapi.routing import APIRoute

    def calls(dep: Any) -> set[str]:
        names = {getattr(dep.call, "__name__", "")}
        for sub in dep.dependencies:
            names |= calls(sub)
        return names

    unguarded = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in PUBLIC_ROUTES:
            continue
        guards = calls(getattr(route, "depend" + "ant"))
        if not guards & {"require_caller", "optional_caller", "sandbox_only"}:
            unguarded.append(route.path)
    assert unguarded == []


def test_scenario_turn_is_never_a_request_body() -> None:
    from fastapi.routing import APIRoute

    for route in app.routes:
        if isinstance(route, APIRoute) and route.body_field is not None:
            annotation = route.body_field.field_info.annotation
            assert annotation is not main.ScenarioTurn, route.path


def test_mcp_with_an_invalid_or_bearer_token_is_401() -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    for auth in ("Bearer something", "DPoP not-a-token"):
        resp = client.post(
            "/mcp/v1/jsonrpc", json=body, headers={"Authorization": auth}
        )
        assert resp.status_code == 401


def test_blocked_turns_return_a_code_not_internal_messages() -> None:
    analyst = _as(FV, "dave@finvault.com", "read_only_analyst")
    resp = _post(
        analyst, "/api/v1/invoke-agent", {"tool_name": "create_jira_incident"}
    )
    detail = resp.json()["detail"]
    assert resp.status_code == 403
    assert set(detail) == {"status", "http_code", "blocked_at_hop", "error"}
    assert detail["error"].startswith("E_")
    for leak in ("tenant-", "@", "completed_hops", "Forbidden:"):
        assert leak not in str(detail)


def test_live_turn_failure_hides_gcp_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agents import gcp_live_bridge

    class Boom:
        async def run_tenant_diagnostic_turn(self, **_: Any) -> dict[str, Any]:
            raise RuntimeError(
                "projects/secret-project serviceAccount:x@y.iam failure"
            )

    monkeypatch.setattr(gcp_live_bridge, "is_live_gcp_enabled", lambda: True)
    monkeypatch.setattr(gcp_live_bridge, "LiveADKVertexRunner", Boom)
    resp = _post(_as(FV, "alice@finvault.com"), "/api/v1/invoke-agent-live", {})
    assert resp.json()["gcp_adc_note"] == "E_LIVE_GCP_STEP_FAILED"
    assert resp.json()["mode"] == "LOCAL_SANDBOX_FALLBACK"
    assert "secret-project" not in resp.text


def test_live_turn_failure_fails_closed_outside_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outside the sandbox a failed live step is a 503, never a simulated answer (as
    /invoke-agent).
    """
    from agents import gcp_live_bridge

    class Boom:
        async def run_tenant_diagnostic_turn(self, **_: Any) -> dict[str, Any]:
            raise RuntimeError(
                "projects/secret-project serviceAccount:x@y.iam failure"
            )

    monkeypatch.setattr(gcp_live_bridge, "is_live_gcp_enabled", lambda: True)
    monkeypatch.setattr(gcp_live_bridge, "LiveADKVertexRunner", Boom)
    caller = _as(FV, "alice@finvault.com")
    monkeypatch.setattr(main, "sandbox_mode_active", lambda cfg: False)
    resp = _post(caller, "/api/v1/invoke-agent-live", {})
    assert (resp.status_code, resp.json()["detail"]) == (
        503,
        {"error": "E_LIVE_GCP_STEP_FAILED"},
    )
    assert "Simulated" not in resp.text
    assert "secret-project" not in resp.text


def test_raw_sql_override_is_sandbox_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller = _as(FV, "alice@finvault.com")
    monkeypatch.setattr(main, "sandbox_mode_active", lambda cfg: False)
    resp = _post(
        caller, "/api/v1/invoke-agent", {"raw_sql_override": "SELECT 1"}
    )
    assert (resp.status_code, resp.json()["detail"]) == (
        422,
        {"error": "E_RAW_SQL_SANDBOX_ONLY"},
    )


def test_live_ticket_creation_needs_the_owning_tenants_admin() -> None:
    path = "/api/v1/live-3p-connectors/create-ticket/jira"
    assert client.post(path).status_code == 401
    for caller in (
        _as(RS, "bob@retailstream.com"),
        _as(FV, "dave@finvault.com", "read_only_analyst"),
    ):
        resp = _post(caller, path, {})
        assert (resp.status_code, resp.json()["detail"]) == (
            403,
            {"error": "E_TICKET_CREATE_FORBIDDEN"},
        )


def test_token_endpoints_emit_no_store_and_defensive_headers() -> None:
    sandbox_resp = client.post(
        "/api/v1/sandbox/token",
        json={
            "tenant_id": FV,
            "sub": "alice@finvault.com",
            "role": "sre_admin",
        },
    )
    assert sandbox_resp.status_code == 200
    assert sandbox_resp.headers["cache-control"] == "no-store"
    assert sandbox_resp.headers["pragma"] == "no-cache"
    assert sandbox_resp.headers["x-content-type-options"] == "nosniff"
    assert sandbox_resp.headers["x-frame-options"] == "DENY"

    caller = _as(FV, "alice@finvault.com")
    proof = caller.dpop_proof("POST", caller.url("/api/v1/auth/token"))
    exchange_resp = client.post(
        "/api/v1/auth/token",
        json={"subject_token": sandbox_resp.json()["id_token"]},
        headers={"DPoP": proof},
    )
    assert exchange_resp.status_code == 200
    assert exchange_resp.headers["cache-control"] == "no-store"
    assert exchange_resp.headers["pragma"] == "no-cache"
    assert exchange_resp.headers["x-content-type-options"] == "nosniff"
    assert exchange_resp.headers["x-frame-options"] == "DENY"


def test_openapi_docs_hidden_outside_synthetic_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for doc_path in ("/openapi.json", "/docs", "/redoc"):
        sandbox_resp = client.get(doc_path)
        assert sandbox_resp.status_code == 200
        assert sandbox_resp.headers["x-content-type-options"] == "nosniff"
        assert sandbox_resp.headers["x-frame-options"] == "DENY"

    monkeypatch.setattr(
        main, "sandbox_mode_active", lambda *_args, **_kwargs: False
    )
    for doc_path in ("/openapi.json", "/docs", "/redoc"):
        prod_resp = client.get(doc_path)
        assert prod_resp.status_code == 404
        assert prod_resp.headers["cache-control"] == "no-store"
        assert prod_resp.headers["x-content-type-options"] == "nosniff"
        assert prod_resp.headers["x-frame-options"] == "DENY"
