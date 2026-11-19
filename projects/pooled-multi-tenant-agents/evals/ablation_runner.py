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

"""5-Layer Failure Ablation Waterfall & Stratified Golden Dataset Evaluator.

Implements Study Guide Chapter 9 Root-Cause Ablation Waterfall:
When an evaluation case fails, attributes the failure to its earliest causal stage across the 5
layers of a compound multi-tenant AI system:
  - `L1_PEP_INGRESS_OR_RBAC`: Edge OBO Auth, Model Armor ingress, Agent/Tool RBAC, Token Bulkhead
  - `L2_RETRIEVAL_OR_CONTEXT_PACKING`: Foreign chunk bleed, superseded chunk, or score-floor miss
  - `L3_TOOL_SCHEMA_OR_3LO_EXECUTION`: Wrong MCP tool selected or invalid tool arguments
  - `L4_CLAIM_GROUNDING_OR_GENERATION`: Unverified number/unit, missing citation, or decision drift
  - `L5_EGRESS_DLP_OR_NLC_GUARDRAIL`: Unredacted PII leak or Egress NLC false positive/negative
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

AblationStage = Literal[
    "PASS_NO_FAILURE",
    "L1_PEP_INGRESS_OR_RBAC",
    "L2_RETRIEVAL_OR_CONTEXT_PACKING",
    "L3_TOOL_SCHEMA_OR_3LO_EXECUTION",
    "L4_CLAIM_GROUNDING_OR_GENERATION",
    "L5_EGRESS_DLP_OR_NLC_GUARDRAIL",
]

DEFAULT_GOLDEN_SUITE_PATH = (
    Path(__file__).resolve().parent / "datasets" / "golden_eval_suite.jsonl"
)
DEFAULT_SANDBOX_BEHAVIORAL_SUITE_PATH = (
    Path(__file__).resolve().parent
    / "datasets"
    / "sandbox_behavioral_eval.jsonl"
)


@dataclass(frozen=True)
class TraceAblationRecord:
    """Per-case trace signals used to classify failures into the 5-layer ablation waterfall."""

    eval_id: str
    slice_name: str
    expected_http: int
    actual_http: int
    expected_decision: str
    actual_decision: str
    retrieval_score: float
    min_score_floor: float = 0.65
    foreign_chunk_retrieved: bool = False
    superseded_chunk_used: bool = False
    expected_tool: str | None = None
    actual_tool: str | None = None
    unverified_claims_count: int = 0
    missing_citations_count: int = 0
    pii_leaked: bool = False
    egress_nlc_mismatch: bool = False
    expected_error_code: str | None = None
    actual_error_code: str | None = None
    sandbox_invoked: bool = False
    sandbox_blocked: bool = False
    sandbox_error_code: str | None = None
    expected_sandbox_exit_code: int | None = None
    actual_sandbox_exit_code: int | None = None


_SANDBOX_L3_ERROR_CODES: frozenset[str] = frozenset(
    {
        "E_SANDBOX_INVALID_CODE",
        "E_SANDBOX_SYNTAX_ERROR",
        "E_SANDBOX_EMPTY_CODE",
        "E_SANDBOX_CODE_TOO_LARGE",
        "E_SANDBOX_INVALID_INPUT",
        "E_SANDBOX_UNAVAILABLE",
        "E_SANDBOX_RUNTIME_ERROR",
    }
)


def _is_sandbox_l3_error(trace: TraceAblationRecord) -> bool:
    code = trace.sandbox_error_code or trace.actual_error_code or ""
    if code in _SANDBOX_L3_ERROR_CODES:
        return True
    return (
        trace.actual_http in (422, 503) or trace.expected_http in (422, 503)
    ) and (
        trace.sandbox_invoked
        or trace.expected_tool == "execute_diagnostic_sandbox"
        or trace.actual_tool == "execute_diagnostic_sandbox"
    )


def attribute_failure_stage(trace: TraceAblationRecord) -> AblationStage:
    """Deterministically attributes a trace to `PASS_NO_FAILURE` or its root-cause waterfall
    layer.
    """
    # Layer 5 check first if egress DLP leaked PII or NLC falsely blocked/allowed at Hop 4
    if trace.pii_leaked or trace.egress_nlc_mismatch:
        return "L5_EGRESS_DLP_OR_NLC_GUARDRAIL"

    # Layer 1 vs Layer 3 HTTP / sandbox refusal & execution error attribution
    if trace.actual_http != trace.expected_http:
        if _is_sandbox_l3_error(trace):
            return "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"
        return "L1_PEP_INGRESS_OR_RBAC"

    if (
        trace.expected_error_code
        and trace.actual_error_code
        and trace.expected_error_code != trace.actual_error_code
    ):
        if trace.expected_http in (401, 403, 429) or trace.actual_http in (
            401,
            403,
            429,
        ):
            return "L1_PEP_INGRESS_OR_RBAC"
        return "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"

    if trace.sandbox_blocked and trace.expected_http == 200:
        if trace.sandbox_error_code in _SANDBOX_L3_ERROR_CODES:
            return "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"
        return "L1_PEP_INGRESS_OR_RBAC"

    # Layer 2: Retrieval & Context Packing (foreign chunk, superseded doc, or missed abstention)
    should_abstain = (
        trace.retrieval_score < trace.min_score_floor
        and trace.expected_http == 200
    )
    if (
        trace.foreign_chunk_retrieved
        or trace.superseded_chunk_used
        or (
            should_abstain
            and trace.actual_decision != "ABSTAIN_INSUFFICIENT_EVIDENCE"
        )
    ):
        return "L2_RETRIEVAL_OR_CONTEXT_PACKING"

    # Layer 3: Tool selection / 3LO execution / sandbox schema & runtime error mismatch
    if (
        trace.expected_tool
        and trace.actual_tool
        and trace.expected_tool != trace.actual_tool
    ):
        return "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"
    if (
        trace.expected_tool
        and trace.expected_http == 200
        and trace.actual_http == 200
        and trace.expected_decision != "ABSTAIN_INSUFFICIENT_EVIDENCE"
        and trace.actual_tool != trace.expected_tool
    ):
        return "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"
    if (
        trace.expected_sandbox_exit_code is not None
        and trace.actual_sandbox_exit_code != trace.expected_sandbox_exit_code
    ):
        return "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"
    if (
        trace.expected_http == 200
        and trace.sandbox_error_code is not None
        and trace.expected_error_code is None
    ):
        return "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"

    # Layer 4: Generation claim grounding, citation completeness, or decision mismatch
    if (
        trace.unverified_claims_count > 0
        or trace.missing_citations_count > 0
        or trace.actual_decision != trace.expected_decision
    ):
        return "L4_CLAIM_GROUNDING_OR_GENERATION"

    return "PASS_NO_FAILURE"


def run_five_layer_ablation_waterfall(
    traces: list[TraceAblationRecord],
) -> dict[str, Any]:
    """Aggregates trace records into a 5-layer failure waterfall and per-slice pass breakdown."""
    stage_counts: dict[AblationStage, int] = {
        "PASS_NO_FAILURE": 0,
        "L1_PEP_INGRESS_OR_RBAC": 0,
        "L2_RETRIEVAL_OR_CONTEXT_PACKING": 0,
        "L3_TOOL_SCHEMA_OR_3LO_EXECUTION": 0,
        "L4_CLAIM_GROUNDING_OR_GENERATION": 0,
        "L5_EGRESS_DLP_OR_NLC_GUARDRAIL": 0,
    }
    by_slice: dict[str, dict[str, Any]] = {}
    classified_cases: list[dict[str, Any]] = []
    sandbox_total = 0
    sandbox_passed = 0
    sandbox_refusals = 0
    sandbox_errors = 0

    for t in traces:
        stage = attribute_failure_stage(t)
        stage_counts[stage] += 1
        passed = stage == "PASS_NO_FAILURE"

        is_sandbox_trace = (
            t.sandbox_invoked
            or t.expected_tool == "execute_diagnostic_sandbox"
            or t.actual_tool == "execute_diagnostic_sandbox"
            or t.sandbox_blocked
            or t.sandbox_error_code is not None
            or t.expected_sandbox_exit_code is not None
        )
        if is_sandbox_trace:
            sandbox_total += 1
            if passed:
                sandbox_passed += 1
            if t.sandbox_blocked or t.actual_http in (403, 429):
                sandbox_refusals += 1
            if (
                t.sandbox_error_code is not None
                or t.actual_http in (422, 503)
                or (
                    t.actual_sandbox_exit_code is not None
                    and t.actual_sandbox_exit_code != 0
                )
            ):
                sandbox_errors += 1

        s_bucket = by_slice.setdefault(
            t.slice_name, {"total": 0, "passed": 0, "failures": {}}
        )
        s_bucket["total"] += 1
        if passed:
            s_bucket["passed"] += 1
        else:
            s_bucket["failures"][stage] = s_bucket["failures"].get(stage, 0) + 1

        classified_cases.append(
            {
                "eval_id": t.eval_id,
                "slice": t.slice_name,
                "passed": passed,
                "stage": stage,
            }
        )

    for stats in by_slice.values():
        stats["pass_rate"] = (
            round(stats["passed"] / stats["total"], 4)
            if stats["total"] > 0
            else 0.0
        )

    total = len(traces)
    passed_total = stage_counts["PASS_NO_FAILURE"]
    failed_total = total - passed_total
    failure_share_by_stage = {
        k: round(v / failed_total, 4) if failed_total > 0 else 0.0
        for k, v in stage_counts.items()
        if k != "PASS_NO_FAILURE"
    }

    return {
        "total_cases": total,
        "passed_cases": passed_total,
        "failed_cases": failed_total,
        "overall_pass_rate": (
            round(passed_total / total, 4) if total > 0 else 0.0
        ),
        "stage_counts": stage_counts,
        "failure_share_by_stage": failure_share_by_stage,
        "by_slice": by_slice,
        "sandbox_summary": {
            "total_sandbox_traces": sandbox_total,
            "sandbox_passed": sandbox_passed,
            "sandbox_policy_refusals": sandbox_refusals,
            "sandbox_execution_errors": sandbox_errors,
        },
        "cases": classified_cases,
    }


def load_golden_eval_suite(
    path: Path = DEFAULT_GOLDEN_SUITE_PATH,
) -> list[dict[str, Any]]:
    """Loads a JSONL evaluation suite (default: 20-case stratified golden suite)."""
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [json.loads(line) for line in lines]


def load_sandbox_behavioral_eval_suite(
    path: Path = DEFAULT_SANDBOX_BEHAVIORAL_SUITE_PATH,
) -> list[dict[str, Any]]:
    """Loads the agent sandbox benign, near-boundary, and adversarial behavioral eval suite."""
    return load_golden_eval_suite(path)
