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

# pylint: disable=line-too-long,redefined-outer-name,unused-argument

"""Hop 0 primary mode: Google Identity Platform as the pooled auth broker (Pattern A diagram).

Tenant A signs in with Okta (SAML), Tenant B with Google, Tenant C with Ping (OIDC), and Tenant D
with Microsoft Entra ID (OIDC). All of them reach the gateway as one Identity Platform token type
(`iss = https://securetoken.google.com/{project}`); `firebase.tenant` selects the pooled tenant.
Tokens are minted locally with RSA keys generated at test time.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from typing import Any

import jwt
import pytest
from agents.context import (
    AsymmetricDPoPProvider,
    EdgeAuthVerifier,
    SubscriptionTier,
    register_tenant,
    reset_dynamic_tenants,
)
from agents.hop0_idp_federation import (
    DEFAULT_OKTA_GROUP_MAP,
    GCIP_JWKS_URI,
    FederatedIdP,
    FederatedIdPConfig,
    HopZeroFederationGate,
    IdentityPlatformBrokerConfig,
    IdentityPlatformTenantConfig,
    IdPFederationRegistry,
    StaticJWKSResolver,
)
from cryptography.hazmat.primitives.asymmetric import rsa

PROJECT = "cymbal-pooled-identity"
BROKER = IdentityPlatformBrokerConfig(project_id=PROJECT)
BROKER_ISS = f"https://securetoken.google.com/{PROJECT}"
INVOKE_HTU = "https://agent-gateway.cymbal.internal/api/v1/invoke-agent"

# (pooled tenant_id, Identity Platform tenant, upstream IdP, allowed sign-in provider)
TENANTS = {
    "A": (
        "tenant-a-okta",
        "tenant-a-1x2y3",
        FederatedIdP.OKTA_ENTERPRISE_OIDC,
        "saml.okta-tenant-a",
    ),
    "B": (
        "tenant-b-google",
        "tenant-b-4d5e6",
        FederatedIdP.GOOGLE_WORKSPACE_OIDC,
        "google.com",
    ),
    "C": (
        "tenant-c-ping",
        "tenant-c-7g8h9",
        FederatedIdP.PING_IDENTITY,
        "oidc.ping-tenant-c",
    ),
    "D": (
        "tenant-d-entra",
        "tenant-d-0j1k2",
        FederatedIdP.MICROSOFT_ENTRA_OIDC,
        "oidc.entra-tenant-d",
    ),
}


class FakeIdentityPlatform:
    """Local stand-in for Identity Platform's signing keys and token format."""

    def __init__(
        self, resolver: StaticJWKSResolver, kid: str = "gcip-key-1"
    ) -> None:
        self.kid = kid
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        resolver.add_key(
            issuer=BROKER_ISS, kid=kid, public_key=self.private_key.public_key()
        )

    def mint(
        self,
        *,
        gcip_tenant: str | None,
        sign_in_provider: str,
        sub: str = "gcip-uid-0001",
        aud: str = PROJECT,
        ttl: int = 3600,
        auth_time_offset: int = -30,
        sign_in_attributes: dict[str, Any] | None = None,
        signing_key: Any = None,
        **custom_claims: Any,
    ) -> str:
        now = int(time.time())
        firebase: dict[str, Any] = {
            "sign_in_provider": sign_in_provider,
            "identities": {},
        }
        if gcip_tenant is not None:
            firebase["tenant"] = gcip_tenant
        if sign_in_attributes is not None:
            firebase["sign_in_attributes"] = sign_in_attributes
        claims = {
            "iss": BROKER_ISS,
            "aud": aud,
            "sub": sub,
            "user_id": sub,
            "iat": now,
            "exp": now + ttl,
            "auth_time": now + auth_time_offset,
            "firebase": firebase,
            **custom_claims,
        }
        return jwt.encode(
            claims,
            signing_key or self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid},
        )


@pytest.fixture
def pooled_tenants() -> Iterator[None]:
    for tenant_id, _, _, _ in TENANTS.values():
        register_tenant(
            tenant_id=tenant_id,
            display_name=tenant_id,
            tier=SubscriptionTier.STANDARD,
            iss=BROKER_ISS,
        )
    yield
    reset_dynamic_tenants()


@pytest.fixture
def resolver() -> StaticJWKSResolver:
    return StaticJWKSResolver()


@pytest.fixture
def registry(pooled_tenants: None) -> IdPFederationRegistry:
    reg = IdPFederationRegistry(identity_platform=BROKER)
    for tenant_id, gcip_tenant, upstream, provider in TENANTS.values():
        reg.register_identity_platform_tenant(
            IdentityPlatformTenantConfig(
                tenant_id=tenant_id,
                gcip_tenant_id=gcip_tenant,
                upstream_idp=upstream,
                allowed_sign_in_providers=(provider,),
            )
        )
    return reg


@pytest.fixture
def gate(
    registry: IdPFederationRegistry, resolver: StaticJWKSResolver
) -> HopZeroFederationGate:
    return HopZeroFederationGate(registry=registry, resolver=resolver)


@pytest.fixture
def gcip(resolver: StaticJWKSResolver) -> FakeIdentityPlatform:
    return FakeIdentityPlatform(resolver)


def _dpop() -> str:
    key = AsymmetricDPoPProvider.generate_client_keypair()
    return AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=key, htu=INVOKE_HTU
    )


# ---------------------------------------------------------------------------------------------
# Happy paths: every tenant/IdP from the Pattern A diagram reaches Hop 1 through one broker
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("label", ["A", "B", "C", "D"])
def test_each_tenant_idp_federates_through_identity_platform(
    label: str, gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    tenant_id, gcip_tenant, upstream, provider = TENANTS[label]
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        sub=f"uid-{label}",
        cymbal_role="read_only_analyst",
    )
    envelope = EdgeAuthVerifier().exchange_federated_idp_token(
        inbound_idp_jwt=token, dpop_proof_jwt=_dpop(), hop0_gate=gate
    )

    assert envelope.tenant.tenant_id == tenant_id
    assert envelope.security.sub == f"uid-{label}"
    assert envelope.security.iss == BROKER_ISS
    assert envelope.security.idp_provider == str(upstream)
    assert envelope.security.user_role == "read_only_analyst"
    assert envelope.tenant.cmek_key_name.endswith(
        f"/cryptoKeys/{tenant_id}-cmek"
    )


def test_normalized_claims_record_broker_provenance(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["A"]
    claims = gate.verify_and_normalize(
        gcip.mint(
            gcip_tenant=gcip_tenant,
            sign_in_provider=provider,
            cymbal_role="sre_admin",
        )
    )
    assert claims["auth_broker"] == "google_identity_platform"
    assert claims["sign_in_provider"] == "saml.okta-tenant-a"
    assert claims["gcip_tenant_id"] == gcip_tenant


def test_role_can_come_from_saml_sign_in_attributes_mapping(
    pooled_tenants: None,
    resolver: StaticJWKSResolver,
    gcip: FakeIdentityPlatform,
) -> None:
    reg = IdPFederationRegistry(identity_platform=BROKER)
    tenant_id, gcip_tenant, upstream, provider = TENANTS["A"]
    reg.register_identity_platform_tenant(
        IdentityPlatformTenantConfig(
            tenant_id=tenant_id,
            gcip_tenant_id=gcip_tenant,
            upstream_idp=upstream,
            allowed_sign_in_providers=(provider,),
            role_claim="groups",
            group_to_role=DEFAULT_OKTA_GROUP_MAP,
        )
    )
    gate = HopZeroFederationGate(registry=reg, resolver=resolver)
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        sign_in_attributes={
            "groups": ["Everyone", "cymbal-compliance-officers"]
        },
    )
    assert gate.verify_and_normalize(token)["user_role"] == "compliance_officer"


def test_direct_fallback_and_broker_coexist(
    registry: IdPFederationRegistry,
    resolver: StaticJWKSResolver,
    gcip: FakeIdentityPlatform,
) -> None:
    registry.register(
        FederatedIdPConfig(
            tenant_id="tenant-finvault-alpha",
            provider=FederatedIdP.GOOGLE_WORKSPACE_OIDC,
            issuer="https://accounts.google.com",
            audience="https://agent-gateway.cymbal.internal",
            role_claim="user_role",
        )
    )
    google_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    resolver.add_key(
        issuer="https://accounts.google.com",
        kid="g1",
        public_key=google_key.public_key(),
    )
    now = int(time.time())
    direct = jwt.encode(
        {
            "iss": "https://accounts.google.com",
            "aud": "https://agent-gateway.cymbal.internal",
            "sub": "alice@finvault.com",
            "iat": now,
            "exp": now + 3600,
            "user_role": "sre_admin",
        },
        google_key,
        algorithm="RS256",
        headers={"kid": "g1"},
    )
    gate = HopZeroFederationGate(registry=registry, resolver=resolver)
    assert gate.verify_and_normalize(direct)["auth_broker"] == "direct"

    _, gcip_tenant, _, provider = TENANTS["B"]
    brokered = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        cymbal_role="sre_admin",
    )
    assert (
        gate.verify_and_normalize(brokered)["auth_broker"]
        == "google_identity_platform"
    )


# ---------------------------------------------------------------------------------------------
# Threats specific to the shared-issuer broker
# ---------------------------------------------------------------------------------------------


def test_rejects_project_level_user_without_tenant(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    token = gcip.mint(
        gcip_tenant=None, sign_in_provider="password", cymbal_role="sre_admin"
    )
    with pytest.raises(PermissionError, match="E_HOP0_GCIP_MISSING_TENANT"):
        gate.verify_and_normalize(token)


def test_rejects_unbound_identity_platform_tenant(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    token = gcip.mint(
        gcip_tenant="tenant-z-unknown",
        sign_in_provider="saml.okta-tenant-a",
        cymbal_role="sre_admin",
    )
    with pytest.raises(PermissionError, match="E_HOP0_GCIP_UNKNOWN_TENANT"):
        gate.verify_and_normalize(token)


def test_rejects_sign_in_provider_not_onboarded_for_tenant(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, _ = TENANTS["A"]
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider="password",
        cymbal_role="sre_admin",
    )
    with pytest.raises(
        PermissionError, match="E_HOP0_GCIP_PROVIDER_NOT_ALLOWED"
    ):
        gate.verify_and_normalize(token)


def test_rejects_another_tenants_provider_inside_a_tenant(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant_a, _, _ = TENANTS["A"]
    _, _, _, ping_provider = TENANTS["C"]
    token = gcip.mint(
        gcip_tenant=gcip_tenant_a,
        sign_in_provider=ping_provider,
        cymbal_role="sre_admin",
    )
    with pytest.raises(
        PermissionError, match="E_HOP0_GCIP_PROVIDER_NOT_ALLOWED"
    ):
        gate.verify_and_normalize(token)


def test_rejects_token_from_another_identity_platform_project(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["A"]
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        aud="some-other-firebase-project",
        cymbal_role="sre_admin",
    )
    with pytest.raises(PermissionError, match="E_HOP0_AUDIENCE_MISMATCH"):
        gate.verify_and_normalize(token)


def test_rejects_forged_broker_signature(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["A"]
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        signing_key=attacker,
        cymbal_role="sre_admin",
    )
    with pytest.raises(PermissionError, match="E_HOP0_INVALID_SIGNATURE"):
        gate.verify_and_normalize(token)


def test_rejects_long_lived_token(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["A"]
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        ttl=86_400,
        cymbal_role="sre_admin",
    )
    with pytest.raises(PermissionError, match="E_HOP0_TOKEN_LIFETIME_TOO_LONG"):
        gate.verify_and_normalize(token)


def test_rejects_future_auth_time(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["A"]
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        auth_time_offset=3600,
        cymbal_role="sre_admin",
    )
    with pytest.raises(PermissionError, match="E_HOP0_INVALID_AUTH_TIME"):
        gate.verify_and_normalize(token)


def test_rejects_oversized_subject(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["A"]
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        sub="u" * 129,
        cymbal_role="sre_admin",
    )
    with pytest.raises(PermissionError, match="E_HOP0_INVALID_SUBJECT"):
        gate.verify_and_normalize(token)


def test_rejects_custom_tenant_id_claim_spoof(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["A"]
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        cymbal_role="sre_admin",
        tenant_id="tenant-b-google",
    )
    with pytest.raises(PermissionError, match="E_HOP0_TENANT_CLAIM_SPOOF"):
        gate.verify_and_normalize(token)


def test_rejects_missing_role_claim(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["C"]
    token = gcip.mint(gcip_tenant=gcip_tenant, sign_in_provider=provider)
    with pytest.raises(PermissionError, match="E_HOP0_NO_RBAC_ROLE"):
        gate.verify_and_normalize(token)


def test_rejects_unknown_role_value(
    gate: HopZeroFederationGate, gcip: FakeIdentityPlatform
) -> None:
    _, gcip_tenant, _, provider = TENANTS["C"]
    token = gcip.mint(
        gcip_tenant=gcip_tenant,
        sign_in_provider=provider,
        cymbal_role="super_admin",
    )
    with pytest.raises(PermissionError, match="E_HOP0_NO_RBAC_ROLE"):
        gate.verify_and_normalize(token)


# ---------------------------------------------------------------------------------------------
# Control-plane registration guards
# ---------------------------------------------------------------------------------------------


def test_broker_defaults_match_identity_platform_token_contract() -> None:
    assert BROKER.issuer == BROKER_ISS
    assert BROKER.audience == PROJECT
    assert BROKER.allowed_algs == ("RS256",)
    assert BROKER.jwks_uri == GCIP_JWKS_URI
    assert BROKER.max_token_lifetime_seconds == 3600


def test_broker_issuer_cannot_be_registered_as_direct_issuer() -> None:
    with pytest.raises(ValueError, match="E_HOP0_BROKER_ISSUER_RESERVED"):
        FederatedIdPConfig(
            tenant_id="tenant-a-okta",
            provider=FederatedIdP.OKTA_ENTERPRISE_OIDC,
            issuer=BROKER_ISS,
            audience=PROJECT,
        )


def test_identity_platform_tenant_cannot_be_bound_twice(
    registry: IdPFederationRegistry,
) -> None:
    register_tenant(
        tenant_id="tenant-e-dup", display_name="dup", iss=BROKER_ISS
    )
    with pytest.raises(ValueError, match="E_HOP0_DUPLICATE_GCIP_TENANT"):
        registry.register_identity_platform_tenant(
            IdentityPlatformTenantConfig(
                tenant_id="tenant-e-dup",
                gcip_tenant_id=TENANTS["A"][1],
                upstream_idp=FederatedIdP.OKTA_ENTERPRISE_OIDC,
                allowed_sign_in_providers=("saml.okta-tenant-a",),
            )
        )


def test_pooled_tenant_cannot_bind_two_identity_platform_tenants(
    registry: IdPFederationRegistry,
) -> None:
    with pytest.raises(ValueError, match="E_HOP0_DUPLICATE_TENANT_BINDING"):
        registry.register_identity_platform_tenant(
            IdentityPlatformTenantConfig(
                tenant_id=TENANTS["A"][0],
                gcip_tenant_id=f"tenant-a-second-{uuid.uuid4().hex[:4]}",
                upstream_idp=FederatedIdP.OKTA_ENTERPRISE_OIDC,
                allowed_sign_in_providers=("saml.okta-tenant-a",),
            )
        )


def test_broker_tenant_requires_tenant_directory_broker_issuer() -> None:
    reg = IdPFederationRegistry(identity_platform=BROKER)
    with pytest.raises(ValueError, match="E_HOP0_TENANT_ISSUER_MISMATCH"):
        reg.register_identity_platform_tenant(
            IdentityPlatformTenantConfig(
                tenant_id="tenant-finvault-alpha",
                gcip_tenant_id="tenant-fv-0001",
                upstream_idp=FederatedIdP.GOOGLE_WORKSPACE_OIDC,
                allowed_sign_in_providers=("google.com",),
            )
        )


def test_broker_tenant_requires_configured_broker(pooled_tenants: None) -> None:
    with pytest.raises(ValueError, match="E_HOP0_BROKER_NOT_CONFIGURED"):
        IdPFederationRegistry().register_identity_platform_tenant(
            IdentityPlatformTenantConfig(
                tenant_id=TENANTS["A"][0],
                gcip_tenant_id=TENANTS["A"][1],
                upstream_idp=FederatedIdP.OKTA_ENTERPRISE_OIDC,
                allowed_sign_in_providers=("saml.okta-tenant-a",),
            )
        )


def test_tenant_config_requires_at_least_one_sign_in_provider() -> None:
    with pytest.raises(ValueError, match="E_HOP0_NO_SIGN_IN_PROVIDERS"):
        IdentityPlatformTenantConfig(
            tenant_id="tenant-a-okta",
            gcip_tenant_id="tenant-a-1x2y3",
            upstream_idp=FederatedIdP.OKTA_ENTERPRISE_OIDC,
            allowed_sign_in_providers=(),
        )
