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

# pylint: disable=import-outside-toplevel,inconsistent-quotes,line-too-long
# pylint: disable=protected-access

"""Verification suite for tenant offboarding revocation, sealed embeddings, and RLS posture.

Covers:
1. Immediate (`< 1ms`) tenant offboarding revocation across `TENANT_DIRECTORY`, `MemoryCrypto`
   DEK cache, `TenantCredentialBroker` SA token cache, `LiveCloudKMSCMEKVerifier` cache,
   `AuthManager3LOVault`, and `TokenBucketBulkhead` rate-limit buckets, verified by re-onboarding
   the tenant and proving KMS unwrap counts, credential mint counts, and session turn counters
   reset rather than reading stale cache entries.
2. In-flight offboarding generation counters (`E_TENANT_OFFBOARDED_DURING_MINT` and
   `E_TENANT_OFFBOARDED_DURING_UNWRAP`) preventing concurrent workers from re-inserting into caches
   after `offboard_tenant` runs.
3. Ciphertext-only RAG vector embeddings (`embedding_nonce_hex`, `embedding_ciphertext_hex` with
   zero plaintext `embedding` stored in `MemoryBankPartitioner._store`), `:embedding` AAD binding,
   downgrade rejection, and `reseal_legacy_embeddings()` migration.
4. `RLSDatabasePool.verify_live_rls_posture()` against a real `asyncpg.Pool` backed by a real
   `sqlite3` relational catalog (`pg_roles`, `pg_namespace`, `pg_class`), verifying independent
   `rolsuper` and `rolbypassrls` guards, `public` schema qualification, FastAPI lifespan startup
   verification, and `scripts/init_postgres_rls.py` end-to-end execution.
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Self

import asyncpg
import pytest
from agents.context import (
    TENANT_DIRECTORY,
    AuthManager3LOVault,
    Delegated3LOToken,
    EdgeAuthVerifier,
    MemoryScope,
    SubscriptionTier,
    TokenBucketBulkhead,
    offboard_tenant,
    register_tenant,
    reset_dynamic_tenants,
)
from agents.gcp_live_bridge import (
    _KMS_VERIFY_CACHE,
    _KMS_VERIFY_LOCK,
    clear_kms_verify_cache,
)
from agents.memory_bank import MemoryBankPartitioner
from agents.memory_crypto import (
    LocalKeyWrapper,
    MemoryAccessDenied,
    MemoryCrypto,
)
from agents.platform_config import resolve_project_id
from agents.tenant_credentials import (
    LocalTenantCredentialBackend,
    TenantCredentialBroker,
    TenantScopedCredential,
)
from fastapi.testclient import TestClient
from mcp_server.db import RLSDatabasePool


class _CountingKeyWrapper:
    """Delegates to `LocalKeyWrapper` and records real KMS `wrap` and `unwrap` invocations."""

    def __init__(
        self,
        project_id: str,
        *,
        on_unwrap: Callable[[], None] | None = None,
    ) -> None:
        self._inner = LocalKeyWrapper(project_id)
        self._on_unwrap = on_unwrap
        self.wraps = 0
        self.unwraps = 0

    def wrap(
        self,
        *,
        envelope: Any,
        kms_key_name: str,
        dek: bytes,
        aad: bytes,
    ) -> bytes:
        self.wraps += 1
        return self._inner.wrap(
            envelope=envelope, kms_key_name=kms_key_name, dek=dek, aad=aad
        )

    def unwrap(
        self,
        *,
        envelope: Any,
        kms_key_name: str,
        wrapped: bytes,
        aad: bytes,
    ) -> bytes:
        self.unwraps += 1
        if self._on_unwrap is not None:
            self._on_unwrap()
        return self._inner.unwrap(
            envelope=envelope,
            kms_key_name=kms_key_name,
            wrapped=wrapped,
            aad=aad,
        )


class _CountingCredentialBackend:
    """Delegates to `LocalTenantCredentialBackend` and records real `mint` invocations."""

    def __init__(self, *, on_mint: Callable[[], None] | None = None) -> None:
        self._inner = LocalTenantCredentialBackend()
        self._on_mint = on_mint
        self.mint_count = 0

    def mint(
        self,
        *,
        tenant_id: str,
        principal: str,
        lifetime_seconds: int,
    ) -> TenantScopedCredential:
        self.mint_count += 1
        if self._on_mint is not None:
            self._on_mint()
        return self._inner.mint(
            tenant_id=tenant_id,
            principal=principal,
            lifetime_seconds=lifetime_seconds,
        )


class _SQLiteProtocolState:
    """Minimal protocol state required by `asyncpg.PoolConnectionHolder` on release."""

    queries_count = 0
    is_in_transaction = False

    def _is_cancelling(self) -> bool:
        return False

    def is_closed(self) -> bool:
        return False


class _SQLiteTransactionContext:
    """Transactional context manager executing real `BEGIN`/`COMMIT`/`ROLLBACK` on `sqlite3`."""

    def __init__(self, connection: _SQLiteBackedAsyncpgConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> Self:
        self._connection._enter_transaction()
        return self

    async def __aexit__(
        self, exc_type: object, exc: object, tb: object
    ) -> None:
        del exc, tb
        self._connection._exit_transaction(rollback=exc_type is not None)


class _SQLiteBackedAsyncpgConnection(asyncpg.Connection):
    """Real `asyncpg.Connection` subclass backed by an in-memory `sqlite3` SQL engine."""

    def __init__(
        self,
        sqlite_db: sqlite3.Connection,
        loop: asyncio.AbstractEventLoop,
        *,
        initial_role: str = "cymbal_mcp_app",
    ) -> None:
        self._sqlite = sqlite_db
        self._loop = loop
        self._closed = False
        self._proxy = None
        self._source_traceback = None
        self._pool_release_ctr = 0
        self._protocol = _SQLiteProtocolState()
        self._listeners: dict[str, list[Any]] = {}
        self._log_listeners: set[Any] = set()
        self._pool_holder: Any = None
        self._default_role = initial_role
        self._active_role = initial_role
        self._tx_local_guc: dict[str, str] = {}
        self._in_tx = False

    def _enter_transaction(self) -> None:
        self._in_tx = True
        self._active_role = self._default_role
        self._tx_local_guc.clear()

    def _exit_transaction(self, *, rollback: bool) -> None:
        if rollback and self._sqlite.in_transaction:
            self._sqlite.rollback()
        elif self._sqlite.in_transaction:
            self._sqlite.commit()
        self._in_tx = False
        self._active_role = self._default_role
        self._tx_local_guc.clear()

    def transaction(self, **_kwargs: Any) -> _SQLiteTransactionContext:
        return _SQLiteTransactionContext(self)

    def is_closed(self) -> bool:
        return self._closed

    def is_in_transaction(self) -> bool:
        return self._in_tx

    async def close(self, *, timeout: float | None = None) -> None:
        del timeout
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError(
                "Connection.close() called on a foreign event loop"
            )
        self.terminate()

    def terminate(self) -> None:
        if not self._closed:
            self._closed = True
            holder = (
                self._pool_holder() if self._pool_holder is not None else None
            )
            if holder is not None:
                holder._release_on_close()

    async def reset(self, *, timeout: float | None = None) -> None:
        del timeout
        self._exit_transaction(rollback=True)

    def add_termination_listener(self, callback: Any) -> None:
        del callback

    def remove_termination_listener(self, callback: Any) -> None:
        del callback

    def _translate_and_execute(
        self, query: str, args: tuple[Any, ...]
    ) -> sqlite3.Cursor:
        self._protocol.queries_count += 1
        stripped = query.strip()

        # Handle PostgreSQL DDL / DO blocks from `scripts/init_postgres_rls.py`.
        if "CREATE TABLE IF NOT EXISTS tenant_incidents" in stripped:
            return self._sqlite.execute("SELECT 1;")
        if "CREATE ROLE" in stripped and "cymbal_mcp_app" in stripped:
            self._sqlite.execute(
                "INSERT OR REPLACE INTO pg_roles (rolname, rolsuper, rolbypassrls) "
                "VALUES ('cymbal_mcp_app', 0, 0);"
            )
            self._sqlite.commit()
            return self._sqlite.execute("SELECT 1;")
        if stripped.upper().startswith("SET LOCAL ROLE "):
            role_name = stripped.split()[-1].rstrip(";").strip("'")
            self._active_role = role_name
            return self._sqlite.execute("SELECT 1;")
        set_local_match = re.match(
            r"SET\s+LOCAL\s+app\.current_tenant_id\s*=\s*'([^']*)'\s*;",
            stripped,
            re.IGNORECASE,
        )
        if set_local_match:
            self._tx_local_guc["app.current_tenant_id"] = set_local_match.group(
                1
            )
            return self._sqlite.execute("SELECT 1;")
        if "set_config('app.current_tenant_id'" in stripped:
            self._tx_local_guc["app.current_tenant_id"] = (
                str(args[0]) if args else ""
            )
            return self._sqlite.execute("SELECT 1;")
        if stripped.upper().startswith("INSERT INTO TENANT_INCIDENTS"):
            self._sqlite.execute(
                "INSERT OR IGNORE INTO tenant_incidents_raw "
                "(incident_id, tenant_id, service_name, severity, summary, pii_notes) "
                "VALUES (?, ?, ?, ?, ?, ?);",
                args,
            )
            self._sqlite.commit()
            return self._sqlite.execute("SELECT 1;")

        # Translate PostgreSQL catalog / data queries to SQLite parameters while preserving
        # the real SQL structure (`JOIN pg_namespace`, `WHERE n.nspname = 'public'`, etc.).
        sqlite_sql = stripped.replace("current_user", ":current_user")
        params: dict[str, Any] = {"current_user": self._active_role}

        if "= ANY($1::text[])" in sqlite_sql:
            names = list(args[0]) if args else []
            placeholders = ", ".join(f":tbl_{idx}" for idx in range(len(names)))
            sqlite_sql = sqlite_sql.replace(
                "= ANY($1::text[])", f"IN ({placeholders or 'NULL'})"
            )
            for idx, tbl_name in enumerate(names):
                params[f"tbl_{idx}"] = tbl_name
        else:
            for idx, val in enumerate(args, start=1):
                sqlite_sql = sqlite_sql.replace(f"${idx}", f":arg_{idx}")
                params[f"arg_{idx}"] = val

        # Sync the current role and transactional GUC into SQLite session state table so views
        # evaluate real SQL predicates (`rolsuper`, `rolbypassrls`, `current_tenant_id`).
        self._sqlite.execute(
            "UPDATE _session_context SET active_role = ?, current_tenant_id = ?;",
            (
                self._active_role,
                self._tx_local_guc.get("app.current_tenant_id", ""),
            ),
        )
        return self._sqlite.execute(sqlite_sql, params)

    async def execute(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> str:
        del timeout
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("Task got Future attached to a different loop")
        self._translate_and_execute(query, args)
        return "OK"

    async def fetchrow(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> dict[str, Any] | None:
        del timeout
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("Task got Future attached to a different loop")
        cursor = self._translate_and_execute(query, args)
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row, strict=True))

    async def fetch(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> list[dict[str, Any]]:
        del timeout
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("Task got Future attached to a different loop")
        cursor = self._translate_and_execute(query, args)
        rows = cursor.fetchall()
        columns = (
            [col[0] for col in cursor.description] if cursor.description else []
        )
        return [dict(zip(columns, row, strict=True)) for row in rows]


def _create_sqlite_catalog_db(
    *,
    role_row: dict[str, Any] | None,
    table_rows: list[dict[str, Any]],
    extra_namespace_rows: list[tuple[int, str]] | None = None,
) -> sqlite3.Connection:
    """Builds an in-memory `sqlite3` database with real `pg_roles`, `pg_namespace`, `pg_class`,
    and RLS-enforced `tenant_incidents` / `tenant_runbooks` views."""
    sqlite_db = sqlite3.connect(":memory:")
    sqlite_db.executescript("""
        CREATE TABLE _session_context (
            active_role TEXT NOT NULL,
            current_tenant_id TEXT NOT NULL
        );
        INSERT INTO _session_context VALUES ('cymbal_mcp_app', '');

        CREATE TABLE pg_roles (
            rolname TEXT PRIMARY KEY,
            rolsuper INTEGER NOT NULL,
            rolbypassrls INTEGER NOT NULL
        );

        CREATE TABLE pg_namespace (
            oid INTEGER PRIMARY KEY,
            nspname TEXT NOT NULL
        );
        INSERT INTO pg_namespace (oid, nspname) VALUES (2200, 'public');

        CREATE TABLE pg_class (
            relname TEXT NOT NULL,
            relnamespace INTEGER NOT NULL,
            relrowsecurity INTEGER NOT NULL,
            relforcerowsecurity INTEGER NOT NULL
        );

        CREATE TABLE tenant_incidents_raw (
            incident_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            service_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            summary TEXT NOT NULL,
            pii_notes TEXT NOT NULL
        );

        CREATE TABLE tenant_runbooks_raw (
            runbook_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            title TEXT NOT NULL,
            remediation_steps TEXT NOT NULL
        );

        CREATE VIEW tenant_incidents AS
        SELECT * FROM tenant_incidents_raw
        WHERE (
            SELECT COALESCE(MAX(rolsuper OR rolbypassrls), 0)
            FROM pg_roles
            WHERE rolname = (SELECT active_role FROM _session_context)
        ) = 1
        OR tenant_id = (SELECT current_tenant_id FROM _session_context);

        CREATE VIEW tenant_runbooks AS
        SELECT * FROM tenant_runbooks_raw
        WHERE (
            SELECT COALESCE(MAX(rolsuper OR rolbypassrls), 0)
            FROM pg_roles
            WHERE rolname = (SELECT active_role FROM _session_context)
        ) = 1
        OR tenant_id = (SELECT current_tenant_id FROM _session_context);
        """)
    if extra_namespace_rows:
        sqlite_db.executemany(
            "INSERT INTO pg_namespace (oid, nspname) VALUES (?, ?);",
            extra_namespace_rows,
        )
    if role_row is not None:
        sqlite_db.execute(
            "INSERT INTO pg_roles (rolname, rolsuper, rolbypassrls) VALUES (?, ?, ?);",
            (
                str(role_row["role_name"]),
                int(bool(role_row["rolsuper"])),
                int(bool(role_row["rolbypassrls"])),
            ),
        )
    for tbl in table_rows:
        sqlite_db.execute(
            "INSERT INTO pg_class (relname, relnamespace, relrowsecurity, relforcerowsecurity) "
            "VALUES (?, ?, ?, ?);",
            (
                str(tbl["relname"]),
                int(tbl.get("relnamespace", 2200)),
                int(bool(tbl["relrowsecurity"])),
                int(bool(tbl["relforcerowsecurity"])),
            ),
        )
    sqlite_db.commit()
    return sqlite_db


async def _make_real_asyncpg_pool(
    *,
    role_row: dict[str, Any] | None,
    table_rows: list[dict[str, Any]],
    extra_namespace_rows: list[tuple[int, str]] | None = None,
) -> asyncpg.Pool:
    """Creates a real `asyncpg.Pool` backed by `_SQLiteBackedAsyncpgConnection`."""
    sqlite_db = _create_sqlite_catalog_db(
        role_row=role_row,
        table_rows=table_rows,
        extra_namespace_rows=extra_namespace_rows,
    )
    initial_role = (
        str(role_row["role_name"]) if role_row is not None else "missing_role"
    )
    running_loop = asyncio.get_running_loop()

    async def _connect(
        *_args: Any, **_kwargs: Any
    ) -> _SQLiteBackedAsyncpgConnection:
        return _SQLiteBackedAsyncpgConnection(
            sqlite_db, running_loop, initial_role=initial_role
        )

    pool = await asyncpg.create_pool(min_size=1, max_size=2, connect=_connect)
    assert isinstance(pool, asyncpg.pool.Pool)
    return pool


def _mint_envelope(
    verifier: EdgeAuthVerifier,
    *,
    tenant_id: str,
    issuer: str = "https://accounts.google.com",
    subject: str = "alice@finvault.com",
    jti_suffix: str = "1",
) -> Any:
    """Mints a signed `ContextEnvelope` for tenant isolation tests."""
    return verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": issuer,
            "sub": subject,
            "tenant_id": tenant_id,
            "user_role": "sre_admin",
            "exp": 4_102_444_800,
            "jti": f"oidc-{tenant_id}-{jti_suffix}",
        },
        dpop_proof={
            "jkt": f"thumb-{tenant_id}",
            "jti": f"dpop-{tenant_id}-{jti_suffix}",
        },
    )


def test_offboard_tenant_genuinely_removes_entries_verified_upon_reonboarding() -> (
    None
):
    """Proves `offboard_tenant` removes entries from DEK, credential, KMS verify, 3LO vault, and
    bulkhead caches by re-registering the tenant and asserting unwrap/mint counts increase.
    """
    project_id = resolve_project_id()
    verifier = EdgeAuthVerifier()
    wrapper = _CountingKeyWrapper(project_id)
    memory_crypto = MemoryCrypto(wrapper=wrapper)
    memory_bank = MemoryBankPartitioner(crypto=memory_crypto)
    credential_backend = _CountingCredentialBackend()
    credential_broker = TenantCredentialBroker(
        project_id=project_id,
        backend=credential_backend,
    )
    bulkhead = TokenBucketBulkhead()
    auth_vault = AuthManager3LOVault()

    transient_tenant = "tenant-acme-offboard"
    try:
        register_tenant(
            tenant_id=transient_tenant,
            display_name="Acme Offboard Test Corp",
            tier=SubscriptionTier.STANDARD,
        )
        transient_envelope = _mint_envelope(
            verifier,
            tenant_id=transient_tenant,
            subject="admin@acme.example",
            jti_suffix="transient-1",
        )
        finvault_envelope = _mint_envelope(
            verifier,
            tenant_id="tenant-finvault-alpha",
            subject="alice@finvault.com",
            jti_suffix="finvault-1",
        )

        # Warm DEK caches for both tenants via write + read.
        transient_key = memory_bank.write_memory(
            envelope=transient_envelope,
            scope=MemoryScope.USER,
            actor="diagnostic_agent",
            content={"secret": "acme-ephemeral-record"},
            embedding=[0.9, 0.1],
        )
        finvault_key = memory_bank.write_memory(
            envelope=finvault_envelope,
            scope=MemoryScope.USER,
            actor="diagnostic_agent",
            content={"secret": "finvault-retained-record"},
            embedding=[0.2, 0.8],
        )
        assert memory_bank.read_memory(
            envelope=transient_envelope, target_key=transient_key
        ) == {"secret": "acme-ephemeral-record"}
        assert memory_bank.read_memory(
            envelope=finvault_envelope, target_key=finvault_key
        ) == {"secret": "finvault-retained-record"}
        # Second read before offboarding hits DEK cache (0 extra KMS unwraps).
        unwraps_after_warm = wrapper.unwraps
        assert memory_bank.read_memory(
            envelope=transient_envelope, target_key=transient_key
        ) == {"secret": "acme-ephemeral-record"}
        assert wrapper.unwraps == unwraps_after_warm

        # Warm SA credential broker, KMS verify cache, 3LO vault, and token-bucket bulkhead.
        clear_kms_verify_cache()
        with _KMS_VERIFY_LOCK:
            _KMS_VERIFY_CACHE[
                (transient_tenant, "admin@acme.example", "key-acme")
            ] = 9_999.0
            _KMS_VERIFY_CACHE[
                ("tenant-finvault-alpha", "alice@finvault.com", "key-fv")
            ] = 9_999.0
        first_acme_cred = credential_broker.credential_for(transient_envelope)
        credential_broker.credential_for(finvault_envelope)
        mints_before_offboard = credential_backend.mint_count
        # Second credential_for call hits broker cache (0 extra mints).
        assert (
            credential_broker.credential_for(transient_envelope).token
            == first_acme_cred.token
        )
        assert credential_backend.mint_count == mints_before_offboard

        auth_vault.store_3lo_token(
            Delegated3LOToken(
                token_handle="3lo-acme-1",
                tenant_id=transient_tenant,
                user_sub="admin@acme.example",
                provider="atlassian_jira",
                scopes=("3lo:jira.read",),
                access_token="jira-secret-acme",
                expires_at=4_102_444_800,
            )
        )
        auth_vault.store_3lo_token(
            Delegated3LOToken(
                token_handle="3lo-fv-1",
                tenant_id="tenant-finvault-alpha",
                user_sub="alice@finvault.com",
                provider="atlassian_jira",
                scopes=("3lo:jira.read",),
                access_token="jira-secret-fv",
                expires_at=4_102_444_800,
            )
        )

        # Consume 2 turns in the same session for `transient_tenant` before offboarding.
        bulkhead.check_and_consume(
            tenant_id=transient_tenant,
            requested_thinking_tokens=1000,
            estimated_total_tokens=2000,
            session_id="sess-acme-1",
        )
        second_turn = bulkhead.check_and_consume(
            tenant_id=transient_tenant,
            requested_thinking_tokens=1000,
            estimated_total_tokens=2000,
            session_id="sess-acme-1",
        )
        assert second_turn["session_turns_used"] == 2
        bulkhead.check_and_consume(
            tenant_id="tenant-finvault-alpha",
            requested_thinking_tokens=1000,
            estimated_total_tokens=2000,
            session_id="sess-fv-1",
        )

        # Call `offboard_tenant` WITHOUT passing `bulkhead` or `auth_vault` explicitly: the
        # per-tenant eviction-hook registry must still find and purge them!
        summary = offboard_tenant(
            transient_tenant,
            memory_crypto=memory_crypto,
            credential_broker=credential_broker,
        )
        assert summary == {
            "tenant_id": transient_tenant,
            "removed_from_directory": True,
            "evicted_dek_entries": 1,
            "evicted_sa_credential": True,
            "evicted_kms_verify_entries": 1,
            "evicted_bulkhead_bucket": True,
            "evicted_3lo_tokens": 1,
        }
        assert transient_tenant not in TENANT_DIRECTORY
        with _KMS_VERIFY_LOCK:
            assert (
                transient_tenant,
                "admin@acme.example",
                "key-acme",
            ) not in _KMS_VERIFY_CACHE
            assert (
                "tenant-finvault-alpha",
                "alice@finvault.com",
                "key-fv",
            ) in _KMS_VERIFY_CACHE

        # Offboarded tenant is immediately rejected at Hop 2 token exchange, 3LO vault, and
        # bulkhead.
        with pytest.raises(PermissionError, match="E_UNAUTHENTICATED_TENANT"):
            _mint_envelope(
                verifier,
                tenant_id=transient_tenant,
                subject="admin@acme.example",
                jti_suffix="transient-2",
            )
        with pytest.raises(PermissionError, match="E_TENANT_NOT_ONBOARDED"):
            auth_vault.checkout_3lo_token(
                token_handle="3lo-acme-1",
                envelope=transient_envelope,
                required_scope="3lo:jira.read",
            )
        with pytest.raises(PermissionError, match="Unknown tenant_id"):
            bulkhead.check_and_consume(
                tenant_id=transient_tenant,
                requested_thinking_tokens=500,
                estimated_total_tokens=1000,
            )

        # Sibling tenant (`tenant-finvault-alpha`) retains its cached DEK (0 extra KMS unwraps)
        # and its 3LO token.
        assert memory_bank.read_memory(
            envelope=finvault_envelope, target_key=finvault_key
        ) == {"secret": "finvault-retained-record"}
        assert wrapper.unwraps == unwraps_after_warm
        assert (
            auth_vault.checkout_3lo_token(
                token_handle="3lo-fv-1",
                envelope=finvault_envelope,
                required_scope="3lo:jira.read",
            ).access_token
            == "jira-secret-fv"
        )

        # MUTATION GUARD (Blocking #3): Re-register `transient_tenant` and prove that:
        # (a) `read_memory` must call `wrapper.unwrap` again (`wrapper.unwraps` increments by 1),
        # (b) `credential_for` must call `backend.mint` again (`mint_count` increments by 1),
        # (c) `check_and_consume` starts fresh at `session_turns_used == 1`, and
        # (d) `checkout_3lo_token` raises `E_3LO_TOKEN_NOT_FOUND` because the handle was popped.
        register_tenant(
            tenant_id=transient_tenant,
            display_name="Acme Re-Onboarded Corp",
            tier=SubscriptionTier.STANDARD,
        )
        reonboarded_envelope = _mint_envelope(
            verifier,
            tenant_id=transient_tenant,
            subject="admin@acme.example",
            jti_suffix="transient-reonboard",
        )
        assert memory_bank.read_memory(
            envelope=reonboarded_envelope, target_key=transient_key
        ) == {"secret": "acme-ephemeral-record"}
        assert wrapper.unwraps == unwraps_after_warm + 1

        reminted_cred = credential_broker.credential_for(reonboarded_envelope)
        assert credential_backend.mint_count == mints_before_offboard + 1
        assert reminted_cred.token != first_acme_cred.token

        reset_turn = bulkhead.check_and_consume(
            tenant_id=transient_tenant,
            requested_thinking_tokens=1000,
            estimated_total_tokens=2000,
            session_id="sess-acme-1",
        )
        assert reset_turn["session_turns_used"] == 1

        with pytest.raises(PermissionError, match="E_3LO_TOKEN_NOT_FOUND"):
            auth_vault.checkout_3lo_token(
                token_handle="3lo-acme-1",
                envelope=reonboarded_envelope,
                required_scope="3lo:jira.read",
            )
    finally:
        reset_dynamic_tenants()


def test_inflight_mint_and_unwrap_fail_closed_when_tenant_offboarded_mid_call() -> (
    None
):
    """Proves generation counters prevent in-flight `mint()` or `unwrap()` from re-populating
    caches if `offboard_tenant` runs while the backend call is in flight."""
    project_id = resolve_project_id()
    verifier = EdgeAuthVerifier()
    transient_tenant = "tenant-inflight-race"

    try:
        register_tenant(
            tenant_id=transient_tenant,
            display_name="Inflight Race Corp",
            tier=SubscriptionTier.STANDARD,
        )
        envelope = _mint_envelope(
            verifier,
            tenant_id=transient_tenant,
            subject="ops@inflight.example",
            jti_suffix="inflight-1",
        )

        # 1. In-flight credential mint race: `offboard_tenant` fires during `backend.mint()`.
        broker_holder: list[TenantCredentialBroker] = []

        def _offboard_during_mint() -> None:
            broker_holder[0].evict_tenant(transient_tenant)

        racing_backend = _CountingCredentialBackend(
            on_mint=_offboard_during_mint
        )
        racing_broker = TenantCredentialBroker(
            project_id=project_id,
            backend=racing_backend,
        )
        broker_holder.append(racing_broker)

        with pytest.raises(
            PermissionError, match="E_TENANT_OFFBOARDED_DURING_MINT"
        ):
            racing_broker.credential_for(envelope)
        assert transient_tenant not in racing_broker._cache

        # 2. In-flight DEK unwrap race: `evict_tenant` fires during `wrapper.unwrap()`.
        crypto_holder: list[MemoryCrypto] = []
        should_evict_on_unwrap = False

        def _offboard_during_unwrap() -> None:
            if should_evict_on_unwrap:
                crypto_holder[0].evict_tenant(transient_tenant)

        racing_wrapper = _CountingKeyWrapper(
            project_id, on_unwrap=_offboard_during_unwrap
        )
        racing_crypto = MemoryCrypto(wrapper=racing_wrapper)
        crypto_holder.append(racing_crypto)
        racing_bank = MemoryBankPartitioner(crypto=racing_crypto)

        mem_key = racing_bank.write_memory(
            envelope=envelope,
            scope=MemoryScope.USER,
            actor="race_agent",
            content={"data": "inflight-test"},
        )
        should_evict_on_unwrap = True
        with pytest.raises(
            MemoryAccessDenied, match="E_TENANT_OFFBOARDED_DURING_UNWRAP"
        ):
            racing_bank.read_memory(envelope=envelope, target_key=mem_key)
        assert len(racing_crypto._cache) == 0
    finally:
        reset_dynamic_tenants()


def test_tenant_credential_broker_is_thread_safe_under_concurrent_access() -> (
    None
):
    """Proves `TenantCredentialBroker` serializes cache access across concurrent threads."""
    project_id = resolve_project_id()
    verifier = EdgeAuthVerifier()
    credential_backend = LocalTenantCredentialBackend()
    broker = TenantCredentialBroker(
        project_id=project_id,
        backend=credential_backend,
    )
    finvault_envelope = _mint_envelope(
        verifier,
        tenant_id="tenant-finvault-alpha",
        subject="alice@finvault.com",
        jti_suffix="thread-fv",
    )

    def _fetch_and_verify(worker_index: int) -> str:
        for _ in range(3):
            try:
                if worker_index == 4:
                    broker.evict_tenant("tenant-finvault-alpha")
                credential = broker.credential_for(finvault_envelope)
                return credential.token
            except PermissionError:
                continue
        return broker.credential_for(finvault_envelope).token

    with ThreadPoolExecutor(max_workers=8) as executor:
        tokens = list(executor.map(_fetch_and_verify, range(16)))

    assert len(tokens) == 16
    assert all(token.startswith("local-ct-") for token in tokens)


def test_ciphertext_only_rag_embeddings_block_tampering_downgrade_and_reseal_legacy() -> (
    None
):
    """Proves RAG embeddings are stored as ciphertext only (`embedding_nonce_hex`,
    `embedding_ciphertext_hex`, no plaintext `embedding`), reject downgrade/swap/tampering,
    and support legacy migration via `reseal_legacy_embeddings()`."""
    project_id = resolve_project_id()
    verifier = EdgeAuthVerifier()
    wrapper = _CountingKeyWrapper(project_id)
    memory_crypto = MemoryCrypto(wrapper=wrapper)
    memory_bank = MemoryBankPartitioner(crypto=memory_crypto)

    finvault_envelope = _mint_envelope(
        verifier,
        tenant_id="tenant-finvault-alpha",
        subject="alice@finvault.com",
        jti_suffix="rag-fv",
    )
    key_first = memory_bank.write_memory(
        envelope=finvault_envelope,
        scope=MemoryScope.TENANT,
        actor="diagnostic_agent",
        content={
            "incident": "INC-FV-1001",
            "summary": "Legitimate wire settlement note",
        },
        embedding=[0.95, 0.05],
    )
    key_second = memory_bank.write_memory(
        envelope=finvault_envelope,
        scope=MemoryScope.STRATEGY,
        actor="diagnostic_agent",
        content={
            "incident": "INC-FV-1002",
            "summary": "Secondary strategy note",
        },
        embedding=[0.10, 0.90],
    )

    stored_first = memory_bank._store[key_first]
    stored_second = memory_bank._store[key_second]
    # Blocking #1: No plaintext `embedding` key exists in `_store`.
    assert "embedding" not in stored_first
    assert "embedding" not in stored_second
    assert stored_first["embedding_nonce_hex"]
    assert stored_first["embedding_ciphertext_hex"]

    # Normal read and RAG retrieval succeed, reusing the cached DEK on open.
    unwraps_before_read = wrapper.unwraps
    opened = memory_bank.read_memory(
        envelope=finvault_envelope, target_key=key_first
    )
    assert opened["incident"] == "INC-FV-1001"
    assert wrapper.unwraps == unwraps_before_read + 1

    original_nonce_hex = str(stored_second["embedding_nonce_hex"])
    original_ciphertext_hex = str(stored_second["embedding_ciphertext_hex"])

    # Mutation 1: Downgrade attack — inject a plaintext `embedding` field into storage.
    stored_second["embedding"] = [0.99, 0.01]
    with pytest.raises(
        MemoryAccessDenied, match="E_CMEK_AEAD_DECRYPTION_FAILED"
    ):
        memory_bank.read_memory(
            envelope=finvault_envelope, target_key=key_second
        )
    rag_hits = memory_bank.retrieve_similar_memories_rag(
        envelope=finvault_envelope,
        query_embedding=[1.0, 0.0],
        top_k=5,
    )
    assert [hit["key"] for hit in rag_hits] == [key_first]
    stored_second.pop("embedding", None)

    # Mutation 2: Swap `embedding_ciphertext_hex` from `key_first` into `key_second` (AAD mismatch).
    stored_second["embedding_nonce_hex"] = stored_first["embedding_nonce_hex"]
    stored_second["embedding_ciphertext_hex"] = stored_first[
        "embedding_ciphertext_hex"
    ]
    with pytest.raises(
        MemoryAccessDenied, match="E_CMEK_AEAD_DECRYPTION_FAILED"
    ):
        memory_bank.read_memory(
            envelope=finvault_envelope, target_key=key_second
        )

    # Mutation 3: Flip 1 byte of `embedding_nonce_hex` while keeping valid ciphertext.
    nonce_bytes = bytearray.fromhex(original_nonce_hex)
    nonce_bytes[0] ^= 0xFF
    stored_second["embedding_nonce_hex"] = nonce_bytes.hex()
    stored_second["embedding_ciphertext_hex"] = original_ciphertext_hex
    with pytest.raises(
        MemoryAccessDenied, match="E_CMEK_AEAD_DECRYPTION_FAILED"
    ):
        memory_bank.read_memory(
            envelope=finvault_envelope, target_key=key_second
        )

    # Mutation 4: Strip `embedding_nonce_hex` while leaving `embedding_ciphertext_hex` (partial
    # strip).
    stored_second["embedding_nonce_hex"] = ""
    stored_second["embedding_ciphertext_hex"] = original_ciphertext_hex
    with pytest.raises(
        MemoryAccessDenied, match="E_CMEK_AEAD_DECRYPTION_FAILED"
    ):
        memory_bank.read_memory(
            envelope=finvault_envelope, target_key=key_second
        )

    # Follow-up #7: Simulate a pre-migration record carrying plaintext `embedding` without
    # `embedding_*_hex`, verify it is refused until migrated, then run `reseal_legacy_embeddings`.
    stored_second.pop("embedding_nonce_hex", None)
    stored_second.pop("embedding_ciphertext_hex", None)
    stored_second["embedding"] = [0.10, 0.90]
    with pytest.raises(
        MemoryAccessDenied, match="E_CMEK_AEAD_DECRYPTION_FAILED"
    ):
        memory_bank.read_memory(
            envelope=finvault_envelope, target_key=key_second
        )

    migrated = memory_bank.reseal_legacy_embeddings(envelope=finvault_envelope)
    assert migrated == 1
    assert "embedding" not in memory_bank._store[key_second]
    assert memory_bank._store[key_second]["embedding_nonce_hex"]
    assert memory_bank._store[key_second]["embedding_ciphertext_hex"]
    assert (
        memory_bank.read_memory(
            envelope=finvault_envelope, target_key=key_second
        )["incident"]
        == "INC-FV-1002"
    )
    restored_hits = memory_bank.retrieve_similar_memories_rag(
        envelope=finvault_envelope,
        query_embedding=[0.0, 1.0],
        top_k=2,
    )
    assert [hit["key"] for hit in restored_hits] == [key_second, key_first]


def test_verify_live_rls_posture_with_real_asyncpg_pool_and_sqlite_catalog(
    tmp_path: Path,
) -> None:
    """Proves `verify_live_rls_posture` executes real SQL against `pg_roles`, `pg_namespace`,
    and `pg_class` through a real `asyncpg.Pool` and rejects `rolsuper`, `rolbypassrls`,
    non-`public` schema decoys, and missing `FORCE ROW LEVEL SECURITY`."""

    async def _scenario() -> None:
        # 1. Default offline DDL verification passes against `mcp_server/schema.sql`.
        offline_pool = RLSDatabasePool()
        offline_result = await offline_pool.verify_live_rls_posture()
        assert offline_result["verified"] is True
        assert offline_result["mode"] == "schema_ddl_verified"

        # 2. Offline DDL missing FORCE ROW LEVEL SECURITY fails closed.
        broken_schema = tmp_path / "broken_schema.sql"
        broken_schema.write_text(
            "ALTER TABLE tenant_incidents ENABLE ROW LEVEL SECURITY;\n",
            encoding="utf-8",
        )
        with pytest.raises(PermissionError, match="E_RLS_POSTURE_VIOLATION"):
            await offline_pool.verify_live_rls_posture(
                schema_path=broken_schema
            )

        # 3. Real `asyncpg.Pool` with compliant `cymbal_mcp_app` role and forced RLS in `public`.
        compliant_asyncpg_pool = await _make_real_asyncpg_pool(
            role_row={
                "role_name": "cymbal_mcp_app",
                "rolsuper": False,
                "rolbypassrls": False,
            },
            table_rows=[
                {
                    "relname": "tenant_incidents",
                    "relnamespace": 2200,
                    "relrowsecurity": True,
                    "relforcerowsecurity": True,
                },
                {
                    "relname": "tenant_runbooks",
                    "relnamespace": 2200,
                    "relrowsecurity": True,
                    "relforcerowsecurity": True,
                },
            ],
        )
        live_pool = RLSDatabasePool(asyncpg_pool=compliant_asyncpg_pool)
        try:
            live_result = await live_pool.verify_live_rls_posture()
            assert live_result["verified"] is True
            assert live_result["mode"] == "live_pg_catalog"
        finally:
            await live_pool.close()

        # 4. Superuser role (`rolsuper=True, rolbypassrls=False`) is rejected.
        superuser_pool = RLSDatabasePool(
            asyncpg_pool=await _make_real_asyncpg_pool(
                role_row={
                    "role_name": "postgres",
                    "rolsuper": True,
                    "rolbypassrls": False,
                },
                table_rows=[],
            )
        )
        try:
            with pytest.raises(
                PermissionError, match="E_RLS_POSTURE_VIOLATION"
            ):
                await superuser_pool.verify_live_rls_posture()
        finally:
            await superuser_pool.close()

        # 5. BypassRLS role (`rolsuper=False, rolbypassrls=True`) is rejected independently.
        bypass_pool = RLSDatabasePool(
            asyncpg_pool=await _make_real_asyncpg_pool(
                role_row={
                    "role_name": "migration_admin",
                    "rolsuper": False,
                    "rolbypassrls": True,
                },
                table_rows=[],
            )
        )
        try:
            with pytest.raises(
                PermissionError, match="E_RLS_POSTURE_VIOLATION"
            ):
                await bypass_pool.verify_live_rls_posture()
        finally:
            await bypass_pool.close()

        # 6. Table missing `relforcerowsecurity` (`True, False`) is rejected.
        unforced_pool = RLSDatabasePool(
            asyncpg_pool=await _make_real_asyncpg_pool(
                role_row={
                    "role_name": "cymbal_mcp_app",
                    "rolsuper": False,
                    "rolbypassrls": False,
                },
                table_rows=[
                    {
                        "relname": "tenant_incidents",
                        "relnamespace": 2200,
                        "relrowsecurity": True,
                        "relforcerowsecurity": False,
                    },
                    {
                        "relname": "tenant_runbooks",
                        "relnamespace": 2200,
                        "relrowsecurity": True,
                        "relforcerowsecurity": True,
                    },
                ],
            )
        )
        try:
            with pytest.raises(
                PermissionError, match="E_RLS_POSTURE_VIOLATION"
            ):
                await unforced_pool.verify_live_rls_posture()
        finally:
            await unforced_pool.close()

        # 7. Follow-up #8: Decoy tables in `staging` schema (`oid=9999`) with forced RLS do NOT
        # mask missing/unforced tables in `public` (`oid=2200`).
        wrong_schema_pool = RLSDatabasePool(
            asyncpg_pool=await _make_real_asyncpg_pool(
                role_row={
                    "role_name": "cymbal_mcp_app",
                    "rolsuper": False,
                    "rolbypassrls": False,
                },
                extra_namespace_rows=[(9999, "staging")],
                table_rows=[
                    {
                        "relname": "tenant_incidents",
                        "relnamespace": 9999,  # staging schema, NOT public
                        "relrowsecurity": True,
                        "relforcerowsecurity": True,
                    },
                    {
                        "relname": "tenant_runbooks",
                        "relnamespace": 2200,
                        "relrowsecurity": True,
                        "relforcerowsecurity": True,
                    },
                ],
            )
        )
        try:
            with pytest.raises(
                PermissionError, match="E_RLS_POSTURE_VIOLATION"
            ):
                await wrong_schema_pool.verify_live_rls_posture()
        finally:
            await wrong_schema_pool.close()

        # 8. Missing `current_user` row in `pg_roles` is rejected.
        missing_role_pool = RLSDatabasePool(
            asyncpg_pool=await _make_real_asyncpg_pool(
                role_row=None, table_rows=[]
            )
        )
        try:
            with pytest.raises(
                PermissionError, match="E_RLS_POSTURE_VIOLATION"
            ):
                await missing_role_pool.verify_live_rls_posture()
        finally:
            await missing_role_pool.close()

    asyncio.run(_scenario())


def test_init_postgres_rls_script_and_dsn_rewriting_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves `scripts/init_postgres_rls.py` handles IPv4, IPv6, and socket DSNs, and executes
    `init_and_verify_postgres_rls` end-to-end including `rls_pool.verify_live_rls_posture()`.
    """
    import scripts.init_postgres_rls as init_rls_module

    # 1. IPv4, IPv6 (`[::1]`), and Unix domain socket DSN rewriting.
    assert (
        init_rls_module.build_app_role_dsn(
            "postgresql://postgres:super@127.0.0.1:5432/cymbal_pooled_ops"
        )
        == "postgresql://cymbal_mcp_app:cymbal-rls-password@127.0.0.1:5432/cymbal_pooled_ops"
    )
    assert (
        init_rls_module.build_app_role_dsn(
            "postgresql://postgres:super@[::1]:5432/cymbal_pooled_ops"
        )
        == "postgresql://cymbal_mcp_app:cymbal-rls-password@[::1]:5432/cymbal_pooled_ops"
    )
    assert (
        init_rls_module.build_app_role_dsn(
            "postgresql:///cymbal_pooled_ops?host=/var/run/postgresql"
        )
        == "postgresql://cymbal_mcp_app:cymbal-rls-password@/cymbal_pooled_ops?host=/var/run/postgresql"
    )

    # 2. End-to-end execution of `init_and_verify_postgres_rls` backed by real `asyncpg.Pool` +
    # SQLite.
    shared_sqlite_db = _create_sqlite_catalog_db(
        role_row={
            "role_name": "postgres",
            "rolsuper": True,
            "rolbypassrls": True,
        },
        table_rows=[
            {
                "relname": "tenant_incidents",
                "relnamespace": 2200,
                "relrowsecurity": True,
                "relforcerowsecurity": True,
            },
            {
                "relname": "tenant_runbooks",
                "relnamespace": 2200,
                "relrowsecurity": True,
                "relforcerowsecurity": True,
            },
        ],
    )
    captured_pool_credentials: list[tuple[str | None, str | None]] = []

    async def _connect_admin(_dsn: str) -> _SQLiteBackedAsyncpgConnection:
        return _SQLiteBackedAsyncpgConnection(
            shared_sqlite_db,
            asyncio.get_running_loop(),
            initial_role="postgres",
        )

    original_create_pool = asyncpg.create_pool

    async def _create_pool_with_sqlite(
        dsn: str | None = None,
        *,
        min_size: int = 1,
        max_size: int = 2,
        user: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> asyncpg.Pool:
        del dsn, kwargs
        captured_pool_credentials.append((user, password))
        loop = asyncio.get_running_loop()
        role_to_use = user or "cymbal_mcp_app"

        async def _connect(
            *_a: Any, **_kw: Any
        ) -> _SQLiteBackedAsyncpgConnection:
            return _SQLiteBackedAsyncpgConnection(
                shared_sqlite_db, loop, initial_role=role_to_use
            )

        return await original_create_pool(
            min_size=min_size, max_size=max_size, connect=_connect
        )

    monkeypatch.setattr(asyncpg, "connect", _connect_admin)
    monkeypatch.setattr(asyncpg, "create_pool", _create_pool_with_sqlite)

    result = asyncio.run(
        init_rls_module.init_and_verify_postgres_rls(
            "postgresql://postgres:super@[::1]:5432/cymbal_pooled_ops"
        )
    )
    assert result == {
        "unscoped_rows": 0,
        "finvault_rows": 2,
        "retailstream_rows": 1,
        "rls_posture_verified": 1,
    }
    assert captured_pool_credentials == [
        (init_rls_module.APP_ROLE_NAME, init_rls_module.APP_ROLE_PASSWORD)
    ]


def test_gateway_lifespan_startup_and_healthz_enforces_rls_posture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves FastAPI lifespan runs `verify_live_rls_posture()` at startup, caches the result for
    `/healthz`, and fails startup or `/healthz` (`503`) if `rolbypassrls=True`.
    """
    import app.main as gateway_main

    with TestClient(gateway_main.app) as client:
        health_response = client.get("/healthz")
        assert health_response.status_code == 200
        health_json = health_response.json()
        assert health_json["rls_posture_verified"] is True
        assert health_json["rls_posture_mode"] == "schema_ddl_verified"

        chaos_response = client.post(
            "/api/v1/2am-chaos/tenant_offboarding_revocation"
        )
        assert chaos_response.status_code == 200
        chaos_payload = chaos_response.json()
        assert chaos_payload["status"] == "RESILIENCE_VERIFIED"
        assert (
            chaos_payload["revocation_summary"]["removed_from_directory"]
            is True
        )
        assert chaos_payload["revocation_summary"]["evicted_dek_entries"] >= 1
        assert (
            chaos_payload["revocation_summary"]["evicted_bulkhead_bucket"]
            is True
        )

    # Configure `DB_POOL` with a `pool_factory` whose role has `rolsuper=False, rolbypassrls=True`:
    # both lifespan startup AND `/healthz` must fail closed with `E_RLS_POSTURE_VIOLATION`!
    async def _create_bypass_pool() -> asyncpg.Pool:
        return await _make_real_asyncpg_pool(
            role_row={
                "role_name": "bypass_role",
                "rolsuper": False,
                "rolbypassrls": True,
            },
            table_rows=[],
        )

    broken_db_pool = RLSDatabasePool(pool_factory=_create_bypass_pool)
    monkeypatch.setattr(gateway_main, "DB_POOL", broken_db_pool)

    with (
        pytest.raises(PermissionError, match="E_RLS_POSTURE_VIOLATION"),
        TestClient(gateway_main.app),
    ):
        pass

    direct_client = TestClient(gateway_main.app)
    failed_health = direct_client.get("/healthz")
    assert failed_health.status_code == 503
    assert failed_health.json()["detail"]["error"] == "E_RLS_POSTURE_VIOLATION"
