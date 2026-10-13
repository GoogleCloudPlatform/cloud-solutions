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

"""Unit tests for the Gemini CLI Extension Oracle EBS ExecutionEngine."""

import asyncio
from typing import Any

import pytest
from src.gemini_cli_extensions.oracle import ExecutionEngine


def test_execution_engine_lazy_clients_and_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ExecutionEngine lazily initializes DB and REST clients."""
    engine = ExecutionEngine(
        dsn="127.0.0.1:1521/ebsdb", user="apps", password="pwd"
    )
    assert engine.dsn == "127.0.0.1:1521/ebsdb"
    assert engine.user == "apps"
    assert engine.db_client.dsn == "127.0.0.1:1521/ebsdb"
    assert engine.rest_client is not None
    assert engine.get_pool() is None

    closed = False

    class _DummyPool:
        def close(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(engine.db_client, "pool", _DummyPool())
    assert engine.get_pool() is not None
    engine.close()
    assert closed is True


def test_execution_engine_delegation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify execute_plsql, respond_plsql, and respond_rest delegate calls."""
    engine = ExecutionEngine(
        dsn="127.0.0.1:1521/ebsdb", user="apps", password="pwd"
    )

    monkeypatch.setattr(
        engine.db_client,
        "execute_plsql",
        lambda block, params=None: {"status": "SUCCESS", "block": block},
    )
    res_sql = engine.execute_plsql("BEGIN NULL; END;", {"a": 1})
    assert res_sql["status"] == "SUCCESS"

    monkeypatch.setattr(
        engine.db_client,
        "respond_to_notification",
        lambda nid, action, comment, user_name, context=None: {
            "status": "SUCCESS",
            "notification_id": nid,
            "action": action,
        },
    )
    res_plsql = engine.respond_plsql(
        nid=1001, action="APPROVE", comment="OK", user_name="JDOE"
    )
    assert res_plsql["notification_id"] == 1001

    async def _fake_respond_rest(**kwargs: Any) -> dict[str, Any]:
        return {"status": "SUCCESS", "notification_id": kwargs["nid"]}

    monkeypatch.setattr(
        engine.rest_client, "respond_to_notification", _fake_respond_rest
    )
    res_rest = asyncio.run(
        engine.respond_rest(
            nid=1002, action="APPROVE", comment="OK", user_name="JDOE"
        )
    )
    assert res_rest["notification_id"] == 1002
