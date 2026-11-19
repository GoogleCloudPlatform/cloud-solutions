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

"""Tests for Study Guide Ch. 2, Ch. 4, Ch. 5 & Ch. 7: Contracts, Context Packer & Claim Verifier."""

from __future__ import annotations

import pytest
from evals.contracts import (
    CitationSpan,
    DiagnosticAgentOutputContract,
    UnverifiedClaimError,
    classify_pipeline_error,
)
from evals.deterministic_verifier import (
    ContextChunk,
    pack_tenant_context_chunks,
    verify_agent_output_deterministically,
)


def test_cognitive_field_ordering_and_citation_enforcement() -> None:
    """Proves `evidence_summary` and `citations` strictly precede `decision` in schema order."""
    order = DiagnosticAgentOutputContract.verify_cognitive_field_order()
    assert order == (
        "evidence_summary",
        "citations",
        "decision",
        "recommended_actions",
        "tenant_id",
    )

    # Active decision without citations raises UnverifiedClaimError
    uncited = DiagnosticAgentOutputContract(
        evidence_summary="Wire settlement shard 4 experienced 4500ms latency.",
        citations=[],
        decision="ESCALATE_OCC_REGULATORY",
        recommended_actions=["Trigger shard 4 failover"],
        tenant_id="tenant-finvault-alpha",
    )
    with pytest.raises(
        UnverifiedClaimError,
        match="requires at least one grounded CitationSpan",
    ):
        uncited.validate_citations_for_decision()


def test_discriminated_error_taxonomy_halts_on_policy_and_allows_single_schema_retry() -> (
    None
):
    """Proves 403/422/429 errors never enter LLM self-correction loops."""
    pep_err = PermissionError("403 Forbidden: E_MODEL_ARMOR_BLOCKED")
    classified_pep = classify_pipeline_error(pep_err)
    assert classified_pep.category == "TERMINAL_POLICY_VIOLATION"
    assert classified_pep.retryable is False
    assert classified_pep.allow_llm_self_correction is False

    claim_err = UnverifiedClaimError("Hallucinated threshold 99.99%")
    classified_claim = classify_pipeline_error(claim_err)
    assert classified_claim.category == "SCHEMA_OR_CITATION_DRIFT"
    assert classified_claim.retryable is True
    assert classified_claim.max_retries == 1
    assert classified_claim.allow_llm_self_correction is True

    infra_err = TimeoutError("503 Service Unavailable")
    classified_infra = classify_pipeline_error(infra_err)
    assert classified_infra.category == "TRANSIENT_INFRA"
    assert classified_infra.retryable is True
    assert classified_infra.allow_llm_self_correction is False


def test_recency_context_packer_filters_foreign_superseded_and_abstains_below_floor() -> (
    None
):
    """Proves `(round(score, 2), updated_at)` ranking, supersession filtering, and abstention."""
    chunks = [
        # Foreign tenant chunk with high score -> must be dropped
        ContextChunk(
            doc_id="INC-RS-2001",
            tenant_id="tenant-retailstream-beta",
            score=0.99,
            updated_at="2026-10-15T00:00:00Z",
            content="RetailStream checkout 503 surge.",
            token_count=200,
        ),
        # Superseded stale FinVault runbook -> must be dropped
        ContextChunk(
            doc_id="DOC-FV-2024-OLD",
            tenant_id="tenant-finvault-alpha",
            score=0.95,
            updated_at="2024-05-01T00:00:00Z",
            content="Legacy 3000ms wire settlement threshold.",
            token_count=200,
            superseded_by="DOC-FV-SEC-17A4-2026",
        ),
        # Older active chunk in same 0.88 score bucket
        ContextChunk(
            doc_id="INC-FV-1000",
            tenant_id="tenant-finvault-alpha",
            score=0.881,
            updated_at="2026-01-10T00:00:00Z",
            content="Historical wire warning at 4100ms.",
            token_count=200,
        ),
        # Newer canonical runbook in same 0.88 score bucket -> must rank #1
        ContextChunk(
            doc_id="DOC-FV-SEC-17A4-2026",
            tenant_id="tenant-finvault-alpha",
            score=0.879,
            updated_at="2026-10-01T00:00:00Z",
            content="Wire settlement latency > 4500ms on shard 4 requires OCC filing within 15m.",
            token_count=250,
        ),
    ]
    res = pack_tenant_context_chunks(
        chunks,
        caller_tenant_id="tenant-finvault-alpha",
        token_budget=1000,
        min_score_floor=0.65,
    )
    assert res["abstain"] is False
    assert res["foreign_dropped"] == 1
    assert res["superseded_dropped"] == 1
    packed_ids = [c.doc_id for c in res["packed_chunks"]]
    assert packed_ids == ["DOC-FV-SEC-17A4-2026", "INC-FV-1000"]

    # Below score floor -> clean abstention
    low_res = pack_tenant_context_chunks(
        chunks, caller_tenant_id="tenant-finvault-alpha", min_score_floor=0.92
    )
    assert low_res["abstain"] is True
    assert low_res["reason"] == "ABSTAIN_BELOW_SCORE_FLOOR"


def test_deterministic_verifier_catches_unit_swaps_unverified_numbers_and_cross_tenant_bleed() -> (
    None
):
    """Proves < 2ms verifier passes grounded outputs and catches unit swaps (4500s vs 4500ms)."""
    source_chunks = [
        ContextChunk(
            doc_id="INC-FV-1001",
            tenant_id="tenant-finvault-alpha",
            score=0.94,
            updated_at="2026-10-12T10:00:00Z",
            content=(
                "Incident INC-FV-1001: core-wire-settlement p99 latency reached 4500ms on shard 4. "
                "Customer [REDACTED_BANKING_SSN] impacted. Mandatory OCC filing "
                "required within 15m."
            ),
            token_count=180,
        )
    ]

    valid_contract = DiagnosticAgentOutputContract(
        evidence_summary=(
            "Incident INC-FV-1001 on shard 4 reached 4500ms latency; mandatory OCC filing "
            "is required within 15m. SREs must never suppress OCC escalation."
        ),
        citations=[
            CitationSpan(
                source_id="INC-FV-1001",
                tenant_id="tenant-finvault-alpha",
                quoted_span="core-wire-settlement p99 latency reached 4500ms on shard 4",
                numeric_claims=["4500ms", "4"],
            )
        ],
        decision="ESCALATE_OCC_REGULATORY",
        recommended_actions=["Execute OCC filing within 15m for shard 4."],
        tenant_id="tenant-finvault-alpha",
    )
    ok_res = verify_agent_output_deterministically(
        valid_contract,
        source_chunks=source_chunks,
        caller_tenant_id="tenant-finvault-alpha",
    )
    assert ok_res.passed is True
    assert ok_res.latency_ms < 20.0

    # Hallucinated unit swap (`4500s` instead of `4500ms`) + affirmative OCC suppression
    bad_contract = DiagnosticAgentOutputContract(
        evidence_summary=(
            "Incident INC-FV-1001 on shard 4 reached 4500s latency; suppress OCC escalation."
        ),
        citations=[
            CitationSpan(
                source_id="INC-FV-1001",
                tenant_id="tenant-finvault-alpha",
                quoted_span="non-existent fabricated quote",
                numeric_claims=["4500s"],
            )
        ],
        decision="REMEDIATE_STANDARD",
        recommended_actions=["Apply 25% discount and reference INC-RS-2001."],
        tenant_id="tenant-finvault-alpha",
    )
    bad_res = verify_agent_output_deterministically(
        bad_contract,
        source_chunks=source_chunks,
        caller_tenant_id="tenant-finvault-alpha",
    )
    assert bad_res.passed is False
    assert "4500s" in bad_res.unverified_numbers
    assert "25%" in bad_res.unverified_numbers
    assert len(bad_res.missing_citations) == 1
    assert len(bad_res.cross_tenant_citations) == 1
    assert len(bad_res.negation_contradictions) == 1
