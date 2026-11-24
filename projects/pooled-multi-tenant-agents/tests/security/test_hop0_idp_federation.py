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
# pylint: disable=redefined-outer-name,reimported

"""Hop 0 Multi-IdP Federation tests (Okta, Microsoft Entra ID, Google OIDC).

All tokens are minted locally with keys generated at test time (nothing is committed), so the suite
is hermetic. Each negative test maps to one row of the threat table in
`docs/adr/0009-hop-0-multi-idp-federation.md`.
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
    propagate_to_subagent,
    register_tenant,
    reset_dynamic_tenants,
)
from agents.hop0_idp_federation import (
    DEFAULT_GATEWAY_AUDIENCE,
    DEFAULT_OKTA_GROUP_MAP,
    FederatedIdP,
    FederatedIdPConfig,
    HopZeroFederationGate,
    HttpJWKSResolver,
    IdPFederationRegistry,
    StaticJWKSResolver,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

GOOGLE_ISS = "https://accounts.google.com"
ENTRA_TID = "retailstream-tenant-id"
ENTRA_ISS = f"https://login.microsoftonline.com/{ENTRA_TID}/v2.0"
OKTA_ISS = "https://healthcore.okta.com/oauth2/default"
OKTA_TENANT = "tenant-healthcore-gamma"
OKTA_CLIENT_ID = "0oa-healthcore-agent-gateway"
INVOKE_HTU = "https://agent-gateway.cymbal.internal/api/v1/invoke-agent"


class FakeIdP:
    """A local RS256 IdP: signing key + `kid`, published into a `StaticJWKSResolver`."""

    def __init__(
        self, issuer: str, resolver: StaticJWKSResolver, kid: str = "key-1"
    ) -> None:
        self.issuer = issuer
        self.kid = kid
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        resolver.add_key(
            issuer=issuer, kid=kid, public_key=self.private_key.public_key()
        )

    def mint(
        self,
        *,
        sub: str,
        aud: str = DEFAULT_GATEWAY_AUDIENCE,
        ttl: int = 3600,
        alg: str = "RS256",
        kid: str | None = None,
        signing_key: Any = None,
        **extra: Any,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "sub": sub,
            "aud": aud,
            "iat": now,
            "exp": now + ttl,
            "jti": f"idp-{uuid.uuid4().hex[:12]}",
            **extra,
        }
        return jwt.encode(
            claims,
            signing_key or self.private_key,
            algorithm=alg,
            headers={"kid": kid or self.kid},
        )


@pytest.fixture
def okta_tenant() -> Iterator[str]:
    register_tenant(
        tenant_id=OKTA_TENANT,
        display_name="HealthCore Systems",
        tier=SubscriptionTier.ENTERPRISE,
        iss=OKTA_ISS,
        org_unit="healthcare-hipaa-us",
    )
    yield OKTA_TENANT
    reset_dynamic_tenants()


@pytest.fixture
def resolver() -> StaticJWKSResolver:
    return StaticJWKSResolver()


@pytest.fixture
def registry(okta_tenant: str) -> IdPFederationRegistry:
    reg = IdPFederationRegistry.with_anchor_tenants()
    reg.register(
        FederatedIdPConfig(
            tenant_id=okta_tenant,
            provider=FederatedIdP.OKTA_ENTERPRISE_OIDC,
            issuer=OKTA_ISS,
            audience=OKTA_CLIENT_ID,
            role_claim="groups",
            group_to_role=DEFAULT_OKTA_GROUP_MAP,
        )
    )
    return reg


@pytest.fixture
def gate(
    registry: IdPFederationRegistry, resolver: StaticJWKSResolver
) -> HopZeroFederationGate:
    return HopZeroFederationGate(registry=registry, resolver=resolver)


@pytest.fixture
def okta(resolver: StaticJWKSResolver) -> FakeIdP:
    return FakeIdP(OKTA_ISS, resolver)


@pytest.fixture
def entra(resolver: StaticJWKSResolver) -> FakeIdP:
    return FakeIdP(ENTRA_ISS, resolver)


@pytest.fixture
def google(resolver: StaticJWKSResolver) -> FakeIdP:
    return FakeIdP(GOOGLE_ISS, resolver)


def _dpop() -> str:
    client_key = AsymmetricDPoPProvider.generate_client_keypair()
    return AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=client_key, htu=INVOKE_HTU
    )


# ---------------------------------------------------------------------------------------------
# Happy paths: Hop 0 -> Hop 1 end to end
# ---------------------------------------------------------------------------------------------


def test_okta_token_federates_to_healthcore_with_group_mapped_role(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-dana",
        aud=OKTA_CLIENT_ID,
        groups=["Everyone", "cymbal-read-only-analysts"],
    )
    envelope = EdgeAuthVerifier().exchange_federated_idp_token(
        inbound_idp_jwt=token, dpop_proof_jwt=_dpop(), hop0_gate=gate
    )

    assert envelope.tenant.tenant_id == OKTA_TENANT
    assert envelope.security.idp_provider == "okta_enterprise_oidc"
    assert envelope.security.user_role == "read_only_analyst"
    assert envelope.security.iss == OKTA_ISS
    assert "2lo:cymbal.telemetry.read" in envelope.tenant.authorized_scopes
    assert envelope.tenant.cmek_key_name.endswith(
        f"/cryptoKeys/{OKTA_TENANT}-cmek"
    )


def test_entra_token_federates_to_retailstream_with_app_role(
    gate: HopZeroFederationGate, entra: FakeIdP
) -> None:
    token = entra.mint(sub="bob-oid", tid=ENTRA_TID, roles=["Cymbal.SreAdmin"])
    envelope = EdgeAuthVerifier().exchange_federated_idp_token(
        inbound_idp_jwt=token, dpop_proof_jwt=_dpop(), hop0_gate=gate
    )

    assert envelope.tenant.tenant_id == "tenant-retailstream-beta"
    assert envelope.tenant.subscription_tier == SubscriptionTier.STANDARD
    assert envelope.security.idp_provider == "microsoft_entra_oidc"
    assert envelope.security.user_role == "sre_admin"
    assert "3lo:servicenow.itom.write" in envelope.tenant.authorized_scopes


def test_google_anchor_tenant_keeps_user_role_claim(
    gate: HopZeroFederationGate, google: FakeIdP
) -> None:
    token = google.mint(
        sub="alice@finvault.com", user_role="compliance_officer"
    )
    envelope = EdgeAuthVerifier().exchange_federated_idp_token(
        inbound_idp_jwt=token, dpop_proof_jwt=_dpop(), hop0_gate=gate
    )

    assert envelope.tenant.tenant_id == "tenant-finvault-alpha"
    assert envelope.security.user_role == "compliance_officer"
    assert "3lo:jira.incidents.write" not in envelope.tenant.authorized_scopes


def test_most_privileged_mapped_role_wins(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-erin",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-read-only-analysts", "cymbal-sre-admins"],
    )
    assert gate.verify_and_normalize(token)["user_role"] == "sre_admin"


def test_envelope_carries_role_and_idp_into_adk_state_and_subagents(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-dana",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-compliance-officers"],
    )
    envelope = EdgeAuthVerifier().exchange_federated_idp_token(
        inbound_idp_jwt=token, dpop_proof_jwt=_dpop(), hop0_gate=gate
    )
    state = envelope.to_adk_state()
    assert state["temp:user_role"] == "compliance_officer"
    assert state["temp:idp_provider"] == "okta_enterprise_oidc"

    child = propagate_to_subagent(state)
    assert child["temp:tenant_id"] == OKTA_TENANT
    assert child["temp:delegation_depth"] == 1


# ---------------------------------------------------------------------------------------------
# Threat table: one negative test per row
# ---------------------------------------------------------------------------------------------


def test_rejects_token_signed_by_attacker_key(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    attacker_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    token = okta.mint(
        sub="00u-mallory",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-sre-admins"],
        signing_key=attacker_key,
    )
    with pytest.raises(PermissionError, match="E_HOP0_INVALID_SIGNATURE"):
        gate.verify_and_normalize(token)


def test_rejects_alg_none(gate: HopZeroFederationGate) -> None:
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": OKTA_ISS,
            "sub": "x",
            "aud": OKTA_CLIENT_ID,
            "iat": now,
            "exp": now + 60,
        },
        key=None,
        algorithm="none",
    )
    with pytest.raises(PermissionError, match="E_HOP0_DISALLOWED_ALG"):
        gate.verify_and_normalize(token)


def test_rejects_hs256_key_confusion_with_public_key(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    public_pem = okta.private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    now = int(time.time())
    header = {"alg": "HS256", "kid": okta.kid, "typ": "JWT"}
    payload = {
        "iss": OKTA_ISS,
        "sub": "00u-mallory",
        "aud": OKTA_CLIENT_ID,
        "iat": now,
        "exp": now + 60,
        "groups": ["cymbal-sre-admins"],
    }
    # PyJWT refuses to HMAC-sign with a PEM, so build the forged token by hand.
    import base64
    import hashlib
    import hmac
    import json

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    signing_input = f"{b64(json.dumps(header).encode())}.{b64(json.dumps(payload).encode())}"
    sig = hmac.new(public_pem, signing_input.encode(), hashlib.sha256).digest()
    forged = f"{signing_input}.{b64(sig)}"

    with pytest.raises(PermissionError, match="E_HOP0_DISALLOWED_ALG"):
        gate.verify_and_normalize(forged)


def test_rejects_algorithm_not_pinned_for_issuer(
    gate: HopZeroFederationGate, okta: FakeIdP, resolver: StaticJWKSResolver
) -> None:
    from cryptography.hazmat.primitives.asymmetric import ec

    ec_key = ec.generate_private_key(ec.SECP256R1())
    resolver.add_key(
        issuer=OKTA_ISS, kid="ec-1", public_key=ec_key.public_key()
    )
    token = okta.mint(
        sub="00u-x",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-sre-admins"],
        alg="ES256",
        kid="ec-1",
        signing_key=ec_key,
    )
    with pytest.raises(PermissionError, match="E_HOP0_DISALLOWED_ALG"):
        gate.verify_and_normalize(token)


def test_rejects_token_minted_for_another_client(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-dana", aud="0oa-some-other-app", groups=["cymbal-sre-admins"]
    )
    with pytest.raises(PermissionError, match="E_HOP0_AUDIENCE_MISMATCH"):
        gate.verify_and_normalize(token)


def test_rejects_unfederated_issuer(
    gate: HopZeroFederationGate, resolver: StaticJWKSResolver
) -> None:
    rogue = FakeIdP("https://evil.okta.com/oauth2/default", resolver)
    token = rogue.mint(
        sub="00u-x", aud=OKTA_CLIENT_ID, groups=["cymbal-sre-admins"]
    )
    with pytest.raises(PermissionError, match="E_HOP0_UNKNOWN_ISSUER"):
        gate.verify_and_normalize(token)


def test_rejects_entra_token_from_different_directory(
    gate: HopZeroFederationGate, entra: FakeIdP
) -> None:
    token = entra.mint(
        sub="bob-oid", tid="some-other-directory", roles=["Cymbal.SreAdmin"]
    )
    with pytest.raises(
        PermissionError, match="E_HOP0_ENTRA_DIRECTORY_MISMATCH"
    ):
        gate.verify_and_normalize(token)


def test_rejects_self_asserted_tenant_id_spoof(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-dana",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-sre-admins"],
        tenant_id="tenant-finvault-alpha",
    )
    with pytest.raises(PermissionError, match="E_HOP0_TENANT_CLAIM_SPOOF"):
        gate.verify_and_normalize(token)


def test_rejects_okta_token_replayed_against_entra_tenant(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    # Valid Okta signature, but aimed at RetailStream's gateway client: audience binding fails.
    token = okta.mint(
        sub="00u-dana",
        aud=DEFAULT_GATEWAY_AUDIENCE,
        groups=["cymbal-sre-admins"],
        tid=ENTRA_TID,
    )
    with pytest.raises(PermissionError, match="E_HOP0_AUDIENCE_MISMATCH"):
        gate.verify_and_normalize(token)


def test_rejects_user_with_no_mapped_group(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-frank", aud=OKTA_CLIENT_ID, groups=["Everyone", "marketing"]
    )
    with pytest.raises(PermissionError, match="E_HOP0_NO_RBAC_ROLE"):
        gate.verify_and_normalize(token)


def test_rejects_google_token_without_role_instead_of_defaulting_to_admin(
    gate: HopZeroFederationGate, google: FakeIdP
) -> None:
    token = google.mint(sub="alice@finvault.com")
    with pytest.raises(PermissionError, match="E_HOP0_NO_RBAC_ROLE"):
        gate.verify_and_normalize(token)


def test_entra_ignores_raw_group_guids(
    gate: HopZeroFederationGate, entra: FakeIdP
) -> None:
    token = entra.mint(
        sub="bob-oid",
        tid=ENTRA_TID,
        groups=["1ce9c55a-9826-4e32-871c-a2488144bb32"],
    )
    with pytest.raises(PermissionError, match="E_HOP0_NO_RBAC_ROLE"):
        gate.verify_and_normalize(token)


def test_entra_group_overage_fails_closed(
    gate: HopZeroFederationGate, entra: FakeIdP
) -> None:
    token = entra.mint(
        sub="bob-oid",
        tid=ENTRA_TID,
        _claim_names={"groups": "src1"},
        _claim_sources={
            "src1": {
                "endpoint": "https://graph.microsoft.com/v1.0/me/getMemberObjects"
            }
        },
    )
    with pytest.raises(PermissionError, match="E_HOP0_ENTRA_GROUP_OVERAGE"):
        gate.verify_and_normalize(token)


def test_rejects_expired_token(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-dana",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-sre-admins"],
        ttl=-120,
    )
    with pytest.raises(PermissionError, match="E_HOP0_TOKEN_EXPIRED"):
        gate.verify_and_normalize(token)


def test_rejects_long_lived_direct_token(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-dana",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-sre-admins"],
        ttl=86_400,
    )
    with pytest.raises(PermissionError, match="E_HOP0_TOKEN_LIFETIME_TOO_LONG"):
        gate.verify_and_normalize(token)


def test_rejects_unknown_kid(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-dana",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-sre-admins"],
        kid="gone",
    )
    with pytest.raises(PermissionError, match="E_HOP0_UNKNOWN_KID"):
        gate.verify_and_normalize(token)


def test_rotated_signing_key_is_accepted_once_published(
    gate: HopZeroFederationGate, okta: FakeIdP, resolver: StaticJWKSResolver
) -> None:
    rotated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    resolver.add_key(
        issuer=OKTA_ISS, kid="key-2", public_key=rotated.public_key()
    )
    token = okta.mint(
        sub="00u-dana",
        aud=OKTA_CLIENT_ID,
        groups=["cymbal-sre-admins"],
        kid="key-2",
        signing_key=rotated,
    )
    assert gate.verify_and_normalize(token)["tenant_id"] == OKTA_TENANT


def test_dpop_proof_is_still_required_after_hop0(
    gate: HopZeroFederationGate, okta: FakeIdP
) -> None:
    token = okta.mint(
        sub="00u-dana", aud=OKTA_CLIENT_ID, groups=["cymbal-sre-admins"]
    )
    with pytest.raises(jwt.PyJWTError):
        EdgeAuthVerifier().exchange_federated_idp_token(
            inbound_idp_jwt=token,
            dpop_proof_jwt="not-a-dpop-proof",
            hop0_gate=gate,
        )


# ---------------------------------------------------------------------------------------------
# Control-plane registration guards
# ---------------------------------------------------------------------------------------------


def test_registry_rejects_second_tenant_on_same_issuer(
    registry: IdPFederationRegistry,
) -> None:
    register_tenant(
        tenant_id="tenant-shared-okta", display_name="Shared", iss=OKTA_ISS
    )
    with pytest.raises(ValueError, match="E_HOP0_DUPLICATE_ISSUER"):
        registry.register(
            FederatedIdPConfig(
                tenant_id="tenant-shared-okta",
                provider=FederatedIdP.OKTA_ENTERPRISE_OIDC,
                issuer=OKTA_ISS,
                audience="0oa-other",
                group_to_role=DEFAULT_OKTA_GROUP_MAP,
            )
        )


def test_registry_rejects_issuer_not_matching_tenant_directory() -> None:
    reg = IdPFederationRegistry()
    with pytest.raises(ValueError, match="E_HOP0_TENANT_ISSUER_MISMATCH"):
        reg.register(
            FederatedIdPConfig(
                tenant_id="tenant-finvault-alpha",
                provider=FederatedIdP.OKTA_ENTERPRISE_OIDC,
                issuer=OKTA_ISS,
                audience=OKTA_CLIENT_ID,
                group_to_role=DEFAULT_OKTA_GROUP_MAP,
            )
        )


@pytest.mark.parametrize("segment", ["common", "organizations"])
def test_config_rejects_entra_multi_tenant_issuer(segment: str) -> None:
    with pytest.raises(ValueError, match="E_HOP0_ENTRA_MULTI_TENANT_ISSUER"):
        FederatedIdPConfig(
            tenant_id="tenant-retailstream-beta",
            provider=FederatedIdP.MICROSOFT_ENTRA_OIDC,
            issuer=f"https://login.microsoftonline.com/{segment}/v2.0",
            audience="app",
            directory_id=segment,
            role_claim="roles",
        )


@pytest.mark.parametrize("algs", [("HS256",), ("none",), ()])
def test_config_rejects_symmetric_or_empty_algorithms(
    algs: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="E_HOP0_DISALLOWED_ALG_CONFIG"):
        FederatedIdPConfig(
            tenant_id=OKTA_TENANT,
            provider=FederatedIdP.OKTA_ENTERPRISE_OIDC,
            issuer=OKTA_ISS,
            audience=OKTA_CLIENT_ID,
            allowed_algs=algs,
        )


def test_config_rejects_unknown_rbac_role_in_mapping() -> None:
    with pytest.raises(ValueError, match="E_HOP0_UNKNOWN_RBAC_ROLE"):
        FederatedIdPConfig(
            tenant_id=OKTA_TENANT,
            provider=FederatedIdP.OKTA_ENTERPRISE_OIDC,
            issuer=OKTA_ISS,
            audience=OKTA_CLIENT_ID,
            group_to_role={"cymbal-root": "super_admin"},
        )


def test_http_resolver_rejects_discovery_issuer_mismatch() -> None:
    config = FederatedIdPConfig(
        tenant_id=OKTA_TENANT,
        provider=FederatedIdP.OKTA_ENTERPRISE_OIDC,
        issuer=OKTA_ISS,
        audience=OKTA_CLIENT_ID,
    )
    resolver = HttpJWKSResolver(
        discovery_fetcher=lambda _iss: {
            "issuer": "https://evil.okta.com/oauth2/default",
            "jwks_uri": "https://evil.okta.com/oauth2/default/v1/keys",
        }
    )
    with pytest.raises(LookupError, match="discovery issuer"):
        resolver.get_key(config=config, kid="key-1")


# ---------------------------------------------------------------------------------------------
# Backward compatibility: existing Hop 1 callers are unchanged
# ---------------------------------------------------------------------------------------------


def test_legacy_exchange_obo_token_defaults_are_unchanged(
    edge_verifier: EdgeAuthVerifier,
) -> None:
    envelope = edge_verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": GOOGLE_ISS,
            "sub": "alice@finvault.com",
            "tenant_id": "tenant-finvault-alpha",
            "exp": int(time.time()) + 3600,
        },
        dpop_proof={"jkt": "thumb", "jti": f"dpop-{uuid.uuid4().hex}"},
    )
    assert envelope.security.user_role == "sre_admin"
    assert envelope.security.idp_provider == "google_workspace_oidc"


def test_jwks_discovery_runs_once_per_issuer_under_concurrency() -> None:
    """Review follow-up: concurrent first tokens from one issuer trigger a single discovery."""
    import threading
    import time as _time

    calls: list[str] = []

    def slow_discovery(issuer: str) -> dict[str, str]:
        calls.append(issuer)
        _time.sleep(0.05)
        return {"issuer": issuer, "jwks_uri": f"{issuer}/jwks"}

    resolver = HttpJWKSResolver(discovery_fetcher=slow_discovery)
    config = FederatedIdPConfig(
        tenant_id=OKTA_TENANT,
        provider=FederatedIdP.OKTA_ENTERPRISE_OIDC,
        issuer="https://idp.example.com",
        audience=OKTA_CLIENT_ID,
    )
    threads = [
        threading.Thread(target=resolver._client_for, args=(config,))
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == ["https://idp.example.com"]
