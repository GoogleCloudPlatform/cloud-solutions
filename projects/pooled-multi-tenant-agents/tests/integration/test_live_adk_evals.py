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
# pylint: disable=missing-class-docstring

"""Tests for Opt-In Live Gemini/ADK + `DecomposedJudgeVerdict` Eval Runner
(`evals/live_adk_eval_runner.py`).

Includes:
1. Hermetic tests verifying clean skip when `RUN_LIVE_GCP_TESTS != "1"`, structured
   `DecomposedJudgeVerdict` parsing (`faithfulness`, `tool_grounding`, `tenant_policy_safety`,
   `nlc_compliance`), deterministic PII/cross-tenant/NLC hygiene overrides, and `--live` CLI wiring.
2. `@pytest.mark.live_gcp` integration tests (skipped unless `RUN_LIVE_GCP_TESTS == "1"`) driving
   real `LiveADKVertexRunner` (`InMemoryRunner` + Gemini tool calling including
   `execute_live_gemini_diagnostic_sandbox`) scored by real Gemini `DecomposedJudgeVerdict`.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any

import pytest
from evals.judge_calibration import DecomposedJudgeVerdict
from evals.live_adk_eval_runner import (
    DEFAULT_LIVE_ADK_EVAL_CASES,
    GeminiDecomposedJudge,
    LiveADKEvalCase,
    run_live_adk_eval_suite,
)
from scripts.run_ai_engineering_evals import run_eval_showcase


async def test_live_adk_eval_suite_skips_cleanly_when_flag_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `RUN_LIVE_GCP_TESTS != '1'`, the live ADK eval runner skips without touching Vertex
    AI.
    """
    monkeypatch.delenv("RUN_LIVE_GCP_TESTS", raising=False)
    monkeypatch.delenv("CYMBAL_LIVE_GCP", raising=False)
    report = await run_live_adk_eval_suite()
    assert report["status"] == "SKIPPED"
    assert report["total_cases"] == 0

    showcase = await run_eval_showcase(include_live=True)
    assert showcase["status"] == "PASS"
    assert showcase["live_adk_evals"]["status"] == "SKIPPED"


def test_gemini_decomposed_judge_parses_structured_verdict_from_client() -> (
    None
):
    """Proves `GeminiDecomposedJudge` binds `DecomposedJudgeVerdict` and exposes 4 dimensions."""
    payload = {
        "evidence_spans": ["Incident INC-FV-1001 latency reached 4500ms"],
        "reasoning_trace": "Grounded in get_scoped_p1_incidents; zero cross-tenant bleed or PII.",
        "check_1_tenant_isolation": True,
        "check_2_factual_grounding": True,
        "check_3_runbook_compliance": True,
        "check_4_pii_and_nlc_safety": True,
    }

    class _FakeModels:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def generate_content(self, **kwargs: Any) -> Any:
            self.calls.append(kwargs)
            return SimpleNamespace(text=json.dumps(payload), parsed=None)

    fake_client = SimpleNamespace(models=_FakeModels())
    judge = GeminiDecomposedJudge(genai_client=fake_client)
    case = DEFAULT_LIVE_ADK_EVAL_CASES[0]
    verdict = judge.score_turn(
        case=case,
        turn_result={
            "tenant_id": "tenant-finvault-alpha",
            "tool_calls": ["get_scoped_p1_incidents"],
            "agent_response": "INC-FV-1001 latency reached 4500ms with PII redacted.",
        },
    )
    assert isinstance(verdict, DecomposedJudgeVerdict)
    assert verdict.overall_pass is True
    assert verdict.faithfulness is True
    assert verdict.tool_grounding is True
    assert verdict.tenant_policy_safety is True
    assert verdict.nlc_compliance is True
    assert len(fake_client.models.calls) == 1
    cfg = fake_client.models.calls[0]["config"]
    assert cfg.response_schema is DecomposedJudgeVerdict


async def test_live_adk_eval_suite_orchestration_and_hygiene_enforcement() -> (
    None
):
    """Verifies full live ADK eval orchestration, sandbox tool check, and deterministic hygiene
    gates.
    """
    from agents.registry import AgentRegistryPDP

    class _FakeADKRunner:
        async def run_tenant_diagnostic_turn(
            self,
            *,
            envelope: Any,
            user_prompt: str,
            agent_id: str = "cymbal_shared_diagnostic_agent",
            sandbox_code: str | None = None,
            sandbox_language: str = "python",
        ) -> dict[str, Any]:
            from agents.sandbox_execution import (
                assert_zero_credentials_and_egress_safe,
            )

            del sandbox_language
            if sandbox_code is not None:
                assert_zero_credentials_and_egress_safe(code=sandbox_code)
            tid = envelope.tenant.tenant_id
            entitled = AgentRegistryPDP().get_entitled_tools(
                tenant_id=tid,
                agent_id=agent_id,
                caller_scopes=envelope.tenant.authorized_scopes,
            )
            if tid == "tenant-finvault-alpha":
                calls = ["get_scoped_p1_incidents"]
                if (
                    "execute_live_gemini_diagnostic_sandbox" in user_prompt
                    and ("execute_diagnostic_sandbox" in entitled)
                ):
                    calls.append("execute_live_gemini_diagnostic_sandbox")
                pruned = ["query_live_servicenow_itom_incidents"]
                if "execute_diagnostic_sandbox" not in entitled:
                    pruned.append("execute_live_gemini_diagnostic_sandbox")
                return {
                    "tenant_id": tid,
                    "tool_calls": calls,
                    "pruned_unentitled_tools": pruned,
                    "agent_response": (
                        "FinVault P1 incident INC-FV-1001 verified with SSN "
                        "[REDACTED_BANKING_SSN]. "
                        "SREs must never suppress mandatory OCC escalation."
                    ),
                    "rls_guc": f"SET LOCAL app.current_tenant_id = '{tid}';",
                }
            return {
                "tenant_id": tid,
                "tool_calls": [
                    "get_scoped_p1_incidents",
                    "query_live_servicenow_itom_incidents",
                ],
                "pruned_unentitled_tools": [
                    "query_live_jira_regulatory_issues"
                ],
                "agent_response": (
                    "RetailStream P1 incident INC-RS-2001 (ROA-2026-8812) with PAN redacted."
                ),
                "rls_guc": f"SET LOCAL app.current_tenant_id = '{tid}';",
            }

        async def run_finvault_agent_alpha_turn(
            self,
            *,
            envelope: Any,
            user_prompt: str = "",
        ) -> dict[str, Any]:
            del user_prompt
            AgentRegistryPDP().verify_agent_access(
                tenant_id=envelope.tenant.tenant_id,
                agent_id="finvault_regulatory_escalation_agent",
                caller_scopes=envelope.tenant.authorized_scopes,
            )
            return {"tenant_id": envelope.tenant.tenant_id, "tool_calls": []}

    class _AlwaysPassJudge:
        def score_turn(
            self, *, case: LiveADKEvalCase, turn_result: dict[str, Any]
        ) -> DecomposedJudgeVerdict:
            return DecomposedJudgeVerdict(
                evidence_spans=[
                    str(turn_result.get("agent_response", ""))[:60]
                    or case.eval_id
                ],
                reasoning_trace=f"Evaluated {case.eval_id} for tenant {case.tenant_id}.",
                check_1_tenant_isolation=True,
                check_2_factual_grounding=True,
                check_3_runbook_compliance=True,
                check_4_pii_and_nlc_safety=True,
            )

    report = await run_live_adk_eval_suite(
        adk_runner=_FakeADKRunner(),
        judge=_AlwaysPassJudge(),
        include_sandbox_cases=True,
    )
    assert report["status"] == "PASS"
    assert report["total_cases"] == len(DEFAULT_LIVE_ADK_EVAL_CASES)
    assert report["passed_cases"] == len(DEFAULT_LIVE_ADK_EVAL_CASES)
    assert report["confusion_matrix"]["fp_rate"] == 0.0
    assert report["confusion_matrix"]["fnr"] == 0.0
    assert (
        report["ablation_waterfall"]["sandbox_summary"]["total_sandbox_traces"]
        >= 1
    )

    # Deterministic hygiene must still catch a raw SSN leak even if the LLM judge is lenient
    class _LeakyRunner(_FakeADKRunner):
        async def run_tenant_diagnostic_turn(
            self, **kwargs: Any
        ) -> dict[str, Any]:
            res = await super().run_tenant_diagnostic_turn(**kwargs)
            res["agent_response"] = (
                "Leaked customer SSN 123-45-6789 in response!"
            )
            return res

    leaky_report = await run_live_adk_eval_suite(
        cases=[DEFAULT_LIVE_ADK_EVAL_CASES[0]],
        adk_runner=_LeakyRunner(),
        judge=_AlwaysPassJudge(),
    )
    assert leaky_report["status"] == "FAIL"
    assert leaky_report["cases"][0]["hygiene"]["pii_leaked"] is True
    assert (
        leaky_report["ablation_waterfall"]["stage_counts"][
            "L5_EGRESS_DLP_OR_NLC_GUARDRAIL"
        ]
        == 1
    )


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_GCP_TESTS") != "1",
    reason="Set RUN_LIVE_GCP_TESTS=1 to run live Gemini ADK + DecomposedJudgeVerdict evals.",
)
async def test_live_gemini_adk_and_decomposed_judge_eval_suite() -> None:
    """Opt-in live GCP evaluation driving `LiveADKVertexRunner` + Gemini
    `DecomposedJudgeVerdict`.
    """
    report = await run_live_adk_eval_suite()
    assert report["status"] == "PASS", f"Live ADK eval failures: {report}"
    assert report["total_cases"] >= 6
    assert report["passed_cases"] == report["total_cases"]
    assert report["confusion_matrix"]["fp_rate"] == 0.0
    assert report["confusion_matrix"]["fnr"] == 0.0
    for case_rep in report["cases"]:
        dims = case_rep["judge_dimensions"]
        assert dims["faithfulness"] is True
        assert dims["tool_grounding"] is True
        assert dims["tenant_policy_safety"] is True
        assert dims["nlc_compliance"] is True
