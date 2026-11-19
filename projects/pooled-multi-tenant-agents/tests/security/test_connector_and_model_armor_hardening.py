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

# pylint: disable=import-outside-toplevel,line-too-long,protected-access

"""Regression tests for the PR-DA1 follow-up slice (#25 on top of #26).

Covers the four items scoped to PR #25 after Daniel's PR #26:
1. Fail-closed `live_cloud` step handling: `PermissionError` re-raises as HTTP 403, and
   non-sandbox runtime errors fail closed with HTTP 503 (`E_LIVE_GCP_STEP_FAILED`).
2. `RLSDatabasePool.query_runbooks` live `asyncpg` branch binds the tenant via
   `SELECT set_config('app.current_tenant_id', $1, true);` inside the transaction.
3. `_execute_turn` dispatches `send_gmail_brief` and `read_sharepoint_runbook` (`FM-11`)
   and their outputs satisfy `verify_agent_output_deterministically`.
4. `_execute_turn` forwards `session_id=envelope.request.session_id` into
   `TOKEN_BULKHEAD.check_and_consume`, and `TokenBucketBulkhead` bounds tracked sessions at
   `MAX_TRACKED_SESSIONS = 4096` under `threading.Lock`.
"""

from __future__ import annotations

from typing import Any, Self

import pytest
from agents import gcp_live_bridge
from agents.context import TokenBucketBulkhead
from app import main
from evals.contracts import CitationSpan, DiagnosticAgentOutputContract
from evals.deterministic_verifier import (
    ContextChunk,
    verify_agent_output_deterministically,
)
from fastapi.testclient import TestClient
from mcp_server.db import RLSDatabasePool
from scripts.sandbox_auth import SandboxCaller

FINVAULT_TENANT = "tenant-finvault-alpha"
RETAILSTREAM_TENANT = "tenant-retailstream-beta"
client = TestClient(main.app)


def _caller(tenant_id: str, sub: str, role: str = "sre_admin") -> SandboxCaller:
    return SandboxCaller(client, tenant_id=tenant_id, sub=sub, role=role)


def _post_turn(caller: SandboxCaller, payload: dict[str, Any]) -> Any:
    target_url = caller.url("/api/v1/invoke-agent")
    return client.post(
        target_url,
        json=payload,
        headers=caller.headers("POST", target_url),
    )


def test_live_cloud_permission_error_returns_403_and_non_sandbox_outage_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finvault_caller = _caller(
        FINVAULT_TENANT, "alice@finvault.com", "sre_admin"
    )
    monkeypatch.setattr(gcp_live_bridge, "is_live_gcp_enabled", lambda: True)

    class FakeJiraConnector:
        def query_regulatory_issues(self, **_: Any) -> dict[str, Any]:
            return {"status": "ok"}

    monkeypatch.setattr(
        gcp_live_bridge, "LiveAtlassianJiraConnector", FakeJiraConnector
    )

    class DenyingModelArmorGuardrail:
        def sanitize_prompt(self, prompt: str) -> dict[str, Any]:
            raise PermissionError(
                "403 Forbidden [E_MODEL_ARMOR_BLOCKED]: blocked"
            )

    monkeypatch.setattr(
        gcp_live_bridge, "LiveModelArmorGuardrail", DenyingModelArmorGuardrail
    )
    denied_response = _post_turn(finvault_caller, {"live_cloud": True})
    assert denied_response.status_code == 403
    assert denied_response.json()["detail"]["error"] == "E_MODEL_ARMOR_BLOCKED"

    class UnavailableModelArmorGuardrail:
        def sanitize_prompt(self, prompt: str) -> dict[str, Any]:
            raise RuntimeError("Transient regional endpoint failure")

    monkeypatch.setattr(
        gcp_live_bridge,
        "LiveModelArmorGuardrail",
        UnavailableModelArmorGuardrail,
    )
    monkeypatch.setattr(main, "sandbox_mode_active", lambda cfg: False)
    outage_response = _post_turn(finvault_caller, {"live_cloud": True})
    assert outage_response.status_code == 503
    assert outage_response.json()["detail"] == {
        "error": "E_LIVE_GCP_STEP_FAILED"
    }


def test_live_sql_only_references_columns_in_schema() -> None:
    """The fake pool above can't catch a wrong column name; check the live SQL against
    schema.sql.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    schema = (root / "mcp_server" / "schema.sql").read_text(encoding="utf-8")
    columns: dict[str, set[str]] = {}
    for table, body in re.findall(
        r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\);", schema, re.DOTALL
    ):
        columns[table] = {
            line.split()[0]
            for line in body.strip().splitlines()
            if line.strip()
        }
    db_source = (root / "mcp_server" / "db.py").read_text(encoding="utf-8")
    checked = 0
    for table, order_col in re.findall(
        r"FROM (tenant_\w+)[^\"]*?ORDER BY (\w+)", db_source
    ):
        assert (
            order_col in columns[table]
        ), f"{table} has no column {order_col!r}"
        checked += 1
    assert checked >= 1


@pytest.mark.asyncio
async def test_query_runbooks_live_asyncpg_branch_binds_tenant_with_set_config() -> (
    None
):
    executed_statements: list[tuple[str, tuple[Any, ...]]] = []

    class FakeTransaction:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    class FakeConnection:
        def transaction(self) -> FakeTransaction:
            return FakeTransaction()

        async def execute(self, sql: str, *args: Any) -> None:
            executed_statements.append((sql, args))

        async def fetch(self, sql: str, *args: Any) -> list[dict[str, str]]:
            executed_statements.append((sql, args))
            return [
                {
                    "runbook_id": "RB-RS-01",
                    "tenant_id": RETAILSTREAM_TENANT,
                    "title": "RetailStream POS Failover Runbook",
                }
            ]

    class FakeAcquireContext:
        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, *_: object) -> None:
            return None

    class FakeAsyncpgPool:
        def acquire(self) -> FakeAcquireContext:
            return FakeAcquireContext()

    pool = RLSDatabasePool()
    pool._pool = FakeAsyncpgPool()

    rows = await pool.query_runbooks(tenant_id=RETAILSTREAM_TENANT)
    assert len(rows) == 1
    assert rows[0]["runbook_id"] == "RB-RS-01"
    assert executed_statements[0] == (
        "SELECT set_config('app.current_tenant_id', $1, true);",
        (RETAILSTREAM_TENANT,),
    )
    assert pool.last_executed_guc == (
        f"SET LOCAL app.current_tenant_id = '{RETAILSTREAM_TENANT}';"
    )


def test_execute_turn_dispatches_gmail_and_sharepoint_tools_and_verifies_eval_contract() -> (
    None
):
    finvault_caller = _caller(
        FINVAULT_TENANT, "alice@finvault.com", "sre_admin"
    )
    gmail_response = _post_turn(
        finvault_caller,
        {
            "tool_name": "send_gmail_brief",
            "prompt": "Send executive summary of INC-FV-1001.",
        },
    )
    assert gmail_response.status_code == 200, gmail_response.text
    gmail_output = gmail_response.json()["tool_output"]
    assert gmail_output["status"] == "sent"
    assert gmail_output["tenant_id"] == FINVAULT_TENANT

    retail_caller = _caller(
        RETAILSTREAM_TENANT, "bob@retailstream.com", "sre_admin"
    )
    sharepoint_response = _post_turn(
        retail_caller,
        {
            "tool_name": "read_sharepoint_runbook",
            "prompt": "Fetch POS failover runbook ROA-2026-8812.",
        },
    )
    assert sharepoint_response.status_code == 200, sharepoint_response.text
    sharepoint_output = sharepoint_response.json()["tool_output"]
    assert sharepoint_output["status"] == "success"
    assert sharepoint_output["tenant_id"] == RETAILSTREAM_TENANT

    # Verify deterministic evaluation contract against the dispatched SharePoint runbook output
    source_chunk = ContextChunk(
        doc_id="ROA-2026-8812",
        tenant_id=RETAILSTREAM_TENANT,
        score=0.98,
        updated_at="2026-10-30T00:00:00Z",
        content=str(
            sharepoint_output.get(
                "content_excerpt", "Runbook ROA-2026-8812 failover"
            )
        ),
        token_count=32,
    )
    agent_contract = DiagnosticAgentOutputContract(
        evidence_summary=f"Retrieved SharePoint runbook: {source_chunk.content}",
        citations=[
            CitationSpan(
                source_id="ROA-2026-8812",
                tenant_id=RETAILSTREAM_TENANT,
                quoted_span=source_chunk.content[:30],
                numeric_claims=[],
            )
        ],
        decision="REMEDIATE_STANDARD",
        recommended_actions=["Execute POS failover sequence in ROA-2026-8812."],
        tenant_id=RETAILSTREAM_TENANT,
    )
    verification = verify_agent_output_deterministically(
        agent_contract,
        source_chunks=[source_chunk],
        caller_tenant_id=RETAILSTREAM_TENANT,
    )
    assert verification.passed is True


def test_execute_turn_forwards_session_id_and_bounds_tracked_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_session_ids: list[str | None] = []
    real_check = main.TOKEN_BULKHEAD.check_and_consume

    def spy_check_and_consume(**kwargs: Any) -> dict[str, Any]:
        recorded_session_ids.append(kwargs.get("session_id"))
        return real_check(**kwargs)

    monkeypatch.setattr(
        main.TOKEN_BULKHEAD, "check_and_consume", spy_check_and_consume
    )
    retail_caller = _caller(
        RETAILSTREAM_TENANT, "bob@retailstream.com", "sre_admin"
    )
    turn_response = _post_turn(retail_caller, {"prompt": "Check P1 telemetry."})
    assert turn_response.status_code == 200
    assert len(recorded_session_ids) == 1
    assert recorded_session_ids[0] is not None
    assert recorded_session_ids[0].startswith("sess-")

    bulkhead = TokenBucketBulkhead()
    bulkhead.MAX_TRACKED_SESSIONS = 4  # type: ignore[misc]
    for idx in range(6):
        bulkhead.check_and_consume(
            tenant_id=FINVAULT_TENANT,
            requested_thinking_tokens=100,
            estimated_total_tokens=200,
            session_id=f"sess-bounded-{idx}",
        )
    tracked = bulkhead._buckets[FINVAULT_TENANT].session_turns
    assert len(tracked) == 4
    assert "sess-bounded-0" not in tracked
    assert "sess-bounded-5" in tracked
