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

"""Tests for Study Guide Ch. 8 & Ch. 9: Calibrated Judge, Rogan-Gladen, McNemar & 5-Layer
Ablation.
"""

from __future__ import annotations

import pytest
from agents.sandbox_execution import SandboxUnavailableError
from evals.ablation_runner import (
    TraceAblationRecord,
    attribute_failure_stage,
    load_golden_eval_suite,
    load_sandbox_behavioral_eval_suite,
    run_five_layer_ablation_waterfall,
)
from evals.contracts import classify_pipeline_error
from evals.judge_calibration import (
    DecomposedJudgeVerdict,
    calibrate_judge_against_human,
    compute_security_confusion_matrix,
    evaluate_pairwise_swapped,
    paired_mcnemar_test,
    rogan_gladen_true_pass_rate,
)


def test_decomposed_judge_verdict_enforces_binary_conjunction_and_evidence_order() -> (
    None
):
    """Proves `overall_pass` is strictly the conjunction of the 4 binary sub-checks."""
    fields = tuple(DecomposedJudgeVerdict.model_fields.keys())
    assert fields[:2] == ("evidence_spans", "reasoning_trace")

    all_pass = DecomposedJudgeVerdict(
        evidence_spans=["core-wire-settlement p99 latency reached 4500ms"],
        reasoning_trace="All claims grounded in INC-FV-1001 with zero cross-tenant bleed or PII.",
        check_1_tenant_isolation=True,
        check_2_factual_grounding=True,
        check_3_runbook_compliance=True,
        check_4_pii_and_nlc_safety=True,
    )
    assert all_pass.overall_pass is True

    one_fail = DecomposedJudgeVerdict(
        evidence_spans=["core-wire-settlement p99 latency reached 4500s"],
        reasoning_trace="Unit swap detected: candidate states 4500s instead of 4500ms.",
        check_1_tenant_isolation=True,
        check_2_factual_grounding=False,
        check_3_runbook_compliance=True,
        check_4_pii_and_nlc_safety=True,
        overall_pass=True,  # Even if caller passes True, validator forces False!
    )
    assert one_fail.overall_pass is False


def test_pairwise_position_swap_catches_first_position_bias_and_confirms_true_winner() -> (
    None
):
    """Proves `(A, B)` + `(B, A)` position swapping demotes position-biased judges to TIE."""
    # Biased comparator that always picks whatever response is placed in position 1 ("A")
    biased_res = evaluate_pairwise_swapped(
        response_a="Concise grounded FinVault response",
        response_b="Verbose padded response",
        comparator=lambda _first, _second: "A",
    )
    assert biased_res["outcome"] == "TIE_POSITION_BIAS"
    assert biased_res["position_bias_detected"] is True

    # Content-based comparator that prefers the response containing 'INC-FV-1001' regardless of
    # order
    consistent_res = evaluate_pairwise_swapped(
        response_a="Grounded in INC-FV-1001 (4500ms)",
        response_b="Generic ungrounded summary",
        comparator=lambda first, _second: (
            "A" if "INC-FV-1001" in first else "B"
        ),
    )
    assert consistent_res["outcome"] == "CONSISTENT_A"
    assert consistent_res["position_bias_detected"] is False


def test_judge_calibration_kappa_and_rogan_gladen_bias_correction() -> None:
    """Proves Cohen's kappa, $p + q > 1.5$ gate, and Rogan-Gladen $\\hat{\\theta}$ correction."""
    # 20 gold examples: 10 true pass (1), 10 true fail (0)
    # Judge has sensitivity p = 0.90 (9/10) and specificity q = 0.80 (8/10) -> p + q = 1.70 > 1.50
    human = [1] * 10 + [0] * 10
    judge = [1] * 9 + [0] * 1 + [0] * 8 + [1] * 2

    cal = calibrate_judge_against_human(human_labels=human, judge_labels=judge)
    assert cal["sensitivity_p"] == 0.9
    assert cal["specificity_q"] == 0.8
    assert cal["p_plus_q"] == 1.7
    assert cal["cohens_kappa"] == 0.7
    assert cal["calibrated"] is True

    # Suppose on production traffic, observed judge pass rate is 0.76 with p=0.90, q=0.80:
    # True pass rate theta = (0.76 + 0.80 - 1) / (0.90 + 0.80 - 1) = 0.56 / 0.70 = 0.80!
    rg = rogan_gladen_true_pass_rate(
        observed_pass_rate=0.76,
        sensitivity_p=0.90,
        specificity_q=0.80,
        n_samples=500,
    )
    assert rg["corrected_true_pass_rate"] == 0.8
    assert rg["ci_95_low"] < 0.8 < rg["ci_95_high"]

    # Uncalibrated judge with p + q <= 1.0 must raise ValueError
    with pytest.raises(
        ValueError, match="worse than or equal to random guessing"
    ):
        rogan_gladen_true_pass_rate(
            observed_pass_rate=0.5, sensitivity_p=0.5, specificity_q=0.5
        )


def test_paired_mcnemar_test_detects_statistically_significant_improvement() -> (
    None
):
    """Proves paired McNemar $\\chi^2 = (b - c)^2 / (b + c)$ on discordant pairs."""
    # 50 paired cases:
    # 35 both pass (a=35), 2 regressions (b=2), 11 improvements (c=11), 2 both fail (d=2)
    # chi2 = (2 - 11)^2 / (2 + 11) = 81 / 13 = 6.2308 > 3.841 -> SIGNIFICANT_IMPROVEMENT
    baseline = [1] * 35 + [1] * 2 + [0] * 11 + [0] * 2
    candidate = [1] * 35 + [0] * 2 + [1] * 11 + [0] * 2

    res = paired_mcnemar_test(
        baseline_outcomes=baseline, candidate_outcomes=candidate
    )
    assert res["b_regressions"] == 2
    assert res["c_improvements"] == 11
    assert res["discordant_pairs"] == 13
    assert res["mcnemar_chi2"] == 6.2308
    assert res["significant_at_alpha"] is True
    assert res["decision"] == "SIGNIFICANT_IMPROVEMENT"
    assert res["baseline_pass_rate"] == 0.74
    assert res["candidate_pass_rate"] == 0.92


def test_five_layer_ablation_waterfall_and_stratified_golden_suite() -> None:
    """Proves 20-case golden suite loads across 4 slices and 5-layer waterfall attributes
    failures.
    """
    suite = load_golden_eval_suite()
    assert len(suite) == 20
    slices = {row["slice"] for row in suite}
    assert slices == {
        "TYPICAL_HAPPY_PATH",
        "BOUNDARY_AMBIGUOUS_ABSTENTION",
        "ADVERSARIAL_RED_TEAM",
        "MULTI_STEP_3LO_RBAC",
    }

    traces = [
        # Passing case
        TraceAblationRecord(
            eval_id="GOLD-01",
            slice_name="TYPICAL_HAPPY_PATH",
            expected_http=200,
            actual_http=200,
            expected_decision="ESCALATE_OCC_REGULATORY",
            actual_decision="ESCALATE_OCC_REGULATORY",
            retrieval_score=0.94,
        ),
        # Stage 2 Retrieval / Score-floor abstention failure (score 0.32 < 0.65 but model answered
        # instead of abstaining)
        TraceAblationRecord(
            eval_id="GOLD-06",
            slice_name="BOUNDARY_AMBIGUOUS_ABSTENTION",
            expected_http=200,
            actual_http=200,
            expected_decision="ABSTAIN_INSUFFICIENT_EVIDENCE",
            actual_decision="REMEDIATE_STANDARD",
            retrieval_score=0.32,
        ),
        # Stage 4 Claim grounding failure (hallucinated number)
        TraceAblationRecord(
            eval_id="GOLD-03",
            slice_name="TYPICAL_HAPPY_PATH",
            expected_http=200,
            actual_http=200,
            expected_decision="REMEDIATE_STANDARD",
            actual_decision="REMEDIATE_STANDARD",
            retrieval_score=0.92,
            unverified_claims_count=1,
        ),
        # Stage 5 Egress NLC false block on compliant negated statement
        TraceAblationRecord(
            eval_id="GOLD-08",
            slice_name="BOUNDARY_AMBIGUOUS_ABSTENTION",
            expected_http=200,
            actual_http=403,
            expected_decision="ESCALATE_OCC_REGULATORY",
            actual_decision="BLOCKED_POLICY",
            retrieval_score=0.89,
            egress_nlc_mismatch=True,
        ),
    ]
    report = run_five_layer_ablation_waterfall(traces)
    assert report["total_cases"] == 4
    assert report["passed_cases"] == 1
    assert report["failed_cases"] == 3
    assert report["stage_counts"]["L2_RETRIEVAL_OR_CONTEXT_PACKING"] == 1
    assert report["stage_counts"]["L4_CLAIM_GROUNDING_OR_GENERATION"] == 1
    assert report["stage_counts"]["L5_EGRESS_DLP_OR_NLC_GUARDRAIL"] == 1


def test_sandbox_error_taxonomy_confusion_matrix_and_ablation_attribution() -> (
    None
):
    """Proves sandbox errors classify cleanly and attribute across ablation layers + confusion
    matrix.
    """
    # 1. Pipeline error taxonomy for SandboxUnavailableError vs syntax/input ValueError vs PEP 403
    unavail = classify_pipeline_error(
        SandboxUnavailableError("Gemini pool exhausted")
    )
    assert unavail.category == "TRANSIENT_INFRA"
    assert unavail.retryable is True
    assert unavail.allow_llm_self_correction is False

    syntax_err = classify_pipeline_error(
        ValueError("E_SANDBOX_SYNTAX_ERROR: bad syntax")
    )
    assert syntax_err.category == "SCHEMA_OR_CITATION_DRIFT"
    assert syntax_err.retryable is True
    assert syntax_err.max_retries == 1
    assert syntax_err.allow_llm_self_correction is True

    empty_err = classify_pipeline_error(
        ValueError("E_SANDBOX_EMPTY_CODE: empty")
    )
    assert empty_err.category == "SCHEMA_OR_CITATION_DRIFT"

    cred_err = classify_pipeline_error(
        PermissionError("403 Forbidden: E_SANDBOX_CREDENTIAL_INJECTION_BLOCKED")
    )
    assert cred_err.category == "TERMINAL_POLICY_VIOLATION"
    assert cred_err.allow_llm_self_correction is False

    # 2. DecomposedJudgeVerdict dimension aliases
    verdict = DecomposedJudgeVerdict(
        evidence_spans=["INC-FV-1001"],
        reasoning_trace="All 4 binary dimensions verified against tool outputs.",
        check_1_tenant_isolation=True,
        check_2_factual_grounding=True,
        check_3_runbook_compliance=False,
        check_4_pii_and_nlc_safety=True,
    )
    assert verdict.tenant_policy_safety is True
    assert verdict.faithfulness is True
    assert verdict.tool_grounding is False
    assert verdict.nlc_compliance is True
    assert verdict.overall_pass is False

    # 3. Confusion matrix calculation (including non-security exclusion)
    cm = compute_security_confusion_matrix(
        [
            {"ground_truth_adversarial": True, "predicted_blocked": True},
            {"ground_truth_adversarial": True, "predicted_blocked": False},
            {"ground_truth_adversarial": False, "predicted_blocked": False},
            {"ground_truth_adversarial": False, "predicted_blocked": True},
            {
                "ground_truth_adversarial": False,
                "predicted_blocked": False,
                "exclude_from_security_cm": True,
            },
        ]
    )
    assert cm["evaluated_total"] == 4
    assert cm["excluded_non_security_cases"] == 1
    assert (cm["tp"], cm["tn"], cm["fp"], cm["fn"]) == (1, 1, 1, 1)
    assert cm["fp_rate"] == 0.5
    assert cm["fnr"] == 0.5
    assert cm["refusal_accuracy"] == 0.5

    # 4. Sandbox ablation attribution (missing tool, syntax/503, exit code mismatch, policy block)
    missing_tool = TraceAblationRecord(
        eval_id="SBX-T1",
        slice_name="SANDBOX",
        expected_http=200,
        actual_http=200,
        expected_decision="REMEDIATE_STANDARD",
        actual_decision="REMEDIATE_STANDARD",
        retrieval_score=0.95,
        expected_tool="execute_diagnostic_sandbox",
        actual_tool=None,
        sandbox_invoked=True,
    )
    assert (
        attribute_failure_stage(missing_tool)
        == "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"
    )

    syntax_fail = TraceAblationRecord(
        eval_id="SBX-T2",
        slice_name="SANDBOX",
        expected_http=200,
        actual_http=422,
        expected_decision="REMEDIATE_STANDARD",
        actual_decision="SCHEMA_ERROR",
        retrieval_score=0.95,
        sandbox_invoked=True,
        sandbox_error_code="E_SANDBOX_INVALID_CODE",
    )
    assert (
        attribute_failure_stage(syntax_fail)
        == "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"
    )

    exit_mismatch = TraceAblationRecord(
        eval_id="SBX-T3",
        slice_name="SANDBOX",
        expected_http=200,
        actual_http=200,
        expected_decision="REMEDIATE_STANDARD",
        actual_decision="REMEDIATE_STANDARD",
        retrieval_score=0.95,
        sandbox_invoked=True,
        expected_sandbox_exit_code=0,
        actual_sandbox_exit_code=1,
    )
    assert (
        attribute_failure_stage(exit_mismatch)
        == "L3_TOOL_SCHEMA_OR_3LO_EXECUTION"
    )

    sbx_suite = load_sandbox_behavioral_eval_suite()
    assert len(sbx_suite) >= 33
    assert {
        "BENIGN_SANDBOX_EXECUTION",
        "BENIGN_NEAR_BOUNDARY",
        "ADVERSARIAL_SANDBOX_RBAC_SCOPE",
        "ADVERSARIAL_CREDENTIAL_METADATA_OBFUSCATION",
        "ADVERSARIAL_INJECTION_EGRESS_AND_TAINT",
        "SANDBOX_RUNTIME_AND_SYNTAX_ERRORS",
    }.issubset({row["slice"] for row in sbx_suite})
