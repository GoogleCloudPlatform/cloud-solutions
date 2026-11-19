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
# pylint: disable=missing-class-docstring,protected-access
# pylint: disable=redefined-outer-name,unnecessary-lambda,unused-argument
# pylint: disable=unused-variable

"""ADR-0014 B4: the credential broker mints tenant credentials; the runtime no longer can.

Proves (ADR-0014 Verification, "Broker"):
- it mints only for the token's tenant (the request cannot name one);
- it refuses an expired broker token, a non-broker-audience token (internal / external / gateway),
  a replay of the same (jti, kind, audience), and callers other than the runtime SA; a new turn
  with a fresh broker token still succeeds;
- it refuses kinds and ID-token audiences that are not allowlisted, and offboarded tenants;
- every mint and refusal is audited without token values; backend outages are 503;
- the broker entrypoint imports no ADK or agent modules;
- the runtime's `RemoteBrokerBackend` goes exchange -> broker and maps refusals / outages;
- Terraform: broker SA holds TokenCreator on ct-*, the runtime's grant is removable (step 4),
  only the runtime SA can invoke the broker.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import jwt
import pytest
from agents import context_token as ct
from agents import tenant_credentials as tc
from agents.context_exchange import ContextTokenExchange
from agents.tenant_identity import tenant_service_account_email
from app import gateway_tokens as gt
from broker_service.core import (
    BrokerRefused,
    CredentialBroker,
    MintedCredential,
)
from broker_service.main import broker_from_env, create_app
from fastapi.testclient import TestClient
from tests.helpers.context_token_fakes import (
    _compact,
    _default_signer,
    _envelope,
)

REPO = Path(__file__).resolve().parents[2]
PROJECT = "cymbal-multitenancy-example"
RUNTIME_SA = f"cymbal-pooled-runtime-sa@{PROJECT}.iam.gserviceaccount.com"
BROKER_URL = "https://cymbal-credential-broker.example"
ROUTER = "https://model-router.example"
FV, RS = "tenant-finvault-alpha", "tenant-retailstream-beta"
PATH = "/internal/v1/tenant-credential"


def _jwt_unsigned(claims: dict[str, Any]) -> str:
    def enc(d: dict[str, Any]) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(d).encode())
            .rstrip(b"=")
            .decode()
        )

    return f"{enc({'alg': 'RS256', 'typ': 'JWT'})}.{enc(claims)}.SIGNATURE_REMOVED_BY_GOOGLE"


def _caller(email: str = RUNTIME_SA, **overrides: Any) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": BROKER_URL,
        "email": email,
        "email_verified": True,
        "exp": int(time.time()) + 3600,
        **overrides,
    }
    return "Bearer " + _jwt_unsigned(claims)


class FakeMint:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.fail: Exception | None = None

    def access_token(
        self, *, principal: str, lifetime_seconds: int
    ) -> MintedCredential:
        self.calls.append(("access_token", principal, lifetime_seconds))
        if self.fail:
            raise self.fail
        return MintedCredential(
            kind="access_token",
            token=f"fake-access-token-{uuid.uuid4().hex}",
            expires_at=time.time() + lifetime_seconds,
            principal=principal,
        )

    def id_token(self, *, principal: str, audience: str) -> MintedCredential:
        self.calls.append(("id_token", principal, audience))
        if self.fail:
            raise self.fail
        return MintedCredential(
            kind="id_token",
            token="eyJ.fake.idt",
            expires_at=time.time() + 3600,
            principal=principal,
        )


ONBOARDED: dict[str, tuple[str, ...]] = {FV: (ROUTER,), RS: ()}


@pytest.fixture
def fake() -> FakeMint:
    return FakeMint()


@pytest.fixture
def broker(fake: FakeMint) -> CredentialBroker:
    return CredentialBroker(
        project_id=PROJECT,
        allowed_callers=frozenset({RUNTIME_SA}),
        backend=fake,
        tenants=lambda: dict(ONBOARDED),
        expected_caller_audience=BROKER_URL,
    )


@pytest.fixture
def client(broker: CredentialBroker) -> TestClient:
    return TestClient(create_app(broker))


def _broker_token(tenant: str = FV) -> str:
    env = _envelope(tenant, f"u-{uuid.uuid4().hex[:6]}@{tenant}.example")
    return ContextTokenExchange().exchange(
        env.context_token, audience="broker"
    )[0]


def _post(
    client: TestClient,
    token: str | None,
    *,
    caller: str | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    headers = {"X-Serverless-Authorization": caller or _caller()}
    if token is not None:
        headers["X-Cymbal-Context-Token"] = token
    return client.post(
        PATH, headers=headers, json=body or {"kind": "access_token"}
    )


# --- mints only for the token's tenant ------------------------------------------------------------


@pytest.mark.parametrize("tenant", [FV, RS])
def test_mints_only_for_the_tokens_tenant(
    client: TestClient,
    fake: FakeMint,
    tenant: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = _broker_token(tenant)
    with caplog.at_level(logging.INFO, logger="cymbal.audit.broker"):
        resp = _post(client, token)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    principal = tenant_service_account_email(tenant, PROJECT)
    assert body["tenant_id"] == tenant
    assert body["principal"] == principal
    assert fake.calls == [("access_token", principal, 300)]
    line = json.loads(caplog.records[-1].getMessage())
    assert line["event"] == "tenant_credential_mint"
    assert line["tenant_id"] == tenant
    assert line["kind"] == "access_token"
    assert line["caller"] == RUNTIME_SA
    assert line["token_jti"] == ct.unverified_claims(token)["jti"]
    assert body["access_token"] not in caplog.text
    assert token not in caplog.text


def test_the_request_cannot_name_a_tenant(
    client: TestClient, fake: FakeMint
) -> None:
    resp = _post(
        client,
        _broker_token(RS),
        body={"kind": "access_token", "tenant_id": FV},
    )
    assert resp.status_code == 422
    assert fake.calls == []


def test_lifetime_is_capped_at_300_seconds(
    client: TestClient, fake: FakeMint
) -> None:
    assert _post(
        client,
        _broker_token(),
        body={"kind": "access_token", "lifetime_seconds": 3600},
    )
    assert fake.calls[-1][2] == 300


# --- token checks ---------------------------------------------------------------------------------


def test_refuses_an_expired_broker_token(
    client: TestClient, fake: FakeMint
) -> None:
    claims = ct.unverified_claims(_broker_token())
    now = int(time.time())
    expired = _compact(
        {"alg": "ES256", "typ": "ctx+jwt", "kid": _default_signer().kid},
        {**claims, "iat": now - 400, "exp": now - 100},
        _default_signer().sign,
    )
    resp = _post(client, expired)
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "E_CONTEXT_TOKEN_EXPIRED"
    assert fake.calls == []


def test_refuses_tokens_for_any_other_audience(
    client: TestClient, fake: FakeMint
) -> None:
    env = _envelope(FV, "alice@finvault.com")
    external = ContextTokenExchange().exchange(
        env.context_token, audience="https://mcp.finvault.example/mcp"
    )[0]
    gateway_token, _ = gt.get_token_service().issue(env)
    for bad, code in [
        (
            env.context_token,
            "E_CONTEXT_TOKEN_AUDIENCE",
        ),  # internal runtime/mcp token
        (external, "E_CONTEXT_TOKEN_AUDIENCE"),  # MCP-audience token
        (gateway_token, "E_CONTEXT_TOKEN_TYPE"),
    ]:
        resp = _post(client, bad)
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == code
    assert _post(client, None).status_code == 401
    assert fake.calls == []


def test_refuses_a_replay_but_a_fresh_turn_succeeds(
    client: TestClient, fake: FakeMint
) -> None:
    token = _broker_token()
    assert _post(client, token).status_code == 200
    replay = _post(client, token)
    assert replay.status_code == 409
    assert replay.json()["detail"]["error"] == "E_BROKER_TOKEN_REPLAYED"
    # A different (kind, audience) with the same token is a separate, allowlisted mint...
    assert (
        _post(
            client, token, body={"kind": "id_token", "audience": ROUTER}
        ).status_code
        == 200
    )
    # ...and a new turn gets a fresh broker token (fresh jti), which works.
    assert _post(client, _broker_token()).status_code == 200
    assert len(fake.calls) == 3


def test_mints_per_token_are_bounded(broker: CredentialBroker) -> None:
    from broker_service import core

    token = _broker_token()
    tenants = {FV: tuple(f"https://aud{i}.example" for i in range(5))}
    broker._tenants = lambda: tenants  # type: ignore[method-assign]
    for i in range(core.MAX_MINTS_PER_TOKEN):
        broker.mint(
            caller_header=_caller(),
            context_token=token,
            kind="id_token",
            audience=f"https://aud{i}.example",
        )
    with pytest.raises(BrokerRefused, match="E_BROKER_TOKEN_MINT_LIMIT"):
        broker.mint(
            caller_header=_caller(),
            context_token=token,
            kind="id_token",
            audience="https://aud4.example",
        )


# --- caller checks --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("caller", "status", "code"),
    [
        ("", 401, "E_BROKER_CALLER_MISSING"),
        ("Bearer not-a-jwt", 401, "E_BROKER_CALLER_MISSING"),
        (
            _caller(f"cymbal-broker-sa@{PROJECT}.iam.gserviceaccount.com"),
            403,
            "E_BROKER_CALLER_NOT_ALLOWED",
        ),
        (_caller("attacker@evil.example"), 403, "E_BROKER_CALLER_NOT_ALLOWED"),
        (_caller(email_verified=False), 403, "E_BROKER_CALLER_NOT_ALLOWED"),
        (
            _caller(aud="https://other.example"),
            403,
            "E_BROKER_CALLER_NOT_ALLOWED",
        ),
        (
            _caller(iss="https://evil.example"),
            403,
            "E_BROKER_CALLER_NOT_ALLOWED",
        ),
    ],
)
def test_refuses_callers_other_than_the_runtime_sa(
    client: TestClient, fake: FakeMint, caller: str, status: int, code: str
) -> None:
    headers = {"X-Cymbal-Context-Token": _broker_token()}
    if caller:
        headers["X-Serverless-Authorization"] = caller
    resp = client.post(PATH, headers=headers, json={"kind": "access_token"})
    assert resp.status_code == status
    assert resp.json()["detail"]["error"] == code
    assert fake.calls == []


# --- allowlists and onboarding --------------------------------------------------------------------


def test_refuses_kinds_and_audiences_not_allowlisted(
    client: TestClient, broker: CredentialBroker, fake: FakeMint
) -> None:
    assert (
        _post(
            client, _broker_token(), body={"kind": "refresh_token"}
        ).status_code
        == 422
    )
    with pytest.raises(BrokerRefused, match="E_BROKER_KIND_NOT_ALLOWED"):
        broker.mint(
            caller_header=_caller(),
            context_token=_broker_token(),
            kind="sa_key",
        )
    resp = _post(
        client,
        _broker_token(),
        body={"kind": "id_token", "audience": "https://evil.example"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "E_BROKER_AUDIENCE_NOT_ALLOWED"
    resp = _post(
        client, _broker_token(RS), body={"kind": "id_token", "audience": ROUTER}
    )
    assert resp.status_code == 403  # allowlisted for FinVault only
    resp = _post(
        client,
        _broker_token(),
        body={"kind": "access_token", "audience": ROUTER},
    )
    assert resp.status_code == 400
    assert fake.calls == []
    ok = _post(
        client, _broker_token(), body={"kind": "id_token", "audience": ROUTER}
    )
    assert ok.status_code == 200
    assert ok.json()["id_token"]
    assert fake.calls == [
        ("id_token", tenant_service_account_email(FV, PROJECT), ROUTER)
    ]


def test_refuses_tenants_no_longer_onboarded(
    broker: CredentialBroker, fake: FakeMint
) -> None:
    broker._tenants = lambda: {RS: ()}  # type: ignore[method-assign]  # FinVault offboarded
    with pytest.raises(BrokerRefused, match="E_BROKER_TENANT_NOT_ONBOARDED"):
        broker.mint(
            caller_header=_caller(),
            context_token=_broker_token(FV),
            kind="access_token",
        )
    assert fake.calls == []


def test_refusals_are_audited(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="cymbal.audit.broker"):
        _post(client, _broker_token(), caller=_caller("attacker@evil.example"))
    line = json.loads(caplog.records[-1].getMessage())
    assert line["event"] == "tenant_credential_refused"
    assert line["code"] == "E_BROKER_CALLER_NOT_ALLOWED"
    assert line["caller"] == "attacker@evil.example"


def test_backend_and_key_outages_are_503(
    client: TestClient, broker: CredentialBroker, fake: FakeMint
) -> None:
    fake.fail = RuntimeError("IAM Credentials unavailable")
    resp = _post(client, _broker_token())
    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "10"
    fake.fail = None

    class _Down:
        def verify(self, *_a: Any, **_k: Any) -> Any:
            raise ct.ContextKeyUnavailableError("kms down")

    broker._verifier = lambda: _Down()  # type: ignore[assignment,return-value,method-assign]
    resp = _post(client, _broker_token())
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "E_CONTEXT_KEY_UNAVAILABLE"


def test_broker_refuses_to_start_on_a_wrong_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in (
        "K_SERVICE",
        "BROKER_ALLOWED_CALLERS",
        "BROKER_EXPECTED_AUDIENCE",
    ):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="K_SERVICE"):
        broker_from_env()  # not on Cloud Run
    monkeypatch.setenv("K_SERVICE", "cymbal-credential-broker")
    with pytest.raises(RuntimeError, match="BROKER_ALLOWED_CALLERS"):
        broker_from_env()
    monkeypatch.setenv("BROKER_ALLOWED_CALLERS", RUNTIME_SA)
    with pytest.raises(RuntimeError, match="BROKER_EXPECTED_AUDIENCE"):
        broker_from_env()
    monkeypatch.setenv("BROKER_EXPECTED_AUDIENCE", "http://not-https.example")
    with pytest.raises(RuntimeError, match="BROKER_EXPECTED_AUDIENCE"):
        broker_from_env()
    monkeypatch.setenv("BROKER_EXPECTED_AUDIENCE", BROKER_URL)
    built = broker_from_env()
    assert built._expected_aud == BROKER_URL
    assert built._verify_caller_signature is not None
    monkeypatch.delenv("K_SERVICE")
    assert broker_from_env(require_cloud_run=False)  # test-only override
    with pytest.raises(ValueError, match="allowed caller"):
        CredentialBroker(
            project_id=PROJECT,
            allowed_callers=frozenset(),
            backend=FakeMint(),
            tenants=dict,
        )


def test_broker_app_exposes_only_its_endpoints(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    for path in ("/docs", "/openapi.json", "/api/v1/whoami", "/"):
        assert client.get(path).status_code == 404


# --- the broker imports no ADK or agent modules ---------------------------------------------------

_ALLOWED_AGENT_MODULES = {
    "agents",
    "agents.context_token",
    "agents.kms_rest",
    "agents.platform_config",
    "agents.tenant_identity",
    "agents.workload_identity",  # ADR-0016 caller principal + agent binding (stdlib only)
}


def test_broker_entrypoint_imports_no_adk_or_agent_modules() -> None:
    code = (
        "import sys, json\n"
        "import broker_service.main, broker_service.core, broker_service.iam_backend\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith(('agents', 'google.adk',"
        " 'google.genai', 'app', 'mcp_server')))))\n"
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k != "CYMBAL_LOCAL_CONTEXT_SIGNER"
    }
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={**env, "PYTHONPATH": str(REPO)},
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    loaded = set(json.loads(proc.stdout.strip().splitlines()[-1]))
    assert loaded <= _ALLOWED_AGENT_MODULES, sorted(
        loaded - _ALLOWED_AGENT_MODULES
    )


# --- runtime side: RemoteBrokerBackend ------------------------------------------------------------


def _remote(
    client: TestClient, caller: str = RUNTIME_SA
) -> tc.RemoteBrokerBackend:
    def post(url: str, **kw: Any) -> Any:
        assert url.startswith("http://testserver")
        return client.post(url.removeprefix("http://testserver"), **kw)

    return tc.RemoteBrokerBackend(
        "http://testserver",
        id_token_provider=lambda aud: _caller(caller).removeprefix("Bearer "),
        http_post=post,
    )


def test_runtime_mints_through_the_broker(
    client: TestClient, fake: FakeMint
) -> None:
    backend = _remote(client)
    runtime_broker = tc.TenantCredentialBroker(
        project_id=PROJECT, backend=backend
    )
    env = _envelope(FV, "alice@finvault.com")
    cred = runtime_broker.credential_for(env)
    assert cred.tenant_id == FV
    assert cred.principal == tenant_service_account_email(FV, PROJECT)
    assert (
        runtime_broker.credential_for(env) is cred
    )  # cached until near expiry
    other = runtime_broker.credential_for(_envelope(RS, "bob@retailstream.com"))
    assert other.principal == tenant_service_account_email(RS, PROJECT)
    assert [c[1] for c in fake.calls] == [cred.principal, other.principal]


def test_runtime_maps_broker_refusals_and_outages(
    client: TestClient, fake: FakeMint
) -> None:
    env = _envelope(FV, "alice@finvault.com")
    principal = tenant_service_account_email(FV, PROJECT)
    with pytest.raises(PermissionError, match="E_BROKER_CALLER_NOT_ALLOWED"):
        _remote(client, caller="attacker@evil.example").mint(
            tenant_id=FV,
            principal=principal,
            lifetime_seconds=300,
            context_token=env.context_token,
        )
    fake.fail = RuntimeError("iam down")
    with pytest.raises(tc.TenantCredentialUnavailable, match="HTTP 503"):
        _remote(client).mint(
            tenant_id=FV,
            principal=principal,
            lifetime_seconds=300,
            context_token=env.context_token,
        )

    def broken(*_a: Any, **_k: Any) -> Any:
        raise OSError("connection refused")

    backend = tc.RemoteBrokerBackend(
        "https://broker.example",
        id_token_provider=lambda a: "x",
        http_post=broken,
    )
    with pytest.raises(
        tc.TenantCredentialUnavailable, match="E_BROKER_UNAVAILABLE"
    ):
        backend.mint(
            tenant_id=FV,
            principal=principal,
            lifetime_seconds=300,
            context_token=env.context_token,
        )
    with pytest.raises(PermissionError, match="E_BROKER_NO_CONTEXT_TOKEN"):
        backend.mint(
            tenant_id=FV,
            principal=principal,
            lifetime_seconds=300,
            context_token="",
        )


def test_runtime_rejects_a_credential_for_the_wrong_principal(
    client: TestClient,
) -> None:
    env = _envelope(FV, "alice@finvault.com")
    with pytest.raises(PermissionError, match="E_CREDENTIAL_TENANT_MISMATCH"):
        _remote(client).mint(
            tenant_id=FV,
            principal=tenant_service_account_email(RS, PROJECT),
            lifetime_seconds=300,
            context_token=env.context_token,
        )


def test_each_mint_uses_a_fresh_broker_token(client: TestClient) -> None:
    seen: list[str] = []
    real_post = client.post

    def post(url: str, **kw: Any) -> Any:
        seen.append(kw["headers"]["X-Cymbal-Context-Token"])
        return real_post(url.removeprefix("http://testserver"), **kw)

    backend = tc.RemoteBrokerBackend(
        "http://testserver",
        id_token_provider=lambda a: _caller().removeprefix("Bearer "),
        http_post=post,
    )
    env = _envelope(FV, "alice@finvault.com")
    principal = tenant_service_account_email(FV, PROJECT)
    for _ in range(2):
        backend.mint(
            tenant_id=FV,
            principal=principal,
            lifetime_seconds=300,
            context_token=env.context_token,
        )
    jtis = {ct.unverified_claims(t)["jti"] for t in seen}
    assert len(jtis) == 2
    assert all(
        jwt.decode(t, options={"verify_signature": False})["aud"] == "broker"
        for t in seen
    )


def test_default_broker_uses_the_remote_broker_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tc, "is_live_mode", lambda: True)
    try:
        monkeypatch.setenv("CREDENTIAL_BROKER_URL", BROKER_URL)
        tc.set_default_broker(None)
        backend = tc.get_default_broker(PROJECT).backend
        assert isinstance(backend, tc.RemoteBrokerBackend)
        assert backend.broker_url == BROKER_URL
        monkeypatch.delenv("CREDENTIAL_BROKER_URL")
        monkeypatch.setenv(
            "CYMBAL_DIRECT_IMPERSONATION", "1"
        )  # explicit pre-B4 choice
        tc.set_default_broker(None)
        assert isinstance(
            tc.get_default_broker(PROJECT).backend,
            tc.ImpersonatedTenantCredentialBackend,
        )
        monkeypatch.setattr(tc, "is_live_mode", lambda: False)
        monkeypatch.setenv("CREDENTIAL_BROKER_URL", BROKER_URL)
        tc.set_default_broker(None)
        assert isinstance(
            tc.get_default_broker(PROJECT).backend,
            tc.LocalTenantCredentialBackend,
        )

        import google.oauth2.id_token

        captured_id_token_calls: list[tuple[str, Any]] = []

        def fake_fetch_id_token(
            _req: Any, aud: str, *, bind_id_token: Any = None
        ) -> str:
            captured_id_token_calls.append((aud, bind_id_token))
            return "unbound-spiffe-s2s-id-token"

        monkeypatch.setattr(
            google.oauth2.id_token, "fetch_id_token", fake_fetch_id_token
        )
        assert (
            tc._fetch_cloud_run_id_token(BROKER_URL)
            == "unbound-spiffe-s2s-id-token"
        )
        assert captured_id_token_calls == [(BROKER_URL, False)]
    finally:
        tc.set_default_broker(None)


def test_lazy_agents_package_still_exposes_root_agent() -> None:
    import agents
    from agents.shared_diagnostic_agent import shared_diagnostic_agent

    assert agents.root_agent is shared_diagnostic_agent
    with pytest.raises(AttributeError):
        _ = agents.does_not_exist  # type: ignore[attr-defined]


# --- Terraform and image --------------------------------------------------------------------------


def test_terraform_moves_token_creator_to_the_broker() -> None:
    tf = (
        REPO
        / "terraform"
        / "modules"
        / "platform_core"
        / "credential_broker.tf"
    ).read_text()
    iso = (REPO / "terraform" / "modules" / "tenant" / "main.tf").read_text()
    root = (REPO / "terraform" / "main.tf").read_text()
    assert 'account_id   = "cymbal-broker-sa"' in tf
    broker_grant = iso[iso.index('"broker_impersonates_tenant"') :].split(
        "\n}\n"
    )[0]
    assert (
        'role               = "roles/iam.serviceAccountTokenCreator"'
        in broker_grant
    )
    assert "var.broker_sa_email" in broker_grant
    assert "var.broker_enabled ? 1 : 0" in broker_grant
    assert (
        "broker_sa_email             = module.platform_core.credential_broker_sa_email"
        in root
    )
    runtime_grant = iso[iso.index('"gateway_impersonates_tenant"') :].split(
        "\n}\n"
    )[0]
    assert "var.runtime_keeps_token_creator ? 1 : 0" in runtime_grant


def test_terraform_only_the_runtime_can_invoke_the_broker() -> None:
    tf = (
        REPO
        / "terraform"
        / "modules"
        / "platform_core"
        / "credential_broker.tf"
    ).read_text()
    invokers = re.findall(
        r'role\s*=\s*"roles/run.invoker"\s*\n\s*member\s*=\s*"([^"]+)"', tf
    )
    assert invokers == [
        "serviceAccount:${google_service_account.pooled_agent_runtime.email}"
    ]
    members = re.findall(r'^\s*member\s*=\s*"([^"]+)"', tf, re.MULTILINE)
    assert members
    assert not [
        m
        for m in members
        if m.startswith(("allUsers", "allAuthenticatedUsers"))
    ]
    assert "max_instance_count = 1" in tf
    assert '"broker_service.main:create_app", "--factory"' in tf
    assert 'name  = "BROKER_ALLOWED_CALLERS"' in tf


def test_image_contains_the_broker_service() -> None:
    assert (
        "COPY broker_service/ ./broker_service/"
        in (REPO / "Dockerfile").read_text()
    )


# --- review fixes ---------------------------------------------------------------------------------


def test_caller_comes_from_x_serverless_authorization_when_both_headers_are_sent(
    client: TestClient, fake: FakeMint
) -> None:
    """Cloud Run verifies X-Serverless-Authorization when present and passes Authorization through
    unverified, so a forged runtime identity in Authorization must not win."""
    resp = client.post(
        PATH,
        headers={
            "X-Serverless-Authorization": _caller(
                f"other-sa@{PROJECT}.iam.gserviceaccount.com"
            ),
            "Authorization": _caller(
                RUNTIME_SA
            ),  # forged, unverified by Cloud Run
            "X-Cymbal-Context-Token": _broker_token(),
        },
        json={"kind": "access_token"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "E_BROKER_CALLER_NOT_ALLOWED"
    assert fake.calls == []
    # Authorization alone is used only when it is the header Cloud Run verified.
    ok = client.post(
        PATH,
        headers={
            "Authorization": _caller(),
            "X-Cymbal-Context-Token": _broker_token(),
        },
        json={"kind": "access_token"},
    )
    assert ok.status_code == 200


def _signed_caller(email: str = RUNTIME_SA) -> str:
    unsigned = _caller(email).removeprefix("Bearer ")
    return (
        "Bearer " + unsigned.rsplit(".", 1)[0] + ".c2lnbmF0dXJl"
    )  # a signature still present


def test_a_caller_token_with_its_signature_is_verified_or_refused(
    fake: FakeMint,
) -> None:
    def make(verifier: Any) -> CredentialBroker:
        return CredentialBroker(
            project_id=PROJECT,
            allowed_callers=frozenset({RUNTIME_SA}),
            backend=fake,
            tenants=lambda: dict(ONBOARDED),
            expected_caller_audience=BROKER_URL,
            caller_signature_verifier=verifier,
        )

    header = _signed_caller()
    with pytest.raises(BrokerRefused, match="E_BROKER_CALLER_UNVERIFIED"):
        make(None).mint(
            caller_header=header,
            context_token=_broker_token(),
            kind="access_token",
        )

    def bad(_token: str) -> dict[str, Any]:
        raise ValueError("Could not verify token signature.")

    with pytest.raises(BrokerRefused, match="E_BROKER_CALLER_UNVERIFIED"):
        make(bad).mint(
            caller_header=header,
            context_token=_broker_token(),
            kind="access_token",
        )
    seen: list[str] = []

    def good(token: str) -> dict[str, Any]:
        seen.append(token)
        return ct.unverified_claims(
            token
        )  # stands in for google.oauth2.id_token.verify_token

    _cred, tenant = make(good).mint(
        caller_header=header, context_token=_broker_token(), kind="access_token"
    )
    assert tenant == FV
    assert seen == [header.removeprefix("Bearer ")]
    # The verified claims still go through the allowlist.
    with pytest.raises(BrokerRefused, match="E_BROKER_CALLER_NOT_ALLOWED"):
        make(good).mint(
            caller_header=_signed_caller("attacker@evil.example"),
            context_token=_broker_token(),
            kind="access_token",
        )


def test_google_signature_verifier_checks_the_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import google.oauth2.id_token
    from broker_service.core import google_id_token_signature_verifier

    calls: dict[str, Any] = {}

    def fake_verify(
        token: str, request: Any, audience: str | None = None, **_: Any
    ) -> dict[str, Any]:
        calls.update(token=token, audience=audience)
        return {"email": RUNTIME_SA}

    monkeypatch.setattr(google.oauth2.id_token, "verify_token", fake_verify)
    assert google_id_token_signature_verifier(BROKER_URL)("t.o.k") == {
        "email": RUNTIME_SA
    }
    assert calls == {"token": "t.o.k", "audience": BROKER_URL}


def test_live_mode_requires_an_explicit_credential_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tc, "is_live_mode", lambda: True)
    monkeypatch.delenv("CREDENTIAL_BROKER_URL", raising=False)
    monkeypatch.delenv("CYMBAL_DIRECT_IMPERSONATION", raising=False)
    try:
        tc.set_default_broker(None)
        with pytest.raises(
            tc.TenantCredentialUnavailable,
            match="E_CREDENTIAL_BACKEND_UNCONFIGURED",
        ):
            tc.get_default_broker(PROJECT)
        monkeypatch.setenv("CYMBAL_DIRECT_IMPERSONATION", "1")
        tc.set_default_broker(None)
        assert isinstance(
            tc.get_default_broker(PROJECT).backend,
            tc.ImpersonatedTenantCredentialBackend,
        )
    finally:
        tc.set_default_broker(None)


def test_remote_backend_maps_429_and_malformed_bodies(
    client: TestClient,
) -> None:
    env = _envelope(FV, "alice@finvault.com")
    principal = tenant_service_account_email(FV, PROJECT)

    class _Resp:
        def __init__(self, status: int, body: Any) -> None:
            self.status_code, self._body = status, body

        def json(self) -> Any:
            if isinstance(self._body, Exception):
                raise self._body
            return self._body

    def backend(resp: _Resp) -> tc.RemoteBrokerBackend:
        return tc.RemoteBrokerBackend(
            "https://broker.example",
            id_token_provider=lambda a: "x",
            http_post=lambda *a, **k: resp,
        )

    kw = {"tenant_id": FV, "principal": principal, "lifetime_seconds": 300}
    limited = _Resp(429, {"detail": {"error": "E_BROKER_TOKEN_MINT_LIMIT"}})
    with pytest.raises(PermissionError, match="E_BROKER_TOKEN_MINT_LIMIT"):
        backend(limited).mint(**kw, context_token=env.context_token)
    for body in (
        ValueError("not json"),
        {"tenant_id": FV},
        {"access_token": "", "expires_at": 1},
    ):
        with pytest.raises(
            tc.TenantCredentialUnavailable, match="E_BROKER_MALFORMED_RESPONSE"
        ):
            backend(_Resp(200, body)).mint(
                **kw, context_token=env.context_token
            )


def test_plain_http_broker_urls_are_refused() -> None:
    with pytest.raises(ValueError, match="https"):
        tc.RemoteBrokerBackend("http://broker.example")
    with pytest.raises(ValueError, match="https"):
        tc.RemoteBrokerBackend("http://testserver.evil.example")
    assert tc.RemoteBrokerBackend("http://testserver")
    assert tc.RemoteBrokerBackend(
        "http://anything", http_post=lambda *a, **k: None
    )


def test_terraform_sets_the_broker_audience_and_the_explicit_runtime_backend() -> (
    None
):
    tf = (
        REPO
        / "terraform"
        / "modules"
        / "platform_core"
        / "credential_broker.tf"
    ).read_text()
    gw = (
        REPO / "terraform" / "modules" / "platform_core" / "iap_gateway.tf"
    ).read_text()
    assert 'name  = "BROKER_EXPECTED_AUDIENCE"' in tf
    assert "value = local.credential_broker_url" in tf
    assert (
        "CREDENTIAL_BROKER_URL     = local.effective_credential_broker_url"
        in gw
    )
    assert (
        'CYMBAL_DIRECT_IMPERSONATION = local.effective_credential_broker_url == "" ? "1" : "0"'
        in gw
    )


def test_terraform_grants_token_creator_on_tenant_sas_only_to_the_broker_or_runtime() -> (
    None
):
    """Only the broker SA (and the runtime SA until B4 step 4) may mint ct-* tokens; the retired
    legacy gateway identity (cymbal-ingress-pep-sa) is not defined and gets nothing.
    """
    all_tf = "\n".join(
        p.read_text()
        for p in (REPO / "terraform").rglob("*.tf")
        if ".terraform" not in p.parts
    )
    assert "cymbal-ingress-pep-sa" not in all_tf.replace(
        "`cymbal-ingress-pep-sa`", ""
    )
    assert (
        'resource "google_service_account" "ingress_gateway_pep"' not in all_tf
    )
    assert "ingress_gateway_pep" not in all_tf
    blocks = re.findall(
        r'resource "google_service_account_iam_member" "(\w+)" \{(.*?)\n\}',
        all_tf,
        re.DOTALL,
    )
    creators = [
        (name, re.search(r"^\s*member\s*=\s*(.+)$", body, re.MULTILINE).group(1), body)  # type: ignore[union-attr]
        for name, body in blocks
        if "roles/iam.serviceAccountTokenCreator" in body
    ]
    # modules/tenant: broker / runtime (inputs wired from platform_core in the root composition);
    # modules/platform_core and modules/tenant: expiring operator grants.
    assert sorted((name, member) for name, member, _ in creators) == [
        (
            "broker_impersonates_tenant",
            '"serviceAccount:${var.broker_sa_email}"',
        ),
        (
            "gateway_impersonates_tenant",
            '"serviceAccount:${var.runtime_sa_email}"',
        ),
        ("operator_time_boxed_impersonation", "each.value"),
        ("operator_time_boxed_impersonation", "each.value.member"),
    ]
    # Human operators only ever get an expiring grant.
    for name, _, body in creators:
        if name == "operator_time_boxed_impersonation":
            assert "condition {" in body
            assert "request.time < timestamp(" in body
