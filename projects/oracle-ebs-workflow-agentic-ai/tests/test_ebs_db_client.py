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

"""Unit tests for EBSDatabaseClient pooled connections and PL/SQL execution."""

from typing import Any

import pytest
from fastapi import HTTPException
from src.mcp import ebs_db_client
from src.mcp.ebs_db_client import EBSDatabaseClient, load_plsql_template


class _DummyVar:
    """Simulated Oracle bind variable holding CLOB JSON output."""

    def __init__(self, value: str) -> None:
        self._value = value

    def getvalue(self) -> str:
        """Return simulated bind variable content."""
        return self._value


class _DummyCursor:
    """Simulated Oracle cursor tracking executed statements and binds."""

    def __init__(self, out_payload: str = "[]") -> None:
        self.executed: list[tuple[str, dict[str, Any]]] = []
        self.closed = False
        self._out_payload = out_payload

    def var(self, _var_type: Any) -> _DummyVar:
        """Create a simulated output bind variable."""
        return _DummyVar(self._out_payload)

    def execute(self, sql: str, params: dict[str, Any]) -> None:
        """Record SQL execution and bind parameters."""
        self.executed.append((sql, params))

    def close(self) -> None:
        """Mark cursor as closed."""
        self.closed = True


class _DummyConnection:
    """Simulated Oracle connection providing a cursor and commit tracking."""

    def __init__(self, cursor: _DummyCursor) -> None:
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self) -> _DummyCursor:
        """Return the simulated cursor."""
        return self._cursor

    def commit(self) -> None:
        """Mark transaction as committed."""
        self.committed = True

    def close(self) -> None:
        """Mark connection as closed."""
        self.closed = True


def test_load_plsql_template() -> None:
    """Verify external SQL files load from src/workflow/sql/."""
    sql = load_plsql_template("init_apps_context.sql")
    assert "fnd_global.apps_initialize" in sql


def test_execute_plsql_and_apps_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify execute_plsql handles :out_json binds and commits cleanly."""
    client = EBSDatabaseClient(user="apps", password="pwd", dsn="db:1521/ebs")
    cursor = _DummyCursor(out_payload='[{"notification_id": 1001}]')
    conn = _DummyConnection(cursor)
    monkeypatch.setattr(client, "get_connection", lambda: conn)

    res = client.execute_plsql("BEGIN :out_json := 'ok'; END;", {"p1": 10})
    assert res["status"] == "SUCCESS"
    assert res["out_json"] == '[{"notification_id": 1001}]'
    assert conn.committed is True
    assert cursor.closed is True
    assert conn.closed is True

    client.initialize_apps_context(
        cursor, user_id=10, resp_id=20420, resp_appl_id=1
    )
    assert len(cursor.executed) == 2


def test_respond_to_notification_rest_and_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify respond_to_notification uses REST primary and PL/SQL fallback."""
    client = EBSDatabaseClient(user="apps", password="pwd", dsn="db:1521/ebs")
    monkeypatch.setattr(
        client.rest_client,
        "respond_to_notification_sync",
        lambda nid, action, comment, user_name: {"rest_ok": True},
    )
    res_rest = client.respond_to_notification(
        nid=1001, action="APPROVE", comment="Approved", user_name="JDOE"
    )
    assert res_rest["execution_path"] == "REST"
    assert res_rest["action"] == "APPROVE"

    def _raise_runtime_err(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("REST offline")

    monkeypatch.setattr(
        client.rest_client, "respond_to_notification_sync", _raise_runtime_err
    )
    plsql_calls: list[dict[str, Any]] = []

    def _record_plsql(_sql: str, binds: dict[str, Any]) -> dict[str, Any]:
        plsql_calls.append(binds)
        return {"status": "SUCCESS"}

    monkeypatch.setattr(client, "execute_plsql", _record_plsql)
    res_plsql = client.respond_to_notification(
        nid=1001, action="REJECT", comment="Denied", user_name="JDOE"
    )
    assert res_plsql["status"] == "SUCCESS"
    assert res_plsql["action"] == "REJECT"
    assert plsql_calls[0]["result_val"] == "REJECTED"


def test_get_pending_notifications_validation_and_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify input validation and PL/SQL fallback for pending notifications."""
    client = EBSDatabaseClient(user="apps", password="pwd", dsn="db:1521/ebs")

    with pytest.raises(HTTPException) as exc_limit:
        client.get_pending_notifications(limit=0)
    assert exc_limit.value.status_code == 422

    with pytest.raises(HTTPException) as exc_amt:
        client.get_pending_notifications(max_amount=-10.0)
    assert exc_amt.value.status_code == 422

    with pytest.raises(HTTPException) as exc_type:
        client.get_pending_notifications(notification_type="INVALID_TYPE")
    assert exc_type.value.status_code == 422

    def _raise_rest_err(**_kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("ISG unavailable")

    monkeypatch.setattr(
        client.rest_client, "get_pending_notifications_sync", _raise_rest_err
    )
    monkeypatch.setattr(
        client,
        "execute_plsql",
        lambda _sql, _binds: {
            "out_json": (
                '[{"notification_id": 1001, "amount": 300.0}, '
                '{"notification_id": 1002, "amount": 5000.0}]'
            )
        },
    )
    items = client.get_pending_notifications(
        recipient="JDOE", notification_type="APEXP", max_amount=1000.0
    )
    assert len(items) == 1
    assert items[0]["notification_id"] == 1001
    assert ebs_db_client.ORACLE_DRIVER is not None


def test_get_connection_lazily_initializes_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify get_connection lazily initializes the pool when pool is None."""
    client = EBSDatabaseClient(user="apps", password="pwd", dsn="db:1521/ebs")
    cursor = _DummyCursor()
    conn = _DummyConnection(cursor)

    class _DummyPool:
        def __init__(self) -> None:
            self.acquired = 0
            self.released: list[Any] = []

        def acquire(self) -> _DummyConnection:
            self.acquired += 1
            return conn

        def release(self, released_conn: Any) -> None:
            self.released.append(released_conn)

    dummy_pool = _DummyPool()
    monkeypatch.setattr(
        ebs_db_client.ORACLE_DRIVER,
        "create_pool",
        lambda **kwargs: dummy_pool,
    )

    assert client.pool is None
    acquired_conn = client.get_connection()
    assert client.pool is dummy_pool
    assert acquired_conn is conn
    assert dummy_pool.acquired == 2

    client.release_connection(acquired_conn)
    assert dummy_pool.released == [conn, conn]


def test_initialize_pool_dpy_3015_thick_fallback_and_package_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify DPY-3015 triggers Thick Mode, verifier self-heal, and DDL."""
    client = EBSDatabaseClient(user="apps", password="pwd", dsn="db:1521/ebs")
    executed_sql: list[str] = []

    class _PkgCursor(_DummyCursor):
        def execute(self, sql: str, params: dict[str, Any]) -> None:
            executed_sql.append(sql)
            super().execute(sql, params)

        def fetchone(self) -> tuple[int]:
            return (0,)

    cursor = _PkgCursor()
    conn = _DummyConnection(cursor)

    class _FailingThinPool:
        def __init__(self) -> None:
            self.closed = False

        def acquire(self) -> _DummyConnection:
            raise RuntimeError(
                "DPY-3015: password verifier type 0x939 is not supported"
            )

        def close(self, force: bool = False) -> None:
            self.closed = force

    class _WorkingThickPool:
        def acquire(self) -> _DummyConnection:
            return conn

        def release(self, _conn: Any) -> None:
            pass

    thin_pool = _FailingThinPool()
    thick_pool = _WorkingThickPool()
    pools = [thin_pool, thick_pool]
    thick_inits: list[bool] = []

    monkeypatch.setattr(
        ebs_db_client.ORACLE_DRIVER,
        "create_pool",
        lambda **_kwargs: pools.pop(0),
    )
    monkeypatch.setattr(
        ebs_db_client.ORACLE_DRIVER,
        "init_oracle_client",
        lambda: thick_inits.append(True),
    )

    client.initialize_pool()
    assert thin_pool.closed is True
    assert client.pool is thick_pool
    assert thick_inits == [True]
    assert any("sec_case_sensitive_logon" in s for s in executed_sql)
    assert any(
        'ALTER USER apps IDENTIFIED BY "pwd"' in s for s in executed_sql
    )
    assert any(
        "CREATE OR REPLACE PACKAGE APPS.XX_EBS_WF_AGENT_PKG" in s
        for s in executed_sql
    )
    assert any(
        "CREATE OR REPLACE PACKAGE BODY APPS.XX_EBS_WF_AGENT_PKG" in s
        for s in executed_sql
    )
    assert conn.committed is True


def test_self_heal_verifier_skips_unsafe_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify verifier self-heal skips execution on unsafe user or password."""
    cursor = _DummyCursor()
    conn = _DummyConnection(cursor)

    class _Pool:
        def acquire(self) -> _DummyConnection:
            return conn

        def release(self, _conn: Any) -> None:
            pass

    monkeypatch.setattr(
        ebs_db_client.ORACLE_DRIVER, "init_oracle_client", lambda: None
    )

    call_count = 0

    def _create_pool(**_kwargs: Any) -> _Pool:
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 1:
            raise RuntimeError("DPY-3015: verifier 0x939 unsupported")
        return _Pool()

    monkeypatch.setattr(
        ebs_db_client.ORACLE_DRIVER, "create_pool", _create_pool
    )
    for user_val, pwd_val in (("apps;DROP", "pwd"), ("apps", 'pwd"inject')):
        client = EBSDatabaseClient(
            user=user_val, password=pwd_val, dsn="db:1521/ebs"
        )
        client.initialize_pool()
        assert len(cursor.executed) == 0


def test_ensure_agent_package_skips_ddl_when_already_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _ensure_agent_package skips DDL when package count is 2."""
    client = EBSDatabaseClient(user="apps", password="pwd", dsn="db:1521/ebs")
    executed_sql: list[str] = []

    class _ValidPkgCursor(_DummyCursor):
        def execute(self, sql: str, params: dict[str, Any]) -> None:
            executed_sql.append(sql)
            super().execute(sql, params)

        def fetchone(self) -> tuple[int]:
            return (2,)

    conn = _DummyConnection(_ValidPkgCursor())

    class _Pool:
        def acquire(self) -> _DummyConnection:
            return conn

        def release(self, _conn: Any) -> None:
            pass

    monkeypatch.setattr(
        ebs_db_client.ORACLE_DRIVER, "create_pool", lambda **_kwargs: _Pool()
    )
    client.initialize_pool()
    assert len(executed_sql) == 1
    assert "XX_EBS_WF_AGENT_PKG" in executed_sql[0]
    assert conn.committed is False


def test_get_connection_direct_connect_dpy_3015_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify direct connect() falls back to Thick Mode on DPY-3015."""
    client = EBSDatabaseClient(user="apps", password="pwd", dsn="db:1521/ebs")
    cursor = _DummyCursor()
    conn = _DummyConnection(cursor)
    connect_calls = 0
    thick_inits: list[bool] = []

    def _connect(**_kwargs: Any) -> _DummyConnection:
        nonlocal connect_calls
        connect_calls += 1
        if connect_calls == 1:
            raise RuntimeError("DPY-3015: verifier 0x939 is not supported")
        return conn

    monkeypatch.delattr(
        ebs_db_client.ORACLE_DRIVER, "create_pool", raising=False
    )
    monkeypatch.delattr(
        ebs_db_client.ORACLE_DRIVER, "SessionPool", raising=False
    )
    monkeypatch.setattr(ebs_db_client.ORACLE_DRIVER, "connect", _connect)
    monkeypatch.setattr(
        ebs_db_client.ORACLE_DRIVER,
        "init_oracle_client",
        lambda: thick_inits.append(True),
    )

    acquired = client.get_connection()
    assert acquired is conn
    assert connect_calls == 2
    assert thick_inits == [True]
    assert any("ALTER USER apps" in s for s, _ in cursor.executed)


def test_initialize_pool_non_verifier_error_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify non-DPY-3015 errors during pool initialization re-raise."""
    client = EBSDatabaseClient(user="apps", password="pwd", dsn="db:1521/ebs")

    def _fail_pool(**_kwargs: Any) -> Any:
        raise RuntimeError("ORA-12170: TNS:Connect timeout occurred")

    monkeypatch.setattr(ebs_db_client.ORACLE_DRIVER, "create_pool", _fail_pool)
    with pytest.raises(RuntimeError, match="ORA-12170"):
        client.initialize_pool()
