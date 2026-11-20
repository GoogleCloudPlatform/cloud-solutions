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

"""ADR-0014 B3: published context-signing keys (JWKS) and the per-audience token exchange.

Proves (ADR-0014 Verification + D3):
- `/.well-known/cymbal-context-jwks.json` publishes public keys only, every usable version in the
  rotation window, with `Cache-Control: max-age` below the rotation overlap, and fails closed.
- The exchange issues single-audience tokens (`broker` or a registered external MCP URL) from a
  valid internal context token only: tenant and `sub` copied, `exp <= min(300 s, remaining)`,
  fresh `jti`, audited; internal audiences and unregistered URLs are refused.
- Cross-use: an MCP-audience (internal) token is rejected for the broker audience; an
  external-audience token is rejected by every internal verifier and on gateway data endpoints;
  the reference external verifier (`mcp_server/external_verifier.py`) rejects internal, broker
  and other-server tokens and every forgery, using only the JWKS.
- Rotation overlap works through the JWKS; a removed kid fails.
- Nothing under `/internal/` is reachable on the public app.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import hmac
import json
import logging
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
from agents.context_exchange import ContextTokenExchange, ExchangeRefused
from app import gateway_tokens as gt
from app import main
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from mcp_server.external_verifier import (
    ExternalContextTokenVerifier,
    ExternalTokenRejected,
    JwksCache,
    JwksUnavailable,
    parse_max_age,
)
from scripts.sandbox_auth import SandboxCaller
from tests.helpers.context_token_fakes import (
    KEY,
    FakeKms,
    _assert_every_verifier_rejects,
    _compact,
    _default_signer,
    _envelope,
    _es256,
    _with_token,
)

REPO = Path(__file__).resolve().parents[2]
FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
FV_MCP = "https://mcp.finvault.example/mcp"
JWKS_PATH = "/.well-known/cymbal-context-jwks.json"
BASE = "http://testserver"
JWKS_URL = "https://gateway.example" + JWKS_PATH


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


@pytest.fixture
def restore_trust() -> Any:
    issuer = cs.get_context_token_issuer()
    yield
    with cs._ISSUER_LOCK:
        cs._ISSUER = issuer
    ct.install_public_key_source(issuer.signer.public_keys)  # type: ignore[attr-defined]


def _fv_envelope(**kw: Any) -> ctx.ContextEnvelope:
    return _envelope(FV, "alice@finvault.com", **kw)


def _exchange() -> ContextTokenExchange:
    return ContextTokenExchange()


def _testclient_fetcher(client: TestClient) -> Any:
    def fetch(_url: str) -> tuple[dict[str, Any], int]:
        resp = client.get(JWKS_PATH)
        resp.raise_for_status()
        return resp.json(), parse_max_age(
            resp.headers.get("cache-control"), 300
        )

    return fetch


def _external(
    client: TestClient, audience: str = FV_MCP, **kw: Any
) -> ExternalContextTokenVerifier:
    jwks = JwksCache(JWKS_URL, fetch=_testclient_fetcher(client), **kw)
    return ExternalContextTokenVerifier(audience=audience, jwks=jwks)


def _derived(
    audience: str = FV_MCP, **kw: Any
) -> tuple[str, dict[str, Any], ctx.ContextEnvelope]:
    env = _fv_envelope(**kw)
    token, claims = _exchange().exchange(env.context_token, audience=audience)
    return token, claims, env


# --- JWKS -----------------------------------------------------------------------------------------


def test_jwks_publishes_public_keys_only_with_cache_headers(
    client: TestClient,
) -> None:
    resp = client.get(JWKS_PATH)
    assert resp.status_code == 200
    assert (
        resp.headers["cache-control"]
        == f"public, max-age={ct.JWKS_MAX_AGE_SECONDS}"
    )
    # Rotation overlap rule: overlap >= JWKS max-age + max token lifetime; max-age stays short.
    assert ct.JWKS_MAX_AGE_SECONDS <= ct.CONTEXT_TOKEN_MAX_TTL_SECONDS
    keys = resp.json()["keys"]
    signer = _default_signer()
    assert [k["kid"] for k in keys] == [signer.kid]
    for jwk in keys:
        assert set(jwk) == {
            "kty",
            "crv",
            "x",
            "y",
            "kid",
            "alg",
            "use",
        }  # no "d", ever
        assert (jwk["kty"], jwk["crv"], jwk["alg"], jwk["use"]) == (
            "EC",
            "P-256",
            "ES256",
            "sig",
        )
    published = jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(keys[0]))
    expected = signer.public_keys.fetch(signer.kid)
    assert published.public_numbers() == expected.public_numbers()  # type: ignore[union-attr]


def test_jwks_needs_no_authentication(client: TestClient) -> None:
    assert client.get(JWKS_PATH, headers={}).status_code == 200


def test_jwks_rotation_overlap_then_removed_kid(
    client: TestClient, restore_trust: Any
) -> None:
    signer = cs.LocalTestSigner()
    ct.install_public_key_source(signer.public_keys)
    exchange = ContextTokenExchange(issuer=cs.ContextTokenIssuer(signer))
    internal = cs.ContextTokenIssuer(signer)

    def derived() -> str:
        env = ctx.EdgeAuthVerifier(context_issuer=internal).exchange_obo_token(
            verified_idp_claims={
                "iss": str(ctx.TENANT_DIRECTORY[FV]["iss"]),
                "sub": "alice@finvault.com",
                "tenant_id": FV,
                "user_role": "sre_admin",
                "exp": int(time.time()) + 600,
                "jti": f"gw-{uuid.uuid4().hex}",
            },
            dpop_proof={"jkt": "k", "jti": uuid.uuid4().hex},
            session_id="s",
        )
        return exchange.exchange(env.context_token, audience=FV_MCP)[0]

    old_token, old_kid = derived(), signer.kid
    new_kid = signer.rotate()
    new_token = derived()
    assert {k["kid"] for k in client.get(JWKS_PATH).json()["keys"]} == {
        old_kid,
        new_kid,
    }
    verifier = _external(client)
    assert (
        verifier.verify(old_token)["tenant_id"] == FV
    )  # overlap: both kids valid
    assert verifier.verify(new_token)["tenant_id"] == FV
    signer.retire(old_kid)
    assert {k["kid"] for k in client.get(JWKS_PATH).json()["keys"]} == {new_kid}
    fresh = _external(client)
    with pytest.raises(ExternalTokenRejected, match="E_TOKEN_UNKNOWN_KID"):
        fresh.verify(old_token)
    assert fresh.verify(new_token)


class _FlakyKms(FakeKms):
    def __init__(self, versions: int) -> None:
        super().__init__(versions)
        self.fail_names: set[str] = set()

    def get_public_key(self, *, name: str) -> tuple[str, str]:
        if name in self.fail_names:
            self.public_key_calls.append(name)
            raise kms_rest.KmsUnavailableError("E_KMS_HTTP_503", status=503)
        return super().get_public_key(name=name)


def test_jwks_kms_window_omits_missing_and_disabled_versions(
    client: TestClient, restore_trust: Any
) -> None:
    fake = _FlakyKms(versions=3)
    v = {n: f"{KEY}/cryptoKeyVersions/{n}" for n in range(1, 6)}
    source = ct.KmsPublicKeySource(KEY, configured_version=2, client=fake)
    assert source.jwks_kids() == (
        v[1],
        v[2],
        v[3],
        v[4],
    )  # configured - 1 .. + 2
    fake.disabled.add(v[1])
    ct.install_public_key_source(source)
    resp = client.get(JWKS_PATH)
    assert resp.status_code == 200
    assert [k["kid"] for k in resp.json()["keys"]] == [
        v[2],
        v[3],
    ]  # 1 disabled, 4 missing
    assert v[5] not in fake.public_key_calls  # never probed outside the window


def test_jwks_fails_closed_when_the_configured_key_is_unavailable(
    client: TestClient, restore_trust: Any
) -> None:
    fake = _FlakyKms(versions=2)
    fake.fail_names = {f"{KEY}/cryptoKeyVersions/1"}
    ct.install_public_key_source(
        ct.KmsPublicKeySource(KEY, configured_version=1, client=fake)
    )
    resp = client.get(JWKS_PATH)
    assert resp.status_code == 503
    assert resp.headers["cache-control"] == "no-store"
    assert resp.json()["detail"] == {"error": "E_CONTEXT_KEY_UNAVAILABLE"}


def test_jwks_survives_a_transient_failure_on_a_non_configured_version(
    client: TestClient, restore_trust: Any
) -> None:
    fake = _FlakyKms(versions=2)
    fake.fail_names = {f"{KEY}/cryptoKeyVersions/2"}
    ct.install_public_key_source(
        ct.KmsPublicKeySource(KEY, configured_version=1, client=fake)
    )
    resp = client.get(JWKS_PATH)
    assert resp.status_code == 200
    assert [k["kid"] for k in resp.json()["keys"]] == [
        f"{KEY}/cryptoKeyVersions/1"
    ]


def test_jwks_unconfigured_is_503(
    client: TestClient, restore_trust: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ct, "resolve_context_signing_kms_key", lambda: None)
    ct.install_public_key_source(None)
    assert client.get(JWKS_PATH).status_code == 503


# --- the exchange --------------------------------------------------------------------------------


def test_exchange_copies_identity_and_limits_lifetime(
    caplog: pytest.LogCaptureFixture,
) -> None:
    env = _fv_envelope()
    source = ct.unverified_claims(env.context_token)
    exchange = _exchange()
    with caplog.at_level(logging.INFO, logger="cymbal.audit.context_exchange"):
        token, claims = exchange.exchange(env.context_token, audience=FV_MCP)
        token2, claims2 = exchange.exchange(env.context_token, audience=FV_MCP)
    now = int(time.time())
    assert jwt.get_unverified_header(token)["typ"] == "ctx+jwt"
    assert claims["aud"] == FV_MCP  # exactly one audience, a string
    assert claims["tenant_id"] == FV
    assert claims["sub"] == "alice@finvault.com"
    assert claims["max_delegation_depth"] == source["max_delegation_depth"]
    assert claims["src_jti"] == source["jti"]
    assert claims["exp"] <= min(now + 300, source["exp"])
    assert claims["exp"] - claims["iat"] <= 300
    assert (
        len({claims["jti"], claims2["jti"], source["jti"]}) == 3
    )  # fresh jti every time
    for leaked in ("scopes", "cmek_key_name", "cnf", "user_role", "session_id"):
        assert leaked not in claims  # only what a downstream verifier needs
    lines = [json.loads(r.getMessage()) for r in caplog.records]
    assert [line["jti"] for line in lines] == [claims["jti"], claims2["jti"]]
    assert all(
        line["tenant_id"] == FV
        and line["audience"] == FV_MCP
        and line["src_jti"] == source["jti"]
        for line in lines
    )
    assert all(
        token not in r.getMessage() and token2 not in r.getMessage()
        for r in caplog.records
    )


def test_exchange_exp_never_exceeds_the_presented_token() -> None:
    now = int(time.time())
    _, claims, env = _derived(exp=now + 60)
    assert (
        claims["exp"]
        <= ct.unverified_claims(env.context_token)["exp"]
        <= now + 60
    )
    _, long_claims, _ = _derived(exp=now + 3600)
    assert long_claims["exp"] <= int(time.time()) + 300


def test_exchange_for_the_broker_audience() -> None:
    token, claims, _ = _derived(audience=ct.AUDIENCE_BROKER)
    assert claims["aud"] == "broker"
    verified = ct.get_context_verifier().verify(
        token, audience=ct.AUDIENCE_BROKER
    )
    assert verified["tenant_id"] == FV


@pytest.mark.parametrize("audience", ["runtime", "mcp", ""])
def test_exchange_never_issues_internal_audiences(audience: str) -> None:
    with pytest.raises(ExchangeRefused, match="E_EXCHANGE_AUDIENCE_INTERNAL"):
        _exchange().exchange(_fv_envelope().context_token, audience=audience)
    with pytest.raises(PermissionError, match="E_EXCHANGE_AUDIENCE_INTERNAL"):
        cs.get_context_token_issuer().issue_derived(
            audience=audience or "runtime",
            not_after=int(time.time()) + 60,
            max_ttl_seconds=60,
            tenant_id=FV,
        )


@pytest.mark.parametrize(
    "audience",
    [
        "https://mcp.evil.example/mcp",  # not registered anywhere
        "https://mcp.finvault.example/mcp/",  # not an exact match
        "https://mcp.finvault.example/other",
    ],
)
def test_exchange_refuses_unregistered_audiences(audience: str) -> None:
    with pytest.raises(
        ExchangeRefused, match="E_EXCHANGE_AUDIENCE_NOT_REGISTERED"
    ):
        _exchange().exchange(_fv_envelope().context_token, audience=audience)


def test_a_tenant_cannot_get_a_token_for_another_tenants_server() -> None:
    rs = _envelope(RS)
    with pytest.raises(
        ExchangeRefused, match="E_EXCHANGE_AUDIENCE_NOT_REGISTERED"
    ):
        _exchange().exchange(rs.context_token, audience=FV_MCP)


def test_offboarded_tenant_gets_no_external_tokens() -> None:
    exchange = ContextTokenExchange(audiences_for_tenant=lambda _t: ())
    with pytest.raises(
        ExchangeRefused, match="E_EXCHANGE_AUDIENCE_NOT_REGISTERED"
    ):
        exchange.exchange(_fv_envelope().context_token, audience=FV_MCP)


def test_exchange_refuses_anything_but_a_valid_internal_token() -> None:
    env = _fv_envelope()
    derived_mcp, _ = _exchange().exchange(env.context_token, audience=FV_MCP)
    derived_broker, _ = _exchange().exchange(
        env.context_token, audience="broker"
    )
    gateway_token, _ = gt.get_token_service().issue(env)
    claims = ct.unverified_claims(env.context_token)
    other_key = _compact(
        {"alg": "ES256", "typ": "ctx+jwt", "kid": _default_signer().kid},
        claims,
        _es256(ec.generate_private_key(ec.SECP256R1())),
    )
    now = int(time.time())
    expired = _compact(
        {"alg": "ES256", "typ": "ctx+jwt", "kid": _default_signer().kid},
        {**claims, "iat": now - 700, "exp": now - 100},
        _default_signer().sign,
    )
    for bad, code in [
        (
            derived_mcp,
            "E_CONTEXT_TOKEN_AUDIENCE",
        ),  # no re-exchange of derived tokens
        (derived_broker, "E_CONTEXT_TOKEN_AUDIENCE"),
        (gateway_token, "E_CONTEXT_TOKEN_TYPE"),
        (other_key, "E_CONTEXT_TOKEN_SIGNATURE"),
        (expired, "E_CONTEXT_TOKEN_EXPIRED"),
        ("not-a-token", "E_CONTEXT_TOKEN_MALFORMED"),
    ]:
        with pytest.raises(ExchangeRefused) as info:
            _exchange().exchange(bad, audience=FV_MCP)
        assert info.value.code == code


# --- cross-use ------------------------------------------------------------------------------------


def test_internal_mcp_audience_token_is_rejected_for_the_broker_audience() -> (
    None
):
    env = _fv_envelope()
    with pytest.raises(ct.ContextTokenError, match="E_CONTEXT_TOKEN_AUDIENCE"):
        ct.get_context_verifier().verify(
            env.context_token, audience=ct.AUDIENCE_BROKER
        )
    external, _ = _exchange().exchange(env.context_token, audience=FV_MCP)
    with pytest.raises(ct.ContextTokenError, match="E_CONTEXT_TOKEN_AUDIENCE"):
        ct.get_context_verifier().verify(external, audience=ct.AUDIENCE_BROKER)


def test_broker_token_is_rejected_for_an_external_audience() -> None:
    broker, _, _ = _derived(audience="broker")
    with pytest.raises(ct.ContextTokenError, match="E_CONTEXT_TOKEN_AUDIENCE"):
        ct.get_context_verifier().verify(broker, audience=FV_MCP)


@pytest.mark.parametrize("audience", [FV_MCP, "broker"])
def test_derived_tokens_are_rejected_by_every_internal_verifier(
    audience: str,
) -> None:
    token, _, env = _derived(audience=audience)
    for internal in ("runtime", "mcp"):
        with pytest.raises(
            ct.ContextTokenError, match="E_CONTEXT_TOKEN_AUDIENCE"
        ):
            ct.get_context_verifier().verify(token, audience=internal)
    _assert_every_verifier_rejects(_with_token(env.to_adk_state(), token))


def test_derived_token_with_extra_audiences_is_refused() -> None:
    env = _fv_envelope()
    _, claims = _exchange().exchange(env.context_token, audience=FV_MCP)
    multi = _compact(
        {"alg": "ES256", "typ": "ctx+jwt", "kid": _default_signer().kid},
        {**claims, "aud": [FV_MCP, "broker"]},
        _default_signer().sign,
    )
    with pytest.raises(ct.ContextTokenError, match="E_CONTEXT_TOKEN_CLAIMS"):
        ct.get_context_verifier().verify(multi, audience=FV_MCP)


def test_derived_tokens_are_rejected_on_gateway_data_endpoints(
    client: TestClient,
) -> None:
    caller = SandboxCaller(
        client, tenant_id=FV, sub=f"u-{uuid.uuid4().hex[:6]}", role="sre_admin"
    )
    _ = caller.access_token
    for audience in (FV_MCP, "broker"):
        token, _, _ = _derived(audience=audience)
        for path, method in (
            ("/api/v1/whoami", "GET"),
            ("/mcp/v1/jsonrpc", "POST"),
        ):
            headers = {
                "Authorization": f"DPoP {token}",
                "DPoP": caller.dpop_proof(
                    method, BASE + path, access_token=token
                ),
            }
            resp = client.request(
                method,
                path,
                headers=headers,
                json={} if method == "POST" else None,
            )
            assert resp.status_code == 401, (audience, path)


# --- the reference external verifier -------------------------------------------------------------


def test_external_verifier_accepts_its_own_audience_only(
    client: TestClient,
) -> None:
    token, _, env = _derived()
    verifier = _external(client)
    assert verifier.verify_authorization(f"Bearer {token}")["tenant_id"] == FV
    broker, _, _ = _derived(audience="broker")
    for bad, code in [
        (env.context_token, "E_TOKEN_AUDIENCE"),  # internal runtime/mcp token
        (broker, "E_TOKEN_AUDIENCE"),
    ]:
        with pytest.raises(ExternalTokenRejected) as info:
            verifier.verify(bad)
        assert info.value.code == code
    other_server = _external(client, audience="https://mcp.other.example/mcp")
    with pytest.raises(ExternalTokenRejected, match="E_TOKEN_AUDIENCE"):
        other_server.verify(token)
    with pytest.raises(ExternalTokenRejected, match="E_TOKEN_MISSING"):
        verifier.verify_authorization(f"DPoP {token}")


def _external_forgeries(token: str) -> dict[str, str]:
    claims = ct.unverified_claims(token)
    signer = _default_signer()
    header = {"alg": "ES256", "typ": "ctx+jwt", "kid": signer.kid}
    other = ec.generate_private_key(ec.SECP256R1())
    pem = signer.public_keys.fetch(signer.kid).public_bytes(  # type: ignore[union-attr]
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    now = int(time.time())
    return {
        "other_key": _compact(header, claims, _es256(other)),
        "alg_none": _compact({**header, "alg": "none"}, claims, lambda _: b""),
        "hs256_public_key": _compact(
            {**header, "alg": "HS256"},
            claims,
            lambda d: hmac.new(pem, d, hashlib.sha256).digest(),
        ),
        "unknown_kid": _compact(
            {**header, "kid": "nope"}, claims, _es256(other)
        ),
        "expired": _compact(
            header, {**claims, "iat": now - 400, "exp": now - 100}, signer.sign
        ),
        "wrong_iss": _compact(
            header, {**claims, "iss": gt.GATEWAY_ISSUER}, signer.sign
        ),
        "too_long": _compact(
            header, {**claims, "iat": now, "exp": now + 3600}, signer.sign
        ),
        "typ_at_jwt": _compact(
            {**header, "typ": "at+jwt"}, claims, signer.sign
        ),
        "embedded_jwk": _compact(
            {
                **header,
                "jwk": ctx.AsymmetricDPoPProvider.public_key_to_jwk(
                    other.public_key()
                ),
            },
            claims,
            _es256(other),
        ),
        "no_tenant": _compact(
            header,
            {k: v for k, v in claims.items() if k != "tenant_id"},
            signer.sign,
        ),
    }


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("other_key", "E_TOKEN_INVALID"),
        ("alg_none", "E_TOKEN_ALG"),
        ("hs256_public_key", "E_TOKEN_ALG"),
        ("unknown_kid", "E_TOKEN_UNKNOWN_KID"),
        ("expired", "E_TOKEN_EXPIRED"),
        ("wrong_iss", "E_TOKEN_INVALID"),
        ("too_long", "E_TOKEN_LIFETIME"),
        ("typ_at_jwt", "E_TOKEN_TYPE"),
        ("embedded_jwk", "E_TOKEN_HEADER"),
        ("no_tenant", "E_TOKEN_INVALID"),
    ],
)
def test_external_verifier_rejects_forgeries(
    client: TestClient, case: str, code: str
) -> None:
    token, _, _ = _derived()
    with pytest.raises(ExternalTokenRejected) as info:
        _external(client).verify(_external_forgeries(token)[case])
    assert info.value.code == code


def test_external_jwks_cache_honours_max_age_and_rate_limits(
    client: TestClient,
) -> None:
    now = [1_000_000.0]
    fetcher = _testclient_fetcher(client)
    calls: list[int] = []

    def counting(url: str) -> tuple[dict[str, Any], int]:
        calls.append(1)
        return fetcher(url)

    jwks = JwksCache(
        JWKS_URL, fetch=counting, clock=lambda: now[0], min_refetch_seconds=30
    )
    verifier = ExternalContextTokenVerifier(audience=FV_MCP, jwks=jwks)
    token, _, _ = _derived()
    for _ in range(3):
        verifier.verify(token)
    assert len(calls) == 1  # cached for max-age
    forged = _external_forgeries(token)["unknown_kid"]
    for _ in range(5):
        with pytest.raises(ExternalTokenRejected, match="UNKNOWN_KID"):
            verifier.verify(forged)
    assert (
        len(calls) == 1
    )  # unknown-kid refetch is rate-limited (last fetch < 30 s ago)
    now[0] += ct.JWKS_MAX_AGE_SECONDS + 1
    verifier.verify(token)
    assert len(calls) == 2  # expired: refetched


def test_external_jwks_outage_serves_stale_then_fails_closed(
    client: TestClient,
) -> None:
    now = [1_000_000.0]
    fetcher = _testclient_fetcher(client)
    down = [False]

    def fetch(url: str) -> tuple[dict[str, Any], int]:
        if down[0]:
            raise OSError("jwks unreachable")
        return fetcher(url)

    jwks = JwksCache(
        JWKS_URL, fetch=fetch, clock=lambda: now[0], max_stale_seconds=600
    )
    verifier = ExternalContextTokenVerifier(audience=FV_MCP, jwks=jwks)
    token, _, _ = _derived()
    verifier.verify(token)
    down[0] = True
    now[0] += ct.JWKS_MAX_AGE_SECONDS + 1
    assert verifier.verify(token)  # stale key set served during the outage
    now[0] += 600
    with pytest.raises(JwksUnavailable):
        verifier.verify(token)


def test_external_verifier_is_standalone_and_public_key_only() -> None:
    tree = ast.parse((REPO / "mcp_server" / "external_verifier.py").read_text())
    imported = {
        a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import)
        for a in n.names
    } | {
        n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
    }
    assert not {
        m for m in imported if m.startswith(("agents", "app", "mcp_server"))
    }
    text = (REPO / "mcp_server" / "external_verifier.py").read_text()
    for needle in (
        "private_key",
        "load_pem_private",
        "generate_private_key",
        "HS256",
    ):
        assert needle not in text


# --- ingress and config ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["/internal/v1/context-token:exchange", "/internal", "/internal/"]
)
def test_nothing_internal_is_reachable_on_public_ingress(
    client: TestClient, path: str
) -> None:
    assert client.post(path, json={}).status_code == 404
    assert client.get(path).status_code == 404
    assert not [
        r
        for r in main.app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/internal")
    ]


@pytest.mark.parametrize(
    "url",
    [
        "http://mcp.example/mcp",
        "https://user:pw@mcp.example/mcp",
        "https://mcp.example/#x",
        "mcp",
    ],
)
def test_external_mcp_audiences_must_be_plain_https(url: str) -> None:
    data = pc.load_platform_config("sandbox").model_dump()
    data["tenants"][0]["external_mcp_audiences"] = [url]
    with pytest.raises(ValueError, match="external_mcp_audiences"):
        pc.PlatformConfig.model_validate(data)


def test_sandbox_registers_one_synthetic_external_mcp_server() -> None:
    assert ctx.TENANT_DIRECTORY[FV]["external_mcp_audiences"] == (FV_MCP,)
    assert ctx.TENANT_DIRECTORY[RS]["external_mcp_audiences"] == ()


# --- review fixes ---------------------------------------------------------------------------------


@pytest.mark.parametrize("audience", ["broker", FV_MCP])
def test_offboarded_tenant_is_refused_for_every_audience(audience: str) -> None:
    env = _fv_envelope()
    saved = dict(ctx.TENANT_DIRECTORY[FV])
    ctx.offboard_tenant(FV)
    try:
        with pytest.raises(ExchangeRefused) as info:
            _exchange().exchange(env.context_token, audience=audience)
        assert info.value.code == "E_EXCHANGE_TENANT_OFFBOARDED"
    finally:
        ctx.TENANT_DIRECTORY[FV] = saved


def test_issuance_is_bounded_per_source_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    now = [1_000_000.0]
    exchange = ContextTokenExchange(
        max_per_source_per_minute=20, clock=lambda: now[0]
    )
    env, other = _fv_envelope(), _fv_envelope()
    for _ in range(20):
        exchange.exchange(env.context_token, audience="broker")
    with (
        caplog.at_level(logging.INFO, logger="cymbal.audit.context_exchange"),
        pytest.raises(ExchangeRefused, match="E_EXCHANGE_RATE_LIMITED"),
    ):
        exchange.exchange(env.context_token, audience=FV_MCP)
    refusal = json.loads(caplog.records[-1].getMessage())
    assert refusal["event"] == "context_token_exchange_refused"
    assert refusal["code"] == "E_EXCHANGE_RATE_LIMITED"
    assert exchange.exchange(
        other.context_token, audience="broker"
    )  # other source unaffected
    now[0] += 61
    assert exchange.exchange(
        env.context_token, audience="broker"
    )  # window slid


def test_refusals_and_issuances_are_audited_with_a_pseudonymous_user_ref(
    caplog: pytest.LogCaptureFixture,
) -> None:
    env = _envelope(RS)
    exchange = ContextTokenExchange(user_ref=lambda t, s: f"ref({t})")
    with caplog.at_level(logging.INFO, logger="cymbal.audit.context_exchange"):
        with pytest.raises(ExchangeRefused):
            exchange.exchange(
                env.context_token, audience=FV_MCP
            )  # another tenant's server
        with pytest.raises(ExchangeRefused):
            exchange.exchange("garbage", audience="broker")
        token, claims = exchange.exchange(env.context_token, audience="broker")
    lines = [json.loads(r.getMessage()) for r in caplog.records]
    assert lines[0] == {
        "event": "context_token_exchange_refused",
        "code": "E_EXCHANGE_AUDIENCE_NOT_REGISTERED",
        "audience": FV_MCP,
        "tenant_id": RS,
        "user_ref": f"ref({RS})",
        "src_jti": ct.unverified_claims(env.context_token)["jti"],
    }
    assert lines[1]["code"] == "E_CONTEXT_TOKEN_MALFORMED"
    assert "tenant_id" not in lines[1]
    assert lines[2]["event"] == "context_token_exchange"
    assert lines[2]["user_ref"] == f"ref({RS})"
    assert lines[2]["jti"] == claims["jti"]
    text = " ".join(r.getMessage() for r in caplog.records)
    assert token not in text
    assert env.context_token not in text
    assert "bob@" not in text


def test_gateway_wires_its_log_user_ref_into_the_exchange() -> None:
    from agents.context_exchange import get_context_token_exchange

    assert get_context_token_exchange().user_ref is gt.log_user_ref


def test_external_verifier_rejects_extra_audiences(client: TestClient) -> None:
    _, claims, _ = _derived()
    multi = _compact(
        {"alg": "ES256", "typ": "ctx+jwt", "kid": _default_signer().kid},
        {**claims, "aud": [FV_MCP, "https://other.example/mcp"]},
        _default_signer().sign,
    )
    with pytest.raises(ExternalTokenRejected, match="E_TOKEN_AUDIENCE"):
        _external(client).verify(multi)


def test_external_jwks_skips_a_malformed_key_and_requires_https(
    client: TestClient,
) -> None:
    good = _testclient_fetcher(client)

    def fetch(url: str) -> tuple[dict[str, Any], int]:
        doc, max_age = good(url)
        bad = [
            {"kty": "EC", "crv": "P-256", "kid": "bad", "x": "!!", "y": "??"},
            {"kty": "RSA"},
        ]
        return {"keys": bad + doc["keys"]}, max_age

    verifier = ExternalContextTokenVerifier(
        audience=FV_MCP, jwks=JwksCache(JWKS_URL, fetch=fetch)
    )
    token, _, _ = _derived()
    assert verifier.verify(token)["tenant_id"] == FV
    with pytest.raises(ValueError, match="https"):
        JwksCache("http://gateway.example" + JWKS_PATH, fetch=fetch)


def test_external_jwks_refresh_is_single_flight(client: TestClient) -> None:
    import threading

    good = _testclient_fetcher(client)
    doc = good(JWKS_URL)
    calls: list[int] = []

    def slow(_url: str) -> tuple[dict[str, Any], int]:
        calls.append(1)
        time.sleep(0.3)
        return doc

    jwks = JwksCache(JWKS_URL, fetch=slow)
    kid = _default_signer().kid
    results: list[Any] = []
    threads = [
        threading.Thread(target=lambda: results.append(jwks.get(kid)))
        for _ in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert len(results) == 6
    assert all(r is not None for r in results)


def test_internal_guard_hides_even_a_registered_internal_route(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/internal/x")
    async def _leak() -> dict[str, str]:
        return {"leaked": "yes"}

    monkeypatch.setattr(
        main.app.router, "routes", [*main.app.router.routes, *router.routes]
    )
    resp = client.get("/internal/x")
    assert resp.status_code == 404
    assert "leaked" not in resp.text


def test_jwks_is_503_when_the_configured_version_is_disabled(
    client: TestClient, restore_trust: Any
) -> None:
    fake = _FlakyKms(versions=3)
    fake.disabled.add(f"{KEY}/cryptoKeyVersions/2")  # the signing version
    ct.install_public_key_source(
        ct.KmsPublicKeySource(KEY, configured_version=2, client=fake)
    )
    resp = client.get(JWKS_PATH)
    assert resp.status_code == 503  # even though versions 1 and 3 are enabled
    assert resp.headers["cache-control"] == "no-store"


# --- follow-ups -----------------------------------------------------------------------------------


class _Boom(BaseException):
    pass


def test_jwks_fetch_state_resets_even_on_base_exception(
    client: TestClient,
) -> None:
    import threading

    good = _testclient_fetcher(client)
    calls: list[int] = []

    def fetch(url: str) -> tuple[dict[str, Any], int]:
        calls.append(1)
        if len(calls) == 1:
            time.sleep(0.2)
            raise _Boom()
        return good(url)

    now = [1_000_000.0]
    jwks = JwksCache(JWKS_URL, fetch=fetch, clock=lambda: now[0])
    kid = _default_signer().kid
    waited: list[float] = []

    def waiter() -> None:
        time.sleep(
            0.05
        )  # the leader's first fetch is in flight and nothing is loaded yet
        started = time.perf_counter()
        with contextlib.suppress(JwksUnavailable):
            jwks.get(kid)
        waited.append(time.perf_counter() - started)

    t = threading.Thread(
        target=waiter, daemon=True
    )  # a regression must not hang the run
    t.start()
    with pytest.raises(_Boom):
        jwks.get(kid)
    t.join(timeout=5)
    assert waited
    assert waited[0] < 2.0
    now[0] += 31
    assert (
        jwks.get(kid) is not None
    )  # not stuck "fetching": the next refresh works


def test_signing_failure_refunds_the_rate_slot_and_is_audited(
    caplog: pytest.LogCaptureFixture,
) -> None:
    real = cs.get_context_token_issuer()

    class _FlakyIssuer:
        fail = True

        def issue_derived(self, **kw: Any) -> tuple[str, dict[str, Any]]:
            if self.fail:
                raise cs.ContextSigningUnavailableError(
                    "E_CONTEXT_SIGNING_UNAVAILABLE: KMS"
                )
            return real.issue_derived(**kw)

    issuer = _FlakyIssuer()
    exchange = ContextTokenExchange(issuer=issuer, max_per_source_per_minute=1)  # type: ignore[arg-type]
    env = _fv_envelope()
    with caplog.at_level(logging.INFO, logger="cymbal.audit.context_exchange"):
        for _ in range(3):  # each failure gives its slot back
            with pytest.raises(cs.ContextSigningUnavailableError):
                exchange.exchange(env.context_token, audience="broker")
    lines = [json.loads(r.getMessage()) for r in caplog.records]
    assert [line["event"] for line in lines] == [
        "context_token_exchange_failed"
    ] * 3
    assert lines[0]["code"] == "E_CONTEXT_SIGNING_UNAVAILABLE"
    assert lines[0]["tenant_id"] == FV
    issuer.fail = False
    assert exchange.exchange(
        env.context_token, audience="broker"
    )  # the slot is still free
    with pytest.raises(ExchangeRefused, match="E_EXCHANGE_RATE_LIMITED"):
        exchange.exchange(env.context_token, audience="broker")
