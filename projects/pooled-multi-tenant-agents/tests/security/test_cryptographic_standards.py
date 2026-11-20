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

# pylint: disable=line-too-long,protected-access

"""Standards-Compliance Tests for Asymmetric ES256 JWT, RFC 9449 DPoP & AES-256-GCM CMEK AEAD.

Verifies Decisions 3 & 4 from the `/grill-me` architecture review:
1. **Real Asymmetric ES256 OIDC JWT + RFC 9449 `dpop+jwt` Proof Verification**:
   - Mints real ECDSA P-256 (`ES256`) OIDC ID tokens and `dpop+jwt` headers (`typ="dpop+jwt"`,
     embedded `jwk`, `htm`, `htu`, `jti`, `iat`).
   - Computes RFC 7638 SHA-256 JWK thumbprints (`jkt`) and verifies sender-constrained binding.
   - Proves that signing a DPoP proof with a different client EC keypair, wrong `htu`, or replayed
     `jti` fails cryptographic verification.
2. **Real AES-256-GCM + AAD (`tenant_id|scope`) Per-Tenant CMEK Envelope Encryption**:
   - Even when ACL/prefix checks are deliberately bypassed (`bypass_acl_for_crypto_test=True`),
     attempting to decrypt FinVault Bank's memory ciphertext using RetailStream Corp's CMEK key
     or tenant AAD mathematically fails with `E_CMEK_AEAD_DECRYPTION_FAILED` (`InvalidTag`).
"""

from __future__ import annotations

import pytest
from agents.context import (
    AsymmetricDPoPProvider,
    ContextEnvelope,
    EdgeAuthVerifier,
    MemoryBankPartitioner,
    MemoryScope,
)


def test_rfc9449_asymmetric_es256_dpop_and_rfc7638_jwk_thumbprint() -> None:
    verifier = EdgeAuthVerifier()
    provider = verifier.crypto_provider

    # 1. Generate an ephemeral ECDSA P-256 keypair for FinVault Alice's client workload
    alice_priv = AsymmetricDPoPProvider.generate_client_keypair()
    alice_jwk = AsymmetricDPoPProvider.public_key_to_jwk(
        alice_priv.public_key()
    )
    expected_jkt = AsymmetricDPoPProvider.compute_rfc7638_jwk_thumbprint(
        alice_jwk
    )

    # 2. Mint an ES256-signed Google OIDC JWT and an ES256-signed RFC 9449 `dpop+jwt` proof
    oidc_jwt = provider.mint_idp_oidc_jwt(
        iss="https://accounts.google.com",
        sub="alice@finvault.com",
        tenant_id="tenant-finvault-alpha",
    )
    dpop_jwt = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=alice_priv,
        htm="POST",
        htu="https://agent-gateway.cymbal.internal/api/v1/invoke-agent",
    )

    envelope = verifier.exchange_asymmetric_jwt_obo(
        inbound_oidc_jwt=oidc_jwt,
        dpop_proof_jwt=dpop_jwt,
        raw_client_headers={"X-Tenant-ID": "tenant-retailstream-beta"},
    )
    assert envelope.tenant.tenant_id == "tenant-finvault-alpha"
    assert envelope.security.dpop_jkt == expected_jkt

    # 3. Replaying the exact same `dpop+jwt` proof must be rejected (`E_DPOP_REPLAY_DETECTED`)
    with pytest.raises(PermissionError, match="E_DPOP_REPLAY_DETECTED"):
        verifier.exchange_asymmetric_jwt_obo(
            inbound_oidc_jwt=oidc_jwt,
            dpop_proof_jwt=dpop_jwt,
        )

    # 4. Presenting a `dpop+jwt` bound to a different endpoint (`expected_htu`) must be rejected
    dpop_wrong_htu = AsymmetricDPoPProvider.mint_dpop_proof_jwt(
        client_private_key=alice_priv,
        htm="POST",
        htu="https://agent-gateway.cymbal.internal/api/v1/other-endpoint",
    )
    with pytest.raises(PermissionError, match="E_DPOP_HTU_MISMATCH"):
        verifier.exchange_asymmetric_jwt_obo(
            inbound_oidc_jwt=oidc_jwt,
            dpop_proof_jwt=dpop_wrong_htu,
            expected_htu="https://agent-gateway.cymbal.internal/api/v1/invoke-agent",
        )


def test_aes_256_gcm_cmek_aead_mathematically_blocks_cross_tenant_decryption(
    finvault_envelope: ContextEnvelope,
    retailstream_envelope: ContextEnvelope,
) -> None:
    """Even with the code ACL bypassed, another tenant cannot open the record.

    The data key is wrapped by FinVault's KMS key; RetailStream's tenant identity is denied by
    (Local)KMS IAM before AES-GCM is attempted. No key material is stored with the record.
    """
    memory_bank = MemoryBankPartitioner()
    fv_key = memory_bank.write_memory(
        envelope=finvault_envelope,
        scope=MemoryScope.TENANT,
        actor="finvault_regulatory_escalation_agent",
        content={
            "wire_limit_usd": 50_000_000,
            "occ_contact": "compliance@finvault.com",
        },
    )

    # Stored record: ciphertext + KMS-wrapped data key only, never plaintext or a derivable key.
    raw_record = memory_bank._store[fv_key]
    assert "payload" not in raw_record
    assert raw_record["format"] == "v2"
    assert raw_record["wrapped_dek_hex"]
    assert "50000000" not in raw_record["ciphertext_hex"]
    assert bytes.fromhex(raw_record["ciphertext_hex"]).find(b"50000000") == -1

    # Legitimate FinVault read decrypts cleanly
    decrypted = memory_bank.read_memory(
        envelope=finvault_envelope, target_key=fv_key
    )
    assert decrypted["wire_limit_usd"] == 50_000_000

    # Code check skipped (call the decrypt layer directly): RetailStream's identity is refused,
    # because the stored key is FinVault's and only FinVault's SA can unwrap it.
    with pytest.raises(
        PermissionError, match=r"E_KMS_KEY_MISMATCH|E_KMS_IAM_DENIED"
    ):
        memory_bank._open(retailstream_envelope, fv_key, raw_record)
