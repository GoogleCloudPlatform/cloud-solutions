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

# pylint: disable=import-outside-toplevel

"""End-to-End FastAPI Gateway & Breach Simulator Endpoint Tests."""

from __future__ import annotations

import pytest
from app.main import app
from fastapi.testclient import TestClient
from scripts.sandbox_auth import SandboxCaller

client = TestClient(app)


def _as(tenant_id: str, sub: str, role: str = "sre_admin") -> SandboxCaller:
    return SandboxCaller(client, tenant_id=tenant_id, sub=sub, role=role)


def _get(caller: SandboxCaller, path: str, **headers: str) -> object:
    return client.get(
        path, headers={**headers, **caller.headers("GET", caller.url(path))}
    )


def _post(caller: SandboxCaller, path: str, body: dict[str, object]) -> object:
    return client.post(
        path, json=body, headers=caller.headers("POST", caller.url(path))
    )


def test_healthz_and_dashboard_ui() -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    from agents.platform_config import load_platform_config

    assert (
        res.json()["gcp_project"]
        == load_platform_config("sandbox").gcp.project_id
    )

    ui = client.get("/")
    assert ui.status_code == 200
    assert "Cymbal SaaS" in ui.text


def test_ard_catalog_endpoint_filters_by_tenant_and_strips_headers() -> None:
    catalog = "/.well-known/ai-catalog.json"
    assert (
        client.get(catalog).status_code == 401
    )  # no anonymous tenant catalogs
    fv = _get(
        _as("tenant-finvault-alpha", "alice@finvault.com"),
        catalog,
        **{"X-Tenant-ID": "spoofed"},
    )
    assert fv.status_code == 200
    fv_body = fv.json()
    assert len(fv_body["agents"]) == 2
    assert "x-tenant-id" in fv_body["stripped_untrusted_headers"]

    # ?tenant_id= is ignored: the catalog is always the token's tenant.
    rs_caller = _as("tenant-retailstream-beta", "bob@retailstream.com")
    rs = client.get(
        catalog,
        params={"tenant_id": "tenant-finvault-alpha"},
        headers=rs_caller.headers(
            "GET", rs_caller.url(catalog)
        ),  # htu excludes the query
    )
    assert rs.status_code == 200
    rs_body = rs.json()
    assert len(rs_body["agents"]) == 1
    assert rs_body["agents"][0]["agent_id"] == "cymbal_shared_diagnostic_agent"


def test_invoke_agent_5_hop_execution_for_finvault_and_retailstream() -> None:
    # FinVault invokes private Agent Alpha
    fv_resp = _post(
        _as("tenant-finvault-alpha", "alice@finvault.com"),
        "/api/v1/invoke-agent",
        {
            "agent_id": "finvault_regulatory_escalation_agent",
            "tool_name": "escalate_regulatory_filing",
            "requested_thinking_tokens": 8000,
        },
    )
    assert fv_resp.status_code == 200
    data = fv_resp.json()
    assert data["status"] == "SUCCESS"
    assert data["identity_source"] == "HOP0_VERIFIED"
    assert len(data["hops"]) == 4
    assert data["tool_output"]["regulator"] == "OCC"

    # RetailStream invokes Shared Diagnostic Agent with RLS + DLP redaction
    rs_resp = _post(
        _as("tenant-retailstream-beta", "bob@retailstream.com"),
        "/api/v1/invoke-agent",
        {
            "agent_id": "cymbal_shared_diagnostic_agent",
            "tool_name": "query_telemetry_rls",
            "requested_thinking_tokens": 4000,
        },
    )
    assert rs_resp.status_code == 200
    rs_data = rs_resp.json()
    assert rs_data["tenant_id"] == "tenant-retailstream-beta"
    assert (
        "[REDACTED_PAYMENT_PAN]"
        in rs_data["tool_output"]["incidents"][0]["pii_notes"]
    )


@pytest.mark.parametrize(
    ("scenario_id", "expected_http_status"),
    [
        ("catalog_spoof", 403),
        ("header_forging", 403),
        ("prompt_injection", 403),
        ("rls_tampering", 403),
        ("noisy_neighbor", 429),
    ],
)
def test_all_five_breach_simulation_endpoints_block_attacks(
    scenario_id: str, expected_http_status: int
) -> None:
    res = client.post(f"/api/v1/breach-simulations/{scenario_id}")
    assert res.status_code == 200
    payload = res.json()
    assert payload["outcome"] == "BREACH_BLOCKED"
    assert payload["http_status"] == expected_http_status

    telemetry = client.get("/api/v1/finops-telemetry")
    assert telemetry.status_code == 200
    assert telemetry.json()["total_spans_recorded"] >= 1
