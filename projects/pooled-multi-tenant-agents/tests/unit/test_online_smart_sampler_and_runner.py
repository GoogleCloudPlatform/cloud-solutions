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

"""Tests for Study Guide Ch. 6 & Ch. 8: 3-Tier Online Smart Sampler, HT+RG & AsyncEvalRunner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.async_eval_runner import AsyncEvalRunner, EvalCaseInput
from evals.online_smart_sampler import (
    OnlineTraceTelemetry,
    SampledJudgeObservation,
    compute_online_eval_finops_ledger,
    estimate_daily_fleet_quality,
    evaluate_online_sampling_funnel,
)
from scripts.run_ai_engineering_evals import run_eval_showcase


def test_three_tier_online_sampling_funnel_assigns_correct_strata_and_probabilities() -> (
    None
):
    """Proves anomalies get pi=1.00, 3LO write tools get pi=0.25, and healthy reads get pi=0.01."""
    anom = evaluate_online_sampling_funnel(
        OnlineTraceTelemetry(
            trace_id="t-anom-1",
            tenant_id="tenant-finvault-alpha",
            tool_name="query_telemetry_rls",
            http_status=200,
            retrieval_score=0.55,
        )
    )
    assert anom.tier0_inline_anomaly is True
    assert anom.stratum == "STRATUM_ANOMALY_100PCT"
    assert anom.inclusion_probability_pi == 1.00
    assert anom.sampled_for_tier2_judge is True

    write_call = evaluate_online_sampling_funnel(
        OnlineTraceTelemetry(
            trace_id="t-write-1",
            tenant_id="tenant-finvault-alpha",
            tool_name="create_jira_incident",
            http_status=200,
            retrieval_score=0.92,
        )
    )
    assert write_call.tier0_inline_anomaly is False
    assert write_call.tier1_margin_anomaly is False
    assert write_call.stratum == "STRATUM_WRITE_TOOL_25PCT"
    assert write_call.inclusion_probability_pi == 0.25

    healthy_read = evaluate_online_sampling_funnel(
        OnlineTraceTelemetry(
            trace_id="t-read-1",
            tenant_id="tenant-retailstream-beta",
            tool_name="query_telemetry_rls",
            http_status=200,
            retrieval_score=0.91,
        )
    )
    assert healthy_read.stratum == "STRATUM_HEALTHY_BASELINE_1PCT"
    assert healthy_read.inclusion_probability_pi == 0.01

    sandbox_call = evaluate_online_sampling_funnel(
        OnlineTraceTelemetry(
            trace_id="t-sandbox-1",
            tenant_id="tenant-finvault-alpha",
            tool_name="execute_diagnostic_sandbox",
            http_status=200,
            retrieval_score=0.93,
        )
    )
    assert sandbox_call.tier0_inline_anomaly is False
    assert sandbox_call.tier1_margin_anomaly is False
    assert sandbox_call.stratum == "STRATUM_WRITE_TOOL_25PCT"
    assert sandbox_call.inclusion_probability_pi == 0.25

    blocked_sandbox = evaluate_online_sampling_funnel(
        OnlineTraceTelemetry(
            trace_id="t-sandbox-403",
            tenant_id="tenant-finvault-alpha",
            tool_name="execute_diagnostic_sandbox",
            http_status=403,
            retrieval_score=0.0,
        )
    )
    assert blocked_sandbox.stratum == "STRATUM_ANOMALY_100PCT"
    assert blocked_sandbox.inclusion_probability_pi == 1.00
    assert blocked_sandbox.sampled_for_tier2_judge is True


def test_horvitz_thompson_and_rogan_gladen_correct_non_uniform_sampling_bias() -> (
    None
):
    """Proves inverse-probability weighting + Rogan-Gladen recovers true fleet quality."""
    obs = [
        # 10 anomalies sampled at 100% (pi=1.0): all 10 fail (judge_pass=0)
        *[
            SampledJudgeObservation(
                trace_id=f"a-{i}",
                tenant_id="tenant-finvault-alpha",
                stratum="STRATUM_ANOMALY_100PCT",
                inclusion_probability_pi=1.00,
                judge_pass=0,
            )
            for i in range(10)
        ],
        # 10 healthy baseline traces sampled at 1% (pi=0.01, representing 1,000 turns): 9 pass
        *[
            SampledJudgeObservation(
                trace_id=f"h-{i}",
                tenant_id="tenant-retailstream-beta",
                stratum="STRATUM_HEALTHY_BASELINE_1PCT",
                inclusion_probability_pi=0.01,
                judge_pass=1 if i < 9 else 0,
            )
            for i in range(10)
        ],
    ]
    res = estimate_daily_fleet_quality(
        obs, judge_sensitivity_p=0.90, judge_specificity_q=0.90
    )
    # Naive unweighted sample pass rate is 9 / 20 = 0.45 (severely biased downward by 100% anomaly
    # sampling!)
    assert res["naive_biased_sample_pass_rate"] == 0.45
    # Horvitz-Thompson weights the 10 healthy traces by 1/0.01 = 100 each (total weight 1010):
    # HT pass rate = 900 / 1010 = 0.8911
    assert res["horvitz_thompson_pass_rate"] == 0.8911
    # Rogan-Gladen with p=0.90, q=0.90: (0.8911 + 0.90 - 1) / 0.80 = 0.9889
    assert res["rogan_gladen_true_pass_rate"] == 0.9889

    ledger = compute_online_eval_finops_ledger()
    assert ledger["is_net_cost_negative"] is True
    assert ledger["net_daily_eval_cost_usd"] < 0.0


async def test_async_eval_runner_semaphore_sha256_cache_and_jsonl_checkpoint_resume(
    tmp_path: Path,
) -> None:
    """Proves bounded concurrency, transient retry backoff, terminal halt, and JSONL resume."""
    ckpt_file = tmp_path / "eval_checkpoint.jsonl"
    cases = [
        EvalCaseInput(
            case_id="C-01",
            tenant_id="tenant-finvault-alpha",
            prompt="Wire latency > 4500ms",
            expected_decision="ESCALATE_OCC_REGULATORY",
        ),
        EvalCaseInput(
            case_id="C-02",
            tenant_id="tenant-retailstream-beta",
            prompt="Transient flaky call",
            expected_decision="REMEDIATE_STANDARD",
        ),
        EvalCaseInput(
            case_id="C-03",
            tenant_id="tenant-retailstream-beta",
            prompt="Adversarial jailbreak",
            expected_decision="BLOCKED_POLICY",
        ),
    ]

    flaky_attempts = 0

    async def _evaluator(c: EvalCaseInput) -> dict[str, Any]:
        nonlocal flaky_attempts
        if c.case_id == "C-02":
            flaky_attempts += 1
            if flaky_attempts == 1:
                raise TimeoutError("Simulated transient 503 timeout")
            return {"decision": "REMEDIATE_STANDARD"}
        if c.case_id == "C-03":
            raise PermissionError("403 E_MODEL_ARMOR_BLOCKED")
        return {"decision": "ESCALATE_OCC_REGULATORY"}

    runner1 = AsyncEvalRunner(max_concurrency=2, checkpoint_path=ckpt_file)
    rep1 = await runner1.run_suite(cases, _evaluator)
    assert rep1["passed_cases"] == 3
    assert rep1["cache_hits"] == 0
    assert ckpt_file.is_file()

    # New runner instance pointed at the same checkpoint file must serve all 3 from cache (0 live
    # calls!)
    runner2 = AsyncEvalRunner(max_concurrency=2, checkpoint_path=ckpt_file)
    rep2 = await runner2.run_suite(cases, _evaluator)
    assert rep2["passed_cases"] == 3
    assert rep2["cache_hits"] == 3
    assert rep2["live_evaluations"] == 0

    showcase = await run_eval_showcase()
    assert showcase["status"] == "PASS"
    assert (
        showcase["execution_mode"]
        == "REAL_HERMETIC_GATEWAY_AND_SANDBOX_PIPELINE"
    )
    assert showcase["empirical_golden_suite"]["total_cases"] == 20
    assert showcase["empirical_golden_suite"]["passed_cases"] == 20
    assert showcase["empirical_sandbox_suite"]["total_cases"] == 33
    assert showcase["empirical_sandbox_suite"]["passed_cases"] == 33
    cm = showcase["empirical_confusion_matrix"]
    assert cm["tp"] >= 25
    assert cm["tn"] >= 27
    assert cm["fp"] == 0
    assert cm["fn"] == 0
    assert cm["fp_rate"] == 0.0
    assert cm["fnr"] == 0.0
    assert cm["refusal_accuracy"] == 1.0
    waterfall = showcase["empirical_ablation_waterfall"]
    assert waterfall["passed_cases"] == 53
    assert waterfall["sandbox_summary"]["total_sandbox_traces"] >= 33
    assert (
        showcase["empirical_verifier_telemetry"]["all_grounded_passed"] is True
    )
    cal = showcase["empirical_judge_calibration"]
    assert cal["n_gold_examples"] >= 52
    assert cal["tp"] >= 27
    assert cal["tn"] >= 25
    assert cal["fp"] == 0
    assert cal["fn"] == 0
    assert cal["sensitivity_p"] == 1.0
    assert cal["specificity_q"] == 1.0
    assert cal["cohens_kappa"] >= 0.70
    assert cal["calibrated"] is True
    assert (
        showcase["modeled_finops_projection"]["is_modeled_projection"] is True
    )
    assert showcase["async_runner_first_run"]["pass_rate"] == 1.0
    assert (
        showcase["async_runner_second_run_cached"]["cache_hits"]
        == showcase["async_runner_first_run"]["total_cases"]
    )
