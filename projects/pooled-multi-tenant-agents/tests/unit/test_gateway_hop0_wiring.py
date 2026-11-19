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

# pylint: disable=import-outside-toplevel,line-too-long,redefined-outer-name

"""Hop 0 wiring from config, and the sandbox-only dev issuer (roadmap step 1, PR 1).

Proves:
- tenants' `identity:` config builds the real Hop 0 gate (direct federation and broker mode);
- dev-issuer tokens go through the exact production verification + DPoP + OBO path;
- the dev issuer cannot exist outside a synthetic sandbox (config validation, 404 endpoint);
- forged, foreign-signed, expired or tenant-spoofing tokens are rejected.
"""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from agents import platform_config as pc
from agents.context import (
    EdgeAuthVerifier,
    register_tenant,
    reset_dynamic_tenants,
)
from agents.hop0_idp_federation import HttpJWKSResolver, StaticJWKSResolver
from app import auth
from app.main import app
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from scripts.sandbox_auth import SandboxCaller

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
HTU = "https://agent-gateway.cymbal.internal/api/v1/invoke-agent"
ROLES = ("sre_admin", "compliance_officer", "read_only_analyst")


@pytest.fixture
def sandbox() -> pc.PlatformConfig:
    return pc.load_platform_config("sandbox")


@pytest.fixture
def wiring(sandbox: pc.PlatformConfig) -> auth.Hop0Wiring:
    return auth.build_hop0(sandbox)


# --- Wiring ---------------------------------------------------------------------------------


@pytest.mark.parametrize("tenant_id", [FV, RS])
@pytest.mark.parametrize("role", ROLES)
def test_dev_issuer_tokens_verify_through_the_real_gate(
    wiring: auth.Hop0Wiring, tenant_id: str, role: str
) -> None:
    token = wiring.dev_issuer.mint(
        tenant_id=tenant_id, sub="user@example.com", role=role
    )
    claims = wiring.gate.verify_and_normalize(token)
    assert claims["tenant_id"] == tenant_id
    assert claims["user_role"] == role
    assert claims["auth_broker"] == "direct"


def test_full_hop0_to_envelope_path_with_client_dpop(
    wiring: auth.Hop0Wiring,
) -> None:
    token = wiring.dev_issuer.mint(
        tenant_id=RS, sub="bob@retailstream.com", role="read_only_analyst"
    )
    caller = SandboxCaller(None, tenant_id=RS, sub="bob@retailstream.com")
    envelope = EdgeAuthVerifier().exchange_federated_idp_token(
        inbound_idp_jwt=token,
        dpop_proof_jwt=caller.dpop_proof("POST", HTU),
        hop0_gate=wiring.gate,
    )
    assert envelope.tenant.tenant_id == RS
    assert envelope.security.user_role == "read_only_analyst"
    assert envelope.security.idp_provider == "microsoft_entra_oidc"


def test_entra_tokens_carry_the_configured_directory(
    wiring: auth.Hop0Wiring,
) -> None:
    token = wiring.dev_issuer.mint(
        tenant_id=RS, sub="bob@retailstream.com", role="sre_admin"
    )
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["tid"] == "retailstream-tenant-id"
    assert claims["roles"] == [
        "Cymbal.SreAdmin"
    ]  # Entra App Role name, mapped by the gate


def test_production_wiring_has_no_dev_keys(sandbox: pc.PlatformConfig) -> None:
    prod_like = sandbox.model_copy(
        update={
            "identity": sandbox.identity.model_copy(
                update={"dev_issuer": False}
            )
        }
    )
    wired = auth.build_hop0(prod_like)
    assert wired.dev_issuer is None
    assert isinstance(wired.gate.resolver, HttpJWKSResolver)


def test_broker_mode_tenant_from_config_verifies(
    sandbox: pc.PlatformConfig,
) -> None:
    broker_iss = "https://securetoken.google.com/cymbal-sandbox-idp"
    register_tenant(
        tenant_id="tenant-broker-demo",
        display_name="Broker demo",
        iss=broker_iss,
    )
    try:
        data = sandbox.model_dump()
        data["identity"]["broker_project_id"] = "cymbal-sandbox-idp"
        data["tenants"] = [
            *data["tenants"],
            {
                "tenant_id": "tenant-broker-demo",
                "display_name": "Broker demo",
                "tier": "standard",
                "cmek_key": "tenant-broker-demo-cmek",
                "identity": {
                    "issuer": broker_iss,
                    "provider": "okta",
                    "gcip_tenant_id": "broker-demo-x1y2",
                    "sign_in_providers": ["saml.okta-broker-demo"],
                },
            },
        ]
        cfg = pc.PlatformConfig.model_validate(data)
        wired = auth.build_hop0(cfg)
        token = wired.dev_issuer.mint(
            tenant_id="tenant-broker-demo",
            sub="gcip-uid-1",
            role="compliance_officer",
        )
        claims = wired.gate.verify_and_normalize(token)
        assert claims["tenant_id"] == "tenant-broker-demo"
        assert claims["user_role"] == "compliance_officer"
        assert claims["auth_broker"] == "google_identity_platform"
    finally:
        reset_dynamic_tenants()


# --- The dev issuer cannot exist outside a synthetic sandbox ---------------------------------


@pytest.mark.parametrize(
    ("environment", "classification"),
    [
        ("customer-example", "customer"),
        ("sandbox", "customer"),
        ("staging", "synthetic"),
    ],
)
def test_dev_issuer_is_rejected_outside_a_synthetic_sandbox(
    sandbox: pc.PlatformConfig, environment: str, classification: str
) -> None:
    data = sandbox.model_dump()
    data["environment"] = environment
    data["data_classification"] = classification
    with pytest.raises(ValueError, match="dev_issuer"):
        pc.PlatformConfig.model_validate(data)


def test_customer_template_has_no_dev_issuer() -> None:
    cfg = pc.load_platform_config("customer.example")
    assert cfg.identity.dev_issuer is False
    assert cfg.tenants[0].identity.provider == "okta"


def test_broker_tenants_need_a_broker_and_its_issuer(
    sandbox: pc.PlatformConfig,
) -> None:
    data = sandbox.model_dump()
    data["tenants"][0]["identity"] |= {
        "gcip_tenant_id": "x",
        "sign_in_providers": ["saml.x"],
    }
    with pytest.raises(ValueError, match="broker_project_id"):
        pc.PlatformConfig.model_validate(data)
    data["identity"]["broker_project_id"] = "cymbal-sandbox-idp"
    with pytest.raises(ValueError, match="broker tenants must use issuer"):
        pc.PlatformConfig.model_validate(data)


# --- Forged tokens ---------------------------------------------------------------------------


def _claims(wiring: auth.Hop0Wiring, tenant_id: str) -> dict[str, Any]:
    token = wiring.dev_issuer.mint(
        tenant_id=tenant_id, sub="mallory@example.com", role="sre_admin"
    )
    return jwt.decode(token, options={"verify_signature": False})


def test_token_signed_by_another_key_is_rejected(
    wiring: auth.Hop0Wiring,
) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        _claims(wiring, FV),
        other,
        algorithm="RS256",
        headers={"kid": wiring.dev_issuer.kid},
    )
    with pytest.raises(PermissionError, match="E_HOP0_INVALID_SIGNATURE"):
        wiring.gate.verify_and_normalize(forged)


def test_token_claiming_another_tenant_is_rejected(
    wiring: auth.Hop0Wiring,
) -> None:
    claims = _claims(wiring, FV) | {"tenant_id": RS}
    token = jwt.encode(
        claims,
        wiring.dev_issuer.private_key,
        algorithm="RS256",
        headers={"kid": wiring.dev_issuer.kid},
    )
    with pytest.raises(PermissionError, match="E_HOP0_TENANT_CLAIM_SPOOF"):
        wiring.gate.verify_and_normalize(token)


def test_expired_token_is_rejected(wiring: auth.Hop0Wiring) -> None:
    now = int(time.time())
    claims = _claims(wiring, FV) | {"iat": now - 7200, "exp": now - 3600}
    token = jwt.encode(
        claims,
        wiring.dev_issuer.private_key,
        algorithm="RS256",
        headers={"kid": wiring.dev_issuer.kid},
    )
    with pytest.raises(PermissionError, match="E_HOP0_TOKEN_EXPIRED"):
        wiring.gate.verify_and_normalize(token)


# --- Sandbox token endpoint ------------------------------------------------------------------


def test_sandbox_token_endpoint_issues_verifiable_tokens() -> None:
    client = TestClient(app)
    caller = SandboxCaller(
        client,
        tenant_id=FV,
        sub="alice@finvault.com",
        role="compliance_officer",
    )
    claims = auth.get_hop0().gate.verify_and_normalize(caller.id_token)
    assert (claims["tenant_id"], claims["user_role"]) == (
        FV,
        "compliance_officer",
    )
    assert set(caller.headers("POST", HTU)) == {"Authorization", "DPoP"}


def test_sandbox_token_endpoint_rejects_unknown_tenants_and_extra_fields() -> (
    None
):
    client = TestClient(app)
    assert (
        client.post(
            "/api/v1/sandbox/token",
            json={"tenant_id": "tenant-nope", "sub": "x"},
        ).status_code
        == 400
    )
    extra = {"tenant_id": FV, "sub": "x", "tenant_override": RS}
    assert client.post("/api/v1/sandbox/token", json=extra).status_code == 422


def test_sandbox_token_endpoint_is_404_when_the_dev_issuer_is_off(
    monkeypatch: pytest.MonkeyPatch, wiring: auth.Hop0Wiring
) -> None:
    monkeypatch.setattr(
        auth,
        "get_hop0",
        lambda: auth.Hop0Wiring(gate=wiring.gate, dev_issuer=None),
    )
    resp = TestClient(app).post(
        "/api/v1/sandbox/token", json={"tenant_id": FV, "sub": "x"}
    )
    assert resp.status_code == 404


def test_dev_issuer_refuses_to_start_when_disabled(
    sandbox: pc.PlatformConfig,
) -> None:
    off = sandbox.model_copy(
        update={
            "identity": sandbox.identity.model_copy(
                update={"dev_issuer": False}
            )
        }
    )
    with pytest.raises(auth.SandboxIssuerDisabled):
        auth.DevIssuer.create(off, StaticJWKSResolver())


# --- Review hardening: dev issuer pinned to the sandbox project; customer identity rules -------


def test_dev_issuer_is_refused_when_running_in_another_project(
    sandbox: pc.PlatformConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A defaulted CYMBAL_ENV=sandbox deployed into a real project must not mint tokens."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-production-project")
    wiring = auth.build_hop0(sandbox)
    assert wiring.dev_issuer is None
    assert isinstance(wiring.gate.resolver, HttpJWKSResolver)


def test_dev_issuer_runs_in_the_sandbox_project(
    sandbox: pc.PlatformConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", sandbox.gcp.project_id)
    assert auth.build_hop0(sandbox).dev_issuer is not None


def test_sandbox_token_defaults_to_least_privilege_and_validates_role() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/v1/sandbox/token", json={"tenant_id": FV, "sub": "u@finvault.com"}
    )
    assert resp.status_code == 200
    claims = jwt.decode(
        resp.json()["id_token"], options={"verify_signature": False}
    )
    assert claims["user_role"] == "read_only_analyst"
    for bad in (
        {"role": "superuser"},
        {"tenant_id": "X" * 64},
        {"tenant_id": "Tenant_FV"},
    ):
        body = {"tenant_id": FV, "sub": "u@finvault.com", **bad}
        assert (
            client.post("/api/v1/sandbox/token", json=body).status_code == 422
        )


def _customer_cfg(**identity: Any) -> dict[str, Any]:
    base = pc.load_platform_config("customer.example").model_dump()
    tenant = base["tenants"][0]
    tenant["identity"] = {**tenant["identity"], **identity}
    return base


@pytest.mark.parametrize(
    ("identity", "message"),
    [
        ({"role_map": None}, "role_map is required"),
        ({"audience": None}, "audience is required"),
        (
            {"provider": "google", "issuer": "https://accounts.google.com"},
            "direct 'google' federation",
        ),
    ],
)
def test_customer_data_needs_explicit_identity_settings(
    identity: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        pc.PlatformConfig.model_validate(_customer_cfg(**identity))


def test_shipped_customer_template_satisfies_the_customer_rules() -> None:
    cfg = pc.load_platform_config("customer.example")
    assert all(t.identity.role_map and t.identity.audience for t in cfg.tenants)


def test_two_tenants_with_one_issuer_cannot_be_wired(
    sandbox: pc.PlatformConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agents.context import TENANT_DIRECTORY

    monkeypatch.setitem(
        TENANT_DIRECTORY, "tenant-finvault-copy", dict(TENANT_DIRECTORY[FV])
    )
    fv = next(t for t in sandbox.tenants if t.tenant_id == FV)
    clash = fv.model_copy(
        update={"tenant_id": "tenant-finvault-copy"}
    )  # same issuer
    cfg = sandbox.model_copy(update={"tenants": (fv, clash)})
    with pytest.raises(Exception, match="DUPLICATE_ISSUER"):
        auth.build_registry(cfg)
