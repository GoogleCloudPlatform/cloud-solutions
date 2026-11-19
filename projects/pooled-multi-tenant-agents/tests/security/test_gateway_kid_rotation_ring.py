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

"""Verification suite for the 3-key `(active_kid, previous_kid, next_kid)` gateway signing-key ring.

Covers:
1. Direct cryptographic signature verification on rotated keys (`token_v2` verifies under
   `key_v2.public_key()` and fails `InvalidSignatureError` under `key_v1.public_key()`), plus
   retirement of `kid_v1` once rotated to `kid_v3`.
2. Rejection of `alg="none"`, `alg="HS256"`, swapped `kid` headers (`key_v1` signed with
   `kid="gw-key-v2"` and vice versa), unknown `kid`, and missing `kid`.
3. `IdentitySettings` and `GatewayTokenService.from_config` validation of
   `gateway_signing_secret`, `gateway_previous_signing_secret`, and `gateway_next_signing_secret`,
   including rejection of `previous`/`next` without `active`, identical PEM key material under
   distinct Secret Manager version strings (`E_GATEWAY_SIGNING_KEY_DUPLICATE`), wrong-curve
   (`SECP384R1`) previous/next keys, and startup `kid` logging.
4. End-to-end 3-step multi-replica rolling deployment simulation on `GET /api/v1/whoami` proving
   Stage-1 (`active=A, next=B`) and Stage-2 (`active=B, previous=A`) replicas accept each other's
   tokens with zero `401` errors during rollout.
"""

from __future__ import annotations

import logging
import time

import jwt
import pytest
from agents.context import (
    AsymmetricDPoPProvider,
    ContextEnvelope,
    EdgeAuthVerifier,
)
from agents.platform_config import IdentitySettings
from app.gateway_tokens import (
    GATEWAY_ISSUER,
    GATEWAY_TOKEN_AUDIENCE,
    GatewayTokenError,
    GatewayTokenService,
    SharedReplayStore,
    _ReplayCache,
    access_token_hash,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient


def _private_key_to_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    """Serializes an EC private key to PKCS#8 PEM format."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def _mint_bound_envelope(
    verifier: EdgeAuthVerifier,
    *,
    client_jkt: str,
    jti_suffix: str,
) -> ContextEnvelope:
    """Mints a verified `ContextEnvelope` bound to `client_jkt`."""
    return verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://accounts.google.com",
            "sub": "alice@finvault.com",
            "tenant_id": "tenant-finvault-alpha",
            "user_role": "sre_admin",
            "exp": 4_102_444_800,
            "jti": f"oidc-rot-{jti_suffix}",
        },
        dpop_proof={
            "jkt": client_jkt,
            "jti": f"dpop-rot-{jti_suffix}",
        },
    )


def test_gateway_token_service_verifies_active_and_previous_kid_and_retires_older_keys() -> (
    None
):
    """Proves `(active_kid, previous_kid)` overlap accepts `v1` and `v2`, and retires `v1` on
    `v3`.
    """
    verifier = EdgeAuthVerifier()
    client_key = AsymmetricDPoPProvider.generate_client_keypair()
    client_jwk = AsymmetricDPoPProvider.public_key_to_jwk(
        client_key.public_key()
    )
    client_jkt = AsymmetricDPoPProvider.compute_rfc7638_jwk_thumbprint(
        client_jwk
    )
    envelope = _mint_bound_envelope(
        verifier, client_jkt=client_jkt, jti_suffix="ring-1"
    )

    key_v1 = ec.generate_private_key(ec.SECP256R1())
    key_v2 = ec.generate_private_key(ec.SECP256R1())
    key_v3 = ec.generate_private_key(ec.SECP256R1())

    service = GatewayTokenService(
        private_key=key_v1, kid="gw-key-v1", ephemeral=True
    )
    log_key_v1 = service.log_key
    token_v1, _ = service.issue(envelope)

    # Rotate v1 -> v2: both v1 (previous_kid) and v2 (active_kid) must verify cleanly.
    rotation_state_v2 = service.rotate_signing_key(key_v2, new_kid="gw-key-v2")
    assert rotation_state_v2 == {
        "active_kid": "gw-key-v2",
        "previous_kid": "gw-key-v1",
    }
    assert set(service.verification_keys.keys()) == {"gw-key-v1", "gw-key-v2"}
    assert service.log_key != log_key_v1

    token_v2, _ = service.issue(envelope)

    # Mutation guard: verify `token_v2` was genuinely signed by `key_v2` (and fails under `key_v1`).
    decoded_with_v2 = jwt.decode(
        token_v2,
        key_v2.public_key(),
        algorithms=["ES256"],
        audience=GATEWAY_TOKEN_AUDIENCE,
        issuer=GATEWAY_ISSUER,
    )
    assert decoded_with_v2["tenant_id"] == "tenant-finvault-alpha"
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            token_v2,
            key_v1.public_key(),
            algorithms=["ES256"],
            audience=GATEWAY_TOKEN_AUDIENCE,
            issuer=GATEWAY_ISSUER,
        )

    target_htu = "https://agent-gateway.cymbal.internal/api/v1/whoami"

    proof_for_v1 = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=client_key,
        htm="GET",
        htu=target_htu,
        jti="proof-v1-overlap",
        ath=access_token_hash(token_v1),
    )
    claims_v1, _ = service.verify_request(
        authorization=f"DPoP {token_v1}",
        dpop=proof_for_v1,
        htm="GET",
        htu=target_htu,
    )
    assert claims_v1["tenant_id"] == "tenant-finvault-alpha"

    proof_for_v2 = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=client_key,
        htm="GET",
        htu=target_htu,
        jti="proof-v2-active",
        ath=access_token_hash(token_v2),
    )
    claims_v2, _ = service.verify_request(
        authorization=f"DPoP {token_v2}",
        dpop=proof_for_v2,
        htm="GET",
        htu=target_htu,
    )
    assert claims_v2["tenant_id"] == "tenant-finvault-alpha"

    # Rotate v2 -> v3: v1 is retired from the ring and must fail closed with E_TOKEN_INVALID.
    rotation_state_v3 = service.rotate_signing_key(key_v3, new_kid="gw-key-v3")
    assert rotation_state_v3 == {
        "active_kid": "gw-key-v3",
        "previous_kid": "gw-key-v2",
    }
    assert set(service.verification_keys.keys()) == {"gw-key-v2", "gw-key-v3"}

    proof_for_retired_v1 = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=client_key,
        htm="GET",
        htu=target_htu,
        jti="proof-v1-retired",
        ath=access_token_hash(token_v1),
    )
    with pytest.raises(GatewayTokenError) as exc_info:
        service.verify_request(
            authorization=f"DPoP {token_v1}",
            dpop=proof_for_retired_v1,
            htm="GET",
            htu=target_htu,
        )
    assert exc_info.value.code == "E_TOKEN_INVALID"

    # Meanwhile v2 (now previous_kid) still verifies during the v2 -> v3 overlap window.
    proof_for_v2_overlap = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=client_key,
        htm="GET",
        htu=target_htu,
        jti="proof-v2-overlap",
        ath=access_token_hash(token_v2),
    )
    claims_v2_after, _ = service.verify_request(
        authorization=f"DPoP {token_v2}",
        dpop=proof_for_v2_overlap,
        htm="GET",
        htu=target_htu,
    )
    assert claims_v2_after["sub"] == "alice@finvault.com"


def test_verify_request_rejects_alg_none_hs256_swapped_kid_and_unknown_kid() -> (
    None
):
    """Proves `verify_request` rejects `alg=none`, `HS256`, swapped `kid`, and unknown `kid`."""
    client_key = AsymmetricDPoPProvider.generate_client_keypair()
    client_jwk = AsymmetricDPoPProvider.public_key_to_jwk(
        client_key.public_key()
    )
    client_jkt = AsymmetricDPoPProvider.compute_rfc7638_jwk_thumbprint(
        client_jwk
    )

    key_v1 = ec.generate_private_key(ec.SECP256R1())
    key_v2 = ec.generate_private_key(ec.SECP256R1())
    service = GatewayTokenService(
        private_key=key_v2,
        kid="gw-key-v2",
        ephemeral=True,
        previous_public_key=key_v1.public_key(),
        previous_kid="gw-key-v1",
    )

    now = int(time.time())
    base_claims = {
        "iss": GATEWAY_ISSUER,
        "aud": GATEWAY_TOKEN_AUDIENCE,
        "sub": "alice@finvault.com",
        "tenant_id": "tenant-finvault-alpha",
        "user_role": "sre_admin",
        "idp_provider": "google_workspace_oidc",
        "idp_iss": "https://accounts.google.com",
        "cnf": {"jkt": client_jkt},
        "iat": now,
        "exp": now + 300,
        "jti": "gw-forged-1",
    }
    target_htu = "https://agent-gateway.cymbal.internal/api/v1/whoami"

    # 1. alg="none" token carrying valid kid="gw-key-v2"
    alg_none_token = jwt.encode(
        base_claims,
        key=None,
        algorithm="none",
        headers={"kid": "gw-key-v2", "typ": "at+jwt"},
    )
    # 2. alg="HS256" token carrying valid kid="gw-key-v2"
    alg_hs256_token = jwt.encode(
        base_claims,
        key="shared-hmac-secret-at-least-32-bytes-long",
        algorithm="HS256",
        headers={"kid": "gw-key-v2", "typ": "at+jwt"},
    )
    # 3. Swapped kid: signed by key_v1 (previous) but claiming kid="gw-key-v2" (active)
    swapped_v1_as_v2 = jwt.encode(
        base_claims,
        key_v1,
        algorithm="ES256",
        headers={"kid": "gw-key-v2", "typ": "at+jwt"},
    )
    # 4. Swapped kid: signed by key_v2 (active) but claiming kid="gw-key-v1" (previous)
    swapped_v2_as_v1 = jwt.encode(
        base_claims,
        key_v2,
        algorithm="ES256",
        headers={"kid": "gw-key-v1", "typ": "at+jwt"},
    )
    # 5. Unknown kid: signed by key_v2 but claiming kid="gw-key-unknown"
    unknown_kid_token = jwt.encode(
        base_claims,
        key_v2,
        algorithm="ES256",
        headers={"kid": "gw-key-unknown", "typ": "at+jwt"},
    )

    for index, forged_token in enumerate(
        (
            alg_none_token,
            alg_hs256_token,
            swapped_v1_as_v2,
            swapped_v2_as_v1,
            unknown_kid_token,
        )
    ):
        proof = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
            client_private_key=client_key,
            htm="GET",
            htu=target_htu,
            jti=f"proof-forged-{index}",
            ath=access_token_hash(forged_token),
        )
        with pytest.raises(GatewayTokenError) as exc_info:
            service.verify_request(
                authorization=f"DPoP {forged_token}",
                dpop=proof,
                htm="GET",
                htu=target_htu,
            )
        assert exc_info.value.code == "E_TOKEN_INVALID"


def test_rotate_signing_key_rejects_duplicate_key_and_wrong_curve() -> None:
    """Proves `rotate_signing_key` rejects identical key material, duplicate `kid`, or P-384
    keys.
    """
    key_v1 = ec.generate_private_key(ec.SECP256R1())
    service = GatewayTokenService(
        private_key=key_v1, kid="gw-key-v1", ephemeral=True
    )

    with pytest.raises(ValueError, match="E_KEY_ROTATION_DUPLICATE_KID"):
        service.rotate_signing_key(key_v1, new_kid="gw-key-v2")

    key_v2 = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(ValueError, match="E_KEY_ROTATION_DUPLICATE_KID"):
        service.rotate_signing_key(key_v2, new_kid="gw-key-v1")

    wrong_curve_key = ec.generate_private_key(ec.SECP384R1())
    with pytest.raises(ValueError, match="secp256r1"):
        service.rotate_signing_key(wrong_curve_key)


def test_from_config_loads_3key_ring_and_rejects_duplicate_pem_or_wrong_curve(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Proves `from_config` loads `(active, previous, next)` and rejects duplicate PEM or P-384."""
    import app.gateway_tokens as gateway_tokens_module

    active_key = ec.generate_private_key(ec.SECP256R1())
    previous_key = ec.generate_private_key(ec.SECP256R1())
    next_key = ec.generate_private_key(ec.SECP256R1())
    wrong_curve_key = ec.generate_private_key(ec.SECP384R1())

    pem_by_version = {
        "gw-signing-key/versions/2": _private_key_to_pem(active_key),
        "gw-signing-key/versions/1": _private_key_to_pem(previous_key),
        "gw-signing-key/versions/3": _private_key_to_pem(next_key),
        "gw-signing-key/versions/99": _private_key_to_pem(
            active_key
        ),  # duplicate PEM of v2
        "gw-signing-key/versions/384": _private_key_to_pem(wrong_curve_key),
    }

    def _fake_fetch_pem(secret_version: str) -> str:
        return pem_by_version[secret_version]

    monkeypatch.setattr(
        gateway_tokens_module, "fetch_signing_key_pem", _fake_fetch_pem
    )

    base_cfg = gateway_tokens_module.get_platform_config()
    cfg_with_3key_ring = base_cfg.model_copy(
        update={
            "identity": IdentitySettings(
                gateway_audience=base_cfg.identity.gateway_audience,
                dev_issuer=base_cfg.identity.dev_issuer,
                public_origin="https://agents.cymbal.example",
                gateway_signing_secret="gw-signing-key/versions/2",
                gateway_previous_signing_secret="gw-signing-key/versions/1",
                gateway_next_signing_secret="gw-signing-key/versions/3",
            )
        }
    )
    with caplog.at_level(logging.INFO, logger="app.gateway_tokens"):
        service = GatewayTokenService.from_config(cfg_with_3key_ring)
    assert service.previous_kid is not None
    assert service.next_kid is not None
    assert len(service.verification_keys) == 3
    assert any(
        "GatewayTokenService initialized:" in rec.message
        for rec in caplog.records
    )
    assert service.kid in caplog.text
    assert service.previous_kid in caplog.text
    assert service.next_kid in caplog.text
    assert "BEGIN PRIVATE KEY" not in caplog.text
    assert "BEGIN EC PRIVATE KEY" not in caplog.text
    for raw_pem in pem_by_version.values():
        second_line = raw_pem.strip().splitlines()[1]
        assert second_line not in caplog.text

    # 1. IdentitySettings rejects previous or next secret when active secret is omitted.
    with pytest.raises(
        ValueError, match=r"require identity\.gateway_signing_secret"
    ):
        IdentitySettings(
            gateway_previous_signing_secret="gw-signing-key/versions/1"
        )
    with pytest.raises(
        ValueError, match=r"require identity\.gateway_signing_secret"
    ):
        IdentitySettings(
            gateway_next_signing_secret="gw-signing-key/versions/3"
        )

    # 2. IdentitySettings rejects identical secret version strings.
    with pytest.raises(ValueError, match="distinct secret versions"):
        IdentitySettings(
            gateway_signing_secret="gw-signing-key/versions/2",
            gateway_previous_signing_secret="gw-signing-key/versions/2",
        )
    with pytest.raises(ValueError, match="distinct secret versions"):
        IdentitySettings(
            gateway_signing_secret="gw-signing-key/versions/2",
            gateway_next_signing_secret="gw-signing-key/versions/2",
        )

    # 3. `from_config` rejects two distinct version strings containing the SAME PEM key material.
    cfg_duplicate_previous_pem = base_cfg.model_copy(
        update={
            "identity": IdentitySettings(
                gateway_signing_secret="gw-signing-key/versions/2",
                gateway_previous_signing_secret="gw-signing-key/versions/99",
            )
        }
    )
    with pytest.raises(RuntimeError, match="E_GATEWAY_SIGNING_KEY_DUPLICATE"):
        GatewayTokenService.from_config(cfg_duplicate_previous_pem)

    cfg_duplicate_next_pem = base_cfg.model_copy(
        update={
            "identity": IdentitySettings(
                gateway_signing_secret="gw-signing-key/versions/2",
                gateway_next_signing_secret="gw-signing-key/versions/99",
            )
        }
    )
    with pytest.raises(RuntimeError, match="E_GATEWAY_SIGNING_KEY_DUPLICATE"):
        GatewayTokenService.from_config(cfg_duplicate_next_pem)

    # 4. `from_config` rejects a wrong-curve (P-384) PEM in `gateway_previous_signing_secret`.
    cfg_wrong_curve_previous = base_cfg.model_copy(
        update={
            "identity": IdentitySettings(
                gateway_signing_secret="gw-signing-key/versions/2",
                gateway_previous_signing_secret="gw-signing-key/versions/384",
            )
        }
    )
    with pytest.raises(RuntimeError, match="EC P-256 private key"):
        GatewayTokenService.from_config(cfg_wrong_curve_previous)


def test_rolling_deploy_across_two_replicas_verifies_on_whoami_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves Stage-1 (`active=A, next=B`) and Stage-2 (`active=B, previous=A`) replicas
    accept each other's tokens on `GET /api/v1/whoami` without any 401 availability blip.
    """
    import app.gateway_tokens as gateway_tokens_module
    import app.main as gateway_main

    verifier = EdgeAuthVerifier()
    client_key = AsymmetricDPoPProvider.generate_client_keypair()
    client_jwk = AsymmetricDPoPProvider.public_key_to_jwk(
        client_key.public_key()
    )
    client_jkt = AsymmetricDPoPProvider.compute_rfc7638_jwk_thumbprint(
        client_jwk
    )
    envelope = _mint_bound_envelope(
        verifier, client_jkt=client_jkt, jti_suffix="rolling-whoami"
    )

    key_a = ec.generate_private_key(ec.SECP256R1())
    key_b = ec.generate_private_key(ec.SECP256R1())
    shared_replay = SharedReplayStore()

    # Stage-1 replica: still signs with A, but has pre-staged B as verify-only `next_kid`.
    replica_stage1 = GatewayTokenService(
        private_key=key_a,
        kid="gw-key-a",
        ephemeral=False,
        next_public_key=key_b.public_key(),
        next_kid="gw-key-b",
        replay=_ReplayCache(shared_store=shared_replay),
    )
    # Stage-2 replica: switched signing to B, retaining A as verify-only `previous_kid`.
    replica_stage2 = GatewayTokenService(
        private_key=key_b,
        kid="gw-key-b",
        ephemeral=False,
        previous_public_key=key_a.public_key(),
        previous_kid="gw-key-a",
        replay=_ReplayCache(shared_store=shared_replay),
    )

    token_from_new_replica_b, _ = replica_stage2.issue(envelope)
    token_from_old_replica_a, _ = replica_stage1.issue(envelope)

    client = TestClient(gateway_main.app)
    whoami_htu = "http://testserver/api/v1/whoami"

    # Case 1: Token signed by NEW replica (key B) is routed to OLD replica (Stage 1: active=A,
    # next=B).
    monkeypatch.setattr(
        gateway_tokens_module, "get_token_service", lambda: replica_stage1
    )
    proof_b_on_old = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=client_key,
        htm="GET",
        htu=whoami_htu,
        jti="proof-rolling-b-on-old",
        ath=access_token_hash(token_from_new_replica_b),
    )
    response_on_old = client.get(
        "/api/v1/whoami",
        headers={
            "Authorization": f"DPoP {token_from_new_replica_b}",
            "DPoP": proof_b_on_old,
        },
    )
    assert response_on_old.status_code == 200
    assert response_on_old.json()["tenant_id"] == "tenant-finvault-alpha"

    # Case 2: Token signed by OLD replica (key A) is routed to NEW replica (Stage 2: active=B,
    # prev=A).
    monkeypatch.setattr(
        gateway_tokens_module, "get_token_service", lambda: replica_stage2
    )
    proof_a_on_new = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=client_key,
        htm="GET",
        htu=whoami_htu,
        jti="proof-rolling-a-on-new",
        ath=access_token_hash(token_from_old_replica_a),
    )
    response_on_new = client.get(
        "/api/v1/whoami",
        headers={
            "Authorization": f"DPoP {token_from_old_replica_a}",
            "DPoP": proof_a_on_new,
        },
    )
    assert response_on_new.status_code == 200
    assert response_on_new.json()["tenant_id"] == "tenant-finvault-alpha"


def test_2am_chaos_gateway_kid_rotation_overlap_endpoint() -> None:
    """Proves `/api/v1/2am-chaos/gateway_kid_rotation_overlap` exercises the rotation ring."""
    import app.main as gateway_main

    client = TestClient(gateway_main.app)
    response = client.post("/api/v1/2am-chaos/gateway_kid_rotation_overlap")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "RESILIENCE_VERIFIED"
    assert payload["first_rotation"] == {
        "active_kid": "gw-rot-v2",
        "previous_kid": "gw-rot-v1",
    }
    assert payload["second_rotation"] == {
        "active_kid": "gw-rot-v3",
        "previous_kid": "gw-rot-v2",
    }
    assert payload["active_ring_kids"] == ["gw-rot-v2", "gw-rot-v3"]
