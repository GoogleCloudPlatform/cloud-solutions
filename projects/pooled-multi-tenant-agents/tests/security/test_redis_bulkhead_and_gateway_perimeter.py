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

# pylint: disable=line-too-long,protected-access,unbalanced-tuple-unpacking

"""Verification suite for Redis Lua bulkhead state and gateway perimeter contracts.

Covers:
1. Cross-replica RPM, TPM, continuous time refill (custom clock and Redis TIME),
   per-session turn caps, and FIFO session tracking via `RedisBulkheadStore`.
2. Fail-closed validation against `None`, async/coroutine clients, short TTLs,
   `RedisError`/`TimeoutError`/`OSError` outages, and malformed script replies,
   while preserving `AttributeError` programming errors unmasked.
3. End-to-end FastAPI `POST /api/v1/invoke-agent` HTTP 503 + `Retry-After: 10`
   response on bulkhead store unavailability.
4. `offboard_tenant` Redis key eviction and fail-closed eviction outage handling.
5. `REDIS_URL` startup wiring across `build_bulkhead_from_env`,
   `GatewayTokenService.from_config`, `RUNTIME_ENV_CONTRACT`, Terraform, and docs.
"""

from __future__ import annotations

import math
from collections import deque
from pathlib import Path
from typing import Any

import pytest
from agents import platform_config
from agents.auth.vault_and_bulkhead import (
    RedisBulkheadStore,
    TokenBucketBulkhead,
    build_bulkhead_from_env,
)
from agents.context import TENANT_DIRECTORY, offboard_tenant
from agents.runtime_env import RUNTIME_ENV_CONTRACT
from app import main as main_module
from app import runtime_state
from app.gateway_tokens import GatewayTokenService, SharedReplayStore
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from scripts.sandbox_auth import SandboxCaller

REPO_ROOT = Path(__file__).resolve().parents[2]
FINVAULT_TENANT_ID = "tenant-finvault-alpha"
RETAILSTREAM_TENANT_ID = "tenant-retailstream-beta"
HTTP_CLIENT = TestClient(main_module.app)


class _AtomicFakeRedis:
    """In-memory deterministic emulator of the `_REDIS_CONSUME_LUA` Redis contract."""

    def __init__(self, server_time_seconds: float = 1_700_000_000.25) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, deque[str]] = {}
        self.strings: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.server_time_seconds = server_time_seconds
        self.last_clock_argument: str | None = None
        self.raise_error: BaseException | None = None
        self.override_eval_result: object | None = None
        self.override_delete_result: object | None = None

    def set(
        self, key: str, value: str, *, nx: bool = False, ex: int = 60
    ) -> bool | None:
        if self.raise_error is not None:
            raise self.raise_error
        if nx and key in self.strings:
            return None
        self.strings[key] = value
        self.ttls[key] = int(ex)
        return True

    def get(self, key: str) -> bytes | None:
        if self.raise_error is not None:
            raise self.raise_error
        stored_value = self.strings.get(key)
        return (
            stored_value.encode("utf-8") if stored_value is not None else None
        )

    def delete(self, *keys: str) -> object:
        if self.raise_error is not None:
            raise self.raise_error
        if self.override_delete_result is not None:
            return self.override_delete_result
        deleted_count = 0
        for key in keys:
            removed_hash = self.hashes.pop(key, None) is not None
            removed_list = self.lists.pop(key, None) is not None
            removed_str = self.strings.pop(key, None) is not None
            self.ttls.pop(key, None)
            if removed_hash or removed_list or removed_str:
                deleted_count += 1
        return deleted_count

    def eval(self, _script: str, numkeys: int, *keys_and_args: str) -> object:
        if self.raise_error is not None:
            raise self.raise_error
        if self.override_eval_result is not None:
            return self.override_eval_result
        assert numkeys == 3
        bucket_key, turns_key, order_key = keys_and_args[:3]
        (
            clock_arg,
            rpm_text,
            tpm_text,
            billable_text,
            session_id,
            max_turns_text,
            max_sessions_text,
            ttl_text,
        ) = keys_and_args[3:]
        self.last_clock_argument = clock_arg

        now_ts = (
            self.server_time_seconds
            if clock_arg == "SERVER_TIME"
            else float(clock_arg)
        )
        rpm_limit = float(rpm_text)
        tpm_limit = float(tpm_text)
        billable_tokens = float(billable_text)
        max_turns = int(max_turns_text)
        max_tracked_sessions = int(max_sessions_text)
        ttl_seconds = int(ttl_text)

        bucket_fields = self.hashes.setdefault(bucket_key, {})
        if "last_refill_ts" not in bucket_fields:
            requests_used = 0.0
            tokens_used = 0.0
            last_refill_ts = now_ts
        else:
            requests_used = float(bucket_fields["requests_used"])
            tokens_used = float(bucket_fields["tokens_used"])
            last_refill_ts = float(bucket_fields["last_refill_ts"])
            elapsed = now_ts - last_refill_ts
            if elapsed > 0.0:
                requests_used = max(
                    0.0, requests_used - (elapsed / 60.0) * rpm_limit
                )
                tokens_used = max(
                    0.0, tokens_used - (elapsed / 60.0) * tpm_limit
                )
                last_refill_ts = now_ts

        turns_map = self.hashes.setdefault(turns_key, {})
        if session_id:
            current_turns = int(turns_map.get(session_id, "0"))
            if current_turns + 1 > max_turns:
                return [
                    b"ERR_SESSION_TURNS",
                    str(current_turns).encode(),
                    b"0",
                    b"0",
                ]

        if requests_used + 1.0 > rpm_limit:
            return [b"ERR_RPM", b"0", b"0", b"0"]

        if tokens_used + billable_tokens > tpm_limit:
            return [b"ERR_TPM", b"0", b"0", b"0"]

        requests_used += 1.0
        tokens_used += billable_tokens
        bucket_fields["requests_used"] = str(requests_used)
        bucket_fields["tokens_used"] = str(tokens_used)
        bucket_fields["last_refill_ts"] = str(last_refill_ts)
        self.ttls[bucket_key] = ttl_seconds

        turns_used = 1
        if session_id:
            order_queue = self.lists.setdefault(order_key, deque())
            if session_id not in turns_map:
                while len(order_queue) >= max_tracked_sessions:
                    oldest_session = order_queue.popleft()
                    turns_map.pop(oldest_session, None)
                order_queue.append(session_id)
            turns_used = int(turns_map.get(session_id, "0")) + 1
            turns_map[session_id] = str(turns_used)
            self.ttls[turns_key] = ttl_seconds
            self.ttls[order_key] = ttl_seconds

        remaining_rpm = math.floor(rpm_limit - requests_used)
        remaining_tpm = math.floor(tpm_limit - tokens_used)
        return [
            b"OK",
            str(turns_used).encode(),
            str(remaining_rpm).encode(),
            str(remaining_tpm).encode(),
        ]


def test_cross_replica_redis_bulkhead_enforces_turns_rpm_tpm_refill_and_fifo() -> (
    None
):
    """Two `TokenBucketBulkhead` replicas share Redis RPM, TPM, turns, refill, and FIFO limits."""
    fake_redis = _AtomicFakeRedis()
    redis_store = RedisBulkheadStore(fake_redis, ttl_seconds=900)
    clock_state = [1000.0]

    def current_clock() -> float:
        return clock_state[0]

    replica_one = TokenBucketBulkhead(
        clock_fn=current_clock, shared_store=redis_store
    )
    replica_two = TokenBucketBulkhead(
        clock_fn=current_clock, shared_store=redis_store
    )

    # 1. Cross-replica autonomous turn limit (RetailStream Standard max_turns_per_session = 5)
    for _ in range(3):
        replica_one.check_and_consume(
            tenant_id=RETAILSTREAM_TENANT_ID,
            requested_thinking_tokens=512,
            estimated_total_tokens=1_000,
            session_id="sess-replica-shared",
        )
    fifth_turn_result: dict[str, Any] = {}
    for _ in range(2):
        fifth_turn_result = replica_two.check_and_consume(
            tenant_id=RETAILSTREAM_TENANT_ID,
            requested_thinking_tokens=512,
            estimated_total_tokens=1_000,
            session_id="sess-replica-shared",
        )
    assert fifth_turn_result["session_turns_used"] == 5
    assert (
        fake_redis.ttls["cymbal:bulkhead:v1:bucket:tenant-retailstream-beta"]
        == 900
    )

    with pytest.raises(PermissionError, match="E_SESSION_LOOP_CIRCUIT_BREAKER"):
        replica_one.check_and_consume(
            tenant_id=RETAILSTREAM_TENANT_ID,
            requested_thinking_tokens=512,
            estimated_total_tokens=1_000,
            session_id="sess-replica-shared",
        )

    # 2. Cross-replica TPM exhaustion on uncached prompt tokens (40,000 limit; 500 used so far)
    with pytest.raises(PermissionError, match="exceeded TPM bulkhead"):
        replica_two.check_and_consume(
            tenant_id=RETAILSTREAM_TENANT_ID,
            requested_thinking_tokens=512,
            estimated_total_tokens=40_000,
            prompt_cache_hit=False,
            session_id="sess-tpm-burst",
        )

    # 3. Cross-replica RPM exhaustion (30 RPM Standard; 5 already consumed -> 25 remaining)
    for turn_index in range(25):
        replica_target = replica_one if turn_index % 2 == 0 else replica_two
        replica_target.check_and_consume(
            tenant_id=RETAILSTREAM_TENANT_ID,
            requested_thinking_tokens=256,
            estimated_total_tokens=100,
            session_id=f"sess-rpm-{turn_index}",
        )
    with pytest.raises(PermissionError, match="exceeded RPM limit"):
        replica_two.check_and_consume(
            tenant_id=RETAILSTREAM_TENANT_ID,
            requested_thinking_tokens=256,
            estimated_total_tokens=100,
            session_id="sess-rpm-overflow",
        )

    # FinVault Bank remains unaffected during RetailStream starvation
    finvault_result = replica_one.check_and_consume(
        tenant_id=FINVAULT_TENANT_ID,
        requested_thinking_tokens=4_000,
        estimated_total_tokens=2_000,
        session_id="sess-finvault-healthy",
    )
    assert finvault_result["remaining_rpm"] == 119

    # 4. Advancing clock by 30 seconds refills half of RetailStream's 30 RPM bucket (15 requests)
    clock_state[0] = 1030.0
    refilled_result = replica_two.check_and_consume(
        tenant_id=RETAILSTREAM_TENANT_ID,
        requested_thinking_tokens=256,
        estimated_total_tokens=100,
        session_id="sess-after-refill",
    )
    assert refilled_result["remaining_rpm"] == 14

    # 5. Default server-time clock mode uses Redis TIME ("SERVER_TIME") across containers
    default_clock_bulkhead = TokenBucketBulkhead(shared_store=redis_store)
    server_time_result = default_clock_bulkhead.check_and_consume(
        tenant_id=FINVAULT_TENANT_ID,
        requested_thinking_tokens=1_000,
        estimated_total_tokens=1_000,
        session_id="sess-server-time",
    )
    assert fake_redis.last_clock_argument == "SERVER_TIME"
    assert server_time_result["session_turns_used"] == 1


def test_redis_bulkhead_evicts_oldest_session_when_max_tracked_sessions_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bounded FIFO session queue evicts oldest `sess-*` entry when `MAX_TRACKED_SESSIONS` fills."""
    fake_redis = _AtomicFakeRedis()
    redis_store = RedisBulkheadStore(fake_redis)
    monkeypatch.setattr(TokenBucketBulkhead, "MAX_TRACKED_SESSIONS", 3)
    bulkhead = TokenBucketBulkhead(shared_store=redis_store)

    for session_name in ("sess-1", "sess-2", "sess-3"):
        bulkhead.check_and_consume(
            tenant_id=FINVAULT_TENANT_ID,
            requested_thinking_tokens=512,
            estimated_total_tokens=500,
            session_id=session_name,
        )
    # Adding sess-4 evicts sess-1 from the bounded hash and FIFO queue
    bulkhead.check_and_consume(
        tenant_id=FINVAULT_TENANT_ID,
        requested_thinking_tokens=512,
        estimated_total_tokens=500,
        session_id="sess-4",
    )
    reentered_first = bulkhead.check_and_consume(
        tenant_id=FINVAULT_TENANT_ID,
        requested_thinking_tokens=512,
        estimated_total_tokens=500,
        session_id="sess-1",
    )
    assert reentered_first["session_turns_used"] == 1


def test_redis_bulkhead_rejects_invalid_clients_and_fails_closed_on_outage_or_bad_reply() -> (
    None
):
    """Validates constructor guards, fail-closed transport handling, and programming error pass."""

    class _AsyncEvalClient:
        async def eval(self, *_args: object) -> object:
            return [b"OK", b"1", b"10", b"100"]

        def delete(self, *_keys: str) -> int:
            return 1

    class _AsyncDeleteClient:
        def eval(self, *_args: object) -> object:
            return [b"OK", b"1", b"10", b"100"]

        async def delete(self, *_keys: str) -> int:
            return 1

    class _FakeAsyncioModuleClient:
        __module__ = "redis.asyncio.client"

        def eval(self, *_args: object) -> object:
            return [b"OK", b"1", b"10", b"100"]

        def delete(self, *_keys: str) -> int:
            return 1

    class _BrokenAttributeClient:
        def eval(self, *_args: object) -> object:
            raise AttributeError("misconfigured redis wrapper")

        def delete(self, *_keys: str) -> int:
            return 0

    with pytest.raises(ValueError, match="synchronous Redis client"):
        RedisBulkheadStore(None)
    with pytest.raises(ValueError, match="synchronous Redis client"):
        RedisBulkheadStore(_AsyncEvalClient())
    with pytest.raises(ValueError, match="synchronous Redis client"):
        RedisBulkheadStore(_AsyncDeleteClient())
    with pytest.raises(ValueError, match="synchronous Redis client"):
        RedisBulkheadStore(_FakeAsyncioModuleClient())
    with pytest.raises(ValueError, match="at least 60 seconds"):
        RedisBulkheadStore(_AtomicFakeRedis(), ttl_seconds=30)

    # Transport / RedisError / TimeoutError / unhealthy store -> 503 E_BULKHEAD_BACKEND_UNAVAILABLE
    for injected_error in (
        RedisConnectionError("connection reset"),
        TimeoutError("socket timed out"),
        OSError("network unreachable"),
    ):
        failing_redis = _AtomicFakeRedis()
        failing_redis.raise_error = injected_error
        bulkhead = TokenBucketBulkhead(
            shared_store=RedisBulkheadStore(failing_redis)
        )
        try:
            with pytest.raises(
                PermissionError, match="E_BULKHEAD_BACKEND_UNAVAILABLE"
            ):
                bulkhead.check_and_consume(
                    tenant_id=FINVAULT_TENANT_ID,
                    requested_thinking_tokens=512,
                    estimated_total_tokens=1_000,
                    session_id="sess-outage",
                )
        finally:
            failing_redis.raise_error = None

    unhealthy_store = RedisBulkheadStore(_AtomicFakeRedis())
    unhealthy_store.healthy = False
    unhealthy_bulkhead = TokenBucketBulkhead(shared_store=unhealthy_store)
    try:
        with pytest.raises(
            PermissionError, match="E_BULKHEAD_BACKEND_UNAVAILABLE"
        ):
            unhealthy_bulkhead.check_and_consume(
                tenant_id=FINVAULT_TENANT_ID,
                requested_thinking_tokens=512,
                estimated_total_tokens=1_000,
            )
    finally:
        unhealthy_store.healthy = True

    # Malformed Lua return shapes fail closed (never truthy fail-open)
    for bad_reply in (
        "OK",
        [b"OK", b"1"],
        [b"UNKNOWN_STATUS", b"1", b"10", b"100"],
        [b"OK", b"not-an-int", b"10", b"100"],
        [123, b"1", b"10", b"100"],
    ):
        malformed_redis = _AtomicFakeRedis()
        malformed_redis.override_eval_result = bad_reply
        malformed_bulkhead = TokenBucketBulkhead(
            shared_store=RedisBulkheadStore(malformed_redis)
        )
        try:
            with pytest.raises(
                PermissionError, match="E_BULKHEAD_BACKEND_UNAVAILABLE"
            ):
                malformed_bulkhead.check_and_consume(
                    tenant_id=FINVAULT_TENANT_ID,
                    requested_thinking_tokens=512,
                    estimated_total_tokens=1_000,
                )
        finally:
            malformed_redis.override_eval_result = None

    # Boolean delete reply is rejected rather than treated as integer 1
    bool_delete_redis = _AtomicFakeRedis()
    bool_delete_redis.override_delete_result = True
    bool_delete_bulkhead = TokenBucketBulkhead(
        shared_store=RedisBulkheadStore(bool_delete_redis)
    )
    try:
        with pytest.raises(
            PermissionError, match="E_BULKHEAD_BACKEND_UNAVAILABLE"
        ):
            bool_delete_bulkhead.evict_tenant(FINVAULT_TENANT_ID)
    finally:
        bool_delete_redis.override_delete_result = None

    # Programming bugs (AttributeError) propagate directly instead of masquerading as 503 outages
    broken_bulkhead = TokenBucketBulkhead(
        shared_store=RedisBulkheadStore(_BrokenAttributeClient())
    )
    with pytest.raises(AttributeError, match="misconfigured redis wrapper"):
        broken_bulkhead.check_and_consume(
            tenant_id=FINVAULT_TENANT_ID,
            requested_thinking_tokens=512,
            estimated_total_tokens=1_000,
        )


def test_http_invoke_agent_maps_bulkhead_backend_outage_to_503_with_retry_after() -> (
    None
):
    """`POST /api/v1/invoke-agent` returns 503 + `Retry-After: 10` on Redis bulkhead outage."""
    caller = SandboxCaller(
        HTTP_CLIENT,
        tenant_id=RETAILSTREAM_TENANT_ID,
        sub="bob@retailstream.com",
        role="sre_admin",
    )
    target_url = caller.url("/api/v1/invoke-agent")
    request_headers = caller.headers("POST", target_url)

    down_redis = _AtomicFakeRedis()
    down_redis.raise_error = RedisConnectionError("redis primary unreachable")
    failing_bulkhead = TokenBucketBulkhead(
        shared_store=RedisBulkheadStore(down_redis)
    )

    original_main_bulkhead = main_module.TOKEN_BULKHEAD
    original_state_bulkhead = runtime_state.TOKEN_BULKHEAD
    main_module.TOKEN_BULKHEAD = failing_bulkhead
    runtime_state.TOKEN_BULKHEAD = failing_bulkhead
    try:
        outage_response = HTTP_CLIENT.post(
            target_url,
            json={
                "prompt": "Check ServiceNow incident queue",
                "requested_thinking_tokens": 512,
            },
            headers=request_headers,
        )
    finally:
        down_redis.raise_error = None
        main_module.TOKEN_BULKHEAD = original_main_bulkhead
        runtime_state.TOKEN_BULKHEAD = original_state_bulkhead

    assert outage_response.status_code == 503, outage_response.text
    assert outage_response.headers.get("Retry-After") == "10"
    assert "E_BULKHEAD_BACKEND_UNAVAILABLE" in str(
        outage_response.json()["detail"]["error"]
    )


def test_offboard_tenant_purges_redis_bulkhead_keys() -> None:
    """`offboard_tenant` deletes Redis bucket, session-turns, and FIFO order keys for the tenant."""
    synthetic_tenant_id = "tenant-ephemeral-redis-evict"
    TENANT_DIRECTORY[synthetic_tenant_id] = dict(
        TENANT_DIRECTORY[RETAILSTREAM_TENANT_ID]
    )
    fake_redis = _AtomicFakeRedis()
    redis_store = RedisBulkheadStore(fake_redis)
    bulkhead = TokenBucketBulkhead(shared_store=redis_store)

    try:
        bulkhead.check_and_consume(
            tenant_id=synthetic_tenant_id,
            requested_thinking_tokens=256,
            estimated_total_tokens=1_000,
            session_id="sess-before-offboard",
        )
        assert (
            f"cymbal:bulkhead:v1:bucket:{synthetic_tenant_id}"
            in fake_redis.hashes
        )
        assert (
            f"cymbal:bulkhead:v1:turns:{synthetic_tenant_id}"
            in fake_redis.hashes
        )

        eviction_report = offboard_tenant(synthetic_tenant_id)
        assert eviction_report["removed_from_directory"] is True
        assert eviction_report["evicted_bulkhead_bucket"] is True
        assert (
            f"cymbal:bulkhead:v1:bucket:{synthetic_tenant_id}"
            not in fake_redis.hashes
        )
        assert (
            f"cymbal:bulkhead:v1:turns:{synthetic_tenant_id}"
            not in fake_redis.hashes
        )
        assert (
            f"cymbal:bulkhead:v1:order:{synthetic_tenant_id}"
            not in fake_redis.lists
        )
    finally:
        TENANT_DIRECTORY.pop(synthetic_tenant_id, None)


def test_redis_url_env_wiring_and_gateway_perimeter_documentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies `REDIS_URL` startup wiring across bulkhead, gateway tokens, Terraform, and docs."""
    assert "REDIS_URL" in RUNTIME_ENV_CONTRACT

    fake_redis = _AtomicFakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://10.10.0.5:6379/0")
    monkeypatch.setattr(
        "agents.auth.vault_and_bulkhead.redis.Redis.from_url",
        lambda *_args, **_kwargs: fake_redis,
    )

    wired_bulkhead = build_bulkhead_from_env()
    assert isinstance(wired_bulkhead._shared_store, RedisBulkheadStore)

    sandbox_config = platform_config.load_platform_config("sandbox")
    wired_gateway_service = GatewayTokenService.from_config(sandbox_config)
    assert isinstance(wired_gateway_service.replay._shared, SharedReplayStore)
    assert wired_gateway_service.replay._shared._redis is fake_redis

    monkeypatch.delenv("REDIS_URL", raising=False)
    local_bulkhead = build_bulkhead_from_env()
    assert local_bulkhead._shared_store is None

    iap_gateway_tf = (
        REPO_ROOT / "terraform" / "modules" / "platform_core" / "iap_gateway.tf"
    ).read_text(encoding="utf-8")
    assert "REDIS_URL =" in iap_gateway_tf
    assert (
        "var.enable_live_mode && var.enable_memorystore_redis" in iap_gateway_tf
    )

    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    arch_e2e_text = (
        REPO_ROOT / "docs" / "solution_architecture_end_to_end.md"
    ).read_text(encoding="utf-8")
    assert "Optional enterprise upgrade" in readme_text
    expected_heading = (
        "### Gateway Perimeter Options: Cloud Run and IAP Reference "
        "vs. Apigee and Managed Agent Gateway"
    )
    assert expected_heading in arch_e2e_text
