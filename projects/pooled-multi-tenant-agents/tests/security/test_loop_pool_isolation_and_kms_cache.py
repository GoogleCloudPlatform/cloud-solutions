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

"""Tests for per-event-loop `RLSDatabasePool` isolation and Cloud KMS `verify_key_access` caching.

Covers:
1. Production call-site wiring (`scripts.init_postgres_rls.build_app_role_dsn` +
   `make_asyncpg_pool_factory`, and `POST /api/v1/invoke-agent` with `live_cloud=True` calling
   `verify_key_access` and recording `hop3_live_kms_probe_ciphertext_bytes` and
   `hop3_live_kms_cache_hit`).
2. `WeakKeyDictionary` per-loop pool tracking with strong `pool._loop` references (matching real
   `asyncpg.Pool`), loop-close cycle breaking across both `asyncio` and `uvloop`, per-loop
   `asyncio.Lock` deduplication of concurrent first calls, loop-local `await db_pool.close()`,
   and fail-closed post-close / `None`-factory rejection (never falling back to in-memory rows).
3. `LiveCloudKMSCMEKVerifier.verify_key_access` 60s TTL cache against a real local HTTP server
   backed by `LocalKMS`:
   - Synchronous policy check runs before the cache lookup.
   - Cache lookup runs before `_headers` / token minting so cache hits avoid both token minting
     and the KMS `:encrypt` RPC.
   - Separate cache entries per `(tenant_id, principal_sub, kms_key_name)` (mutation-tested).
   - `evict_tenant(tenant_id)` purges a single tenant's cached entries immediately on offboarding.
"""

from __future__ import annotations

import asyncio
import base64
import gc
import json
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Self
from urllib.parse import urlsplit

import httpx
import pytest
import uvloop
from agents import gcp_live_bridge
from agents.context import TENANT_DIRECTORY, ContextEnvelope, EdgeAuthVerifier
from agents.tenant_credentials import (
    LocalKMS,
    LocalTenantCredentialBackend,
    TenantCredentialBroker,
    TenantIsolationPolicy,
    TenantScopedCredential,
    set_default_broker,
    tenant_service_account_email,
)
from app import main as main_module
from fastapi.testclient import TestClient
from mcp_server import db as db_module
from scripts.sandbox_auth import SandboxCaller

FINVAULT_TENANT = "tenant-finvault-alpha"
RETAILSTREAM_TENANT = "tenant-retailstream-beta"
PROJECT_ID = "cymbal-multitenancy-example"
client = TestClient(main_module.app)


def _mint_envelope(
    tenant_id: str,
    principal_sub: str = "alice@finvault.com",
    user_role: str = "sre_admin",
) -> ContextEnvelope:
    """Mints a verified `ContextEnvelope` for test assertions."""
    return EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims={
            "iss": str(TENANT_DIRECTORY[tenant_id]["iss"]),
            "sub": principal_sub,
            "tenant_id": tenant_id,
            "user_role": user_role,
            "exp": 4_102_444_800,
        },
        dpop_proof={
            "jkt": f"jkt-{principal_sub}",
            "jti": f"jti-{tenant_id}-{principal_sub}",
        },
    )


class _LoopBoundAsyncTransaction:
    """Async transaction bound to the originating connection's event loop."""

    def __init__(self, expected_loop: asyncio.AbstractEventLoop) -> None:
        self._expected_loop = expected_loop

    async def __aenter__(self) -> Self:
        if asyncio.get_running_loop() is not self._expected_loop:
            raise RuntimeError("Task got Future attached to a different loop")
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class _LoopBoundAsyncConnection:
    """Async connection that raises RuntimeError if used from a different event loop."""

    def __init__(self, expected_loop: asyncio.AbstractEventLoop) -> None:
        self._expected_loop = expected_loop

    def transaction(self) -> _LoopBoundAsyncTransaction:
        return _LoopBoundAsyncTransaction(self._expected_loop)

    async def execute(self, sql: str, *args: Any) -> None:
        _ = (sql, args)
        if asyncio.get_running_loop() is not self._expected_loop:
            raise RuntimeError("Task got Future attached to a different loop")

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, str]]:
        _ = args
        if asyncio.get_running_loop() is not self._expected_loop:
            raise RuntimeError("Task got Future attached to a different loop")
        if "tenant_runbooks" in sql:
            return [
                {
                    "runbook_id": "RB-FV-01",
                    "tenant_id": FINVAULT_TENANT,
                    "title": "Wire Failover",
                    "remediation_steps": "Drain pool",
                }
            ]
        return [
            {
                "incident_id": "INC-FV-1001",
                "tenant_id": FINVAULT_TENANT,
                "service_name": "wire",
                "severity": "P1",
                "summary": "Latency spike",
                "pii_notes": "REDACTED",
            }
        ]


class _AcquireContext:
    """Async context manager yielding a `_LoopBoundAsyncConnection`."""

    def __init__(self, expected_loop: asyncio.AbstractEventLoop) -> None:
        self._expected_loop = expected_loop

    async def __aenter__(self) -> _LoopBoundAsyncConnection:
        if asyncio.get_running_loop() is not self._expected_loop:
            raise RuntimeError("Task got Future attached to a different loop")
        return _LoopBoundAsyncConnection(self._expected_loop)

    async def __aexit__(self, *_: object) -> None:
        return None


class _LoopBoundAsyncPool:
    """Pool holding a strong reference to its creation event loop (matching `asyncpg.Pool`)."""

    def __init__(self, *, fail_on_close: bool = False) -> None:
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self.closed = False
        self.terminated = False
        self.fail_on_close = fail_on_close

    def acquire(self) -> _AcquireContext:
        if self._loop.is_closed():
            raise RuntimeError("Event loop is closed")
        return _AcquireContext(self._loop)

    def terminate(self) -> None:
        self.terminated = True

    async def close(self) -> None:
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError(
                "Pool.close() called from a different event loop"
            )
        if self.fail_on_close:
            raise OSError("Simulated pool close transport error")
        self.closed = True


@contextmanager
def _local_kms_http_server(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[list[dict[str, Any]]]:
    """Starts a real `ThreadingHTTPServer` backed by `LocalKMS` and routes `httpx.post` to it."""
    recorded_requests: list[dict[str, Any]] = []
    local_kms = LocalKMS(TenantIsolationPolicy(project_id=PROJECT_ID))
    real_httpx_post = httpx.post

    class _KMSRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
            recorded_requests.append(
                {
                    "path": self.path,
                    "headers": dict(self.headers),
                    "json": payload,
                }
            )
            path_without_action = self.path.lstrip("/").removeprefix("v1/")
            key_name = path_without_action.split(":encrypt", 1)[0]
            key_name_base = key_name.split("/cryptoKeyVersions/", 1)[0]
            plaintext = base64.b64decode(payload["plaintext"])
            aad = base64.b64decode(
                payload.get("additionalAuthenticatedData", "")
            )
            tenant_id = aad.decode("utf-8")
            caller_sa = tenant_service_account_email(tenant_id, PROJECT_ID)
            credential = TenantScopedCredential(
                tenant_id=tenant_id,
                principal=caller_sa,
                token="local-kms-token",
                expires_at=4_102_444_800.0,
            )
            ciphertext = local_kms.encrypt(
                kms_key_name=key_name_base,
                plaintext=plaintext,
                aad=aad,
                credential=credential,
            )
            body_bytes = json.dumps(
                {"ciphertext": base64.b64encode(ciphertext).decode("ascii")}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

        def log_message(self, format: str, *args: object) -> None:
            _ = (format, args)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _KMSRequestHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    def routed_httpx_post(url: str, **kwargs: Any) -> httpx.Response:
        parsed = urlsplit(url)
        local_url = f"http://127.0.0.1:{port}{parsed.path}"
        if parsed.query:
            local_url = f"{local_url}?{parsed.query}"
        return real_httpx_post(local_url, **kwargs)

    monkeypatch.setattr(httpx, "post", routed_httpx_post)
    try:
        yield recorded_requests
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)


def test_make_asyncpg_pool_factory_and_app_role_dsn_rewrite() -> None:
    from scripts.init_postgres_rls import build_app_role_dsn

    with pytest.raises(ValueError, match="non-empty"):
        db_module.make_asyncpg_pool_factory("   ")
    factory = db_module.make_asyncpg_pool_factory(
        "postgresql://localhost:5432/cymbal"
    )
    assert callable(factory)

    rewritten_dsn = build_app_role_dsn(
        "postgresql://postgres:example-superuser-pw@127.0.0.1:5432/cymbal_pooled_ops"
    )
    assert (
        rewritten_dsn
        == "postgresql://cymbal_mcp_app:cymbal-rls-password@127.0.0.1:5432/cymbal_pooled_ops"
    )


def test_rls_database_pool_isolates_pools_per_loop_and_evicts_garbage_collected_loops() -> (
    None
):
    created_pools: list[_LoopBoundAsyncPool] = []

    async def create_pool_for_loop() -> _LoopBoundAsyncPool:
        await asyncio.sleep(0.005)
        pool = _LoopBoundAsyncPool()
        created_pools.append(pool)
        return pool

    db_pool = db_module.RLSDatabasePool(pool_factory=create_pool_for_loop)

    first_loop: asyncio.AbstractEventLoop | None = asyncio.new_event_loop()
    try:
        assert first_loop is not None
        incidents_loop_one = first_loop.run_until_complete(
            db_pool.query_incidents(tenant_id=FINVAULT_TENANT)
        )
        runbooks_loop_one = first_loop.run_until_complete(
            db_pool.query_runbooks(tenant_id=FINVAULT_TENANT)
        )
        assert len(incidents_loop_one) == 1
        assert len(runbooks_loop_one) == 1
        assert len(db_pool._pools_by_loop) == 1
    finally:
        if first_loop is not None:
            first_loop.close()

    # Even though `_LoopBoundAsyncPool` holds a strong `self._loop` reference (like real asyncpg),
    # closing `first_loop` triggers the close hook, terminates the pool, and evicts the loop entry.
    assert created_pools[0].terminated is True
    first_loop = None
    gc.collect()
    assert len(db_pool._pools_by_loop) == 0

    second_loop = asyncio.new_event_loop()
    try:
        incidents_loop_two = second_loop.run_until_complete(
            db_pool.query_incidents(tenant_id=FINVAULT_TENANT)
        )
        assert len(incidents_loop_two) == 1
        assert len(created_pools) == 2
        second_loop.run_until_complete(db_pool.close())
        assert created_pools[1].closed is True
        assert len(db_pool._pools_by_loop) == 0
    finally:
        second_loop.close()


def test_uvloop_20_loop_churn_and_unhookable_loop_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Proves 20 `uvloop` event loops are cleanly evicted on `loop.close()` and logs if
    unhookable.
    """
    created_pools: list[_LoopBoundAsyncPool] = []

    async def create_pool_for_loop() -> _LoopBoundAsyncPool:
        pool = _LoopBoundAsyncPool()
        created_pools.append(pool)
        return pool

    db_pool = db_module.RLSDatabasePool(pool_factory=create_pool_for_loop)

    for _ in range(20):
        uv_loop = uvloop.new_event_loop()
        try:
            incidents = uv_loop.run_until_complete(
                db_pool.query_incidents(tenant_id=FINVAULT_TENANT)
            )
            assert len(incidents) == 1
        finally:
            uv_loop.close()
        del uv_loop

    gc.collect()
    assert len(created_pools) == 20
    assert all(pool.terminated for pool in created_pools)
    assert len(db_pool._pools_by_loop) == 0

    # Verify warning path when an event loop implementation forbids reassigning `loop.close`.
    class _ReadOnlyCloseLoop(asyncio.AbstractEventLoop):
        def close(self) -> None:
            return None

        def __setattr__(self, name: str, value: object) -> None:
            if name == "close":
                raise AttributeError("Read-only method 'close'")
            super().__setattr__(name, value)

    readonly_loop = _ReadOnlyCloseLoop.__new__(_ReadOnlyCloseLoop)
    with caplog.at_level(logging.WARNING, logger="mcp_server.db"):
        db_pool._install_loop_close_hook(readonly_loop)
    assert any(
        "Could not install loop.close hook" in record.message
        for record in caplog.records
    )


def test_close_only_closes_current_loop_and_preserves_entry_on_close_error() -> (
    None
):
    """Proves `close()` does not touch foreign loops and retains the pool entry if `close()`
    fails.
    """
    should_fail_close = False

    async def pool_factory() -> _LoopBoundAsyncPool:
        return _LoopBoundAsyncPool(fail_on_close=should_fail_close)

    db_pool = db_module.RLSDatabasePool(pool_factory=pool_factory)
    loop_alpha = asyncio.new_event_loop()
    loop_beta = asyncio.new_event_loop()
    try:
        loop_alpha.run_until_complete(
            db_pool.query_incidents(tenant_id=FINVAULT_TENANT)
        )
        should_fail_close = True
        loop_beta.run_until_complete(
            db_pool.query_incidents(tenant_id=FINVAULT_TENANT)
        )
        assert len(db_pool._pools_by_loop) == 2

        # Failing close on loop_beta raises OSError and does NOT drop loop_beta's pool entry.
        with pytest.raises(
            OSError, match="Simulated pool close transport error"
        ):
            loop_beta.run_until_complete(db_pool.close())
        assert loop_beta in db_pool._pools_by_loop

        # Closing on loop_alpha closes ONLY loop_alpha's pool without touching loop_beta's pool.
        loop_alpha.run_until_complete(db_pool.close())
        assert loop_alpha not in db_pool._pools_by_loop
        assert loop_beta in db_pool._pools_by_loop
    finally:
        loop_alpha.close()
        loop_beta.close()


def test_closed_pool_and_none_factory_fail_closed_without_demo_fallback() -> (
    None
):
    """Proves queries after `close()` or a `None`-returning `pool_factory` raise `RuntimeError`."""

    async def _scenario() -> None:
        # 1. Pool factory returning None must raise E_DB_POOL_FACTORY_RETURNED_NONE, never demo
        # rows.
        none_factory_pool = db_module.RLSDatabasePool(pool_factory=lambda: None)
        with pytest.raises(
            RuntimeError, match="E_DB_POOL_FACTORY_RETURNED_NONE"
        ):
            await none_factory_pool.query_incidents(tenant_id=FINVAULT_TENANT)
        with pytest.raises(
            RuntimeError, match="E_DB_POOL_FACTORY_RETURNED_NONE"
        ):
            await none_factory_pool.query_runbooks(tenant_id=FINVAULT_TENANT)

        # 2. Single-loop pool closed via `await close()` must raise E_DB_POOL_CLOSED, never demo
        # rows.
        single_pool = db_module.RLSDatabasePool(
            asyncpg_pool=_LoopBoundAsyncPool()
        )
        assert (
            len(await single_pool.query_incidents(tenant_id=FINVAULT_TENANT))
            == 1
        )
        await single_pool.close()
        with pytest.raises(RuntimeError, match="E_DB_POOL_CLOSED"):
            await single_pool.query_incidents(tenant_id=FINVAULT_TENANT)
        with pytest.raises(RuntimeError, match="E_DB_POOL_CLOSED"):
            await single_pool.query_runbooks(tenant_id=FINVAULT_TENANT)

        # 3. Per-loop factory pool closed on current loop must raise E_DB_POOL_CLOSED.
        loop_factory_pool = db_module.RLSDatabasePool(
            pool_factory=_LoopBoundAsyncPool
        )
        assert (
            len(
                await loop_factory_pool.query_incidents(
                    tenant_id=FINVAULT_TENANT
                )
            )
            == 1
        )
        await loop_factory_pool.close()
        with pytest.raises(RuntimeError, match="E_DB_POOL_CLOSED"):
            await loop_factory_pool.query_incidents(tenant_id=FINVAULT_TENANT)

    asyncio.run(_scenario())


@pytest.mark.asyncio
async def test_concurrent_first_queries_on_same_loop_create_only_one_pool() -> (
    None
):
    factory_invocations = 0

    async def slow_pool_factory() -> _LoopBoundAsyncPool:
        nonlocal factory_invocations
        factory_invocations += 1
        await asyncio.sleep(0.02)
        return _LoopBoundAsyncPool()

    db_pool = db_module.RLSDatabasePool(pool_factory=slow_pool_factory)
    results = await asyncio.gather(
        *(db_pool.query_incidents(tenant_id=FINVAULT_TENANT) for _ in range(8))
    )
    assert len(results) == 8
    assert factory_invocations == 1
    await db_pool.close()


def test_rls_database_pool_skips_closed_loop_waiters_without_leaking_connections() -> (
    None
):
    db_pool = db_module.RLSDatabasePool(pool_size=1)

    closed_loop = asyncio.new_event_loop()
    stale_future = closed_loop.create_future()
    closed_loop.close()

    db_pool._waiters.append((0, 0, stale_future))

    active_loop = asyncio.new_event_loop()
    try:
        incidents = active_loop.run_until_complete(
            db_pool.query_incidents(tenant_id=FINVAULT_TENANT)
        )
        assert len(incidents) == 2
        assert len(db_pool._available) == 1
        assert db_pool.active_in_use == 0
    finally:
        active_loop.close()


def test_kms_verify_cache_saves_token_mint_isolates_principals_and_evicts_on_offboarding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gcp_live_bridge.clear_kms_verify_cache()
    now_seconds = [1_000.0]
    header_mint_calls: list[tuple[str, str]] = []

    backend = LocalTenantCredentialBackend(clock=lambda: now_seconds[0])
    broker = TenantCredentialBroker(
        project_id=PROJECT_ID,
        backend=backend,
        clock=lambda: now_seconds[0],
    )
    set_default_broker(broker)
    monkeypatch.delenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", raising=False)

    verifier = gcp_live_bridge.LiveCloudKMSCMEKVerifier(
        project_id=PROJECT_ID,
        verify_ttl_seconds=60.0,
        clock_fn=lambda: now_seconds[0],
    )
    original_headers = verifier._headers

    def counting_headers(
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        tenant_id: str,
    ) -> dict[str, str]:
        principal_sub = (
            envelope.security.sub if envelope is not None else "_platform"
        )
        header_mint_calls.append((tenant_id, principal_sub))
        return original_headers(envelope, kms_key_name, tenant_id)

    monkeypatch.setattr(verifier, "_headers", counting_headers)

    alice_finvault = _mint_envelope(FINVAULT_TENANT, "alice@finvault.com")
    bob_finvault = _mint_envelope(FINVAULT_TENANT, "bob@finvault.com")
    carol_retailstream = _mint_envelope(
        RETAILSTREAM_TENANT, "carol@retailstream.com"
    )
    finvault_key = str(TENANT_DIRECTORY[FINVAULT_TENANT]["cmek_key_name"])
    retailstream_key = str(
        TENANT_DIRECTORY[RETAILSTREAM_TENANT]["cmek_key_name"]
    )

    try:
        with _local_kms_http_server(monkeypatch) as http_encrypt_calls:
            # 1. First verification for Alice@FinVault mints headers and calls Cloud KMS (:encrypt).
            first_receipt = verifier.verify_key_access(
                kms_key_name=finvault_key,
                tenant_id=FINVAULT_TENANT,
                envelope=alice_finvault,
            )
            assert first_receipt["verified"] is True
            assert first_receipt["cache_hit"] is False
            assert first_receipt["ciphertext_bytes"] > 0
            assert len(http_encrypt_calls) == 1
            assert len(header_mint_calls) == 1

            # 2. Second verification for Alice@FinVault within 60s hits cache WITHOUT calling
            # _headers.
            now_seconds[0] += 15.0
            second_receipt = verifier.verify_key_access(
                kms_key_name=finvault_key,
                tenant_id=FINVAULT_TENANT,
                envelope=alice_finvault,
            )
            assert second_receipt["verified"] is True
            assert second_receipt["cache_hit"] is True
            assert len(http_encrypt_calls) == 1
            assert (
                len(header_mint_calls) == 1
            )  # Zero extra header/token lookups on cache hit!

            # 3. Different user in the SAME tenant (Bob@FinVault) does NOT share Alice's cache
            # entry.
            bob_receipt = verifier.verify_key_access(
                kms_key_name=finvault_key,
                tenant_id=FINVAULT_TENANT,
                envelope=bob_finvault,
            )
            assert bob_receipt["cache_hit"] is False
            assert len(http_encrypt_calls) == 2
            assert len(header_mint_calls) == 2

            # 4. Different KMS key version for Alice@FinVault does NOT share the base-key cache
            # entry.
            versioned_finvault_key = f"{finvault_key}/cryptoKeyVersions/1"
            versioned_receipt = verifier.verify_key_access(
                kms_key_name=versioned_finvault_key,
                tenant_id=FINVAULT_TENANT,
                envelope=alice_finvault,
            )
            assert versioned_receipt["cache_hit"] is False
            assert len(http_encrypt_calls) == 3

            # 5. Different tenant (Carol@RetailStream) gets a separate cache entry.
            carol_receipt = verifier.verify_key_access(
                kms_key_name=retailstream_key,
                tenant_id=RETAILSTREAM_TENANT,
                envelope=carol_retailstream,
            )
            assert carol_receipt["cache_hit"] is False
            assert len(http_encrypt_calls) == 4

            # 6. Cross-tenant caller attempting to verify FinVault's key fails closed before cache
            # lookup.
            with pytest.raises(
                PermissionError, match="E_TENANT_RESOURCE_SCOPE_VIOLATION"
            ):
                verifier.verify_key_access(
                    kms_key_name=finvault_key,
                    tenant_id=FINVAULT_TENANT,
                    envelope=carol_retailstream,
                )
            assert len(http_encrypt_calls) == 4

            # 7. Offboarding eviction purges all 3 FinVault entries while preserving RetailStream's
            # entry.
            evicted_count = verifier.evict_tenant(FINVAULT_TENANT)
            assert evicted_count == 3

            carol_cached = verifier.verify_key_access(
                kms_key_name=retailstream_key,
                tenant_id=RETAILSTREAM_TENANT,
                envelope=carol_retailstream,
            )
            assert carol_cached["cache_hit"] is True
            assert len(http_encrypt_calls) == 4

            alice_reverified = verifier.verify_key_access(
                kms_key_name=finvault_key,
                tenant_id=FINVAULT_TENANT,
                envelope=alice_finvault,
            )
            assert alice_reverified["cache_hit"] is False
            assert len(http_encrypt_calls) == 5
    finally:
        gcp_live_bridge.clear_kms_verify_cache()
        set_default_broker(None)


def test_invoke_agent_live_cloud_wires_verify_key_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves `POST /api/v1/invoke-agent` with `live_cloud=True` calls real
    `LiveCloudKMSCMEKVerifier`.
    """
    gcp_live_bridge.clear_kms_verify_cache()
    now_seconds = [1_000.0]
    set_default_broker(
        TenantCredentialBroker(
            project_id=PROJECT_ID,
            backend=LocalTenantCredentialBackend(clock=lambda: now_seconds[0]),
            clock=lambda: now_seconds[0],
        )
    )
    monkeypatch.delenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", raising=False)

    class _LocalGuardrailBridge:
        def __init__(self, *_: Any, **__: Any) -> None:
            return None

        def sanitize_prompt(self, prompt: str) -> dict[str, Any]:
            _ = prompt
            return {"blocked": False}

        def query_regulatory_issues(self, **_: Any) -> dict[str, Any]:
            return {"issues": []}

        def write_memory(self, **_: Any) -> str:
            return "mem-doc-1"

        def deidentify_tool_output(self, **_: Any) -> dict[str, Any]:
            return {"redacted": True}

        def read_tenant_runbook(self, **_: Any) -> dict[str, str]:
            return {"bucket": "b", "object_name": "o", "kms_key_name": "k"}

        def insert_span(self, **_: Any) -> None:
            return None

    monkeypatch.setattr(gcp_live_bridge, "is_live_gcp_enabled", lambda: True)
    for class_name in (
        "LiveAtlassianJiraConnector",
        "LiveModelArmorGuardrail",
        "LiveFirestoreMemoryBank",
        "LiveCloudDLPGuardrail",
        "LiveGCSCMEKRunbookVault",
        "LiveBigQueryOTelSink",
    ):
        monkeypatch.setattr(gcp_live_bridge, class_name, _LocalGuardrailBridge)

    caller = SandboxCaller(
        client,
        tenant_id=FINVAULT_TENANT,
        sub="alice@finvault.com",
        role="sre_admin",
    )
    target_url = caller.url("/api/v1/invoke-agent")

    try:
        with _local_kms_http_server(monkeypatch) as http_encrypt_calls:
            first_response = client.post(
                target_url,
                json={"live_cloud": True},
                headers=caller.headers("POST", target_url),
            )
            assert first_response.status_code == 200
            first_receipt = first_response.json()["live_cloud_receipt"]
            assert first_receipt["hop3_live_kms_probe_ciphertext_bytes"] > 0
            assert first_receipt["hop3_live_kms_cache_hit"] is False
            assert len(http_encrypt_calls) == 1

            second_response = client.post(
                target_url,
                json={"live_cloud": True},
                headers=caller.headers("POST", target_url),
            )
            assert second_response.status_code == 200
            second_receipt = second_response.json()["live_cloud_receipt"]
            assert second_receipt["hop3_live_kms_cache_hit"] is True
            assert len(http_encrypt_calls) == 1
    finally:
        gcp_live_bridge.clear_kms_verify_cache()
        set_default_broker(None)


def test_kms_verify_cache_entry_expires_after_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After 60 s the cached 'verified' result must not be reused: KMS is asked again."""
    gcp_live_bridge.clear_kms_verify_cache()
    now_seconds = [1_000.0]
    monkeypatch.delenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", raising=False)
    set_default_broker(
        TenantCredentialBroker(
            project_id=PROJECT_ID,
            backend=LocalTenantCredentialBackend(clock=lambda: now_seconds[0]),
            clock=lambda: now_seconds[0],
        )
    )
    verifier = gcp_live_bridge.LiveCloudKMSCMEKVerifier(
        project_id=PROJECT_ID,
        verify_ttl_seconds=60.0,
        clock_fn=lambda: now_seconds[0],
    )
    alice = _mint_envelope(FINVAULT_TENANT, "alice@finvault.com")
    key = str(TENANT_DIRECTORY[FINVAULT_TENANT]["cmek_key_name"])
    try:
        with _local_kms_http_server(monkeypatch) as encrypt_calls:
            first = verifier.verify_key_access(
                kms_key_name=key, tenant_id=FINVAULT_TENANT, envelope=alice
            )
            assert first["cache_hit"] is False
            assert len(encrypt_calls) == 1

            now_seconds[0] += 59.0
            warm = verifier.verify_key_access(
                kms_key_name=key, tenant_id=FINVAULT_TENANT, envelope=alice
            )
            assert warm["cache_hit"] is True
            assert len(encrypt_calls) == 1

            now_seconds[0] += 2.0  # 61 s after the first check: past the TTL
            expired = verifier.verify_key_access(
                kms_key_name=key, tenant_id=FINVAULT_TENANT, envelope=alice
            )
            assert expired["cache_hit"] is False
            assert len(encrypt_calls) == 2
    finally:
        gcp_live_bridge.clear_kms_verify_cache()
        set_default_broker(None)


def test_kms_policy_check_runs_before_the_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cached allow must never outlive the tenant: an offboarded tenant fails closed even
    while its entry is still warm in the cache."""
    gcp_live_bridge.clear_kms_verify_cache()
    now_seconds = [1_000.0]
    monkeypatch.delenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", raising=False)
    set_default_broker(
        TenantCredentialBroker(
            project_id=PROJECT_ID,
            backend=LocalTenantCredentialBackend(clock=lambda: now_seconds[0]),
            clock=lambda: now_seconds[0],
        )
    )
    verifier = gcp_live_bridge.LiveCloudKMSCMEKVerifier(
        project_id=PROJECT_ID,
        verify_ttl_seconds=60.0,
        clock_fn=lambda: now_seconds[0],
    )
    alice = _mint_envelope(FINVAULT_TENANT, "alice@finvault.com")
    key = str(TENANT_DIRECTORY[FINVAULT_TENANT]["cmek_key_name"])
    try:
        with _local_kms_http_server(monkeypatch) as encrypt_calls:
            verifier.verify_key_access(
                kms_key_name=key, tenant_id=FINVAULT_TENANT, envelope=alice
            )
            assert len(encrypt_calls) == 1

            monkeypatch.delitem(
                TENANT_DIRECTORY, FINVAULT_TENANT
            )  # tenant offboarded
            now_seconds[0] += 5.0  # cache entry still fresh
            with pytest.raises(PermissionError):
                verifier.verify_key_access(
                    kms_key_name=key, tenant_id=FINVAULT_TENANT, envelope=alice
                )
            assert len(encrypt_calls) == 1
    finally:
        gcp_live_bridge.clear_kms_verify_cache()
        set_default_broker(None)
