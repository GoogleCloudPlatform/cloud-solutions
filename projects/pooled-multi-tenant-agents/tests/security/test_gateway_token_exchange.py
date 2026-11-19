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
# pylint: disable=redefined-outer-name,unused-variable

"""Gateway token exchange and key-bound requests (roadmap step 1, PR 2a; RFC 9449).

Proves:
- identity comes only from a gateway token issued after Hop 0, never from headers or body;
- a stolen gateway token is useless without the client's key (`cnf.jkt`);
- proofs are bound to method, URL and token (`ath`), are recent, and are single use;
- an ID token copied after the real client exchanged it cannot be bound to another key;
- tampered or expired tokens and bad subject tokens get a plain 401 (code only);
- customer environments refuse to run without a shared signing key; instances that share the
  key accept each other's tokens; the request context is cleared after every request.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from agents import context as ctx
from agents import platform_config as pc
from agents.context import AsymmetricDPoPProvider
from app import gateway_tokens as gt
from app.main import app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from scripts.sandbox_auth import SandboxCaller

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
WHOAMI = "/api/v1/whoami"
BASE = "http://testserver"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _caller(
    client: TestClient, tenant: str = FV, role: str = "compliance_officer"
) -> SandboxCaller:
    return SandboxCaller(
        client, tenant_id=tenant, sub=f"user-{uuid.uuid4().hex[:6]}", role=role
    )


def _get(client: TestClient, headers: dict[str, str]) -> Any:
    return client.get(WHOAMI, headers=headers)


def test_identity_comes_from_the_gateway_token(client: TestClient) -> None:
    caller = _caller(client, RS, "read_only_analyst")
    resp = _get(client, caller.headers("GET", BASE + WHOAMI))
    assert resp.status_code == 200
    assert resp.json() == {
        "tenant_id": RS,
        "user_role": "read_only_analyst",
        "idp_provider": "microsoft_entra_oidc",
        "identity_source": "HOP0_VERIFIED",
    }


def test_spoofed_tenancy_headers_are_ignored(client: TestClient) -> None:
    caller = _caller(client, RS)
    headers = {
        **caller.headers("GET", BASE + WHOAMI),
        "X-Tenant-ID": FV,
        "X-OBO-Role": "x",
    }
    assert _get(client, headers).json()["tenant_id"] == RS


def test_missing_or_wrong_scheme_is_401_with_dpop_challenge(
    client: TestClient,
) -> None:
    resp = client.get(WHOAMI)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("DPoP")
    caller = _caller(client)
    h = caller.headers("GET", BASE + WHOAMI)
    h["Authorization"] = h["Authorization"].replace("DPoP ", "Bearer ")
    assert _get(client, h).json()["detail"] == {"error": "E_TOKEN_MISSING"}


def test_stolen_gateway_token_fails_with_the_thiefs_key(
    client: TestClient,
) -> None:
    victim, thief = _caller(client), _caller(client)
    token = victim.access_token
    thief_proof = thief.dpop_proof("GET", BASE + WHOAMI, access_token=token)
    resp = _get(client, {"Authorization": f"DPoP {token}", "DPoP": thief_proof})
    assert resp.status_code == 401
    assert resp.json()["detail"] == {"error": "E_DPOP_KEY_MISMATCH"}


@pytest.mark.parametrize(
    ("method", "url", "with_ath", "code"),
    [
        ("POST", BASE + WHOAMI, True, "E_DPOP_INVALID"),  # wrong method
        ("GET", BASE + "/api/v1/other", True, "E_DPOP_INVALID"),  # wrong URL
        (
            "GET",
            BASE + WHOAMI,
            False,
            "E_DPOP_ATH_MISMATCH",
        ),  # not bound to the token
    ],
)
def test_proof_must_match_method_url_and_token(
    client: TestClient, method: str, url: str, with_ath: bool, code: str
) -> None:
    caller = _caller(client)
    token = caller.access_token
    proof = caller.dpop_proof(
        method, url, access_token=token if with_ath else None
    )
    resp = _get(client, {"Authorization": f"DPoP {token}", "DPoP": proof})
    assert (resp.status_code, resp.json()["detail"]) == (401, {"error": code})


def test_proofs_are_single_use(client: TestClient) -> None:
    caller = _caller(client)
    headers = caller.headers("GET", BASE + WHOAMI)
    assert _get(client, headers).status_code == 200
    replay = _get(client, headers)
    assert (replay.status_code, replay.json()["detail"]) == (
        401,
        {"error": "E_DPOP_REPLAY"},
    )


def test_stale_proof_is_rejected(client: TestClient) -> None:
    caller = _caller(client)
    token = caller.access_token
    key = caller._dpop_key
    stale = jwt.encode(
        {
            "htm": "GET",
            "htu": BASE + WHOAMI,
            "iat": int(time.time()) - gt.DPOP_MAX_AGE_SECONDS - 5,
            "jti": uuid.uuid4().hex,
            "ath": gt.access_token_hash(token),
        },
        key,
        algorithm="ES256",
        headers={
            "typ": "dpop+jwt",
            "jwk": AsymmetricDPoPProvider.public_key_to_jwk(key.public_key()),
        },
    )
    resp = _get(client, {"Authorization": f"DPoP {token}", "DPoP": stale})
    assert resp.json()["detail"] == {"error": "E_DPOP_STALE"}


def test_tampered_and_expired_gateway_tokens_are_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller = _caller(client, RS)
    token = caller.access_token
    header, _payload, sig = token.split(".")
    claims = jwt.decode(token, options={"verify_signature": False})
    forged_payload = jwt.utils.base64url_encode(
        jwt.api_jws.json.dumps({**claims, "tenant_id": FV}).encode()
    ).decode()
    forged = f"{header}.{forged_payload}.{sig}"
    proof = caller.dpop_proof("GET", BASE + WHOAMI, access_token=forged)
    resp = _get(client, {"Authorization": f"DPoP {forged}", "DPoP": proof})
    assert resp.json()["detail"] == {"error": "E_TOKEN_INVALID"}

    monkeypatch.setattr(gt, "GATEWAY_TOKEN_TTL_SECONDS", 1)
    expired_caller = _caller(client)
    _ = expired_caller.access_token
    time.sleep(2.1)
    resp = _get(client, expired_caller.headers("GET", BASE + WHOAMI))
    assert resp.json()["detail"] == {"error": "E_TOKEN_EXPIRED"}


def test_copied_id_token_cannot_be_bound_to_another_key(
    client: TestClient,
) -> None:
    victim = _caller(client)
    _ = victim.access_token  # the real client exchanges first
    thief = _caller(client)
    thief._id_token = (
        victim.id_token
    )  # thief replays the victim's ID token with its own key
    with pytest.raises(RuntimeError, match="HTTP 401"):
        _ = thief.access_token
    victim._access_token = None  # the real client may refresh with the same key
    assert victim.access_token


def test_bad_subject_tokens_get_a_plain_401(client: TestClient) -> None:
    caller = _caller(client)
    url = BASE + "/api/v1/auth/token"
    for subject in (
        "not-a-jwt",
        jwt.encode({"iss": "https://evil.example"}, "k", "HS256"),
    ):
        resp = client.post(
            "/api/v1/auth/token",
            json={"subject_token": subject},
            headers={"DPoP": caller.dpop_proof("POST", url)},
        )
        assert (resp.status_code, resp.json()["detail"]) == (
            401,
            {"error": "E_SUBJECT_TOKEN_INVALID"},
        )
    no_proof = client.post(
        "/api/v1/auth/token", json={"subject_token": caller.id_token}
    )
    assert no_proof.json()["detail"] == {"error": "E_DPOP_MISSING"}


def test_login_token_edited_to_another_tenants_issuer_is_a_plain_401(
    client: TestClient,
) -> None:
    """UI Test 0: Bob re-labels his RetailStream login token as FinVault's, keeping his
    signature.
    """
    caller = _caller(client, RS, "read_only_analyst")
    header, _payload, sig = caller.id_token.split(".")
    claims = jwt.decode(caller.id_token, options={"verify_signature": False})
    edited = {
        **claims,
        "iss": "https://accounts.google.com",
        "sub": "alice@finvault.com",
    }
    edited["user_role"] = "sre_admin"
    edited.pop("tid", None)
    edited.pop("roles", None)
    forged_payload = jwt.utils.base64url_encode(
        jwt.api_jws.json.dumps(edited).encode()
    ).decode()
    url = BASE + "/api/v1/auth/token"
    resp = client.post(
        "/api/v1/auth/token",
        json={"subject_token": f"{header}.{forged_payload}.{sig}"},
        headers={"DPoP": caller.dpop_proof("POST", url)},
    )
    assert (resp.status_code, resp.json()["detail"]) == (
        401,
        {"error": "E_SUBJECT_TOKEN_INVALID"},
    )
    assert "access_token" not in resp.json()


async def test_request_context_is_cleared_after_each_request(
    client: TestClient,
) -> None:
    """Drive the dependency directly: the envelope is active during the request, gone after."""
    from app.main import require_caller
    from starlette.requests import Request

    caller = _caller(client)
    headers = caller.headers("GET", BASE + WHOAMI)
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": WHOAMI,
        "query_string": b"",
        "server": ("testserver", 80),
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in {"host": "testserver", **headers}.items()
        ],
    }
    ctx._ACTIVE_TENANT_ENVELOPE.set(None)
    dependency = require_caller(Request(scope))
    envelope = await dependency.__anext__()
    assert ctx._ACTIVE_TENANT_ENVELOPE.get() is envelope
    await dependency.aclose()
    assert ctx._ACTIVE_TENANT_ENVELOPE.get() is None


def _pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def test_customer_environments_need_a_shared_signing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer = pc.load_platform_config("customer.example")
    no_secret = customer.model_copy(
        update={
            "identity": customer.identity.model_copy(
                update={"gateway_signing_secret": None}
            )
        }
    )
    with pytest.raises(RuntimeError, match="E_GATEWAY_SIGNING_KEY_MISSING"):
        gt.GatewayTokenService.from_config(no_secret)
    data = customer.model_dump()
    data["identity"]["gateway_signing_secret"] = None
    with pytest.raises(ValueError, match="gateway_signing_secret"):
        pc.PlatformConfig.model_validate(data)

    pem = _pem()
    fetched: list[str] = []
    monkeypatch.setattr(
        gt, "fetch_signing_key_pem", lambda sid: fetched.append(sid) or pem
    )
    a = gt.GatewayTokenService.from_config(customer)
    b = gt.GatewayTokenService.from_config(
        customer
    )  # a second instance, same secret
    assert fetched == ["cymbal-gateway-signing-key/versions/1"] * 2
    assert not a.ephemeral
    assert a.kid == b.kid

    for bad in (
        "cymbal-gateway-signing-key",
        "x/versions/latest",
        "../other/versions/1",
    ):
        data["identity"]["gateway_signing_secret"] = bad
        with pytest.raises(ValueError, match="pinned"):
            pc.PlatformConfig.model_validate(data)

    def unreachable(_: str) -> str:
        raise OSError("secret manager unreachable")

    monkeypatch.setattr(gt, "fetch_signing_key_pem", unreachable)
    with pytest.raises(OSError, match=r"secret manager unreachable"):
        gt.GatewayTokenService.from_config(customer)
    p384 = ec.generate_private_key(ec.SECP384R1()).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    monkeypatch.setattr(gt, "fetch_signing_key_pem", lambda _: p384.decode())
    with pytest.raises(RuntimeError, match="P-256"):
        gt.GatewayTokenService.from_config(customer)
    envelope = ctx.EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims={
            "iss": str(ctx.TENANT_DIRECTORY[FV]["iss"]),
            "sub": "alice@finvault.com",
            "tenant_id": FV,
            "user_role": "read_only_analyst",
            "exp": int(time.time()) + 600,
        },
        dpop_proof={"jkt": "unused", "jti": uuid.uuid4().hex},
    )
    token, _ = a.issue(envelope)
    claims = jwt.decode(
        token,
        b.private_key.public_key(),
        algorithms=["ES256"],
        audience=gt.GATEWAY_TOKEN_AUDIENCE,
    )
    assert claims["tenant_id"] == FV


# --- Review hardening -------------------------------------------------------------------------


def _proof(
    key: ec.EllipticCurvePrivateKey, htm: str, htu: str, **extra: Any
) -> str:
    jwk = {
        **AsymmetricDPoPProvider.public_key_to_jwk(key.public_key()),
        **extra.pop("jwk", {}),
    }
    claims = {
        "htm": htm,
        "htu": htu,
        "iat": int(time.time()),
        "jti": uuid.uuid4().hex,
        **extra,
    }
    return jwt.encode(
        claims, key, algorithm="ES256", headers={"typ": "dpop+jwt", "jwk": jwk}
    )


def test_forwarded_host_header_cannot_redirect_a_proof(
    client: TestClient,
) -> None:
    caller = _caller(client)
    token = caller.access_token
    foreign = caller.dpop_proof(
        "GET", "http://evil.example" + WHOAMI, access_token=token
    )
    headers = {
        "Authorization": f"DPoP {token}",
        "DPoP": foreign,
        "X-Forwarded-Host": "evil.example",
    }
    assert _get(client, headers).json()["detail"] == {"error": "E_DPOP_INVALID"}


def test_configured_public_origin_fixes_the_htu(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller = _caller(client)
    token = caller.access_token
    cfg = pc.get_platform_config()
    pinned = cfg.model_copy(
        update={
            "identity": cfg.identity.model_copy(
                update={"public_origin": "https://gw.example"}
            )
        }
    )
    monkeypatch.setattr(gt, "get_platform_config", lambda: pinned)
    ok = caller.dpop_proof(
        "GET", "https://gw.example" + WHOAMI, access_token=token
    )
    assert (
        _get(client, {"Authorization": f"DPoP {token}", "DPoP": ok}).status_code
        == 200
    )
    host_based = caller.dpop_proof("GET", BASE + WHOAMI, access_token=token)
    resp = _get(client, {"Authorization": f"DPoP {token}", "DPoP": host_based})
    assert resp.status_code == 401


def test_customer_data_requires_a_public_origin() -> None:
    data = pc.load_platform_config("customer.example").model_dump()
    data["identity"]["public_origin"] = None
    with pytest.raises(ValueError, match="public_origin"):
        pc.PlatformConfig.model_validate(data)


def test_unauthenticated_exchange_attempts_do_not_consume_proofs(
    client: TestClient,
) -> None:
    """Flooding /auth/token with garbage logins must not fill the replay cache."""
    caller = _caller(client)
    url = BASE + "/api/v1/auth/token"
    proof = caller.dpop_proof("POST", url)
    bad = client.post(
        "/api/v1/auth/token",
        json={"subject_token": "x"},
        headers={"DPoP": proof},
    )
    assert bad.status_code == 401
    good = client.post(
        "/api/v1/auth/token",
        json={"subject_token": caller.id_token},
        headers={"DPoP": proof},
    )
    assert (
        good.status_code == 200
    )  # the same proof was not burned by the failed attempt


def test_replay_cache_is_bounded_and_expires_in_insertion_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [1_000_000.0]
    monkeypatch.setattr(gt.time, "time", lambda: now[0])
    cache = gt._ReplayCache(max_entries=2)
    cache.check_and_add("a")
    cache.check_and_add("b")
    with pytest.raises(gt.GatewayTokenError, match="CACHE_FULL"):
        cache.check_and_add("c")
    now[0] += gt._ReplayCache.ENTRY_TTL_SECONDS + 1
    cache.check_and_add("c")  # both old entries expired and were evicted
    with pytest.raises(gt.GatewayTokenError, match="E_DPOP_REPLAY"):
        cache.check_and_add("c")


def test_tokens_and_proofs_of_the_wrong_kind_are_refused(
    client: TestClient,
) -> None:
    caller = _caller(client)
    url = BASE + "/api/v1/auth/token"
    token = caller.access_token
    as_subject = client.post(
        "/api/v1/auth/token",
        json={"subject_token": token},
        headers={"DPoP": caller.dpop_proof("POST", url)},
    )
    assert as_subject.json()["detail"] == {"error": "E_SUBJECT_TOKEN_INVALID"}
    request_proof = caller.dpop_proof(
        "POST", url, access_token=token
    )  # carries ath
    reuse = client.post(
        "/api/v1/auth/token",
        json={"subject_token": caller.id_token},
        headers={"DPoP": request_proof},
    )
    assert reuse.json()["detail"] == {"error": "E_DPOP_INVALID"}


@pytest.mark.parametrize(
    ("extra", "code"),
    [
        ({"jwk": {"d": "private-part"}}, "E_DPOP_INVALID"),
        ({"jwk": {"crv": "P-384"}}, "E_DPOP_INVALID"),
        # Future iat: evaluated at test time so long suites never age out the offset.
        pytest.param(
            lambda: {"iat": int(time.time()) + gt.CLOCK_SKEW_SECONDS + 60},
            "E_DPOP_INVALID",
            id="future-iat",
        ),
    ],
)
def test_malformed_or_future_proofs_are_rejected(
    client: TestClient,
    extra: dict[str, Any] | Callable[[], dict[str, Any]],
    code: str,
) -> None:
    caller = _caller(client)
    token = caller.access_token
    resolved_extra = extra() if callable(extra) else extra
    proof = _proof(
        caller._dpop_key,
        "GET",
        BASE + WHOAMI,
        ath=gt.access_token_hash(token),
        **resolved_extra,
    )
    assert _get(
        client, {"Authorization": f"DPoP {token}", "DPoP": proof}
    ).json()["detail"] == {"error": code}


def test_gateway_token_never_outlives_the_idp_token() -> None:
    service = gt.get_token_service()
    envelope = ctx.EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims={
            "iss": str(ctx.TENANT_DIRECTORY[FV]["iss"]),
            "sub": "alice@finvault.com",
            "tenant_id": FV,
            "user_role": "read_only_analyst",
            "exp": int(time.time()) + 60,
        },
        dpop_proof={"jkt": "k", "jti": uuid.uuid4().hex},
    )
    token, ttl = service.issue(envelope)
    assert ttl <= 60
    assert (
        jwt.decode(token, options={"verify_signature": False})["exp"]
        <= envelope.security.exp
    )


def test_authenticated_requests_do_not_grow_the_legacy_jti_set(
    client: TestClient,
) -> None:
    from app.main import EDGE_VERIFIER

    caller = _caller(client)
    _ = caller.access_token
    before = len(EDGE_VERIFIER._seen_dpop_jtis)
    for _ in range(5):
        assert (
            _get(client, caller.headers("GET", BASE + WHOAMI)).status_code
            == 200
        )
    assert len(EDGE_VERIFIER._seen_dpop_jtis) == before
