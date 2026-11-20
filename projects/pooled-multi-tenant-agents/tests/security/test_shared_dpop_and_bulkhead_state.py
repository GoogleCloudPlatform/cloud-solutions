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

"""ADR-0013 PR-DA2 Verification Suite: Shared DPoP Replay, Shared Bulkhead & Stable Session IDs.

Verifies:
1. Cross-instance DPoP `jti` replay prevention (`FM-01`): a DPoP proof consumed on Gateway
   Instance A is rejected (`E_DPOP_REPLAY`) on Gateway Instance B when backed by `SharedReplayStore`
   (including Redis `SET NX EX` client contract and fail-closed `E_DPOP_REPLAY_STORE_UNAVAILABLE`).
2. Cross-instance subject-token binding (`FM-01`): an IdP subject token bound to Key 1 on
   Instance A is rejected (`E_SUBJECT_TOKEN_BOUND_TO_OTHER_KEY`) when re-exchanged with Key 2 on
   Instance B.
3. Cross-instance `TokenBucketBulkhead` state (`FM-02`): two `TokenBucketBulkhead` instances
   backed by `SharedBulkheadStore` enforce a single fleet-wide RPM/TPM/session-turn quota and fail
   closed (`E_BULKHEAD_BACKEND_UNAVAILABLE`) on backend failure.
4. End-to-end HTTP boundary session turn cap (`TestClient(app)`): sequential `POST
   /api/v1/invoke-agent`
   calls using the same gateway token share a deterministic `sess-{jti}` session identifier and hit
   `HTTP 429 E_SESSION_LOOP_CIRCUIT_BREAKER` on turn `max_turns_per_session + 1`, while optional
   a caller's `X-Session-ID` header never changes the session key (no counter reset).
"""

from __future__ import annotations

import time

import app.main as main_mod
import pytest
from agents.context import (
    AsymmetricDPoPProvider,
    EdgeAuthVerifier,
    SharedBulkheadStore,
    TokenBucketBulkhead,
)
from app.gateway_tokens import (
    GatewayTokenError,
    GatewayTokenService,
    SharedReplayStore,
    _ReplayCache,
    _SubjectTokenBindings,
    access_token_hash,
)
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from scripts.sandbox_auth import SandboxCaller

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
client = TestClient(main_mod.app)


def _make_gateway_pair(
    shared: SharedReplayStore,
) -> tuple[GatewayTokenService, GatewayTokenService]:
    """Two distinct gateway instances sharing a signing key and `SharedReplayStore`."""
    key = ec.generate_private_key(ec.SECP256R1())
    kid = "gw-shared-test"
    svc_a = GatewayTokenService(
        private_key=key,
        kid=kid,
        ephemeral=False,
        replay=_ReplayCache(shared_store=shared),
        exchange_replay=_ReplayCache(shared_store=shared),
        subject_bindings=_SubjectTokenBindings(shared_store=shared),
    )
    svc_b = GatewayTokenService(
        private_key=key,
        kid=kid,
        ephemeral=False,
        replay=_ReplayCache(shared_store=shared),
        exchange_replay=_ReplayCache(shared_store=shared),
        subject_bindings=_SubjectTokenBindings(shared_store=shared),
    )
    return svc_a, svc_b


def test_cross_instance_dpop_proof_replay_blocked_via_shared_store() -> None:
    """A DPoP proof consumed on Instance A must be rejected on Instance B (`E_DPOP_REPLAY`)."""
    shared = SharedReplayStore()
    svc_a, svc_b = _make_gateway_pair(shared)

    client_priv = ec.generate_private_key(ec.SECP256R1())
    client_jwk = AsymmetricDPoPProvider.public_key_to_jwk(
        client_priv.public_key()
    )
    jkt = AsymmetricDPoPProvider.compute_rfc7638_jwk_thumbprint(client_jwk)

    verifier = EdgeAuthVerifier()
    env = verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://accounts.google.com",
            "sub": "alice@finvault.com",
            "tenant_id": FV,
            "user_role": "sre_admin",
            "idp_provider": "google_workspace_oidc",
            "exp": int(time.time()) + 3600,
            "jti": "idp-1",
        },
        dpop_proof={"jkt": jkt, "jti": "exchange-1"},
        replay_checked=True,
    )
    token, _ = svc_a.issue(env)
    htu = "https://agent-gateway.cymbal.internal/api/v1/invoke-agent"
    proof = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=client_priv,
        htm="POST",
        htu=htu,
        ath=access_token_hash(token),
    )

    claims, _ = svc_a.verify_request(
        authorization=f"DPoP {token}", dpop=proof, htm="POST", htu=htu
    )
    assert claims["tenant_id"] == FV

    with pytest.raises(GatewayTokenError) as exc_info:
        svc_b.verify_request(
            authorization=f"DPoP {token}", dpop=proof, htm="POST", htu=htu
        )
    assert exc_info.value.code == "E_DPOP_REPLAY"


def test_shared_replay_store_redis_contract_and_fail_closed_on_outage() -> None:
    """`SharedReplayStore` uses Redis `SET NX EX` semantics and fails closed on `OSError`."""

    class _FakeRedis:
        def __init__(self) -> None:
            self.data: dict[str, str] = {}
            self.fail = False

        def set(
            self, key: str, value: str, *, nx: bool = False, ex: int = 60
        ) -> bool:
            if self.fail:
                raise OSError("Redis connection refused")
            if nx and key in self.data:
                return False
            self.data[key] = value
            return True

        def get(self, key: str) -> bytes | None:
            if self.fail:
                raise OSError("Redis connection refused")
            val = self.data.get(key)
            return val.encode("utf-8") if val is not None else None

    fake_redis = _FakeRedis()
    store = SharedReplayStore(redis_client=fake_redis)
    cache = _ReplayCache(shared_store=store)
    bindings = _SubjectTokenBindings(shared_store=store)

    cache.check_and_add("jkt-1:jti-1")
    with pytest.raises(GatewayTokenError) as replay_err:
        cache.check_and_add("jkt-1:jti-1")
    assert replay_err.value.code == "E_DPOP_REPLAY"

    bindings.bind("subj-token-1", "jkt-1", time.time() + 300)
    bindings.bind("subj-token-1", "jkt-1", time.time() + 300)
    with pytest.raises(GatewayTokenError) as bind_err:
        bindings.bind("subj-token-1", "jkt-attacker", time.time() + 300)
    assert bind_err.value.code == "E_SUBJECT_TOKEN_BOUND_TO_OTHER_KEY"

    fake_redis.fail = True
    with pytest.raises(GatewayTokenError) as store_err:
        cache.check_and_add("jkt-1:jti-2")
    assert store_err.value.code == "E_DPOP_REPLAY_STORE_UNAVAILABLE"

    with pytest.raises(GatewayTokenError) as bind_outage_err:
        bindings.bind("subj-token-2", "jkt-1", time.time() + 300)
    assert bind_outage_err.value.code == "E_DPOP_REPLAY_STORE_UNAVAILABLE"


def test_cross_instance_bulkhead_shares_quotas_and_fails_closed() -> None:
    """Two `TokenBucketBulkhead` instances sharing `SharedBulkheadStore` enforce one fleet quota."""
    shared = SharedBulkheadStore()
    now = [1000.0]
    bulkhead_a = TokenBucketBulkhead(
        clock_fn=lambda: now[0], shared_store=shared
    )
    bulkhead_b = TokenBucketBulkhead(
        clock_fn=lambda: now[0], shared_store=shared
    )

    # RetailStream standard tier has max_turns_per_session = 5: consume 3 on A and 2 on B
    for _ in range(3):
        bulkhead_a.check_and_consume(
            tenant_id=RS,
            requested_thinking_tokens=1000,
            estimated_total_tokens=1000,
            session_id="sess-shared-1",
        )
    for _ in range(2):
        res = bulkhead_b.check_and_consume(
            tenant_id=RS,
            requested_thinking_tokens=1000,
            estimated_total_tokens=1000,
            session_id="sess-shared-1",
        )
    assert res["session_turns_used"] == 5

    with pytest.raises(PermissionError, match="E_SESSION_LOOP_CIRCUIT_BREAKER"):
        bulkhead_a.check_and_consume(
            tenant_id=RS,
            requested_thinking_tokens=1000,
            estimated_total_tokens=1000,
            session_id="sess-shared-1",
        )

    shared.healthy = False
    with pytest.raises(PermissionError, match="E_BULKHEAD_BACKEND_UNAVAILABLE"):
        bulkhead_b.check_and_consume(
            tenant_id=FV,
            requested_thinking_tokens=1000,
            estimated_total_tokens=1000,
            session_id="sess-shared-2",
        )


def test_http_invoke_agent_enforces_session_turn_cap_across_requests() -> None:
    """Sequential `POST /api/v1/invoke-agent` calls with one gateway token share `sess-{jti}`
    and trigger `429 E_SESSION_LOOP_CIRCUIT_BREAKER` on the 6th Standard-tier request.
    """
    caller = SandboxCaller(
        client, tenant_id=RS, sub="bob@retailstream.com", role="sre_admin"
    )
    target_url = caller.url("/api/v1/invoke-agent")

    saved_state = main_mod.TOKEN_BULKHEAD._buckets.pop(RS, None)
    try:
        for expected_turn in range(1, 6):
            resp = client.post(
                target_url,
                json={
                    "prompt": "Check ServiceNow latency",
                    "requested_thinking_tokens": 512,
                },
                headers=caller.headers("POST", target_url),
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["finops"]["session_turns_used"] == expected_turn

        tracked_sessions = list(
            main_mod.TOKEN_BULKHEAD._buckets[RS].session_turns.keys()
        )
        assert len(tracked_sessions) == 1
        default_session_id = tracked_sessions[0]
        assert default_session_id.startswith("sess-gw-")

        # 6th request on the same session hits E_SESSION_LOOP_CIRCUIT_BREAKER (HTTP 429)
        sixth = client.post(
            target_url,
            json={
                "prompt": "Turn 6 on same session",
                "requested_thinking_tokens": 512,
            },
            headers=caller.headers("POST", target_url),
        )
        assert sixth.status_code == 429
        assert (
            sixth.json()["detail"]["error"] == "E_SESSION_LOOP_CIRCUIT_BREAKER"
        )

        # A caller-chosen X-Session-ID must NOT start a fresh counter (that would bypass the cap)
        for label in ("conv-2", "conv-3"):
            spoofed = client.post(
                target_url,
                json={
                    "prompt": f"Turn on {label}",
                    "requested_thinking_tokens": 512,
                },
                headers={
                    **caller.headers("POST", target_url),
                    "X-Session-ID": label,
                },
            )
            assert spoofed.status_code == 429
            assert (
                spoofed.json()["detail"]["error"]
                == "E_SESSION_LOOP_CIRCUIT_BREAKER"
            )
        assert list(main_mod.TOKEN_BULKHEAD._buckets[RS].session_turns) == [
            default_session_id
        ]
    finally:
        if saved_state is not None:
            main_mod.TOKEN_BULKHEAD._buckets[RS] = saved_state
        else:
            main_mod.TOKEN_BULKHEAD._buckets.pop(RS, None)


def test_permission_error_status_mapping_ignores_embedded_503_and_429_in_session_ids() -> (
    None
):
    """Embedded `503`/`429` digits inside `session_id` must never hijack PEP HTTP status codes."""
    from app.api.v1.agents_and_sandboxes import (
        _permission_error_status_and_headers,
    )

    circuit_breaker_with_503_in_sess = PermissionError(
        "429 Too Many Requests: E_SESSION_LOOP_CIRCUIT_BREAKER: Tenant 'tenant-retailstream-beta' "
        "exceeded max autonomous turns per session (5) in 'sess-gw-dead503beef'."
    )
    assert _permission_error_status_and_headers(
        circuit_breaker_with_503_in_sess
    ) == (429, None)

    forbidden_with_429_and_503_in_sess = PermissionError(
        "403 Forbidden: E_TENANT_SCOPE_DENIED: session 'sess-gw-429-503'"
    )
    assert _permission_error_status_and_headers(
        forbidden_with_429_and_503_in_sess
    ) == (403, None)

    backend_outage = PermissionError(
        "503 Service Unavailable: E_BULKHEAD_BACKEND_UNAVAILABLE: "
        "Shared rate-limit bulkhead store unreachable; failing closed."
    )
    assert _permission_error_status_and_headers(backend_outage) == (
        503,
        {"Retry-After": "10"},
    )
