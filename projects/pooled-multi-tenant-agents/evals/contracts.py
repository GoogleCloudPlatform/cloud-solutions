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

"""Structured Output Contracts & Discriminated Error Taxonomy for Multi-Tenant Agents.

Implements:
1. Cognitive Field Ordering (`DiagnosticAgentOutputContract`): Places `evidence_summary` and
   `citations` strictly BEFORE `decision` and `recommended_actions` so autoregressive decoding
   grounds on retrieved telemetry and runbook spans before committing to a classification token.
2. Discriminated Error Taxonomy (`classify_pipeline_error`): Distinguishes terminal security/policy
   blocks (`403`, `422`, `429` — never self-corrected) from retryable schema/citation drift
   (max 1 structured correction turn) and transient infrastructure faults (exponential backoff).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents.sandbox_execution import SandboxUnavailableError
from pydantic import BaseModel, Field, ValidationError, field_validator

DiagnosticDecision = Literal[
    "ESCALATE_OCC_REGULATORY",
    "REMEDIATE_STANDARD",
    "ABSTAIN_INSUFFICIENT_EVIDENCE",
    "BLOCKED_POLICY",
]

GuardrailErrorCategory = Literal[
    "TERMINAL_POLICY_VIOLATION",
    "SCHEMA_OR_CITATION_DRIFT",
    "TRANSIENT_INFRA",
]


class UnverifiedClaimError(ValueError):
    """Raised when a generated claim, number, unit, or citation is not grounded in source chunks."""


class CitationSpan(BaseModel):
    """Exact evidence span linking a generated claim to a tenant-scoped incident or runbook."""

    source_id: str = Field(
        ...,
        min_length=3,
        description="Canonical incident or runbook ID (e.g., INC-FV-1001, DOC-FV-SEC-17A4-2026).",
    )
    tenant_id: str = Field(
        ...,
        min_length=3,
        description="Tenant scope owning the cited artifact.",
    )
    quoted_span: str = Field(
        ...,
        min_length=5,
        description="Exact verbatim substring from the retrieved source chunk.",
    )
    numeric_claims: list[str] = Field(
        default_factory=list,
        description="Explicit number+unit tokens grounded in this span (e.g., '4500ms', '503').",
    )


class DiagnosticAgentOutputContract(BaseModel):
    """Cognitive-ordered structured output contract for the Cymbal Shared Diagnostic Agent.

    Field order is load-bearing for autoregressive generation:
      1. `evidence_summary` (synthesizes retrieved facts first)
      2. `citations` (anchors exact source spans and numeric tokens)
      3. `decision` (commits to classification conditioned on preceding evidence)
      4. `recommended_actions` (proposes concrete runbook steps)
      5. `tenant_id` (cryptographic tenant attribution)
    """

    evidence_summary: str = Field(
        ...,
        min_length=10,
        description="Factual synthesis of retrieved telemetry and runbook evidence.",
    )
    citations: list[CitationSpan] = Field(
        default_factory=list,
        description="Supporting source spans; must be populated for non-abstaining decisions.",
    )
    decision: DiagnosticDecision = Field(
        ...,
        description="Classification decision conditioned on evidence_summary and citations.",
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Concrete remediation actions grounded in the tenant's entitled runbook.",
    )
    tenant_id: str = Field(
        ...,
        description="Authenticated tenant_id bound to this diagnostic response.",
    )

    @field_validator("citations")
    @classmethod
    def _validate_non_empty_for_active_decisions(
        cls, v: list[CitationSpan]
    ) -> list[CitationSpan]:
        return v

    def validate_citations_for_decision(self) -> None:
        """Enforces that active remediation/escalation decisions include at least one citation."""
        if (
            self.decision in ("ESCALATE_OCC_REGULATORY", "REMEDIATE_STANDARD")
            and not self.citations
        ):
            raise UnverifiedClaimError(
                f"Decision '{self.decision}' requires at least one grounded CitationSpan."
            )

    @classmethod
    def verify_cognitive_field_order(cls) -> tuple[str, ...]:
        """Verifies `evidence_summary` and `citations` strictly precede `decision` in the schema."""
        field_names = tuple(cls.model_fields.keys())
        ev_idx = field_names.index("evidence_summary")
        cit_idx = field_names.index("citations")
        dec_idx = field_names.index("decision")
        act_idx = field_names.index("recommended_actions")
        if not (ev_idx < cit_idx < dec_idx < act_idx):
            raise AssertionError(
                f"Cognitive field ordering violated: expected evidence_summary < citations < "
                f"decision < recommended_actions, got {field_names}"
            )
        return field_names


@dataclass(frozen=True)
class ClassifiedPipelineError:
    """Structured error classification governing retry vs. self-correction vs. terminal halt."""

    category: GuardrailErrorCategory
    retryable: bool
    max_retries: int
    allow_llm_self_correction: bool
    error_code: str
    detail: str


_TERMINAL_ERROR_MARKERS: tuple[str, ...] = (
    "403",
    "422",
    "429",
    "E_MODEL_ARMOR_",
    "E_INDIRECT_PROMPT_INJECTION",
    "E_NLC_",
    "E_UNAUTHENTICATED_TENANT",
    "E_TENANT_OFFBOARDED",
    "E_CACHE_POISONING",
    "E_SUBAGENT_",
    "E_3LO_CONFUSED_DEPUTY",
    "E_DPOP_",
    "E_SESSION_LOOP_CIRCUIT_BREAKER",
    "E_SANDBOX_CREDENTIAL_",
    "E_SANDBOX_AST_",
    "E_SANDBOX_SCOPE_",
    "E_SANDBOX_SHELL_",
    "E_SANDBOX_BULKHEAD_",
    "E_CROSS_TENANT_SANDBOX_",
    "E_SANDBOX_ALREADY_DESTROYED",
    "E_SANDBOX_SESSION_PIN_MISMATCH",
)

_SANDBOX_INPUT_ERROR_MARKERS: tuple[str, ...] = (
    "E_SANDBOX_SYNTAX_ERROR",
    "E_SANDBOX_EMPTY_CODE",
    "E_SANDBOX_CODE_TOO_LARGE",
    "E_SANDBOX_INVALID_INPUT",
    "E_SANDBOX_INVALID_CODE",
    "SandboxLanguage",
)


def classify_pipeline_error(exc: BaseException) -> ClassifiedPipelineError:
    """Classifies runtime exceptions into terminal policy blocks, schema drift, or transient infra.

    Prevents the anti-pattern of feeding security/policy violations (`403`, `422`, `429`) back
    into an LLM self-correction loop (which wastes tokens and gives an attacker multiple probes),
    while allowing bounded single-turn self-correction on sandbox syntax/input `ValueError`s and
    marking `SandboxUnavailableError` as backoff-retryable `TRANSIENT_INFRA`.
    """
    msg = str(exc)
    if isinstance(exc, SandboxUnavailableError):
        return ClassifiedPipelineError(
            category="TRANSIENT_INFRA",
            retryable=True,
            max_retries=2,
            allow_llm_self_correction=False,
            error_code=getattr(exc, "code", "E_SANDBOX_UNAVAILABLE")
            or "E_SANDBOX_UNAVAILABLE",
            detail=msg,
        )

    if isinstance(exc, PermissionError):
        return ClassifiedPipelineError(
            category="TERMINAL_POLICY_VIOLATION",
            retryable=False,
            max_retries=0,
            allow_llm_self_correction=False,
            error_code="PEP_TERMINAL_HALT",
            detail=msg,
        )

    if isinstance(exc, (ValidationError, UnverifiedClaimError)) or any(
        marker in msg for marker in _SANDBOX_INPUT_ERROR_MARKERS
    ):
        return ClassifiedPipelineError(
            category="SCHEMA_OR_CITATION_DRIFT",
            retryable=True,
            max_retries=1,
            allow_llm_self_correction=True,
            error_code="STRUCTURED_SELF_CORRECTION_ELIGIBLE",
            detail=msg,
        )

    if any(marker in msg for marker in _TERMINAL_ERROR_MARKERS):
        return ClassifiedPipelineError(
            category="TERMINAL_POLICY_VIOLATION",
            retryable=False,
            max_retries=0,
            allow_llm_self_correction=False,
            error_code="PEP_TERMINAL_HALT",
            detail=msg,
        )

    if isinstance(exc, ValueError) and "sandbox" in msg.lower():
        return ClassifiedPipelineError(
            category="SCHEMA_OR_CITATION_DRIFT",
            retryable=True,
            max_retries=1,
            allow_llm_self_correction=True,
            error_code="STRUCTURED_SELF_CORRECTION_ELIGIBLE",
            detail=msg,
        )

    return ClassifiedPipelineError(
        category="TRANSIENT_INFRA",
        retryable=True,
        max_retries=2,
        allow_llm_self_correction=False,
        error_code="INFRA_BACKOFF_RETRY",
        detail=msg,
    )
