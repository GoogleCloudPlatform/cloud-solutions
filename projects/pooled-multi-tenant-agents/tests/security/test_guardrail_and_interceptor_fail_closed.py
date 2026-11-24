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
# pylint: disable=missing-class-docstring,protected-access,unused-argument

"""Regression tests for the ADR-0013 red-team audit fixes in PR-DA1 (FM-02, 03, 05, 06, 07, 10).

- FM-02: the live block of a turn no longer dies on a missing bulkhead field (silently masked).
- FM-03: the ADK interceptor verifies the envelope signature before trusting tenant/scopes/budget.
- FM-05: real callers cannot set the token estimate or the prefix-cache flag (TPM bypass, billing).
- FM-06: the live Postgres path binds the tenant with set_config(..., true), not `SET LOCAL ... $1`.
- FM-07: live DLP egress screening uses the caller's tenant, not a hard-coded one.
- FM-10: one transient Model Armor error backs off and retries instead of disabling live screening.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from agents import interceptors
from agents.context import (
    TENANT_DIRECTORY,
    EdgeAuthVerifier,
    TokenBucketBulkhead,
)
from agents.testing_fakes import MockADKCallbackContext
from app import main
from fastapi.testclient import TestClient
from scripts.sandbox_auth import SandboxCaller

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
client = TestClient(main.app)


def _env(
    tenant: str, sub: str = "alice@finvault.com", role: str = "sre_admin"
) -> Any:
    return EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims={
            "iss": str(TENANT_DIRECTORY[tenant]["iss"]),
            "sub": sub,
            "tenant_id": tenant,
            "user_role": role,
            "exp": int(time.time()) + 600,
        },
        dpop_proof={"jkt": "k", "jti": uuid.uuid4().hex},
    )


# --- FM-02 --------------------------------------------------------------------------------------


def test_bulkhead_reports_the_effective_thinking_budget() -> None:
    res = TokenBucketBulkhead().check_and_consume(
        tenant_id=FV,
        requested_thinking_tokens=3000,
        estimated_total_tokens=5000,
    )
    assert res["effective_thinking_tokens"] == 3000


def test_live_receipt_completes_instead_of_failing_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With every live client faked, the live block must finish (it used to KeyError, masked)."""
    from agents import gcp_live_bridge as live

    calls: dict[str, Any] = {}

    class Fake:
        def __init__(self, *a: Any, **k: Any) -> None: ...

        def __getattr__(self, name: str) -> Any:
            def method(*args: Any, **kwargs: Any) -> Any:
                calls[name] = kwargs
                return {"bucket": "b", "object_name": "o", "kms_key_name": "k"}

            return method

        def encrypt_for_tenant(self, **_: Any) -> bytes:
            return b"ct"

        def write_memory(self, **_: Any) -> str:
            return "key"

    monkeypatch.setattr(live, "is_live_gcp_enabled", lambda: True)
    for name in (
        "LiveAtlassianJiraConnector",
        "LiveServiceNowITOMConnector",
        "LiveMicrosoftEntraOIDCConnector",
        "LiveModelArmorGuardrail",
        "LiveCloudKMSCMEKVerifier",
        "LiveFirestoreMemoryBank",
        "LiveCloudDLPGuardrail",
        "LiveGCSCMEKRunbookVault",
        "LiveBigQueryOTelSink",
    ):
        monkeypatch.setattr(live, name, Fake)
    caller = SandboxCaller(
        client, tenant_id=FV, sub="alice@finvault.com", role="sre_admin"
    )
    url = caller.url("/api/v1/invoke-agent")
    resp = client.post(
        url, json={"live_cloud": True}, headers=caller.headers("POST", url)
    )
    receipt = resp.json()["live_cloud_receipt"]
    assert "gcp_adc_note" not in receipt, receipt
    assert calls["insert_span"]["thinking_tokens_budget"] == 4000
    assert (
        calls["deidentify_tool_output"]["tenant_id"] == FV
    )  # FM-07: the caller's tenant


# --- FM-03 --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (
            "temp:authorized_scopes",
            ["agent:finvault_regulatory_escalation_agent", "jira:write"],
        ),
        ("temp:tenant_id", FV),
        ("temp:thinking_budget", 64000),
    ],
)
async def test_interceptor_refuses_tampered_state(key: str, value: Any) -> None:
    from agents.shared_diagnostic_agent import build_shared_diagnostic_agent

    state = _env(RS, "bob@retailstream.com").to_adk_state()
    state[key] = value
    ctx = MockADKCallbackContext(
        state=state, agent=build_shared_diagnostic_agent()
    )
    with pytest.raises(
        PermissionError, match=r"E_SUBAGENT_STATE_TAMPERING|E_UNSIGNED"
    ):
        await interceptors.enforce_tenant_isolation_interceptor(ctx)


async def test_requested_thinking_budget_is_clamped_to_the_signed_cap() -> None:
    from agents.shared_diagnostic_agent import build_shared_diagnostic_agent

    state = _env(RS, "bob@retailstream.com").to_adk_state()
    state["temp:requested_thinking_budget"] = 16000
    ctx = MockADKCallbackContext(
        state=state, agent=build_shared_diagnostic_agent()
    )
    await interceptors.enforce_tenant_isolation_interceptor(ctx)
    assert ctx.state["temp:effective_thinking_budget"] == 4000


# --- FM-05 --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field", [{"estimated_total_tokens": 0}, {"prompt_cache_hit": True}]
)
def test_callers_cannot_set_metering_fields(field: dict[str, Any]) -> None:
    caller = SandboxCaller(client, tenant_id=RS, sub="bob@retailstream.com")
    url = caller.url("/api/v1/invoke-agent")
    assert (
        client.post(
            url, json=field, headers=caller.headers("POST", url)
        ).status_code
        == 422
    )


def test_server_side_estimate_always_charges_the_bulkhead() -> None:
    est, cache_hit = main._metering(
        main.InvokeAgentRequest(prompt="x", requested_thinking_tokens=0)
    )
    assert est >= main._TOOL_OUTPUT_TOKEN_ALLOWANCE
    assert (
        cache_hit is False
    )  # no assumed 90% discount on billing or the TPM check
    staged, _ = main._metering(main.ScenarioTurn(estimated_total_tokens=25000))
    assert staged == 25000  # scripted sandbox scenarios may still stage bursts


# --- FM-06 --------------------------------------------------------------------------------------


async def test_live_pool_binds_the_tenant_with_set_config() -> None:
    from mcp_server.db import RLSDatabasePool

    executed: list[tuple[str, tuple[Any, ...]]] = []

    class Conn:
        async def execute(self, sql: str, *args: Any) -> None:
            executed.append((sql, args))

        async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
            return []

        def transaction(self) -> Any:
            return _Ctx(None)

    class _Ctx:
        def __init__(self, value: Any) -> None:
            self.value = value

        async def __aenter__(self) -> Any:
            return self.value

        async def __aexit__(self, *exc: object) -> None:
            return None

    class Pool:
        def acquire(self) -> Any:
            return _Ctx(Conn())

    pool = RLSDatabasePool()
    pool._pool = Pool()
    await pool.query_incidents(tenant_id=RS, severity_filter="P1")
    assert executed[0] == (
        "SELECT set_config('app.current_tenant_id', $1, true);",
        (RS,),
    )
    assert not any(sql.startswith("SET LOCAL") for sql, _ in executed)


# --- FM-10 --------------------------------------------------------------------------------------


def test_model_armor_retries_after_a_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [1000.0]
    outcomes = iter([RuntimeError("transient"), {"blocked": False}])

    class Guardrail:
        def sanitize_prompt(self, _: str) -> dict[str, Any]:
            result = next(outcomes)
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setenv("CYMBAL_LIVE_GCP", "1")
    monkeypatch.delenv("CYMBAL_OFFLINE_CI", raising=False)
    monkeypatch.setattr(interceptors.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(interceptors, "_LIVE_MA_GUARDRAIL", Guardrail())
    monkeypatch.setattr(interceptors, "_LIVE_MA_RETRY_AT", 0.0)
    assert (
        interceptors._try_live_vertex_model_armor("hi") is None
    )  # transient failure
    assert (
        interceptors._try_live_vertex_model_armor("hi") is None
    )  # backing off
    now[0] += interceptors.LIVE_MA_RETRY_SECONDS + 1
    assert interceptors._try_live_vertex_model_armor("hi") == {
        "blocked": False
    }  # live again


def test_live_dlp_screens_egress_as_the_callers_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from agents import gcp_live_bridge as live

    seen: dict[str, str] = {}

    def fake_egress(*, tenant_id: str, **_: Any) -> str:
        seen["tenant_id"] = tenant_id
        return "redacted"

    response = SimpleNamespace(
        overview=SimpleNamespace(
            transformation_summaries=[], transformed_bytes=0
        ),
        item=SimpleNamespace(value="x"),
    )
    guard = object.__new__(live.LiveCloudDLPGuardrail)
    guard.parent, guard.inspect_template, guard.deidentify_template = (
        "p",
        "i",
        "d",
    )
    guard._client = SimpleNamespace(deidentify_content=lambda request: response)
    monkeypatch.setattr(live, "egress_dlp_and_nlc_guardrail", fake_egress)
    guard.deidentify_tool_output(
        raw_output="x", tool_name="query_telemetry_rls", tenant_id=RS
    )
    assert seen["tenant_id"] == RS


def test_turn_runs_with_the_metered_thinking_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metering and enforcement agree: a request for 0 thinking tokens runs with 0, not the cap."""
    seen: dict[str, Any] = {}
    real = interceptors.enforce_tenant_isolation_interceptor

    async def spy(ctx: Any, **kw: Any) -> Any:
        out = await real(ctx, **kw)
        seen["effective"] = ctx.state["temp:effective_thinking_budget"]
        return out

    # The turn body lives in agents.turn_engine (shared by the in-process and remote paths).
    from agents import turn_engine

    monkeypatch.setattr(
        turn_engine, "enforce_tenant_isolation_interceptor", spy
    )
    caller = SandboxCaller(
        client, tenant_id=FV, sub="alice@finvault.com", role="sre_admin"
    )
    url = caller.url("/api/v1/invoke-agent")
    body = {"requested_thinking_tokens": 0}
    assert (
        client.post(
            url, json=body, headers=caller.headers("POST", url)
        ).status_code
        == 200
    )
    assert seen["effective"] == 0


def test_caller_caused_model_armor_error_fails_closed_without_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from google.api_core import exceptions as gexc

    class Guardrail:
        def sanitize_prompt(self, _: str) -> dict[str, Any]:
            raise gexc.InvalidArgument("prompt too large")

    monkeypatch.setenv("CYMBAL_LIVE_GCP", "1")
    monkeypatch.delenv("CYMBAL_OFFLINE_CI", raising=False)
    monkeypatch.setattr(interceptors, "_LIVE_MA_GUARDRAIL", Guardrail())
    monkeypatch.setattr(interceptors, "_LIVE_MA_RETRY_AT", 0.0)
    with pytest.raises(PermissionError, match="E_MODEL_ARMOR_REQUEST_REJECTED"):
        interceptors._try_live_vertex_model_armor("x" * 10)
    assert (
        interceptors._LIVE_MA_RETRY_AT == 0.0
    )  # live screening stays on for everyone


def test_prompt_length_is_capped() -> None:
    caller = SandboxCaller(client, tenant_id=RS, sub="bob@retailstream.com")
    url = caller.url("/api/v1/invoke-agent")
    body = {"prompt": "a" * 16001}
    assert (
        client.post(
            url, json=body, headers=caller.headers("POST", url)
        ).status_code
        == 422
    )
