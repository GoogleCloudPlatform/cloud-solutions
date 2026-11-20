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

"""ADR-0016: agent-level authorization (tenant ∩ user ∩ agent), hermetic.

Proves every refusal path of plan section A2:
- the gateway signs the routed `agent_id` (only after the registry entitles the caller to it);
- a missing `agent_id` is refused once `CONTEXT_TOKEN_REQUIRE_AGENT_ID=1` (and a malformed one
  always); the exchange carries it into derived (broker) tokens;
- the caller principal comes only from a verified ID token: a Google-issued SA token (`email`)
  or a Cloud Run Agent Identity token (issuer pinned to the org's agent STS pool, SPIFFE `sub`
  normalized to the IAM `principal://` form; A0 spike), never from headers or the request body;
- wrong principal for `agent_id`, an unbound agent, a missing caller, or an agent not entitled
  to the purpose (broker) or tool (MCP) is refused;
- with every flag off, behaviour is unchanged (SA-email callers and unbound tokens still work).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import pytest
from agents import context as ctx
from agents import context_token as ct
from agents import platform_config as pc
from agents import workload_identity as wi
from agents.context_exchange import ContextTokenExchange
from agents.registry import AgentRegistryPDP
from broker_service.core import CredentialBroker
from broker_service.main import broker_from_env, create_app
from fastapi.testclient import TestClient
from mcp_server.server import handle_mcp_jsonrpc_request
from pydantic import ValidationError
from tests.helpers.context_token_fakes import (
    BROKER_URL,
    FV,
    PROJECT,
    RUNTIME_SA,
    FakeMint,
    _caller,
    _compact,
    _default_signer,
    _envelope,
    _jwt_unsigned,
)

SHARED = "cymbal_shared_diagnostic_agent"
ALPHA = "finvault_regulatory_escalation_agent"
ORG = str(pc.get_platform_config().agent_identity.org_id)
AGENT_ISS = wi.agent_identity_issuer(ORG)
_RUN = "/resources/run/projects/987654321098/locations/us-central1/services/"
AGENT_P = f"principal://agents.global.org-{ORG}.system.id.goog{_RUN}ws2-shared-diagnostic-agent"
AGENT_SPIFFE = "spiffe://" + AGENT_P[len("principal://") :]
OTHER_AGENT_P = AGENT_P.replace(
    "ws2-shared-diagnostic-agent", "ws2-alpha-agent"
)
FOREIGN_ORG_SPIFFE = f"spiffe://agents.global.org-1.system.id.goog{_RUN}ws2-shared-diagnostic-agent"
PATH = "/internal/v1/tenant-credential"


@pytest.fixture
def gateway_state_restored() -> Any:
    """The gateway's in-process rate-limit buckets are shared by the whole test session (per
    tenant, per minute). These tests call the gateway, so put the buckets back afterwards: they
    must not eat into the budget of later tests (RetailStream's Standard tier is 30 RPM / 40k TPM).
    """
    import copy

    from app import main

    saved = copy.deepcopy(main.TOKEN_BULKHEAD._buckets)
    yield
    with main.TOKEN_BULKHEAD._lock:
        main.TOKEN_BULKHEAD._buckets.clear()
        main.TOKEN_BULKHEAD._buckets.update(saved)


def _bindings(**over: Any) -> dict[str, wi.AgentBinding]:
    base = {
        SHARED: wi.AgentBinding(
            SHARED,
            AGENT_P,
            frozenset(
                {
                    "broker:access_token",
                    "mcp:read_runbook",
                    "mcp:schedule_calendar_postmortem",
                }
            ),
        ),
        ALPHA: wi.AgentBinding(
            ALPHA, OTHER_AGENT_P, frozenset({"mcp:read_runbook"})
        ),
    }
    base.update(over)
    return base


def _bound_envelope(
    agent_id: str = SHARED, tenant: str = FV
) -> ctx.ContextEnvelope:
    env = _envelope(tenant, f"u-{uuid.uuid4().hex[:6]}@{tenant}.example")
    return ctx.EdgeAuthVerifier().bind_routed_agent(env, agent_id)


def _agent_claims(principal: str = AGENT_P, **over: Any) -> dict[str, Any]:
    """The claim shape seen in the A0 spike: STS-pool issuer, SPIFFE `sub`, list `aud`, no email."""
    return {
        "iss": AGENT_ISS,
        "aud": [BROKER_URL],
        "sub": "spiffe://" + principal[len("principal://") :],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "google": {"iam": "opaque"},
        **over,
    }


def _agent_caller(principal: str = AGENT_P, **over: Any) -> str:
    return "Bearer " + _jwt_unsigned(_agent_claims(principal, **over))


# --- caller principal (workload_identity) ---------------------------------------------------------


def test_principal_from_sa_email_and_agent_identity() -> None:
    sa = wi.principal_from_verified_claims(
        {
            "iss": "https://accounts.google.com",
            "email": RUNTIME_SA.upper(),
            "email_verified": True,
        }
    )
    assert sa == wi.CallerPrincipal("service_account", RUNTIME_SA)
    agent = wi.principal_from_verified_claims(
        _agent_claims(), audience=BROKER_URL, agent_org_id=ORG
    )
    assert agent == wi.CallerPrincipal(
        "agent", AGENT_P
    )  # SPIFFE sub -> IAM principal form
    assert wi.normalize_principal(AGENT_SPIFFE) == wi.normalize_principal(
        AGENT_P
    )


@pytest.mark.parametrize(
    ("claims", "code"),
    [
        (
            {"iss": "https://evil.example", "sub": AGENT_SPIFFE},
            "E_CALLER_ISSUER",
        ),
        # another org's agent pool is a different issuer: never accepted
        (
            {**_agent_claims(), "iss": wi.agent_identity_issuer("1")},
            "E_CALLER_ISSUER",
        ),
        ({**_agent_claims(), "aud": ["https://other"]}, "E_CALLER_AUDIENCE"),
        ({**_agent_claims(), "aud": "https://other"}, "E_CALLER_AUDIENCE"),
        # right issuer, but the SPIFFE ID is in another org's trust domain
        (
            {**_agent_claims(), "sub": FOREIGN_ORG_SPIFFE},
            "E_CALLER_PRINCIPAL_UNRECOGNIZED",
        ),
        # the agent pool issues SPIFFE IDs; a principal:// sub or an SA email is not accepted
        (
            {**_agent_claims(), "sub": AGENT_P},
            "E_CALLER_PRINCIPAL_UNRECOGNIZED",
        ),
        (
            {
                **_agent_claims(),
                "sub": "x",
                "email": RUNTIME_SA,
                "email_verified": True,
            },
            "E_CALLER_PRINCIPAL_UNRECOGNIZED",
        ),
        (
            {**_agent_claims(), "sub": AGENT_SPIFFE + "/../x"},
            "E_CALLER_PRINCIPAL",
        ),
        ({**_agent_claims(), "sub": "spiffe://evil/x"}, "E_CALLER_PRINCIPAL"),
        # a Google-issued token never yields an agent principal, even with a SPIFFE sub
        (
            {"iss": "accounts.google.com", "sub": AGENT_SPIFFE},
            "E_CALLER_PRINCIPAL_UNRECOGNIZED",
        ),
        (
            {"iss": "accounts.google.com", "email": RUNTIME_SA},
            "E_CALLER_PRINCIPAL_UNRECOGNIZED",
        ),
        (
            {
                "iss": "accounts.google.com",
                "email": "a@evil.example",
                "email_verified": True,
            },
            "E_CALLER_PRINCIPAL_UNRECOGNIZED",
        ),
        (
            {
                "iss": "accounts.google.com",
                "email": AGENT_P,
                "email_verified": True,
            },
            "E_CALLER",
        ),
    ],
)
def test_unrecognized_or_unverified_callers_are_refused(
    claims: dict[str, Any], code: str
) -> None:
    with pytest.raises(wi.CallerIdentityError, match=code):
        wi.principal_from_verified_claims(
            {"aud": BROKER_URL, **claims}, audience=BROKER_URL, agent_org_id=ORG
        )


def test_agent_tokens_refused_without_configured_org() -> None:
    with pytest.raises(wi.CallerIdentityError, match="E_CALLER_ISSUER"):
        wi.principal_from_verified_claims(_agent_claims(), audience=BROKER_URL)


def test_principal_claim_is_configurable() -> None:
    claims = {
        **_agent_claims(),
        "sub": "opaque",
        "agent_principal": AGENT_SPIFFE,
    }
    with pytest.raises(wi.CallerIdentityError):
        wi.principal_from_verified_claims(
            claims, agent_org_id=ORG
        )  # default reads `sub`
    cfg = wi.PrincipalClaimConfig(agent_claim="agent_principal")
    got = wi.principal_from_verified_claims(
        claims, agent_org_id=ORG, claim_config=cfg
    )
    assert got.value == AGENT_P


def test_principal_claim_config_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(wi.AGENT_PRINCIPAL_CLAIM_ENV, "agent_principal")
    assert wi.PrincipalClaimConfig.from_env().agent_claim == "agent_principal"
    monkeypatch.delenv(wi.AGENT_PRINCIPAL_CLAIM_ENV)
    assert wi.PrincipalClaimConfig.from_env() == wi.PrincipalClaimConfig(
        "sub", "email"
    )


def test_verify_caller_identity_requires_a_verified_token() -> None:
    seen: list[str] = []

    def ok(token: str, audience: str) -> dict[str, Any]:
        seen.append(audience)
        return _agent_claims(aud=[audience])

    def bad(token: str, audience: str) -> dict[str, Any]:
        raise ValueError("bad signature")

    got = wi.verify_caller_identity(
        "a.b.c", BROKER_URL, verify_signature=ok, agent_org_id=ORG
    )
    assert got.kind == "agent"
    assert seen == [BROKER_URL]
    with pytest.raises(
        wi.CallerIdentityError, match="E_CALLER_TOKEN_UNVERIFIED"
    ):
        wi.verify_caller_identity(
            "a.b.c", BROKER_URL, verify_signature=bad, agent_org_id=ORG
        )
    with pytest.raises(
        wi.CallerIdentityError, match="E_CALLER_TOKEN_MALFORMED"
    ):
        wi.verify_caller_identity(
            "not-a-jwt", BROKER_URL, verify_signature=ok, agent_org_id=ORG
        )


class _FakeJwks:
    """Stands in for PyJWKClient against `<issuer>/openid/jwks`."""

    def __init__(self, public_key: Any) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> Any:
        return type("K", (), {"key": self.public_key})()


def _rsa() -> Any:
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def test_agent_identity_token_verifier_pins_issuer_audience_and_alg() -> None:
    import jwt

    key = _rsa()
    verify = wi.agent_identity_token_verifier(
        ORG, jwk_client=_FakeJwks(key.public_key())
    )
    good = jwt.encode(_agent_claims(), key, algorithm="RS256")
    assert wi.verify_caller_identity(
        good, BROKER_URL, verify_signature=verify, agent_org_id=ORG
    )
    bad_tokens = {
        "other issuer": jwt.encode(
            _agent_claims(iss=wi.agent_identity_issuer("1")),
            key,
            algorithm="RS256",
        ),
        "google issuer": jwt.encode(
            _agent_claims(iss="https://accounts.google.com"),
            key,
            algorithm="RS256",
        ),
        "wrong audience": jwt.encode(
            _agent_claims(aud=["https://x"]), key, algorithm="RS256"
        ),
        "expired": jwt.encode(
            _agent_claims(exp=int(time.time()) - 600), key, algorithm="RS256"
        ),
        "other key": jwt.encode(_agent_claims(), _rsa(), algorithm="RS256"),
        "hs256": jwt.encode(_agent_claims(), "k" * 32, algorithm="HS256"),
    }
    for label, token in bad_tokens.items():
        with pytest.raises(
            wi.CallerIdentityError, match="E_CALLER_TOKEN_UNVERIFIED"
        ):
            wi.verify_caller_identity(
                token, BROKER_URL, verify_signature=verify, agent_org_id=ORG
            )
        assert label


def test_routing_verifier_never_trusts_the_iss_it_routes_on() -> None:
    import jwt

    key = _rsa()
    google_calls: list[str] = []

    def google(token: str, audience: str) -> dict[str, Any]:
        google_calls.append(token)
        raise ValueError("not a Google signature")

    route = wi.routing_signature_verifier(
        google_verifier=google,
        agent_verifier=wi.agent_identity_token_verifier(
            ORG, jwk_client=_FakeJwks(key.public_key())
        ),
        agent_org_id=ORG,
    )
    assert route(
        jwt.encode(_agent_claims(), key, algorithm="RS256"), BROKER_URL
    )["sub"]
    # a forged agent-pool `iss` selects the agent verifier, which rejects the signature
    with pytest.raises(jwt.PyJWTError):
        route(
            jwt.encode(_agent_claims(), _rsa(), algorithm="RS256"), BROKER_URL
        )
    with pytest.raises(ValueError, match=r"not a Google signature"):
        route(
            jwt.encode(
                {"iss": "https://accounts.google.com"}, key, algorithm="RS256"
            ),
            BROKER_URL,
        )
    assert len(google_calls) == 1
    # no org configured: agent-pool tokens go to the Google verifier (and fail there)
    no_org = wi.routing_signature_verifier(
        google_verifier=google, agent_verifier=None, agent_org_id=None
    )
    with pytest.raises(ValueError, match=r"not a Google signature"):
        no_org(jwt.encode(_agent_claims(), key, algorithm="RS256"), BROKER_URL)


# --- binding check --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent_id", "caller", "purpose", "code"),
    [
        (None, AGENT_P, "broker:access_token", "E_AGENT_ID_MISSING"),
        ("", AGENT_P, "broker:access_token", "E_AGENT_ID_MISSING"),
        ("unknown_agent", AGENT_P, "broker:access_token", "E_AGENT_NOT_BOUND"),
        (SHARED, None, "broker:access_token", "E_AGENT_CALLER_MISSING"),
        (
            SHARED,
            OTHER_AGENT_P,
            "broker:access_token",
            "E_AGENT_PRINCIPAL_MISMATCH",
        ),
        (
            SHARED,
            RUNTIME_SA,
            "broker:access_token",
            "E_AGENT_PRINCIPAL_MISMATCH",
        ),
        (SHARED, AGENT_P, "broker:id_token", "E_AGENT_PURPOSE_NOT_ALLOWED"),
    ],
)
def test_binding_refusals(
    agent_id: Any, caller: str | None, purpose: str, code: str
) -> None:
    principal = wi.normalize_principal(caller) if caller else None
    with pytest.raises(wi.AgentAuthorizationError, match=code):
        wi.check_agent_binding(
            agent_id=agent_id,
            caller=principal,
            purpose=purpose,
            bindings=_bindings(),
        )


def test_binding_allows_the_right_agent() -> None:
    caller = wi.normalize_principal(AGENT_P)
    got = wi.check_agent_binding(
        agent_id=SHARED,
        caller=caller,
        purpose="broker:access_token",
        bindings=_bindings(),
    )
    assert got.agent_id == SHARED


# --- signed agent_id in the context token ---------------------------------------------------------


def test_gateway_signs_routed_agent_and_keeps_everything_else() -> None:
    env = _envelope(FV, "alice@finvault.example")
    bound = ctx.EdgeAuthVerifier().bind_routed_agent(env, SHARED)
    before = ct.get_context_verifier().verify(
        env.context_token, audience="runtime"
    )
    after = ct.get_context_verifier().verify(
        bound.context_token, audience="runtime"
    )
    assert "agent_id" not in before
    assert after["agent_id"] == SHARED
    for name in (
        "tenant_id",
        "sub",
        "scopes",
        "src_jti",
        "cnf",
        "user_role",
        "session_id",
    ):
        assert after[name] == before[name]
    assert after["exp"] <= before["exp"]
    # the delegation tag follows the new token, so every in-process verifier accepts it
    ctx.verify_signed_adk_state(bound.to_adk_state(), audience="mcp")
    with pytest.raises(PermissionError, match="E_AGENT_ID_INVALID"):
        ctx.EdgeAuthVerifier().bind_routed_agent(env, "Bad Agent!")


def test_missing_agent_id_refused_only_when_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unbound = _envelope(FV, "alice@finvault.example")
    bound = ctx.EdgeAuthVerifier().bind_routed_agent(unbound, SHARED)
    verifier = ct.get_context_verifier()
    verifier.verify(
        unbound.context_token, audience="runtime"
    )  # flag off: unchanged
    monkeypatch.setenv(ct.REQUIRE_AGENT_ID_ENV, "1")
    for aud in ("runtime", "mcp"):
        with pytest.raises(
            ct.ContextTokenError, match="E_CONTEXT_TOKEN_AGENT_ID_MISSING"
        ):
            verifier.verify(unbound.context_token, audience=aud)
        assert (
            verifier.verify(bound.context_token, audience=aud)["agent_id"]
            == SHARED
        )
    with pytest.raises(PermissionError, match="E_SUBAGENT_STATE_TAMPERING"):
        ctx.verify_signed_adk_state(unbound.to_adk_state(), audience="mcp")


def test_malformed_agent_id_claim_refused_even_with_flag_off() -> None:
    env = _envelope(FV, "alice@finvault.example")
    claims = ct.get_context_verifier().verify(
        env.context_token, audience="runtime"
    )
    signer = _default_signer()
    header = {"alg": "ES256", "typ": "ctx+jwt", "kid": signer.kid}
    for bad in (["cymbal_shared_diagnostic_agent"], 7, "Robert'); DROP", ""):
        forged = _compact(header, {**claims, "agent_id": bad}, signer.sign)
        with pytest.raises(
            ct.ContextTokenError, match="E_CONTEXT_TOKEN_CLAIMS"
        ):
            ct.get_context_verifier().verify(forged, audience="runtime")


def test_exchange_carries_agent_id_into_broker_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound = _bound_envelope(SHARED)
    derived = ContextTokenExchange().exchange(
        bound.context_token, audience="broker"
    )[0]
    assert (
        ct.get_context_verifier().verify(derived, audience="broker")["agent_id"]
        == SHARED
    )
    unbound = _envelope(FV, "carol@finvault.example")
    plain = ContextTokenExchange().exchange(
        unbound.context_token, audience="broker"
    )[0]
    assert "agent_id" not in ct.get_context_verifier().verify(
        plain, audience="broker"
    )
    monkeypatch.setenv(ct.REQUIRE_AGENT_ID_ENV, "1")
    with pytest.raises(
        ct.ContextTokenError, match="E_CONTEXT_TOKEN_AGENT_ID_MISSING"
    ):
        ct.get_context_verifier().verify(plain, audience="broker")


# --- registry -------------------------------------------------------------------------------------


def _pdp(**over: Any) -> AgentRegistryPDP:
    b = _bindings(**over)
    return AgentRegistryPDP(agent_bindings=lambda: b)


def test_registry_fills_principal_and_purposes_from_config() -> None:
    entry = _pdp().agent_identity(SHARED)
    assert entry.workload_principal == AGENT_P
    assert "broker:access_token" in entry.allowed_purposes
    assert (
        AgentRegistryPDP(agent_bindings=dict)
        .agent_identity(SHARED)
        .workload_principal
        is None
    )


@pytest.mark.parametrize(
    ("agent_id", "caller", "purpose", "code"),
    [
        (None, AGENT_P, "mcp:read_runbook", "E_AGENT_ID_MISSING"),
        ("no_such_agent", AGENT_P, "mcp:read_runbook", "E_AGENT_NOT_AVAILABLE"),
        (
            SHARED,
            OTHER_AGENT_P,
            "mcp:read_runbook",
            "E_AGENT_PRINCIPAL_MISMATCH",
        ),
        (SHARED, None, "mcp:read_runbook", "E_AGENT_CALLER_MISSING"),
        (
            SHARED,
            AGENT_P,
            "mcp:create_jira_incident",
            "E_AGENT_PURPOSE_NOT_ALLOWED",
        ),
        # purpose listed in config, but the tool is not in the agent's catalog entitlements
        (
            SHARED,
            AGENT_P,
            "mcp:schedule_calendar_postmortem",
            "E_AGENT_TOOL_NOT_ENTITLED",
        ),
    ],
)
def test_registry_verify_agent_caller_refusals(
    agent_id: Any, caller: str | None, purpose: str, code: str
) -> None:
    principal = wi.normalize_principal(caller) if caller else None
    with pytest.raises(wi.AgentAuthorizationError, match=code):
        _pdp().verify_agent_caller(agent_id, principal, purpose)


def test_registry_refuses_unbound_agent_in_every_environment() -> None:
    pdp = AgentRegistryPDP(agent_bindings=dict)
    with pytest.raises(wi.AgentAuthorizationError, match="E_AGENT_NOT_BOUND"):
        pdp.verify_agent_caller(
            SHARED, wi.normalize_principal(AGENT_P), "mcp:read_runbook"
        )


def test_registry_allows_the_bound_agent() -> None:
    entry = _pdp().verify_agent_caller(
        SHARED, wi.normalize_principal(AGENT_P), "mcp:read_runbook"
    )
    assert entry.agent_id == SHARED


@pytest.mark.parametrize(
    "spec",
    [
        {
            "org_id": ORG,
            "bindings": {
                SHARED: {"workload_principal": "attacker@evil.example"}
            },
        },
        {
            "org_id": ORG,
            "bindings": {
                SHARED: {
                    "workload_principal": AGENT_P,
                    "allowed_purposes": ["admin:*"],
                }
            },
        },
        {
            "org_id": ORG,
            "bindings": {"Bad Id": {"workload_principal": AGENT_P}},
        },
        {"org_id": "not-digits"},
        {
            "org_id": "1",
            "bindings": {SHARED: {"workload_principal": AGENT_P}},
        },  # other org
        {
            "bindings": {SHARED: {"workload_principal": AGENT_P}}
        },  # agent principal, no org
    ],
)
def test_config_schema_rejects_malformed_bindings(spec: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        pc.AgentIdentitySettings.model_validate(spec)


def test_config_bindings_round_trip() -> None:
    cfg = pc.AgentIdentitySettings.model_validate(
        {
            "org_id": ORG,
            "bindings": {
                SHARED: {
                    "workload_principal": AGENT_P,
                    "allowed_purposes": ["mcp:read_runbook"],
                }
            },
        }
    )

    class _Cfg:
        agent_identity = cfg

    got = wi.bindings_from_config(_Cfg())
    assert got[SHARED].workload_principal == AGENT_P
    assert got[SHARED].allowed_purposes == frozenset({"mcp:read_runbook"})

    class _UnboundCfg:
        agent_identity = pc.AgentIdentitySettings(org_id=ORG)

    assert wi.bindings_from_config(_UnboundCfg()) == {}

    sandbox_bindings = wi.bindings_from_config(pc.get_platform_config())
    assert set(sandbox_bindings) == {SHARED, ALPHA}
    assert sandbox_bindings[SHARED].workload_principal.endswith(
        "/services/cymbal-agent-shared"
    )
    assert sandbox_bindings[ALPHA].workload_principal.endswith(
        "/services/cymbal-agent-finvault-alpha"
    )
    assert {
        "broker:access_token",
        "broker:id_token",
        "mcp:read_runbook",
    } <= sandbox_bindings[SHARED].allowed_purposes
    assert (
        "mcp:escalate_regulatory_filing"
        not in sandbox_bindings[SHARED].allowed_purposes
    )
    assert (
        "mcp:escalate_regulatory_filing"
        in sandbox_bindings[ALPHA].allowed_purposes
    )
    assert (
        "mcp:create_servicenow_incident"
        not in sandbox_bindings[ALPHA].allowed_purposes
    )


# --- broker ---------------------------------------------------------------------------------------


def _broker(
    *,
    callers: frozenset[str] = frozenset({RUNTIME_SA, AGENT_P}),
    require: bool = False,
    **b: Any,
) -> tuple[TestClient, FakeMint]:
    fake = FakeMint()
    bindings = _bindings(**b)
    broker = CredentialBroker(
        project_id=PROJECT,
        allowed_callers=callers,
        backend=fake,
        tenants=lambda: {FV: ()},
        expected_caller_audience=BROKER_URL,
        require_agent_binding=require,
        agent_bindings=lambda: bindings,
        agent_org_id=ORG,
    )
    return TestClient(create_app(broker)), fake


def _mint(client: TestClient, token: str, caller: str, **headers: str) -> Any:
    return client.post(
        PATH,
        headers={
            "X-Serverless-Authorization": caller,
            "X-Cymbal-Context-Token": token,
            **headers,
        },
        json={"kind": "access_token"},
    )


def _broker_token(agent_id: str | None = SHARED) -> str:
    env = (
        _bound_envelope(agent_id)
        if agent_id
        else _envelope(FV, "dan@finvault.example")
    )
    return ContextTokenExchange().exchange(
        env.context_token, audience="broker"
    )[0]


def test_broker_accepts_agent_principal_callers_when_listed() -> None:
    client, _ = _broker()
    assert _mint(client, _broker_token(), _agent_caller()).status_code == 200
    # an SA-style caller token can't impersonate the agent, nor can another org's agent pool
    resp = _mint(
        client,
        _broker_token(),
        _agent_caller(iss="https://accounts.google.com"),
    )
    assert resp.status_code == 403
    resp = _mint(
        client,
        _broker_token(),
        _agent_caller(iss=wi.agent_identity_issuer("1")),
    )
    assert resp.status_code == 403
    client, _ = _broker(callers=frozenset({RUNTIME_SA}))
    resp = _mint(client, _broker_token(), _agent_caller())
    assert (resp.status_code, resp.json()["detail"]["error"]) == (
        403,
        "E_BROKER_CALLER_NOT_ALLOWED",
    )


def test_broker_with_binding_off_is_unchanged_for_sa_callers() -> None:
    client, fake = _broker(callers=frozenset({RUNTIME_SA}))
    assert _mint(client, _broker_token(None), _caller()).status_code == 200
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    ("agent_id", "caller", "override", "code"),
    [
        (None, AGENT_P, {}, "E_AGENT_ID_MISSING"),
        (SHARED, OTHER_AGENT_P, {}, "E_AGENT_PRINCIPAL_MISMATCH"),
        (
            ALPHA,
            AGENT_P,
            {},
            "E_AGENT_PRINCIPAL_MISMATCH",
        ),  # A presents B's token
        (ALPHA, OTHER_AGENT_P, {}, "E_AGENT_PURPOSE_NOT_ALLOWED"),
        (
            SHARED,
            RUNTIME_SA,
            {},
            "E_AGENT_PRINCIPAL_MISMATCH",
        ),  # old shared SA is not the agent
    ],
)
def test_broker_binding_refusals(
    agent_id: str | None, caller: str, override: dict[str, Any], code: str
) -> None:
    client, fake = _broker(
        callers=frozenset({RUNTIME_SA, AGENT_P, OTHER_AGENT_P}), require=True
    )
    header = _caller() if caller == RUNTIME_SA else _agent_caller(caller)
    resp = _mint(client, _broker_token(agent_id), header)
    assert (resp.status_code, resp.json()["detail"]["error"]) == (403, code)
    assert fake.calls == []


def test_broker_binding_allows_the_routed_agent() -> None:
    client, fake = _broker(require=True)
    resp = _mint(client, _broker_token(SHARED), _agent_caller())
    assert resp.status_code == 200
    assert fake.calls[0][0] == "access_token"


def test_headers_and_body_cannot_inject_a_principal_or_agent() -> None:
    client, fake = _broker(
        callers=frozenset({RUNTIME_SA, AGENT_P}), require=True
    )
    token = _broker_token(SHARED)
    # The verified caller is the runtime SA; an unverified Authorization (Cloud Run passes it
    # through when X-Serverless-Authorization is present) and custom headers claiming the agent
    # principal are ignored.
    resp = _mint(
        client,
        token,
        _caller(),
        Authorization=_agent_caller(),
        **{
            "X-Agent-Principal": AGENT_P,
            "X-Goog-Authenticated-User-Email": AGENT_P,
        },
    )
    assert (resp.status_code, resp.json()["detail"]["error"]) == (
        403,
        "E_AGENT_PRINCIPAL_MISMATCH",
    )
    resp = client.post(
        PATH,
        headers={
            "X-Serverless-Authorization": _agent_caller(),
            "X-Cymbal-Context-Token": _broker_token(None),
        },
        json={"kind": "access_token", "agent_id": SHARED},
    )
    assert resp.status_code == 422  # the body can't name an agent
    assert fake.calls == []


def test_broker_rejects_malformed_allowed_callers_and_missing_bindings() -> (
    None
):
    with pytest.raises(ValueError, match="allowed callers"):
        CredentialBroker(
            project_id=PROJECT,
            allowed_callers=frozenset({"principal://evil/x"}),
            backend=FakeMint(),
            tenants=dict,
        )
    with pytest.raises(ValueError, match="org_id"):
        CredentialBroker(  # agent-identity caller listed, but no org pins its issuer
            project_id=PROJECT,
            allowed_callers=frozenset({AGENT_P}),
            backend=FakeMint(),
            tenants=dict,
        )
    with pytest.raises(ValueError, match="no agent bindings"):
        CredentialBroker(
            project_id=PROJECT,
            allowed_callers=frozenset({AGENT_P}),
            backend=FakeMint(),
            tenants=dict,
            require_agent_binding=True,
            agent_org_id=ORG,
        )


def test_broker_from_env_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROKER_EXPECTED_AUDIENCE", BROKER_URL)
    monkeypatch.setenv(
        "BROKER_ALLOWED_CALLERS", f"{RUNTIME_SA},not-an-identity"
    )
    with pytest.raises(RuntimeError, match="SA emails or Agent Identity"):
        broker_from_env(require_cloud_run=False)
    monkeypatch.setenv("BROKER_ALLOWED_CALLERS", f"{RUNTIME_SA},{AGENT_P}")
    assert broker_from_env(require_cloud_run=False) is not None
    monkeypatch.setenv("BROKER_REQUIRE_AGENT_BINDING", "1")
    # With sandbox.yaml's configured agent_identity.bindings, broker_from_env succeeds:
    assert broker_from_env(require_cloud_run=False) is not None
    # When no bindings exist in config, BROKER_REQUIRE_AGENT_BINDING=1 fails closed:
    monkeypatch.setattr(wi, "bindings_from_config", lambda _cfg: {})
    with pytest.raises(RuntimeError, match=r"agent_identity\.bindings"):
        broker_from_env(require_cloud_run=False)


# --- MCP ------------------------------------------------------------------------------------------


def _mcp_call(
    state: dict[str, Any],
    tool: str,
    caller: str | None,
    pdp: AgentRegistryPDP,
    **params: Any,
) -> dict[str, Any]:
    return asyncio.run(
        handle_mcp_jsonrpc_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool, **params},
            },
            verified_adk_state=state,
            caller_principal=wi.normalize_principal(caller) if caller else None,
            agent_registry=pdp,
        )
    )


@pytest.mark.parametrize(
    ("agent_id", "caller", "tool", "code"),
    [
        (None, AGENT_P, "read_runbook", "E_AGENT_ID_MISSING"),
        (SHARED, None, "read_runbook", "E_AGENT_CALLER_MISSING"),
        (SHARED, OTHER_AGENT_P, "read_runbook", "E_AGENT_PRINCIPAL_MISMATCH"),
        (SHARED, AGENT_P, "query_telemetry_rls", "E_AGENT_PURPOSE_NOT_ALLOWED"),
    ],
)
def test_mcp_per_tool_agent_refusals(
    monkeypatch: pytest.MonkeyPatch,
    agent_id: str | None,
    caller: str | None,
    tool: str,
    code: str,
) -> None:
    monkeypatch.setenv("MCP_REQUIRE_AGENT_BINDING", "1")
    env = (
        _bound_envelope(agent_id)
        if agent_id
        else _envelope(FV, "erin@finvault.example")
    )
    out = _mcp_call(env.to_adk_state(), tool, caller, _pdp())
    assert out["error"]["code"] == -32003
    assert code in out["error"]["message"]


def test_mcp_payload_cannot_supply_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_REQUIRE_AGENT_BINDING", "1")
    state = _bound_envelope(SHARED).to_adk_state()
    state["temp:agent_id"] = SHARED
    out = _mcp_call(
        state, "read_runbook", None, _pdp(), caller_principal=AGENT_P
    )
    assert out["error"]["code"] == -32003
    assert "E_AGENT_CALLER_MISSING" in out["error"]["message"]


def test_mcp_allows_bound_agent_and_is_unchanged_when_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unbound_state = _envelope(FV, "fay@finvault.example").to_adk_state()
    assert "result" in _mcp_call(
        unbound_state, "read_runbook", None, _pdp()
    )  # flag off
    monkeypatch.setenv("MCP_REQUIRE_AGENT_BINDING", "1")
    state = _bound_envelope(SHARED).to_adk_state()
    assert "result" in _mcp_call(state, "read_runbook", AGENT_P, _pdp())


# --- gateway routing ------------------------------------------------------------------------------


def test_gateway_binds_only_entitled_agents(
    monkeypatch: pytest.MonkeyPatch, gateway_state_restored: Any
) -> None:
    from app import main
    from scripts.sandbox_auth import SandboxCaller

    client = TestClient(main.app)
    calls: list[str] = []
    real = main.EDGE_VERIFIER.bind_routed_agent

    def spy(
        envelope: ctx.ContextEnvelope, agent_id: str
    ) -> ctx.ContextEnvelope:
        calls.append(agent_id)
        return real(envelope, agent_id)

    monkeypatch.setattr(main.EDGE_VERIFIER, "bind_routed_agent", spy)

    def post(tenant: str, sub: str, agent: str) -> Any:
        caller = SandboxCaller(
            client, tenant_id=tenant, sub=sub, role="sre_admin"
        )
        path = "/api/v1/invoke-agent"
        return client.post(
            path,
            json={"agent_id": agent},
            headers=caller.headers("POST", caller.url(path)),
        )

    post(FV, "alice@finvault.com", SHARED)
    assert calls == []  # flag off: tokens unchanged
    monkeypatch.setenv("CONTEXT_TOKEN_BIND_AGENT_ID", "1")
    assert post(FV, "alice@finvault.com", SHARED).status_code == 200
    assert calls == [SHARED]
    # RetailStream is not entitled to FinVault's private agent: refused before anything is signed
    resp = post("tenant-retailstream-beta", "bob@retailstream.com", ALPHA)
    assert resp.status_code == 403
    assert calls == [SHARED]


# --- review of #70: exact-match principals, pinned algorithm, routed agent == built agent ---------


@pytest.mark.parametrize(
    "value",
    [
        AGENT_P + "/extra",
        AGENT_P + "?x",
        AGENT_SPIFFE + "/extra",
        "x" + AGENT_P,
        RUNTIME_SA + ".evil.example",
        RUNTIME_SA + "/x",
    ],
)
def test_principals_must_match_exactly(value: str) -> None:
    assert wi.normalize_principal(value) is None
    with pytest.raises(ValidationError):
        pc.AgentIdentitySettings.model_validate(
            {"org_id": ORG, "bindings": {SHARED: {"workload_principal": value}}}
        )
    with pytest.raises(ValueError, match="allowed callers"):
        CredentialBroker(
            project_id=PROJECT,
            allowed_callers=frozenset({value}),
            backend=FakeMint(),
            tenants=dict,
            agent_org_id=ORG,
        )


def test_token_path_refuses_spiffe_with_trailing_segment() -> None:
    with pytest.raises(
        wi.CallerIdentityError, match="E_CALLER_PRINCIPAL_UNRECOGNIZED"
    ):
        wi.principal_from_verified_claims(
            _agent_claims(sub=AGENT_SPIFFE + "/x"),
            audience=BROKER_URL,
            agent_org_id=ORG,
        )


def test_agent_verifier_pins_rs256_against_hmac_and_none() -> None:
    """A JWKS client that hands back key material an HMAC/none token could use must still fail:
    only RS256 is accepted."""
    import jwt

    secret = b"s" * 64

    class _BytesJwks:
        def get_signing_key_from_jwt(self, token: str) -> Any:
            return type("K", (), {"key": secret})()

    verify = wi.agent_identity_token_verifier(ORG, jwk_client=_BytesJwks())
    hs = jwt.encode(_agent_claims(), secret, algorithm="HS256")
    none = jwt.encode(_agent_claims(), None, algorithm="none")
    for token in (hs, none):
        with pytest.raises(
            wi.CallerIdentityError, match="E_CALLER_TOKEN_UNVERIFIED"
        ):
            wi.verify_caller_identity(
                token, BROKER_URL, verify_signature=verify, agent_org_id=ORG
            )


def test_bind_routed_agent_updates_the_active_envelope() -> None:
    reset_token = ctx._ACTIVE_TENANT_ENVELOPE.set(None)
    try:
        env = _envelope(FV, "gus@finvault.example")
        bound = ctx.EdgeAuthVerifier().bind_routed_agent(env, SHARED)
        assert (
            ctx.get_active_envelope().context_token
            == bound.context_token
            != env.context_token
        )
    finally:
        ctx._ACTIVE_TENANT_ENVELOPE.reset(
            reset_token
        )  # leave no envelope behind


def test_gateway_refuses_requested_agent_that_differs_from_built_agent(
    monkeypatch: pytest.MonkeyPatch, gateway_state_restored: Any
) -> None:
    """A catalog agent without its own runtime would otherwise run the shared agent under its own
    signed id; the gateway refuses instead of binding."""
    from app import main
    from scripts.sandbox_auth import SandboxCaller

    client = TestClient(main.app)
    calls: list[str] = []
    monkeypatch.setattr(
        main.EDGE_VERIFIER,
        "bind_routed_agent",
        lambda e, a: calls.append(a) or e,
    )
    monkeypatch.setattr(
        main.REGISTRY_PDP, "verify_agent_access", lambda **_: None
    )
    monkeypatch.setenv("CONTEXT_TOKEN_BIND_AGENT_ID", "1")
    caller = SandboxCaller(
        client, tenant_id=FV, sub="alice@finvault.com", role="sre_admin"
    )
    path = "/api/v1/invoke-agent"
    resp = client.post(
        path,
        json={"agent_id": "future_catalog_agent"},
        headers=caller.headers("POST", caller.url(path)),
    )
    assert resp.status_code == 403
    assert "E_AGENT_ROUTING_MISMATCH" in resp.text
    assert calls == []
