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

# pylint: disable=line-too-long

"""Breach Simulation 2: Header Spoofing, RFC 8693 OBO & DPoP Binding (Pillar 2 — Hops 1, 2 & 3).

Verifies:
1. Forged `X-Tenant-ID: tenant-finvault-alpha` header sent by a RetailStream caller is stripped
   at Hop 1 (Cloud Armor + IAP) and cannot override the signed OIDC JWT claim.
2. IdP issuer spoofing (e.g. Entra ID token claiming `tenant-finvault-alpha`) is rejected.
3. Replayed or mismatched RFC 9449 DPoP proofs are rejected.
4. Sub-agent delegation preserves `temp:tenant_id` and refuses to fall back to the ambient
   runtime service account (Confused Deputy guard).
"""

from __future__ import annotations

import time

import pytest
from agents.context import (
    ContextEnvelope,
    EdgeAuthVerifier,
    MemoryBankPartitioner,
    MemoryScope,
    propagate_to_subagent,
)


def test_forged_x_tenant_id_header_is_stripped_and_ignored(
    edge_verifier: EdgeAuthVerifier,
) -> None:
    envelope = edge_verifier.exchange_obo_token(
        verified_idp_claims={
            "iss": "https://login.microsoftonline.com/retailstream-tenant-id/v2.0",
            "sub": "attacker@retailstream.com",
            "tenant_id": "tenant-retailstream-beta",
            "exp": int(time.time()) + 3600,
        },
        dpop_proof={"jkt": "thumbprint-rs-attacker", "jti": "dpop-unique-101"},
        raw_client_headers={
            "X-Tenant-ID": "tenant-finvault-alpha",
            "X-Subscription-Tier": "enterprise",
            "User-Agent": "CymbalClient/1.0",
        },
    )
    # Must remain locked to RetailStream Standard tier despite spoofed client headers
    assert envelope.tenant.tenant_id == "tenant-retailstream-beta"
    assert str(envelope.tenant.subscription_tier) == "standard"
    assert envelope.tenant.thinking_token_budget == 4000


def test_idp_issuer_cross_tenant_mismatch_rejected(
    edge_verifier: EdgeAuthVerifier,
) -> None:
    with pytest.raises(PermissionError, match="E_IDP_ISSUER_MISMATCH"):
        edge_verifier.exchange_obo_token(
            verified_idp_claims={
                "iss": "https://login.microsoftonline.com/retailstream-tenant-id/v2.0",
                "sub": "spoof@retailstream.com",
                "tenant_id": "tenant-finvault-alpha",
                "exp": int(time.time()) + 3600,
            },
            dpop_proof={"jkt": "thumbprint-spoof", "jti": "dpop-unique-102"},
        )


def test_dpop_replay_and_sender_mismatch_rejected(
    edge_verifier: EdgeAuthVerifier,
    finvault_envelope: ContextEnvelope,
) -> None:
    # Replaying the exact same DPoP jti ("dpop-fv-001") must be blocked
    with pytest.raises(PermissionError, match="E_DPOP_REPLAY_DETECTED"):
        edge_verifier.exchange_obo_token(
            verified_idp_claims={
                "iss": "https://accounts.google.com",
                "sub": "alice@finvault.com",
                "tenant_id": "tenant-finvault-alpha",
                "exp": int(time.time()) + 3600,
            },
            dpop_proof={
                "jkt": "thumbprint-finvault-alice",
                "jti": "dpop-fv-001",
            },
        )

    # Presenting a stolen OBO envelope with a different sender DPoP key thumbprint must fail
    with pytest.raises(PermissionError, match="E_DPOP_BINDING_MISMATCH"):
        edge_verifier.verify_obo_envelope(
            finvault_envelope, presented_dpop_jkt="stolen-token-wrong-key"
        )


def test_subagent_principal_chain_and_5_level_memory_isolation(
    finvault_envelope: ContextEnvelope,
    retailstream_envelope: ContextEnvelope,
    memory_bank: MemoryBankPartitioner,
) -> None:
    # Sub-agent propagation succeeds when temp:tenant_id is present
    child_state = propagate_to_subagent(finvault_envelope.to_adk_state())
    assert child_state["temp:tenant_id"] == "tenant-finvault-alpha"

    # Sub-agent propagation fails closed if temp:tenant_id is dropped
    with pytest.raises(PermissionError, match="E_SUBAGENT_PRINCIPAL_DROP"):
        propagate_to_subagent({})

    # FinVault writes a Tenant-level memory entry encrypted with FinVault's CMEK
    fv_key = memory_bank.write_memory(
        envelope=finvault_envelope,
        scope=MemoryScope.TENANT,
        actor="finvault_regulatory_escalation_agent",
        content={"occ_threshold_hours": 4},
    )
    assert fv_key.startswith("tenant-finvault-alpha/_tenant/tenant/")

    # RetailStream attempting to read FinVault's memory key must raise 403 Forbidden
    with pytest.raises(
        PermissionError,
        match="403 Forbidden: Cross-tenant memory access denied",
    ):
        memory_bank.read_memory(
            envelope=retailstream_envelope, target_key=fv_key
        )
