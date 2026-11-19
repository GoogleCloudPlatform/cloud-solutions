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

r"""3-Tier Online Smart Sampling Funnel, Horvitz-Thompson Estimator & Net Cost-Negative FinOps.

Implements Study Guide Chapter 6 & Chapter 8 production monitoring architecture:
- Tier 0 (100% of turns, < 5ms inline, $0 LLM cost): Deterministic PEP, schema, citation &
  score-floor checks.
- Tier 1 (~12% of turns): Fast margin / retrieval border / loop / negative-feedback anomaly
  detector.
- Tier 2 (~2.5% of turns, async out-of-band, 0ms user latency): Stratified sampling to the
  calibrated
  LLM-as-Judge:
    * 100% (pi = 1.00) on Tier-0/Tier-1 flagged anomalies
    * 25%  (pi = 0.25) on 3LO write / regulatory escalation / sandbox execution tool calls
    * 1%   (pi = 0.01) uniform random baseline on healthy read-only turns
- Horvitz-Thompson + Rogan-Gladen Estimator (`estimate_daily_fleet_quality`): Computes unbiased
  fleet-wide true pass rate by weighting each sampled trace by $w_i = 1 / \pi_i$ and applying
  Rogan-Gladen bias correction for judge $(p, q)$.
- Net Cost-Negative FinOps Ledger (`compute_online_eval_finops_ledger`): Proves that early loop
  termination and prefix cache / routing savings exceed the cost of the 2.5% async judge fleet.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

SamplingStratum = Literal[
    "STRATUM_ANOMALY_100PCT",
    "STRATUM_WRITE_TOOL_25PCT",
    "STRATUM_HEALTHY_BASELINE_1PCT",
]

HIGH_RISK_WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "create_jira_incident",
        "create_servicenow_incident",
        "send_gmail_brief",
        "schedule_calendar_postmortem",
        "escalate_regulatory_filing",
        "execute_diagnostic_sandbox",
    }
)


@dataclass(frozen=True)
class OnlineTraceTelemetry:
    """Per-turn production telemetry evaluated by the 3-tier online smart sampling funnel."""

    trace_id: str
    tenant_id: str
    tool_name: str
    http_status: int
    retrieval_score: float
    unverified_claim_count: int = 0
    session_turn_count: int = 1
    user_feedback: Literal["none", "thumbs_down", "retry", "escalation"] = (
        "none"
    )


@dataclass(frozen=True)
class SamplingDecision:
    """Result of routing a production trace through the 3-tier online funnel."""

    trace_id: str
    tenant_id: str
    tier0_inline_anomaly: bool
    tier1_margin_anomaly: bool
    stratum: SamplingStratum
    inclusion_probability_pi: float
    sampled_for_tier2_judge: bool


def _deterministic_uniform_01(trace_id: str) -> float:
    """Maps `trace_id` deterministically to $[0, 1)$ via SHA-256 for reproducible stratified
    sampling.
    """
    digest = hashlib.sha256(trace_id.encode("utf-8")).digest()
    uint64 = int.from_bytes(digest[:8], "big")
    return uint64 / float(1 << 64)


def evaluate_online_sampling_funnel(
    trace: OnlineTraceTelemetry,
) -> SamplingDecision:
    r"""Routes a production trace through Tier 0 -> Tier 1 -> Tier 2 with stratified probability
    $\pi_i$.
    """
    tier0_anomaly = (
        trace.http_status != 200
        or trace.unverified_claim_count > 0
        or trace.retrieval_score < 0.65
        or trace.session_turn_count >= 4
    )
    tier1_anomaly = (
        0.65 <= trace.retrieval_score < 0.78
        or trace.user_feedback
        in (
            "thumbs_down",
            "retry",
            "escalation",
        )
    )

    if tier0_anomaly or tier1_anomaly:
        stratum: SamplingStratum = "STRATUM_ANOMALY_100PCT"
        pi = 1.00
        sampled = True
    elif trace.tool_name in HIGH_RISK_WRITE_TOOLS:
        stratum = "STRATUM_WRITE_TOOL_25PCT"
        pi = 0.25
        sampled = _deterministic_uniform_01(trace.trace_id) < pi
    else:
        stratum = "STRATUM_HEALTHY_BASELINE_1PCT"
        pi = 0.01
        sampled = _deterministic_uniform_01(trace.trace_id) < pi

    return SamplingDecision(
        trace_id=trace.trace_id,
        tenant_id=trace.tenant_id,
        tier0_inline_anomaly=tier0_anomaly,
        tier1_margin_anomaly=tier1_anomaly,
        stratum=stratum,
        inclusion_probability_pi=pi,
        sampled_for_tier2_judge=sampled,
    )


@dataclass(frozen=True)
class SampledJudgeObservation:
    r"""A trace evaluated by the async Tier-2 LLM judge along with its inclusion probability
    $\pi_i$.
    """

    trace_id: str
    tenant_id: str
    stratum: SamplingStratum
    inclusion_probability_pi: float
    judge_pass: int  # 1 = pass, 0 = fail


def estimate_daily_fleet_quality(
    observations: list[SampledJudgeObservation],
    *,
    judge_sensitivity_p: float = 0.92,
    judge_specificity_q: float = 0.88,
) -> dict[str, Any]:
    r"""Computes the Horvitz-Thompson inverse-probability weighted + Rogan-Gladen true pass rate.

    1. Naive sample mean $\bar{y} = \frac{1}{|S|} \sum_{i \in S} y_i$ is biased downward because
       anomalies are sampled at $\pi = 1.00$ while healthy reads are sampled at $\pi = 0.01$.
    2. Horvitz-Thompson estimator:
       $\hat{p}_{\text{HT}} = \frac{\sum_{i \in S} y_i / \pi_i}{\sum_{i \in S} 1 / \pi_i}$
    3. Rogan-Gladen correction for judge sensitivity $p$ and specificity $q$:
       $\hat{\theta}_{\text{HT, RG}} = \text{clip}((\hat{p}_{\text{HT}} + q - 1) / (p + q - 1), 0,
       1)$
    """
    if not observations:
        raise ValueError("observations must be non-empty.")
    denom_pq = judge_sensitivity_p + judge_specificity_q - 1.0
    if denom_pq <= 0.0:
        raise ValueError("Uncalibrated judge: p + q must exceed 1.0.")

    naive_obs_rate = sum(o.judge_pass for o in observations) / len(observations)
    weighted_num = sum(
        o.judge_pass / o.inclusion_probability_pi for o in observations
    )
    weighted_den = sum(1.0 / o.inclusion_probability_pi for o in observations)
    ht_observed_rate = weighted_num / weighted_den

    rg_theta = max(
        0.0,
        min(1.0, (ht_observed_rate + judge_specificity_q - 1.0) / denom_pq),
    )

    return {
        "sampled_count": len(observations),
        "effective_population_weight": round(weighted_den, 2),
        "naive_biased_sample_pass_rate": round(naive_obs_rate, 4),
        "horvitz_thompson_pass_rate": round(ht_observed_rate, 4),
        "rogan_gladen_true_pass_rate": round(rg_theta, 4),
        "sampling_bias_corrected_delta": round(rg_theta - naive_obs_rate, 4),
    }


def compute_online_eval_finops_ledger(
    *,
    daily_total_requests: int = 100_000,
    tier2_sample_rate: float = 0.025,
    judge_cost_per_eval_usd: float = 0.0004,
    prevented_runaway_loop_rate: float = 0.012,
    saved_pro_tokens_per_halted_loop: int = 12_000,
    pro_cost_per_1k_tokens_usd: float = 0.0025,
) -> dict[str, Any]:
    """Computes the daily FinOps ledger proving the 3-tier eval funnel is net cost-negative."""
    daily_tier2_evals = round(daily_total_requests * tier2_sample_rate)
    daily_judge_cost_usd = daily_tier2_evals * judge_cost_per_eval_usd

    daily_halted_loops = round(
        daily_total_requests * prevented_runaway_loop_rate
    )
    saved_per_loop_usd = (
        saved_pro_tokens_per_halted_loop / 1000.0
    ) * pro_cost_per_1k_tokens_usd
    daily_halted_loop_savings_usd = daily_halted_loops * saved_per_loop_usd

    net_daily_cost_usd = daily_judge_cost_usd - daily_halted_loop_savings_usd
    return {
        "daily_total_requests": daily_total_requests,
        "daily_tier2_evals": daily_tier2_evals,
        "tier2_sample_rate": round(tier2_sample_rate, 4),
        "daily_judge_cost_usd": round(daily_judge_cost_usd, 2),
        "daily_halted_runaway_loops": daily_halted_loops,
        "daily_halted_loop_savings_usd": round(
            daily_halted_loop_savings_usd, 2
        ),
        "net_daily_eval_cost_usd": round(net_daily_cost_usd, 2),
        "is_net_cost_negative": net_daily_cost_usd < 0.0,
    }
