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

# pylint: disable=inconsistent-quotes,line-too-long

"""Deterministic Post-Generation Claim Verifier & Recency-Aware Context Packer (< 2ms).

Implements:
1. `pack_tenant_context_chunks`: Filters retrieved chunks by tenant isolation and supersession
   status (`superseded_by is None`), enforces a minimum retrieval score floor (`min_score_floor`)
   to trigger clean abstention rather than hallucination, and ranks surviving chunks by
   `(round(score, 2), updated_at)` descending within a strict token budget.
2. `verify_agent_output_deterministically`: Executes a sub-2ms deterministic verification gate
   over `DiagnosticAgentOutputContract`:
   - Cross-tenant citation & foreign incident ID check (`INC-FV-*` vs. `INC-RS-*`)
   - Exact source span grounding check (`quoted_span` substring match in `source_chunks`)
   - Numeric & unit token verification (e.g., catches `4500s` when source says `4500ms`, or
     hallucinated thresholds like `99.99%` when source says `99.95%`)
   - Negation polarity contradiction check against mandatory regulatory escalation rules
   - Unredacted PII scan (SSN, ABA, IBAN, SWIFT, PAN)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from agents.interceptors import (
    _ABA_ROUTING_PATTERN,
    _CC_PATTERN,
    _CLAUSE_BOUNDARY_RE,
    _IBAN_PATTERN,
    _NEGATION_WINDOW_RE,
    _OCC_SUPPRESSION_TARGET_RE,
    _SSN_PATTERN,
    _SWIFT_PATTERN,
)
from evals.contracts import DiagnosticAgentOutputContract

_NUMERIC_UNIT_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_-])\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:%|(?:ms|s|m|h|bps|gb|mb|kb|tb)\b))?(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_REDACTION_PLACEHOLDER_RE = re.compile(r"\[REDACTED[_-][A-Z0-9_-]+\]")
_AFFIRMATIVE_SUPPRESS_OCC_RE = _OCC_SUPPRESSION_TARGET_RE
_NEGATION_BEFORE_SUPPRESS_RE = _NEGATION_WINDOW_RE


@dataclass(frozen=True)
class ContextChunk:
    """Retrieved telemetry or runbook chunk with recency and supersession metadata."""

    doc_id: str
    tenant_id: str
    score: float
    updated_at: str
    content: str
    token_count: int
    superseded_by: str | None = None


@dataclass(frozen=True)
class ClaimVerificationResult:
    """Result of the < 2ms deterministic post-generation claim & citation verifier."""

    passed: bool
    latency_ms: float
    unverified_numbers: list[str] = field(default_factory=list)
    missing_citations: list[str] = field(default_factory=list)
    cross_tenant_citations: list[str] = field(default_factory=list)
    negation_contradictions: list[str] = field(default_factory=list)
    pii_leaks: list[str] = field(default_factory=list)


def pack_tenant_context_chunks(
    chunks: list[ContextChunk],
    *,
    caller_tenant_id: str,
    token_budget: int = 4000,
    min_score_floor: float = 0.65,
) -> dict[str, Any]:
    """Packs tenant-isolated, non-superseded context chunks ordered by `(round(score, 2),
    updated_at)`.
    """
    foreign_dropped = 0
    superseded_dropped = 0
    low_score_dropped = 0
    eligible: list[ContextChunk] = []

    for chunk in chunks:
        if chunk.tenant_id != caller_tenant_id:
            foreign_dropped += 1
            continue
        if chunk.superseded_by is not None:
            superseded_dropped += 1
            continue
        if chunk.score < min_score_floor:
            low_score_dropped += 1
            continue
        eligible.append(chunk)

    if not eligible:
        return {
            "abstain": True,
            "reason": "ABSTAIN_BELOW_SCORE_FLOOR",
            "packed_chunks": [],
            "tokens_used": 0,
            "foreign_dropped": foreign_dropped,
            "superseded_dropped": superseded_dropped,
            "low_score_dropped": low_score_dropped,
        }

    # Sort by 2-decimal score bucket first, then ISO-8601 updated_at descending
    ranked = sorted(
        eligible,
        key=lambda c: (round(c.score, 2), c.updated_at),
        reverse=True,
    )

    packed: list[ContextChunk] = []
    tokens_used = 0
    for chunk in ranked:
        if tokens_used + chunk.token_count > token_budget:
            continue
        packed.append(chunk)
        tokens_used += chunk.token_count

    return {
        "abstain": len(packed) == 0,
        "reason": "PACKED_OK" if packed else "ABSTAIN_TOKEN_BUDGET_EXCEEDED",
        "packed_chunks": packed,
        "tokens_used": tokens_used,
        "foreign_dropped": foreign_dropped,
        "superseded_dropped": superseded_dropped,
        "low_score_dropped": low_score_dropped,
    }


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _extract_numeric_tokens(text: str) -> list[str]:
    """Extracts normalized number+unit tokens (excluding years like 2026 or IDs like
    INC-FV-1001).
    """
    # Strip canonical IDs (INC-FV-1001, DOC-FV-SEC-17A4-2026, ROA-2026-8812, Rule 17a-4) first
    cleaned = re.sub(r"\b(?:INC|DOC|ROA)-[A-Z0-9-]+\b", " ", text)
    cleaned = re.sub(r"\bRule\s+17a-4\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bP[1-4]\b", " ", cleaned)
    tokens: list[str] = []
    for match in _NUMERIC_UNIT_TOKEN_RE.finditer(cleaned):
        raw = re.sub(r"\s+", "", match.group(0)).lower()
        if raw not in tokens:
            tokens.append(raw)
    return tokens


def verify_agent_output_deterministically(
    contract: DiagnosticAgentOutputContract,
    *,
    source_chunks: list[ContextChunk],
    caller_tenant_id: str,
) -> ClaimVerificationResult:
    """Executes deterministic < 2ms post-generation verification on a structured agent output."""
    t0 = time.perf_counter()
    unverified_numbers: list[str] = []
    missing_citations: list[str] = []
    cross_tenant_citations: list[str] = []
    negation_contradictions: list[str] = []
    pii_leaks: list[str] = []

    if contract.tenant_id != caller_tenant_id:
        cross_tenant_citations.append(
            f"contract.tenant_id='{contract.tenant_id}' != '{caller_tenant_id}'"
        )

    chunk_by_id = {
        c.doc_id: c for c in source_chunks if c.tenant_id == caller_tenant_id
    }
    combined_source_norm = " | ".join(
        _normalize_ws(c.content) for c in chunk_by_id.values()
    )
    source_numeric_tokens = set(_extract_numeric_tokens(combined_source_norm))

    # 1. Verify citations exist for active decisions and match source chunks verbatim
    if (
        contract.decision in ("ESCALATE_OCC_REGULATORY", "REMEDIATE_STANDARD")
        and not contract.citations
    ):
        missing_citations.append(
            f"Decision '{contract.decision}' has 0 citations."
        )

    for cit in contract.citations:
        if cit.tenant_id != caller_tenant_id:
            cross_tenant_citations.append(
                f"{cit.source_id} (tenant={cit.tenant_id})"
            )
            continue
        src_chunk = chunk_by_id.get(cit.source_id)
        if src_chunk is None:
            missing_citations.append(
                f"Unknown or unentitled source_id '{cit.source_id}'"
            )
            continue
        if _normalize_ws(cit.quoted_span) not in _normalize_ws(
            src_chunk.content
        ):
            missing_citations.append(
                f"Span '{cit.quoted_span}' not verbatim in '{cit.source_id}'"
            )

    # 2. Check for foreign tenant incident prefixes anywhere in output text
    full_output_text = " ".join(
        [
            contract.evidence_summary,
            *contract.recommended_actions,
            *(c.source_id for c in contract.citations),
        ]
    )
    if (
        caller_tenant_id == "tenant-finvault-alpha"
        and "INC-RS-" in full_output_text
    ):
        cross_tenant_citations.append(
            "Foreign RetailStream incident ID (INC-RS-*) in FinVault output"
        )
    if (
        caller_tenant_id == "tenant-retailstream-beta"
        and "INC-FV-" in full_output_text
    ):
        cross_tenant_citations.append(
            "Foreign FinVault incident ID (INC-FV-*) in RetailStream output"
        )

    # 3. Verify every numeric/unit claim in evidence_summary + recommended_actions is grounded
    candidate_numeric_tokens = _extract_numeric_tokens(
        f"{contract.evidence_summary} {' '.join(contract.recommended_actions)}"
    )
    for tok in candidate_numeric_tokens:
        if tok not in source_numeric_tokens:
            unverified_numbers.append(tok)

    # 4. Verify negation polarity (catch affirmative OCC suppression in output, clause-aware)
    norm_occ = re.sub(r"[ \t\r\f\v]+", " ", full_output_text).strip().lower()
    for match in _AFFIRMATIVE_SUPPRESS_OCC_RE.finditer(norm_occ):
        window_start = max(0, match.start() - 80)
        preceding = norm_occ[window_start : match.start()]
        current_clause = _CLAUSE_BOUNDARY_RE.split(preceding)[-1]
        if not _NEGATION_BEFORE_SUPPRESS_RE.search(current_clause):
            negation_contradictions.append(match.group(0))

    # 5. Check for unredacted PII in output
    scrubbed = _REDACTION_PLACEHOLDER_RE.sub("", full_output_text)
    if _SSN_PATTERN.search(scrubbed):
        pii_leaks.append("UNREDACTED_SSN")
    if _ABA_ROUTING_PATTERN.search(scrubbed):
        pii_leaks.append("UNREDACTED_ABA_ROUTING")
    if _IBAN_PATTERN.search(scrubbed):
        pii_leaks.append("UNREDACTED_IBAN")
    if _SWIFT_PATTERN.search(scrubbed):
        pii_leaks.append("UNREDACTED_SWIFT")
    if _CC_PATTERN.search(scrubbed):
        pii_leaks.append("UNREDACTED_PAYMENT_PAN")

    latency_ms = round((time.perf_counter() - t0) * 1000.0, 4)
    passed = not (
        unverified_numbers
        or missing_citations
        or cross_tenant_citations
        or negation_contradictions
        or pii_leaks
    )
    return ClaimVerificationResult(
        passed=passed,
        latency_ms=latency_ms,
        unverified_numbers=unverified_numbers,
        missing_citations=missing_citations,
        cross_tenant_citations=cross_tenant_citations,
        negation_contradictions=negation_contradictions,
        pii_leaks=pii_leaks,
    )
