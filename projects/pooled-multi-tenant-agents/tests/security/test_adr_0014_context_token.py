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
# pylint: disable=redefined-outer-name,unused-argument
# pylint: disable=use-implicit-booleaness-not-comparison

"""ADR-0014 B2: the gateway-signed ES256 context token replaces the constant-key HMAC envelope.

Proves the ADR's "done" list for B2:
- **Forgery:** another key, `alg: none`, HS256 (including the public key as HMAC secret), an
  unknown `kid`, the wrong `aud`, a wrong `typ` or `iss`, and an expired token are rejected by every
  verifier: the ADK interceptor, the MCP wire handler and sub-agent hops.
- **Cross-use:** a gateway access token (`at+jwt`) is rejected as a context token, and a context
  token is rejected as `Authorization` on every gateway data endpoint.
- **Fail closed:** a KMS error or timeout returns 503 on the request path; nothing falls back to a
  local key.
- **Verifiers can't sign:** the verifier modules never load private key material.
- **Rotation:** two kids verify during the overlap; a removed kid fails.
- **KMS path end to end:** DER -> raw `r||s` conversion round-trips; a fake KMS that signs with a
  real P-256 key drives the full request path through the interceptor and MCP.
- The constant key is gone, the gateway refuses to start without a signing key, and the local
  signer is refused on Cloud Run and outside the synthetic sandbox.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import contextlib
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import jwt
import pytest
from agents import context as ctx
from agents import context_signing as cs
from agents import context_token as ct
from agents import kms_rest
from agents import platform_config as pc
from agents.interceptors import enforce_tenant_isolation_interceptor
from agents.shared_diagnostic_agent import build_shared_diagnostic_agent
from agents.testing_fakes import MockADKCallbackContext
from app import gateway_tokens as gt
from app import main
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    decode_dss_signature,
    encode_dss_signature,
)
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from mcp_server.server import handle_mcp_jsonrpc_request
from scripts.sandbox_auth import SandboxCaller

REPO = Path(__file__).resolve().parents[2]
FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
BASE = "http://testserver"
KEY = "projects/test-project/locations/us-central1/keyRings/test-kr/cryptoKeys/ctx-signing"


# --- helpers --------------------------------------------------------------------------------------


def _envelope(
    tenant: str = RS, sub: str = "bob@retailstream.com", **kw: Any
) -> ctx.ContextEnvelope:
    claims = {
        "iss": str(ctx.TENANT_DIRECTORY[tenant]["iss"]),
        "sub": sub,
        "tenant_id": tenant,
        "user_role": "sre_admin",
        "exp": int(time.time()) + 600,
        "jti": f"gw-{uuid.uuid4().hex}",
        **kw,
    }
    return ctx.EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims=claims,
        dpop_proof={"jkt": f"jkt-{sub}", "jti": uuid.uuid4().hex},
        session_id=f"sess-{uuid.uuid4().hex[:8]}",
    )


def _default_signer() -> cs.LocalTestSigner:
    signer = cs.get_context_token_issuer().signer
    assert isinstance(signer, cs.LocalTestSigner)
    return signer


def _compact(header: dict[str, Any], claims: dict[str, Any], sign: Any) -> str:
    signing_input = (
        ct.b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + ct.b64url(json.dumps(claims, separators=(",", ":")).encode())
    )
    return f"{signing_input}.{ct.b64url(sign(signing_input.encode()))}"


def _es256(key: ec.EllipticCurvePrivateKey) -> Any:
    return lambda data: ct.der_to_raw_signature(
        key.sign(data, ec.ECDSA(hashes.SHA256()))
    )


def _real_header() -> dict[str, Any]:
    return {"alg": "ES256", "typ": "ctx+jwt", "kid": _default_signer().kid}


def _forgeries(valid_token: str) -> dict[str, str]:
    """Tokens carrying the valid token's claims, each broken in exactly one way."""
    claims = ct.unverified_claims(valid_token)
    signer = _default_signer()
    real = signer.sign
    other_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = signer.public_keys.fetch(signer.kid).public_bytes(  # type: ignore[union-attr]
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    now = int(time.time())
    return {
        "other_key": _compact(_real_header(), claims, _es256(other_key)),
        "alg_none": _compact(
            {**_real_header(), "alg": "none"}, claims, lambda _: b""
        ),
        "hs256_public_key_as_secret": _compact(
            {**_real_header(), "alg": "HS256"},
            claims,
            lambda d: hmac.new(public_pem, d, hashlib.sha256).digest(),
        ),
        "unknown_kid": _compact(
            {**_real_header(), "kid": "local-test-unknown"},
            claims,
            _es256(other_key),
        ),
        "wrong_aud": _compact(
            _real_header(), {**claims, "aud": ["broker"]}, real
        ),
        "expired": _compact(
            _real_header(), {**claims, "iat": now - 700, "exp": now - 100}, real
        ),
        "typ_at_jwt": _compact(
            {**_real_header(), "typ": "at+jwt"}, claims, real
        ),
        "typ_missing": _compact(
            {"alg": "ES256", "kid": signer.kid}, claims, real
        ),
        "wrong_iss": _compact(
            _real_header(), {**claims, "iss": gt.GATEWAY_ISSUER}, real
        ),
        "embedded_jwk": _compact(
            {
                **_real_header(),
                "jwk": ctx.AsymmetricDPoPProvider.public_key_to_jwk(
                    other_key.public_key()
                ),
            },
            claims,
            _es256(other_key),
        ),
        "lifetime_too_long": _compact(
            _real_header(), {**claims, "iat": now, "exp": now + 3600}, real
        ),
    }


def _with_token(state: dict[str, Any], token: str) -> dict[str, Any]:
    """`state` carrying `token`, with a matching in-process depth tag, so only the token check
    itself can reject it (otherwise the depth tag would mask a broken token check).
    """
    return {
        **state,
        "temp:context_token": token,
        "temp:delegation_sig": ctx._delegation_tag(token, 0),
    }


async def _interceptor(state: dict[str, Any]) -> None:
    agent = build_shared_diagnostic_agent()
    await enforce_tenant_isolation_interceptor(
        MockADKCallbackContext(state=state, agent=agent)
    )


def _mcp(state: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(
        handle_mcp_jsonrpc_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            verified_adk_state=state,
        )
    )


def _assert_every_verifier_rejects(state: dict[str, Any]) -> None:
    with pytest.raises(
        PermissionError, match=r"E_SUBAGENT_STATE_TAMPERING|E_SUBAGENT_UNSIGNED"
    ):
        asyncio.run(_interceptor(state))
    assert _mcp(state)["error"]["code"] == -32001
    with pytest.raises(
        PermissionError, match=r"E_SUBAGENT_STATE_TAMPERING|E_SUBAGENT_UNSIGNED"
    ):
        ctx.propagate_to_subagent(state)


class FakeKms:
    """Fake KMS client: signs digests with real P-256 keys, one per key version."""

    def __init__(self, versions: int = 1) -> None:
        self.keys = {
            f"{KEY}/cryptoKeyVersions/{n}": ec.generate_private_key(
                ec.SECP256R1()
            )
            for n in range(1, versions + 1)
        }
        self.disabled: set[str] = set()
        self.sign_calls = 0
        self.public_key_calls: list[str] = []
        self.fail: Exception | None = None
        self.public_key_fail: Exception | None = None
        self.public_key_hang_seconds = 0.0
        self.hang_seconds = 0.0

    def asymmetric_sign(self, *, name: str, digest_sha256: bytes) -> bytes:
        self.sign_calls += 1
        if self.hang_seconds:
            time.sleep(self.hang_seconds)
        if self.fail is not None:
            raise self.fail
        return self.keys[name].sign(
            digest_sha256, ec.ECDSA(Prehashed(hashes.SHA256()))
        )

    def get_public_key(self, *, name: str) -> tuple[str, str]:
        self.public_key_calls.append(name)
        if self.public_key_hang_seconds:
            time.sleep(self.public_key_hang_seconds)
        if self.public_key_fail is not None:
            raise self.public_key_fail
        if name not in self.keys:
            raise kms_rest.KmsKeyRejectedError("E_KMS_HTTP_404", status=404)
        if name in self.disabled:
            raise kms_rest.KmsKeyRejectedError("E_KMS_HTTP_400", status=400)
        pem = (
            self.keys[name]
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        return pem, kms_rest.EC_SIGN_P256_SHA256


@pytest.fixture
def restore_trust() -> Any:
    """Restores the process signer / trusted public keys after a test swaps them."""
    issuer = cs.get_context_token_issuer()
    yield
    with cs._ISSUER_LOCK:
        cs._ISSUER = issuer
    ct.install_public_key_source(issuer.signer.public_keys)  # type: ignore[attr-defined]


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


def _caller(client: TestClient, tenant: str = RS) -> SandboxCaller:
    return SandboxCaller(
        client,
        tenant_id=tenant,
        sub=f"u-{uuid.uuid4().hex[:6]}",
        role="sre_admin",
    )


# --- the valid path -------------------------------------------------------------------------------


def test_valid_token_passes_every_verifier_and_carries_the_signed_claims() -> (
    None
):
    env = _envelope()
    state = env.to_adk_state()
    asyncio.run(_interceptor(state))
    assert "result" in _mcp(state)
    assert ctx.propagate_to_subagent(state)["temp:delegation_depth"] == 1
    assert ctx.EdgeAuthVerifier().verify_obo_envelope(
        env, env.security.dpop_jkt
    )

    header = jwt.get_unverified_header(env.context_token)
    assert header == {
        "alg": "ES256",
        "kid": _default_signer().kid,
        "typ": "ctx+jwt",
    }
    claims = ct.get_context_verifier().verify(env.context_token, audience="mcp")
    assert claims["aud"] == ["runtime", "mcp"]
    assert claims["iss"] == ct.CONTEXT_TOKEN_ISSUER
    assert claims["tenant_id"] == RS
    assert claims["sub"] == "bob@retailstream.com"
    assert claims["cnf"] == {"jkt": "jkt-bob@retailstream.com"}
    assert claims["scopes"] == sorted(env.tenant.authorized_scopes)
    assert claims["max_delegation_depth"] == ct.DEFAULT_MAX_DELEGATION_DEPTH
    for unsigned in ("trace_id", "correlation_id", "requested_thinking_budget"):
        assert unsigned not in claims


def test_per_turn_fields_are_unsigned_and_do_not_break_verification() -> None:
    state = _envelope().to_adk_state()
    state["temp:trace_id"] = "trace-rewritten"
    state["temp:correlation_id"] = "corr-rewritten"
    state["temp:requested_thinking_budget"] = 999_999
    asyncio.run(_interceptor(state))
    assert (
        state["temp:effective_thinking_budget"] <= state["temp:thinking_budget"]
    )


def test_context_token_exp_never_exceeds_the_source_token_or_ten_minutes() -> (
    None
):
    now = int(time.time())
    short = _envelope(exp=now + 60)
    assert ct.unverified_claims(short.context_token)["exp"] <= now + 60
    long = _envelope(exp=now + 3600)
    assert ct.unverified_claims(long.context_token)["exp"] <= now + 1 + 600


def test_signed_once_per_gateway_token(client: TestClient) -> None:
    issuer = main.EDGE_VERIFIER._context_issuer
    caller = _caller(client)
    before = issuer.sign_count
    for _ in range(3):
        url = BASE + "/api/v1/whoami"
        assert (
            client.get(
                "/api/v1/whoami", headers=caller.headers("GET", url)
            ).status_code
            == 200
        )
    assert issuer.sign_count == before + 1
    other = _caller(client)
    client.get(
        "/api/v1/whoami", headers=other.headers("GET", BASE + "/api/v1/whoami")
    )
    assert issuer.sign_count == before + 2


def test_changed_tenant_claims_are_never_served_from_the_cache() -> None:
    jti = f"gw-{uuid.uuid4().hex}"
    a = _envelope(jti=jti, user_role="read_only_analyst")
    b = _envelope(jti=jti, user_role="sre_admin")
    assert a.context_token != b.context_token
    assert ct.unverified_claims(b.context_token)["user_role"] == "sre_admin"


# --- forgery --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    [
        "other_key",
        "alg_none",
        "hs256_public_key_as_secret",
        "unknown_kid",
        "wrong_aud",
        "expired",
        "typ_at_jwt",
        "typ_missing",
        "wrong_iss",
        "embedded_jwk",
        "lifetime_too_long",
    ],
)
def test_forged_context_token_is_rejected_by_every_verifier(case: str) -> None:
    env = _envelope()
    forged_token = _forgeries(env.context_token)[case]
    _assert_every_verifier_rejects(
        _with_token(env.to_adk_state(), forged_token)
    )
    forged_env = ctx.ContextEnvelope(
        security=env.security,
        tenant=env.tenant,
        request=env.request,
        context_token=forged_token,
        delegation_sig=env.delegation_sig,
    )
    with pytest.raises(PermissionError, match="E_INVALID_OBO_SIGNATURE"):
        ctx.EdgeAuthVerifier().verify_obo_envelope(
            forged_env, env.security.dpop_jkt
        )


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("other_key", "E_CONTEXT_TOKEN_SIGNATURE"),
        ("alg_none", "E_CONTEXT_TOKEN_ALG"),
        ("hs256_public_key_as_secret", "E_CONTEXT_TOKEN_ALG"),
        ("unknown_kid", "E_CONTEXT_TOKEN_UNKNOWN_KID"),
        ("wrong_aud", "E_CONTEXT_TOKEN_AUDIENCE"),
        ("expired", "E_CONTEXT_TOKEN_EXPIRED"),
        ("typ_at_jwt", "E_CONTEXT_TOKEN_TYPE"),
        ("typ_missing", "E_CONTEXT_TOKEN_TYPE"),
        ("wrong_iss", "E_CONTEXT_TOKEN_ISSUER"),
        ("embedded_jwk", "E_CONTEXT_TOKEN_HEADER"),
        ("lifetime_too_long", "E_CONTEXT_TOKEN_CLAIMS"),
    ],
)
def test_forgeries_fail_for_the_intended_reason(case: str, code: str) -> None:
    forged = _forgeries(_envelope().context_token)[case]
    for audience in ("runtime", "mcp"):
        with pytest.raises(ct.ContextTokenError) as exc_info:
            ct.get_context_verifier().verify(forged, audience=audience)
        assert exc_info.value.code == code


def test_each_audience_is_enforced_separately() -> None:
    env = _envelope()
    claims = ct.unverified_claims(env.context_token)
    signer = _default_signer()
    mcp_only = _compact(_real_header(), {**claims, "aud": ["mcp"]}, signer.sign)
    runtime_only = _compact(
        _real_header(), {**claims, "aud": ["runtime"]}, signer.sign
    )
    base = env.to_adk_state()

    state = _with_token(base, mcp_only)
    assert "result" in _mcp(state)
    with pytest.raises(PermissionError, match="E_CONTEXT_TOKEN_AUDIENCE"):
        asyncio.run(_interceptor(state))
    with pytest.raises(PermissionError, match="E_CONTEXT_TOKEN_AUDIENCE"):
        ctx.propagate_to_subagent(state)

    state = _with_token(base, runtime_only)
    asyncio.run(_interceptor(state))
    assert _mcp(state)["error"]["code"] == -32001


def test_a_valid_token_for_another_tenant_cannot_be_spliced_into_state() -> (
    None
):
    rs_state = _envelope(RS).to_adk_state()
    fv_token = _envelope(FV, "alice@finvault.com").context_token
    _assert_every_verifier_rejects(_with_token(rs_state, fv_token))


def test_auth_token_exchange_envelope_is_unsigned_and_refused_downstream() -> (
    None
):
    claims = {
        "iss": str(ctx.TENANT_DIRECTORY[RS]["iss"]),
        "sub": "bob@retailstream.com",
        "tenant_id": RS,
        "user_role": "sre_admin",
        "exp": int(time.time()) + 600,
    }
    unsigned = ctx.EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims=claims,
        dpop_proof={"jkt": "k", "jti": uuid.uuid4().hex},
        issue_context_token=False,
    )
    assert unsigned.context_token == ""
    _assert_every_verifier_rejects(unsigned.to_adk_state())


# --- cross-use ------------------------------------------------------------------------------------


def test_gateway_access_token_is_rejected_as_a_context_token() -> None:
    env = _envelope()
    gateway_token, _ = gt.get_token_service().issue(env)
    assert jwt.get_unverified_header(gateway_token)["typ"] == "at+jwt"
    with pytest.raises(ct.ContextTokenError, match="E_CONTEXT_TOKEN_TYPE"):
        ct.get_context_verifier().verify(gateway_token, audience="runtime")
    _assert_every_verifier_rejects(
        _with_token(env.to_adk_state(), gateway_token)
    )


def _caller_routes() -> list[APIRoute]:
    def calls(dependent: Any) -> set[str]:
        names = {getattr(getattr(dependent, "call", None), "__name__", "")}
        for sub in dependent.dependencies:
            names |= calls(sub)
        return names

    return [
        r
        for r in main.app.routes
        if isinstance(r, APIRoute)
        and calls(getattr(r, "dep" + "endant"))
        & {"require_caller", "optional_caller"}
    ]


def test_context_token_is_rejected_on_every_gateway_data_endpoint(
    client: TestClient,
) -> None:
    caller = _caller(client)
    gw_claims = jwt.decode(
        caller.access_token, options={"verify_signature": False}
    )
    jkt = gw_claims["cnf"]["jkt"]
    # A context token for this very caller and key: the strongest possible misuse.
    env = main.EDGE_VERIFIER.exchange_obo_token(
        verified_idp_claims={
            "iss": gw_claims["idp_iss"],
            "sub": gw_claims["sub"],
            "tenant_id": gw_claims["tenant_id"],
            "user_role": gw_claims["user_role"],
            "idp_provider": gw_claims["idp_provider"],
            "exp": gw_claims["exp"],
            "jti": gw_claims["jti"],
        },
        dpop_proof={"jkt": jkt, "jti": uuid.uuid4().hex},
        replay_checked=True,
    )
    routes = _caller_routes()
    assert {"/api/v1/whoami", "/api/v1/invoke-agent", "/mcp/v1/jsonrpc"} <= {
        r.path for r in routes
    }
    for route in routes:
        path = route.path
        for param in route.param_convertors:
            path = path.replace("{" + param + "}", "x")
        method = min(route.methods)
        headers = {
            "Authorization": f"DPoP {env.context_token}",
            "DPoP": caller.dpop_proof(
                method, BASE + path, access_token=env.context_token
            ),
        }
        resp = client.request(
            method, path, headers=headers, json={} if method == "POST" else None
        )
        assert resp.status_code == 401, (path, resp.status_code, resp.text)
        assert resp.json()["detail"] == {"error": "E_TOKEN_INVALID"}, path


# --- fail closed on KMS outage --------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["error", "timeout"])
def test_kms_failure_returns_503_with_no_local_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    fake = FakeKms()
    if mode == "error":
        fake.fail = RuntimeError("PERMISSION_DENIED or UNAVAILABLE")
    else:
        fake.hang_seconds = 2.0
    issuer = cs.ContextTokenIssuer(
        cs.KmsContextSigner(
            f"{KEY}/cryptoKeyVersions/1", client=fake, timeout=0.2
        )
    )
    monkeypatch.setattr(main.EDGE_VERIFIER, "_context_issuer", issuer)
    caller = _caller(client)
    _ = (
        caller.access_token
    )  # /auth/token signs nothing, so it still works during the outage
    started = time.monotonic()
    resp = client.get(
        "/api/v1/whoami", headers=caller.headers("GET", BASE + "/api/v1/whoami")
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == {"error": "E_CONTEXT_SIGNING_UNAVAILABLE"}
    assert resp.headers["retry-after"] == "10"
    assert (
        time.monotonic() - started < 1.5
    )  # bounded by the signer timeout, not the KMS hang
    assert fake.sign_calls == 1
    assert issuer.sign_count == 0
    with pytest.raises(cs.ContextSigningUnavailableError):
        issuer.issue(
            source_jti="j", not_after=int(time.time()) + 60, tenant_id=RS
        )


def test_kms_failure_on_scenario_endpoints_is_also_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeKms()
    fake.fail = RuntimeError("UNAVAILABLE")
    monkeypatch.setattr(
        main.EDGE_VERIFIER,
        "_context_issuer",
        cs.ContextTokenIssuer(
            cs.KmsContextSigner(f"{KEY}/cryptoKeyVersions/1", client=fake)
        ),
    )
    with pytest.raises(cs.ContextSigningUnavailableError):
        main._persona_envelope(main.ScenarioTurn())
    handler = main.app.exception_handlers[cs.ContextSigningUnavailableError]
    resp = asyncio.run(handler(None, cs.ContextSigningUnavailableError("x")))  # type: ignore[arg-type]
    assert resp.status_code == 503


# --- the KMS path end to end with a fake KMS ------------------------------------------------------


def test_der_raw_signature_round_trip() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    for i in range(50):
        der = key.sign(f"msg-{i}".encode(), ec.ECDSA(hashes.SHA256()))
        raw = ct.der_to_raw_signature(der)
        assert len(raw) == 64
        assert ct.raw_to_der_signature(raw) == der
        assert decode_dss_signature(der) == (
            int.from_bytes(raw[:32], "big"),
            int.from_bytes(raw[32:], "big"),
        )
    small = encode_dss_signature(
        1, 2
    )  # leading zero bytes must be padded, not dropped
    assert ct.raw_to_der_signature(ct.der_to_raw_signature(small)) == small
    with pytest.raises(ValueError, match=r"64 bytes"):
        ct.raw_to_der_signature(b"\x00" * 63)
    with pytest.raises(ValueError, match=r"too large for the curve"):
        ct.der_to_raw_signature(encode_dss_signature(1 << 256, 1))


def test_kms_signed_token_verifies_with_pyjwt_and_the_kms_public_key() -> None:
    fake = FakeKms()
    version = f"{KEY}/cryptoKeyVersions/1"
    issuer = cs.ContextTokenIssuer(cs.KmsContextSigner(version, client=fake))
    token, _ = _envelope_with(issuer)
    assert jwt.get_unverified_header(token)["kid"] == version
    jwt.decode(
        token,
        fake.keys[version].public_key(),
        algorithms=["ES256"],
        audience="runtime",
    )
    verifier = ct.ContextTokenVerifier(ct.KmsPublicKeySource(KEY, client=fake))
    assert verifier.verify(token, audience="mcp")["tenant_id"] == RS


def _envelope_with(
    issuer: cs.ContextTokenIssuer,
) -> tuple[str, ctx.ContextEnvelope]:
    env = ctx.EdgeAuthVerifier(context_issuer=issuer).exchange_obo_token(
        verified_idp_claims={
            "iss": str(ctx.TENANT_DIRECTORY[RS]["iss"]),
            "sub": "bob@retailstream.com",
            "tenant_id": RS,
            "user_role": "sre_admin",
            "exp": int(time.time()) + 600,
            "jti": f"gw-{uuid.uuid4().hex}",
        },
        dpop_proof={"jkt": "k", "jti": uuid.uuid4().hex},
        session_id="sess-kms",
    )
    return env.context_token, env


def test_full_request_path_with_fake_kms(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, restore_trust: Any
) -> None:
    fake = FakeKms()
    issuer = cs.ContextTokenIssuer(
        cs.KmsContextSigner(f"{KEY}/cryptoKeyVersions/1", client=fake)
    )
    monkeypatch.setattr(main.EDGE_VERIFIER, "_context_issuer", issuer)
    ct.install_public_key_source(
        ct.KmsPublicKeySource(KEY, client=fake)
    )  # KMS trust only
    caller = _caller(client)
    url = "/mcp/v1/jsonrpc"
    resp = client.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers=caller.headers("POST", BASE + url),
    )
    assert resp.status_code == 200, resp.text
    assert "result" in resp.json(), resp.text
    assert resp.json()["result"]["tenant_id"] == RS
    assert fake.sign_calls == 1
    assert fake.public_key_calls == [f"{KEY}/cryptoKeyVersions/1"]
    # A token from the local test key is not trusted once only the KMS key is.
    with pytest.raises(PermissionError, match="E_CONTEXT_TOKEN_UNKNOWN_KID"):
        asyncio.run(_interceptor(_local_state()))


def _local_state() -> dict[str, Any]:
    issuer = cs.ContextTokenIssuer(cs.LocalTestSigner())
    return _envelope_with(issuer)[1].to_adk_state()


def test_kms_rest_client_checks_crc32c_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    key = ec.generate_private_key(ec.SECP256R1())
    name = f"{KEY}/cryptoKeyVersions/1"
    digest = hashlib.sha256(b"x").digest()
    der = key.sign(digest, ec.ECDSA(Prehashed(hashes.SHA256())))
    body: dict[str, Any] = {
        "name": name,
        "verifiedDigestCrc32c": True,
        "signature": base64.b64encode(der).decode(),
        "signatureCrc32c": str(kms_rest.crc32c(der)),
    }

    class _Resp:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return body

    seen: dict[str, Any] = {}

    def fake_request(method: str, url: str, **kw: Any) -> _Resp:
        seen.update(
            method=method,
            url=url,
            json=kw.get("json"),
            timeout=kw.get("timeout"),
        )
        return _Resp()

    client = kms_rest.KmsRestClient(timeout=1.0)
    monkeypatch.setattr(
        client, "_auth_header", lambda: {"Authorization": "Bearer t"}
    )
    monkeypatch.setattr(httpx, "request", fake_request)
    assert client.asymmetric_sign(name=name, digest_sha256=digest) == der
    assert seen["url"].endswith(f"{name}:asymmetricSign")
    assert seen["timeout"] == 1.0
    assert seen["json"]["digestCrc32c"] == str(kms_rest.crc32c(digest))
    body["signatureCrc32c"] = "1"
    with pytest.raises(kms_rest.KmsUnavailableError, match="INTEGRITY"):
        client.asymmetric_sign(name=name, digest_sha256=digest)
    body["signatureCrc32c"] = str(kms_rest.crc32c(der))
    body["verifiedDigestCrc32c"] = False
    with pytest.raises(kms_rest.KmsUnavailableError, match="INTEGRITY"):
        client.asymmetric_sign(name=name, digest_sha256=digest)


# --- rotation and the kid ring --------------------------------------------------------------------


def test_local_rotation_overlap_then_removed_kid_fails() -> None:
    signer = cs.LocalTestSigner()
    issuer = cs.ContextTokenIssuer(signer)
    verifier = ct.ContextTokenVerifier(signer.public_keys)
    old_token, _ = _envelope_with(issuer)
    old_kid = signer.kid
    new_kid = signer.rotate()
    new_token, _ = _envelope_with(issuer)
    assert jwt.get_unverified_header(new_token)["kid"] == new_kid != old_kid
    assert verifier.verify(
        old_token, audience="runtime"
    )  # overlap: both kids valid
    assert verifier.verify(new_token, audience="runtime")
    signer.retire(old_kid)
    with pytest.raises(
        ct.ContextTokenError, match="E_CONTEXT_TOKEN_UNKNOWN_KID"
    ):
        verifier.verify(old_token, audience="runtime")
    assert verifier.verify(new_token, audience="runtime")


def test_kms_rotation_overlap_then_disabled_version_fails() -> None:
    fake = FakeKms(versions=2)
    now = [1_000_000.0]
    verifier = ct.ContextTokenVerifier(
        ct.KmsPublicKeySource(KEY, client=fake),
        key_cache_ttl_seconds=300,
        refetch_interval_seconds=30,
        clock=lambda: now[0],
    )
    v1, v2 = (f"{KEY}/cryptoKeyVersions/{n}" for n in (1, 2))
    t1, _ = _envelope_with(
        cs.ContextTokenIssuer(cs.KmsContextSigner(v1, client=fake))
    )
    t2, _ = _envelope_with(
        cs.ContextTokenIssuer(cs.KmsContextSigner(v2, client=fake))
    )
    # Real time for exp; the verifier's clock only drives key caching.
    assert verifier.verify(t1, audience="runtime")
    assert verifier.verify(t2, audience="runtime")
    fake.disabled.add(v1)
    assert verifier.verify(t1, audience="runtime")  # still cached
    now[0] += 301
    with pytest.raises(
        ct.ContextTokenError, match="E_CONTEXT_TOKEN_UNKNOWN_KID"
    ):
        verifier.verify(t1, audience="runtime")
    assert verifier.verify(t2, audience="runtime")


def test_unknown_kid_refetch_is_scoped_to_the_configured_key_and_rate_limited() -> (
    None
):
    fake = FakeKms()
    now = [1_000_000.0]
    verifier = ct.ContextTokenVerifier(
        ct.KmsPublicKeySource(KEY, client=fake),
        max_fetches_per_minute=3,
        clock=lambda: now[0],
    )
    env = _envelope()
    claims = ct.unverified_claims(env.context_token)
    other = ec.generate_private_key(ec.SECP256R1())

    def token_with_kid(kid: str) -> str:
        return _compact(
            {"alg": "ES256", "typ": "ctx+jwt", "kid": kid},
            claims,
            _es256(other),
        )

    foreign = "projects/evil/locations/us-central1/keyRings/x/cryptoKeys/y/cryptoKeyVersions/1"
    for kid in (foreign, "local-test-x", "../../etc"):
        with pytest.raises(ct.ContextTokenError, match="UNKNOWN_KID"):
            verifier.verify(token_with_kid(kid), audience="runtime")
    assert (
        fake.public_key_calls == []
    )  # never fetched outside the configured key

    missing = f"{KEY}/cryptoKeyVersions/7"
    for _ in range(5):
        with pytest.raises(ct.ContextTokenError, match="UNKNOWN_KID"):
            verifier.verify(token_with_kid(missing), audience="runtime")
    assert fake.public_key_calls == [
        missing
    ]  # one attempt per refetch interval
    for n in range(8, 14):
        with pytest.raises(ct.ContextTokenError):
            verifier.verify(
                token_with_kid(f"{KEY}/cryptoKeyVersions/{n}"),
                audience="runtime",
            )
    assert len(fake.public_key_calls) == 3  # global cap per minute


# --- verifiers can't sign -------------------------------------------------------------------------


_VERIFIER_MODULES = (
    "agents/context_token.py",
    "agents/interceptors.py",
    "mcp_server/server.py",
)


def test_verifier_modules_do_not_import_the_signer() -> None:
    for rel in _VERIFIER_MODULES:
        tree = ast.parse((REPO / rel).read_text())
        imported = {
            *(
                a.name
                for n in ast.walk(tree)
                if isinstance(n, ast.Import)
                for a in n.names
            ),
            *(
                n.module or ""
                for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom)
            ),
            *(
                f"{n.module}.{a.name}"
                for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom)
                for a in n.names
            ),
        }
        assert not {m for m in imported if "context_signing" in m}, rel
    with pytest.raises(TypeError):
        ct.StaticPublicKeySource({"k": ec.generate_private_key(ec.SECP256R1())})  # type: ignore[dict-item]


_CHILD = r"""
import asyncio, json, sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

def _forbidden(*a, **k):
    raise AssertionError("verifier path loaded or generated private key material")

ec.generate_private_key = _forbidden
ec.derive_private_key = _forbidden
serialization.load_pem_private_key = _forbidden
serialization.load_der_private_key = _forbidden

data = json.loads(sys.stdin.read())
from agents import context_token as ct
ct.install_public_key_source(
    ct.StaticPublicKeySource({data["kid"]: serialization.load_pem_public_key(data["pem"].encode())})
)
from agents.context import propagate_to_subagent
from agents.interceptors import enforce_tenant_isolation_interceptor
from mcp_server.server import handle_mcp_jsonrpc_request

class Agent:
    name = "cymbal_shared_diagnostic_agent"
    model = "gemini-4-argon"
    tools = []

class Ctx:
    def __init__(self, state):
        self.state, self.agent, self.active_tools = state, Agent(), []

state = data["state"]
from agents.context import _delegation_tag  # this process's own in-process depth tag
state["temp:delegation_depth"] = 0
state["temp:delegation_sig"] = _delegation_tag(state["temp:context_token"], 0)
asyncio.run(enforce_tenant_isolation_interceptor(Ctx(dict(state))))
res = asyncio.run(handle_mcp_jsonrpc_request(
    {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, verified_adk_state=dict(state)))
assert "result" in res, res
child = propagate_to_subagent(dict(state))
bad = dict(state, **{"temp:tenant_id": "tenant-finvault-alpha"})
try:
    propagate_to_subagent(bad)
    raise SystemExit("tampered state accepted")
except PermissionError:
    pass
loaded = sorted(m for m in sys.modules if "context_signing" in m)
assert not loaded, loaded
print("VERIFIED_PUBLIC_KEY_ONLY", child["temp:delegation_depth"])
"""


def test_verifiers_never_load_private_key_material() -> None:
    env = _envelope()
    signer = _default_signer()
    pem = signer.public_keys.fetch(signer.kid).public_bytes(  # type: ignore[union-attr]
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    state = env.to_adk_state()
    state.pop(
        "temp:delegation_sig"
    )  # per-process depth tag; the child is another process
    state.pop("temp:delegation_depth")
    env_vars = {
        k: v
        for k, v in os.environ.items()
        if k not in {"CYMBAL_LOCAL_CONTEXT_SIGNER", "CONTEXT_SIGNING_KMS_KEY"}
    }
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD],
        input=json.dumps(
            {"kid": signer.kid, "pem": pem.decode(), "state": state}
        ),
        capture_output=True,
        text=True,
        cwd=REPO,
        env={**env_vars, "PYTHONPATH": str(REPO)},
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert "VERIFIED_PUBLIC_KEY_ONLY 1" in proc.stdout


# --- the constant key is gone; startup and signer gating ----------------------------------------


def test_constant_keys_are_removed_from_code() -> None:
    assert not hasattr(ctx, "DEFAULT_PEP_SIGNING_SECRET")
    assert not hasattr(ctx, "compute_obo_hmac")
    for folder in ("agents", "app", "mcp_server"):
        for path in (REPO / folder).rglob("*.py"):
            text = path.read_text()
            for needle in (
                "pep-signing-secret",
                "cymbal-3lo-oauth-csrf-key",
                "signing_secret=",
            ):
                assert needle not in text, (path, needle)


def _cfg_with_identity(**identity: Any) -> pc.PlatformConfig:
    cfg = pc.get_platform_config()
    return cfg.model_copy(
        update={"identity": cfg.identity.model_copy(update=identity)}
    )


@pytest.fixture
def clean_signer_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in (
        "CYMBAL_LOCAL_CONTEXT_SIGNER",
        "CONTEXT_SIGNING_KMS_KEY",
        "CONTEXT_SIGNING_KMS_KEY_VERSION",
        "K_SERVICE",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_startup_fails_without_a_context_signing_key(
    clean_signer_env: pytest.MonkeyPatch,
) -> None:
    no_key = _cfg_with_identity(context_signing_kms_key=None)
    clean_signer_env.setattr(pc, "get_platform_config", lambda: no_key)
    with pytest.raises(RuntimeError, match="E_CONTEXT_SIGNING_KEY_MISSING"):
        cs._build_default_issuer()
    ct.install_public_key_source(None)
    try:
        with pytest.raises(
            ct.ContextTokenError, match="E_CONTEXT_VERIFIER_UNCONFIGURED"
        ):
            ct.get_context_verifier()
    finally:
        ct.install_public_key_source(_default_signer().public_keys)


def test_sandbox_config_selects_the_kms_key(
    clean_signer_env: pytest.MonkeyPatch,
) -> None:
    sandbox = pc.load_platform_config("sandbox")
    assert sandbox.identity.context_signing_kms_key == (
        f"projects/{sandbox.gcp.project_id}/locations/us-central1/keyRings/cymbal-platform-kr/"
        "cryptoKeys/ws2-context-signing"
    )
    clean_signer_env.setattr(pc, "get_platform_config", lambda: sandbox)
    issuer = cs._build_default_issuer()
    assert isinstance(issuer.signer, cs.KmsContextSigner)
    assert (
        issuer.signer.kid
        == sandbox.identity.context_signing_kms_key + "/cryptoKeyVersions/1"
    )
    clean_signer_env.setenv("CONTEXT_SIGNING_KMS_KEY_VERSION", "3")
    assert ct.resolve_context_signing_kms_key()[1].endswith("/cryptoKeyVersions/3")  # type: ignore[index]
    clean_signer_env.setenv(
        "CONTEXT_SIGNING_KMS_KEY", f"{KEY}/cryptoKeyVersions/9"
    )
    assert ct.resolve_context_signing_kms_key() == (
        KEY,
        f"{KEY}/cryptoKeyVersions/9",
    )
    clean_signer_env.setenv("CONTEXT_SIGNING_KMS_KEY", "not-a-key")
    with pytest.raises(RuntimeError, match="E_CONTEXT_SIGNING_KEY_INVALID"):
        ct.resolve_context_signing_kms_key()


def test_local_signer_refused_on_cloud_run_and_outside_the_sandbox(
    clean_signer_env: pytest.MonkeyPatch,
) -> None:
    sandbox = pc.load_platform_config("sandbox")
    clean_signer_env.setattr(pc, "get_platform_config", lambda: sandbox)
    clean_signer_env.setenv("CYMBAL_LOCAL_CONTEXT_SIGNER", "1")
    issuer = (
        cs._build_default_issuer()
    )  # offline synthetic sandbox: allowed, explicit flag
    assert isinstance(issuer.signer, cs.LocalTestSigner)
    ct.install_public_key_source(_default_signer().public_keys)

    clean_signer_env.setenv("K_SERVICE", "cymbal-pooled-gateway")
    with pytest.raises(
        RuntimeError, match=r"E_LOCAL_CONTEXT_SIGNER_REFUSED.*Cloud Run"
    ):
        cs._build_default_issuer()  # a refused request is fatal, never a silent downgrade
    clean_signer_env.delenv("K_SERVICE")

    customer = pc.load_platform_config("customer.example")
    clean_signer_env.setattr(pc, "get_platform_config", lambda: customer)
    with pytest.raises(RuntimeError, match="E_LOCAL_CONTEXT_SIGNER_REFUSED"):
        cs._build_default_issuer()

    clean_signer_env.setattr(cs, "_PYTEST_MODE", False)
    clean_signer_env.delenv("CYMBAL_LOCAL_CONTEXT_SIGNER")
    clean_signer_env.setattr(pc, "get_platform_config", lambda: sandbox)
    with pytest.raises(RuntimeError, match="E_LOCAL_CONTEXT_SIGNER_REFUSED"):
        cs.LocalTestSigner()  # no flag, not under pytest


def test_customer_config_requires_a_context_signing_key() -> None:
    data = pc.load_platform_config("customer.example").model_dump()
    data["identity"]["context_signing_kms_key"] = None
    with pytest.raises(ValueError, match="context_signing_kms_key"):
        pc.PlatformConfig.model_validate(data)
    data["identity"]["context_signing_kms_key"] = "keyRings/x/cryptoKeys/y"
    with pytest.raises(ValueError, match="context_signing_kms_key"):
        pc.PlatformConfig.model_validate(data)


def test_oauth_state_csrf_key_is_not_a_constant() -> None:
    from agents import workspace_plugins as wp

    assert isinstance(wp._OAUTH_STATE_KEY, bytes)
    assert len(wp._OAUTH_STATE_KEY) == 32
    env = _envelope()
    state = wp.WorkspacePluginRegistry.mint_csrf_bound_oauth_state(
        envelope=env, required_scope="3lo:google.drive.readonly"
    )
    assert wp.WorkspacePluginRegistry.verify_oauth_callback_state(
        callback_state=state,
        active_envelope=env,
        required_scope="3lo:google.drive.readonly",
    )


# --- review fixes: key ring resilience (P2-1) -----------------------------------------------------


def _kms_verifier(
    fake: FakeKms, now: list[float], **kw: Any
) -> ct.ContextTokenVerifier:
    return ct.ContextTokenVerifier(
        ct.KmsPublicKeySource(KEY, configured_version=1, client=fake),
        clock=lambda: now[0],
        **kw,
    )


def _token_with_kid(kid: str) -> str:
    claims = ct.unverified_claims(_envelope().context_token)
    other = ec.generate_private_key(ec.SECP256R1())
    return _compact(
        {"alg": "ES256", "typ": "ctx+jwt", "kid": kid}, claims, _es256(other)
    )


def _flood(verifier: ct.ContextTokenVerifier, versions: range) -> None:
    for n in versions:
        with pytest.raises(ct.ContextTokenError, match="UNKNOWN_KID"):
            verifier.verify(
                _token_with_kid(f"{KEY}/cryptoKeyVersions/{n}"),
                audience="runtime",
            )


def _real_kms_token(fake: FakeKms) -> str:
    signer = cs.KmsContextSigner(f"{KEY}/cryptoKeyVersions/1", client=fake)
    return _envelope_with(cs.ContextTokenIssuer(signer))[0]


def test_bogus_version_flood_after_cache_expiry_does_not_break_the_real_token() -> (
    None
):
    fake = FakeKms()
    now = [1_000_000.0]
    verifier = _kms_verifier(fake, now, max_fetches_per_minute=2)
    token = _real_kms_token(fake)
    assert verifier.verify(token, audience="runtime")
    now[0] += 301  # cache lapsed
    _flood(
        verifier, range(2, 4)
    )  # within the version window: consume the unknown budget
    _flood(
        verifier, range(4, 60)
    )  # beyond configured + 2: never fetched at all
    assert all(int(k.rsplit("/", 1)[1]) <= 3 for k in fake.public_key_calls)
    for _ in range(3):
        _flood(
            verifier, range(2, 4)
        )  # unknown budget exhausted, kids rate-limited
    assert verifier.verify(token, audience="runtime")["tenant_id"] == RS


def test_configured_kid_still_loads_after_a_flood_on_a_cold_verifier() -> None:
    fake = FakeKms()
    now = [1_000_000.0]
    verifier = _kms_verifier(fake, now, max_fetches_per_minute=2)
    _flood(
        verifier, range(2, 4)
    )  # unknown budget gone before the real kid was ever seen
    assert verifier.verify(_real_kms_token(fake), audience="runtime")


def test_transient_fetch_error_serves_stale_then_fails_closed() -> None:
    fake = FakeKms()
    now = [1_000_000.0]
    verifier = _kms_verifier(
        fake, now, key_cache_ttl_seconds=300, max_stale_seconds=600
    )
    token = _real_kms_token(fake)
    assert verifier.verify(token, audience="runtime")
    fake.public_key_fail = kms_rest.KmsUnavailableError(
        "E_KMS_HTTP_503", status=503
    )
    now[0] += 301
    assert verifier.verify(
        token, audience="runtime"
    )  # refresh failed: cached key served
    now[0] += 31
    assert verifier.verify(
        token, audience="runtime"
    )  # still within TTL + max stale
    fake.public_key_fail = None
    now[0] += 31
    assert verifier.verify(
        token, audience="runtime"
    )  # refreshed; the key was never dropped
    fake.public_key_fail = kms_rest.KmsUnavailableError("E_KMS_TIMEOUT")
    now[0] += 300 + 600 + 1
    with pytest.raises(ct.ContextKeyUnavailableError):
        verifier.verify(
            token, audience="runtime"
        )  # too stale: fail closed (503, not 401)


def test_definitive_disabled_evicts_even_within_the_stale_window() -> None:
    fake = FakeKms()
    now = [1_000_000.0]
    verifier = _kms_verifier(fake, now)
    token = _real_kms_token(fake)
    assert verifier.verify(token, audience="runtime")
    fake.disabled.add(f"{KEY}/cryptoKeyVersions/1")
    now[0] += 301
    with pytest.raises(ct.ContextTokenError, match="UNKNOWN_KID"):
        verifier.verify(token, audience="runtime")


def test_unknown_kid_during_kms_outage_is_unavailable_not_forged() -> None:
    fake = FakeKms()
    fake.public_key_fail = kms_rest.KmsUnavailableError(
        "E_KMS_HTTP_503", status=503
    )
    verifier = _kms_verifier(fake, [1_000_000.0])
    with pytest.raises(ct.ContextKeyUnavailableError):
        verifier.verify(_real_kms_token(fake), audience="runtime")


def test_attempt_table_is_pruned_and_bounded() -> None:
    fake = FakeKms()
    now = [1_000_000.0]
    verifier = ct.ContextTokenVerifier(
        ct.KmsPublicKeySource(
            KEY, client=fake
        ),  # no configured version: any version accepted
        max_fetches_per_minute=10**6,
        clock=lambda: now[0],
    )
    for n in range(1, 1500):
        with contextlib.suppress(ct.ContextKeyUnavailableError):
            verifier._key_for(f"{KEY}/cryptoKeyVersions/{n + 1}")
    assert (
        len(verifier._last_attempt)
        <= ct.ContextTokenVerifier._MAX_ATTEMPT_ENTRIES
    )
    now[0] += 31
    verifier._key_for(f"{KEY}/cryptoKeyVersions/99999")
    assert len(verifier._last_attempt) == 1  # expired attempts pruned


def test_prewarm_loads_the_configured_key_and_never_raises() -> None:
    fake = FakeKms()
    verifier = _kms_verifier(fake, [1_000_000.0])
    verifier.prewarm()
    assert fake.public_key_calls == [f"{KEY}/cryptoKeyVersions/1"]
    assert not verifier.may_block(_real_kms_token(fake))
    broken = FakeKms()
    broken.public_key_fail = kms_rest.KmsUnavailableError("E_KMS_TIMEOUT")
    _kms_verifier(broken, [1_000_000.0]).prewarm()  # logs, does not raise


def test_key_outage_on_the_request_path_is_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, restore_trust: Any
) -> None:
    fake = FakeKms()
    issuer = cs.ContextTokenIssuer(
        cs.KmsContextSigner(f"{KEY}/cryptoKeyVersions/1", client=fake)
    )
    monkeypatch.setattr(main.EDGE_VERIFIER, "_context_issuer", issuer)
    fake.public_key_fail = kms_rest.KmsUnavailableError(
        "E_KMS_HTTP_503", status=503
    )
    ct.install_public_key_source(
        ct.KmsPublicKeySource(KEY, configured_version=1, client=fake)
    )
    caller = _caller(client)
    url = "/mcp/v1/jsonrpc"
    resp = client.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers=caller.headers("POST", BASE + url),
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == {"error": "E_CONTEXT_KEY_UNAVAILABLE"}


# --- review fixes: event loop, gating, depth tag, org unit, cache key -----------------------------


async def test_slow_kms_does_not_stall_a_concurrent_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    fake = FakeKms()
    fake.hang_seconds = 1.0
    issuer = cs.ContextTokenIssuer(
        cs.KmsContextSigner(
            f"{KEY}/cryptoKeyVersions/1", client=fake, timeout=5.0
        )
    )
    monkeypatch.setattr(main.EDGE_VERIFIER, "_context_issuer", issuer)
    caller = _caller(TestClient(main.app))
    headers = caller.headers("GET", BASE + "/api/v1/whoami")
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE) as ac:

        async def slow() -> tuple[int, float]:
            t0 = time.perf_counter()
            r = await ac.get("/api/v1/whoami", headers=headers)
            return r.status_code, time.perf_counter() - t0

        async def fast() -> tuple[int, float]:
            await asyncio.sleep(0.2)  # the slow request is now waiting on KMS
            r = await ac.get("/healthz")
            # Measured from the common start: a blocked event loop delays the sleep itself.
            return r.status_code, time.perf_counter() - started

        started = time.perf_counter()
        (slow_status, slow_s), (fast_status, fast_done) = await asyncio.gather(
            slow(), fast()
        )
    assert slow_status == 200
    assert slow_s >= 1.0
    assert fast_status == 200
    assert fast_done < 0.7, fast_done


@pytest.mark.parametrize(
    "env_var", ["K_SERVICE", "CLOUD_RUN_JOB", "KUBERNETES_SERVICE_HOST"]
)
def test_local_signer_refused_on_every_managed_runtime(
    clean_signer_env: pytest.MonkeyPatch, env_var: str
) -> None:
    from app import auth

    assert (
        auth._MANAGED_RUNTIME_ENV is pc.MANAGED_RUNTIME_ENV
    )  # one shared list
    sandbox = pc.load_platform_config("sandbox")
    clean_signer_env.setattr(pc, "get_platform_config", lambda: sandbox)
    for var in pc.MANAGED_RUNTIME_ENV:
        clean_signer_env.delenv(var, raising=False)
    clean_signer_env.setenv("CYMBAL_LOCAL_CONTEXT_SIGNER", "1")
    clean_signer_env.setenv(env_var, "1")
    with pytest.raises(
        RuntimeError, match=r"E_LOCAL_CONTEXT_SIGNER_REFUSED.*managed runtime"
    ):
        cs._build_default_issuer()
    clean_signer_env.setattr(cs, "_PYTEST_MODE", False)
    with pytest.raises(RuntimeError, match="E_LOCAL_CONTEXT_SIGNER_REFUSED"):
        cs.LocalTestSigner()


@pytest.mark.parametrize(
    "drop", ["temp:delegation_sig", "temp:delegation_depth"]
)
def test_missing_depth_tag_or_depth_is_refused(drop: str) -> None:
    state = _envelope().to_adk_state()
    state.pop(drop)
    _assert_every_verifier_rejects(state)


def test_org_unit_is_bound_to_the_signed_token() -> None:
    env = _envelope()
    assert (
        ct.unverified_claims(env.context_token)["org_unit"]
        == env.tenant.org_unit
    )
    _assert_every_verifier_rejects(
        {**env.to_adk_state(), "temp:org_unit": "other-unit"}
    )


def test_issuer_cache_is_keyed_by_signer_kid() -> None:
    signer = cs.LocalTestSigner()
    issuer = cs.ContextTokenIssuer(signer)
    args = {
        "source_jti": "gw-1",
        "not_after": int(time.time()) + 600,
        "tenant_id": RS,
    }
    first, _ = issuer.issue(**args)
    assert issuer.issue(**args)[0] == first  # cached
    new_kid = signer.rotate()
    second, _ = issuer.issue(**args)
    assert second != first
    assert jwt.get_unverified_header(second)["kid"] == new_kid


# --- review fixes: deploy preflight (P2-4) --------------------------------------------------------


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (None, None),
        ("missing", "does not exist"),
        ("disabled", "not ENABLED"),
        ("iam", "roles/cloudkms.signerVerifier"),
        ("wrong_alg", "EC_SIGN_P256_SHA256"),
    ],
)
def test_preflight_reports_clear_causes(
    mutate: str | None, expected: str | None
) -> None:
    from scripts.preflight_context_signing import preflight

    fake = FakeKms()
    version = f"{KEY}/cryptoKeyVersions/1"
    if mutate == "missing":
        version = f"{KEY}/cryptoKeyVersions/5"
        fake.keys[version] = fake.keys[f"{KEY}/cryptoKeyVersions/1"]
        fake.fail = kms_rest.KmsKeyRejectedError("E_KMS_HTTP_404", status=404)
    elif mutate == "disabled":
        fake.fail = kms_rest.KmsKeyRejectedError("E_KMS_HTTP_400", status=400)
    elif mutate == "iam":
        fake.fail = kms_rest.KmsUnavailableError("E_KMS_HTTP_403", status=403)
    elif mutate == "wrong_alg":
        original = fake.get_public_key
        fake.get_public_key = lambda *, name: (original(name=name)[0], "RSA_SIGN_PSS_2048_SHA256")  # type: ignore[method-assign]
    problems = preflight(version, client=fake, timeout=2.0)
    if expected is None:
        assert problems == []
    else:
        assert len(problems) == 1, problems
        assert expected in problems[0], problems


# --- delta review ---------------------------------------------------------------------------------


def test_version_beyond_the_window_is_rejected_without_any_fetch() -> None:
    fake = FakeKms()
    verifier = _kms_verifier(fake, [1_000_000.0])
    with pytest.raises(ct.ContextTokenError, match="UNKNOWN_KID"):
        verifier.verify(
            _token_with_kid(f"{KEY}/cryptoKeyVersions/4"), audience="runtime"
        )
    assert fake.public_key_calls == []  # configured (1) + 3: never fetched
    with pytest.raises(ct.ContextTokenError, match="UNKNOWN_KID"):
        verifier.verify(
            _token_with_kid(f"{KEY}/cryptoKeyVersions/3"), audience="runtime"
        )
    assert fake.public_key_calls == [
        f"{KEY}/cryptoKeyVersions/3"
    ]  # configured + 2: fetched


async def test_cold_key_fetch_in_async_verification_does_not_stall_the_loop() -> (
    None
):
    fake = FakeKms()
    signer = cs.KmsContextSigner(f"{KEY}/cryptoKeyVersions/1", client=fake)
    _, env = _envelope_with(cs.ContextTokenIssuer(signer))
    fake.public_key_hang_seconds = 1.0
    verifier = ct.ContextTokenVerifier(
        ct.KmsPublicKeySource(KEY, configured_version=1, client=fake)
    )
    assert verifier.may_block(env.context_token)

    async def ticker() -> float:
        await asyncio.sleep(0.2)
        return time.perf_counter() - started

    started = time.perf_counter()
    claims, ticked = await asyncio.gather(
        ctx.averify_signed_adk_state(env.to_adk_state(), verifier=verifier),
        ticker(),
    )
    assert claims["tenant_id"] == RS
    assert time.perf_counter() - started >= 1.0
    assert (
        ticked < 0.7
    ), ticked  # the loop kept running while the key was fetched
    assert not verifier.may_block(
        env.context_token
    )  # now cached: no thread hop


def test_rate_limited_known_kid_without_a_stale_key_is_unavailable_not_forged() -> (
    None
):
    fake = FakeKms()
    now = [1_000_000.0]
    verifier = _kms_verifier(fake, now)
    token = _real_kms_token(fake)
    fake.public_key_fail = kms_rest.KmsUnavailableError(
        "E_KMS_HTTP_503", status=503
    )
    for _ in range(
        3
    ):  # first attempt fails, then rate-limited: still 503-class, never 401
        with pytest.raises(ct.ContextKeyUnavailableError):
            verifier.verify(token, audience="runtime")
    assert len(fake.public_key_calls) == 1
    # A cached kid past TTL + max stale while rate-limited: also unavailable, not unknown.
    fake.public_key_fail = None
    now[0] += 31
    assert verifier.verify(token, audience="runtime")
    fake.public_key_fail = kms_rest.KmsUnavailableError("E_KMS_TIMEOUT")
    now[0] += 300 + 600 + 1
    for _ in range(2):
        with pytest.raises(ct.ContextKeyUnavailableError):
            verifier.verify(token, audience="runtime")


@pytest.mark.parametrize("inside_loop", [False, True])
def test_reasoning_engine_does_not_swallow_or_rerun_on_key_outage(
    monkeypatch: pytest.MonkeyPatch, inside_loop: bool
) -> None:
    from agents import reasoning_engine_app as rea

    calls: list[int] = []

    async def outage(*_a: Any, **_k: Any) -> None:
        calls.append(1)
        raise ct.ContextKeyUnavailableError("KMS down")

    monkeypatch.setattr(rea, "enforce_tenant_isolation_interceptor", outage)
    app = rea.CymbalMultiTenantReasoningEngineApp(
        project_id="projects/cymbal-multitenancy-example"
    )
    app.set_up()

    def run() -> None:
        app.query(
            prompt="x", authorization_bearer="Bearer mock-finvault-oidc-jwt"
        )

    if inside_loop:

        async def in_loop() -> None:
            run()

        with pytest.raises(ct.ContextKeyUnavailableError):
            asyncio.run(in_loop())
    else:
        with pytest.raises(ct.ContextKeyUnavailableError):
            run()
    assert calls == [
        1
    ]  # awaited once; the error propagated instead of a second asyncio.run
