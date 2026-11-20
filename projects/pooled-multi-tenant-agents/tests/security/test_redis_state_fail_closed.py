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

# pylint: disable=line-too-long

"""DA2 follow-ups (after #29).

1. A Redis outage fails closed with HTTP 503 `E_DPOP_REPLAY_STORE_UNAVAILABLE`, on data requests and
   on `/api/v1/auth/token`. Redis client errors are not `OSError`, so the store normalizes them; a
   valid login must never be told its token is invalid (401) because a backend is down.
2. The per-session turn counter is keyed on the gateway token only (see the updated
   `test_http_invoke_agent_enforces_session_turn_cap_across_requests`).
"""

from __future__ import annotations

import time

import pytest
from app import main as main_mod
from app.gateway_tokens import (
    GatewayTokenError,
    SharedReplayStore,
    _ReplayCache,
    _session_id_for_request,
    _SubjectTokenBindings,
    gateway_error,
    get_token_service,
)
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from scripts.sandbox_auth import TOKEN_EXCHANGE_PATH, SandboxCaller

client = TestClient(main_mod.app)
RS = "tenant-retailstream-beta"


class _DownRedis:
    """`redis.exceptions.ConnectionError` is a `RedisError(Exception)`, not an `OSError`."""

    def set(self, *_: object, **__: object) -> bool:
        raise RedisConnectionError("connection refused")

    def get(self, *_: object) -> bytes | None:
        raise RedisConnectionError("connection refused")


def test_non_oserror_redis_failures_map_to_store_unavailable() -> None:
    store = SharedReplayStore(redis_client=_DownRedis())
    with pytest.raises(GatewayTokenError) as replay_err:
        _ReplayCache(shared_store=store).check_and_add("jkt:jti")
    assert replay_err.value.code == "E_DPOP_REPLAY_STORE_UNAVAILABLE"
    with pytest.raises(GatewayTokenError) as bind_err:
        _SubjectTokenBindings(shared_store=store).bind(
            "subject", "jkt", time.time() + 300
        )
    assert bind_err.value.code == "E_DPOP_REPLAY_STORE_UNAVAILABLE"


def test_replay_store_outage_returns_503_on_data_requests() -> None:
    caller = SandboxCaller(
        client, tenant_id=RS, sub="bob@retailstream.com", role="sre_admin"
    )
    url = caller.url("/api/v1/whoami")
    headers = caller.headers("GET", url)  # signs in before the outage
    service = get_token_service()
    saved = service.replay
    service.replay = _ReplayCache(
        shared_store=SharedReplayStore(redis_client=_DownRedis())
    )
    try:
        resp = client.get(url, headers=headers)
    finally:
        service.replay = saved
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "E_DPOP_REPLAY_STORE_UNAVAILABLE"


def test_replay_store_outage_returns_503_on_token_exchange() -> None:
    caller = SandboxCaller(
        client, tenant_id=RS, sub="carol@retailstream.com", role="sre_admin"
    )
    subject_token = (
        caller.id_token
    )  # sandbox IdP token, minted before the outage
    service = get_token_service()
    saved = service.subject_bindings
    service.subject_bindings = _SubjectTokenBindings(
        shared_store=SharedReplayStore(redis_client=_DownRedis())
    )
    try:
        resp = client.post(
            TOKEN_EXCHANGE_PATH,
            json={"subject_token": subject_token},
            headers={
                "DPoP": caller.dpop_proof(
                    "POST", caller.url(TOKEN_EXCHANGE_PATH)
                )
            },
        )
    finally:
        service.subject_bindings = saved
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "E_DPOP_REPLAY_STORE_UNAVAILABLE"


def test_session_id_ignores_anything_the_caller_sends() -> None:
    assert _session_id_for_request("gw-abc") == "sess-gw-abc"


class _AsyncRedis:
    async def set(self, *_: object, **__: object) -> bool:
        return True

    async def get(self, *_: object) -> bytes | None:
        return None


class _TruthyRedis:
    """A client whose SET returns some truthy object instead of True/None."""

    def set(self, *_: object, **__: object) -> object:
        return "OK-but-not-True"

    def get(self, *_: object) -> bytes | None:
        return b"someone-else"


class _ExpiredBindingRedis:
    """SET NX says the key exists, but it expired before GET."""

    def set(self, *_: object, **__: object) -> None:
        return None

    def get(self, *_: object) -> None:
        return None


class _BrokenApiRedis:
    def set(self, *_: object, **__: object) -> bool:
        raise AttributeError("wrong client API")

    def get(self, *_: object) -> None:
        raise AttributeError("wrong client API")


def test_async_redis_client_is_refused() -> None:
    with pytest.raises(ValueError, match=r"synchronous Redis client"):
        SharedReplayStore(redis_client=_AsyncRedis())


def test_unexpected_set_result_fails_closed_not_open() -> None:
    store = SharedReplayStore(redis_client=_TruthyRedis())
    with pytest.raises(GatewayTokenError) as replay_err:
        _ReplayCache(shared_store=store).check_and_add("jkt:jti")
    assert replay_err.value.code == "E_DPOP_REPLAY_STORE_UNAVAILABLE"
    with pytest.raises(GatewayTokenError) as bind_err:
        _SubjectTokenBindings(shared_store=store).bind(
            "subject", "attacker", time.time() + 300
        )
    assert bind_err.value.code == "E_DPOP_REPLAY_STORE_UNAVAILABLE"


def test_binding_that_vanished_between_set_and_get_is_not_a_match() -> None:
    store = SharedReplayStore(redis_client=_ExpiredBindingRedis())
    with pytest.raises(GatewayTokenError) as err:
        _SubjectTokenBindings(shared_store=store).bind(
            "subject", "jkt", time.time() + 300
        )
    assert err.value.code == "E_DPOP_REPLAY_STORE_UNAVAILABLE"


def test_programming_errors_are_not_reported_as_outages() -> None:
    store = SharedReplayStore(redis_client=_BrokenApiRedis())
    with pytest.raises(AttributeError):
        _ReplayCache(shared_store=store).check_and_add("jkt:jti")


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("E_DPOP_REPLAY_STORE_UNAVAILABLE", 503),
        ("E_DPOP_REPLAY_CACHE_FULL", 503),
        ("E_SUBJECT_TOKEN_CACHE_FULL", 503),
        ("E_TOKEN_INVALID", 401),
        ("E_DPOP_REPLAY", 401),
    ],
)
def test_gateway_error_status_mapping(code: str, status: int) -> None:
    exc = gateway_error(code)
    assert exc.status_code == status
    headers = exc.headers or {}
    if status == 503:
        assert "Retry-After" in headers
        assert "WWW-Authenticate" not in headers
    else:
        assert "WWW-Authenticate" in headers
