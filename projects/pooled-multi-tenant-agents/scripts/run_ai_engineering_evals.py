#!/usr/bin/env python3
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

# pylint: disable=inconsistent-quotes,line-too-long,protected-access
# pylint: disable=redefined-outer-name,wrong-import-position

"""CLI Runner for Empirical Multi-Tenant & Agent Sandbox Behavioral Evals & Smart Sampling.

Executes BOTH `evals/datasets/golden_eval_suite.jsonl` and
`evals/datasets/sandbox_behavioral_eval.jsonl` end-to-end against the real FastAPI 5-Hop
Gateway (`TestClient(app)` on `/api/v1/invoke-agent` and `/mcp/v1/jsonrpc`) and
`GeminiAgentSandboxManager`, verifies post-generation claims with
`verify_agent_output_deterministically()`, and computes:
  - Empirical Confusion Matrix (`tp`, `tn`, `fp`, `fn`, `fp_rate`, `fnr`, `precision`, `recall`,
    `refusal_accuracy`)
  - Empirical 5-Layer Failure Ablation Waterfall (`run_five_layer_ablation_waterfall`)
  - 3-Tier Online Smart Sampling Funnel + Horvitz-Thompson / Rogan-Gladen Fleet Quality
  - AsyncEvalRunner SHA-256 cache verification on real evaluated cases
  - Clearly separated Modeled 100k req/day FinOps Projection (`is_modeled_projection=True`)
  - Optional `--live` Opt-In Live Gemini ADK + `DecomposedJudgeVerdict` evaluation

Usage:
  uv run python scripts/run_ai_engineering_evals.py
  uv run python scripts/run_ai_engineering_evals.py --json
  RUN_LIVE_GCP_TESTS=1 uv run python scripts/run_ai_engineering_evals.py --live --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.context_signing import enable_offline_local_signer

if "pytest" not in sys.modules and not os.getenv("K_SERVICE"):
    # Offline harness: context tokens are signed by a per-process local key (never on Cloud Run).
    enable_offline_local_signer()

from agents import context as agent_context
from agents import sandbox_execution
from app import main as gateway_main
from evals.ablation_runner import (
    TraceAblationRecord,
    load_golden_eval_suite,
    load_sandbox_behavioral_eval_suite,
    run_five_layer_ablation_waterfall,
)
from evals.async_eval_runner import AsyncEvalRunner, EvalCaseInput
from evals.contracts import CitationSpan, DiagnosticAgentOutputContract
from evals.deterministic_verifier import (
    ContextChunk,
    pack_tenant_context_chunks,
    verify_agent_output_deterministically,
)
from evals.judge_calibration import (
    calibrate_judge_against_human,
    compute_security_confusion_matrix,
)
from evals.live_adk_eval_runner import run_live_adk_eval_suite
from evals.online_smart_sampler import (
    OnlineTraceTelemetry,
    SampledJudgeObservation,
    compute_online_eval_finops_ledger,
    estimate_daily_fleet_quality,
    evaluate_online_sampling_funnel,
)
from fastapi.testclient import TestClient
from mcp_server import server as mcp_tools
from scripts.run_verifiable_batch_audit import contains_unredacted_pii
from scripts.sandbox_auth import SandboxCaller

_ROLE_SUB_DEFAULTS: dict[tuple[str, str], str] = {
    ("tenant-finvault-alpha", "sre_admin"): "alice@finvault.com",
    ("tenant-finvault-alpha", "read_only_analyst"): "dave@finvault.com",
    ("tenant-finvault-alpha", "compliance_officer"): "carol@finvault.com",
    ("tenant-retailstream-beta", "sre_admin"): "bob@retailstream.com",
    (
        "tenant-retailstream-beta",
        "read_only_analyst",
    ): "charlie@retailstream.com",
}


def _sub_for(tenant_id: str, user_role: str) -> str:
    return _ROLE_SUB_DEFAULTS.get(
        (tenant_id, user_role),
        (
            f"{user_role}@finvault.com"
            if tenant_id == "tenant-finvault-alpha"
            else f"{user_role}@retailstream.com"
        ),
    )


def _mint_direct_envelope(
    *,
    tenant_id: str,
    user_sub: str,
    user_role: str,
    extra_scopes: list[str] | None = None,
) -> agent_context.ContextEnvelope:
    meta = agent_context.TENANT_DIRECTORY[tenant_id]
    env = agent_context.EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims={
            "iss": str(meta["iss"]),
            "sub": user_sub,
            "tenant_id": tenant_id,
            "user_role": user_role,
            "exp": int(time.time()) + 3600,
            "jti": f"jwt-eval-{uuid.uuid4().hex[:10]}",
        },
        dpop_proof={
            "jkt": f"jkt-eval-{tenant_id}",
            "jti": f"dpop-eval-{uuid.uuid4().hex}",
        },
        session_id=f"sess-eval-{uuid.uuid4().hex[:8]}",
    )
    if not extra_scopes:
        return env
    merged_scopes = tuple(
        dict.fromkeys((*env.tenant.authorized_scopes, *extra_scopes))
    )
    return agent_context.ContextEnvelope(
        security=env.security,
        tenant=agent_context.TenantContext(
            tenant_id=env.tenant.tenant_id,
            subscription_tier=env.tenant.subscription_tier,
            org_unit=env.tenant.org_unit,
            authorized_scopes=merged_scopes,
            thinking_token_budget=env.tenant.thinking_token_budget,
            cmek_key_name=env.tenant.cmek_key_name,
        ),
        request=env.request,
        context_token=env.context_token,
        delegation_sig=env.delegation_sig,
    )


def _build_chunks_from_turn_output(
    *,
    case: Mapping[str, Any],
    tool_output: Any,
    sandbox_execution: Mapping[str, Any] | None,
) -> list[ContextChunk]:
    """Converts real `/api/v1/invoke-agent` tool & sandbox output into `ContextChunk` records."""
    tenant_id = str(case["tenant_id"])
    score = float(case.get("retrieval_score", 0.90))
    chunks: list[ContextChunk] = []

    if isinstance(tool_output, Mapping):
        incidents = tool_output.get("incidents")
        if isinstance(incidents, list) and incidents:
            for inc in incidents:
                if isinstance(inc, Mapping):
                    inc_id = str(inc.get("incident_id", "INC-UNKNOWN"))
                    content = (
                        "Incident "
                        f"{inc_id}"
                        ": "
                        f"{inc.get('service_name', '')}"
                        " "
                        f"{inc.get('summary', '')}"
                        " "
                        f"Notes: {inc.get('pii_notes', '')}"
                    ).strip()
                    chunks.append(
                        ContextChunk(
                            doc_id=inc_id,
                            tenant_id=str(inc.get("tenant_id", tenant_id)),
                            score=score,
                            updated_at="2026-10-30T00:00:00Z",
                            content=content,
                            token_count=max(16, len(content) // 4),
                        )
                    )

        runbooks = tool_output.get("runbooks")
        if isinstance(runbooks, list) and runbooks:
            for rb in runbooks:
                if isinstance(rb, Mapping):
                    rb_id = str(rb.get("runbook_id", "RB-UNKNOWN"))
                    content = (
                        f"Runbook {rb_id}: {rb.get('title', '')}. "
                        f"Steps: {rb.get('remediation_steps', '')}"
                    ).strip()
                    chunks.append(
                        ContextChunk(
                            doc_id=rb_id,
                            tenant_id=str(rb.get("tenant_id", tenant_id)),
                            score=score,
                            updated_at="2026-10-30T00:00:00Z",
                            content=content,
                            token_count=max(16, len(content) // 4),
                        )
                    )

        if not chunks:
            doc_id = str(
                tool_output.get("ticket_key")
                or tool_output.get("incident_number")
                or tool_output.get("incident_id")
                or tool_output.get("site_path")
                or (
                    sandbox_execution.get("sandbox_id")
                    if sandbox_execution
                    else None
                )
                or case.get("eval_id", "TOOL-OUTPUT")
            )
            content = json.dumps(
                {
                    "tool_output": tool_output,
                    "sandbox_execution": (
                        dict(sandbox_execution) if sandbox_execution else None
                    ),
                },
                sort_keys=True,
                default=str,
            )
            chunks.append(
                ContextChunk(
                    doc_id=str(doc_id),
                    tenant_id=tenant_id,
                    score=score,
                    updated_at="2026-10-30T00:00:00Z",
                    content=content,
                    token_count=max(16, len(content) // 4),
                )
            )
    elif sandbox_execution:
        doc_id = str(
            sandbox_execution.get("sandbox_id", case.get("eval_id", "SBX-OUT"))
        )
        content = json.dumps(
            dict(sandbox_execution), sort_keys=True, default=str
        )
        chunks.append(
            ContextChunk(
                doc_id=doc_id,
                tenant_id=tenant_id,
                score=score,
                updated_at="2026-10-30T00:00:00Z",
                content=content,
                token_count=max(16, len(content) // 4),
            )
        )

    return chunks


def _infer_decision_from_turn(
    *,
    case: Mapping[str, Any],
    actual_http: int,
    packed: Mapping[str, Any],
    tool_output: Any,
) -> str:
    if actual_http == 422:
        return "SCHEMA_ERROR"
    if actual_http != 200:
        return "BLOCKED_POLICY"
    if packed["abstain"]:
        return "ABSTAIN_INSUFFICIENT_EVIDENCE"
    tool_name = str(case.get("tool_name", ""))
    prompt_lower = str(case.get("prompt", "")).lower()
    out_lower = json.dumps(tool_output, default=str).lower()
    if (
        tool_name == "escalate_regulatory_filing"
        or "occ" in prompt_lower
        or "17a-4" in prompt_lower
        or "occ" in out_lower
        or (
            tool_name == "query_telemetry_rls"
            and case.get("tenant_id") == "tenant-finvault-alpha"
        )
    ):
        return "ESCALATE_OCC_REGULATORY"
    return "REMEDIATE_STANDARD"


def _verify_turn_contract(
    *,
    case: Mapping[str, Any],
    actual_http: int,
    tool_output: Any,
    sandbox_execution: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Packs real tool/sandbox output chunks and verifies a `DiagnosticAgentOutputContract`."""
    if actual_http != 200:
        return {
            "actual_decision": (
                "SCHEMA_ERROR" if actual_http == 422 else "BLOCKED_POLICY"
            ),
            "verifier_passed": True,
            "verifier_latency_ms": 0.0,
            "unverified_claims_count": 0,
            "missing_citations_count": 0,
            "foreign_chunk_retrieved": False,
            "pii_leaked_in_verifier": False,
            "negation_contradiction": False,
        }

    tenant_id = str(case["tenant_id"])
    chunks = _build_chunks_from_turn_output(
        case=case,
        tool_output=tool_output,
        sandbox_execution=sandbox_execution,
    )
    packed = pack_tenant_context_chunks(
        chunks,
        caller_tenant_id=tenant_id,
        min_score_floor=0.65,
    )
    decision = _infer_decision_from_turn(
        case=case,
        actual_http=actual_http,
        packed=packed,
        tool_output=tool_output,
    )
    if decision == "ABSTAIN_INSUFFICIENT_EVIDENCE":
        contract = DiagnosticAgentOutputContract(
            evidence_summary=(
                "Retrieved evidence fell below minimum score floor; abstaining cleanly."
            ),
            citations=[],
            decision="ABSTAIN_INSUFFICIENT_EVIDENCE",
            recommended_actions=[],
            tenant_id=tenant_id,
        )
        source_chunks: list[ContextChunk] = chunks
    else:
        top_chunk: ContextChunk = packed["packed_chunks"][0]
        span = top_chunk.content[:140]
        if len(span) < 5:
            span = top_chunk.content.ljust(5)
        contract = DiagnosticAgentOutputContract(
            evidence_summary=f"Grounded in {top_chunk.doc_id}: {span}",
            citations=[
                CitationSpan(
                    source_id=top_chunk.doc_id,
                    tenant_id=tenant_id,
                    quoted_span=span,
                    numeric_claims=[],
                )
            ],
            decision=decision,  # type: ignore[arg-type]
            recommended_actions=[
                "Proceed with tenant-entitled diagnostic remediation."
            ],
            tenant_id=tenant_id,
        )
        source_chunks = packed["packed_chunks"]

    contract.validate_citations_for_decision()
    ver = verify_agent_output_deterministically(
        contract,
        source_chunks=source_chunks,
        caller_tenant_id=tenant_id,
    )
    return {
        "actual_decision": decision,
        "verifier_passed": ver.passed,
        "verifier_latency_ms": ver.latency_ms,
        "unverified_claims_count": len(ver.unverified_numbers),
        "missing_citations_count": len(ver.missing_citations),
        "foreign_chunk_retrieved": bool(ver.cross_tenant_citations)
        or int(packed["foreign_dropped"]) > 0,
        "pii_leaked_in_verifier": bool(ver.pii_leaks),
        "negation_contradiction": bool(ver.negation_contradictions),
    }


def _check_response_hygiene(
    *, tenant_id: str, payload: Any
) -> tuple[bool, bool]:
    payload_str = json.dumps(payload, default=str)
    pii_leaked = contains_unredacted_pii(payload_str)
    cross_tenant_bleed = (
        tenant_id == "tenant-finvault-alpha" and "INC-RS-" in payload_str
    ) or (tenant_id == "tenant-retailstream-beta" and "INC-FV-" in payload_str)
    return pii_leaked, cross_tenant_bleed


def _error_code_matches(
    case: Mapping[str, Any], actual_error_code: str | None
) -> bool:
    expected = case.get("expected_error_code")
    if expected is not None:
        return actual_error_code == expected
    prefixes = case.get("expected_error_code_prefixes")
    if isinstance(prefixes, list) and prefixes:
        return actual_error_code is not None and any(
            actual_error_code.startswith(str(p)) for p in prefixes
        )
    return True


def _execute_single_case(
    *,
    case: Mapping[str, Any],
    client: TestClient,
    callers: dict[tuple[str, str, str], SandboxCaller],
    suite_name: str,
) -> dict[str, Any]:
    """Executes one JSONL case (golden or sandbox behavioral) against the real gateway/manager."""
    tenant_id = str(case["tenant_id"])
    user_role = str(case.get("user_role", "sre_admin"))
    user_sub = str(case.get("user_sub") or _sub_for(tenant_id, user_role))
    agent_id = str(case.get("agent_id", "cymbal_shared_diagnostic_agent"))
    tool_name = str(case.get("tool_name", "query_telemetry_rls"))
    execution_mode = str(case.get("execution_mode", "http_invoke_agent"))

    gateway_main.TOKEN_BULKHEAD._buckets.clear()
    gateway_main.SANDBOX_MANAGER.evict_tenant(tenant_id)

    def _get_caller() -> SandboxCaller:
        key = (tenant_id, user_sub, user_role)
        if key not in callers:
            callers[key] = SandboxCaller(
                client, tenant_id=tenant_id, sub=user_sub, role=user_role
            )
        return callers[key]

    actual_http = 200
    actual_error_code: str | None = None
    actual_sandbox_exit_code: int | None = None
    sandbox_blocked = False
    sandbox_error_code: str | None = None
    actual_tool: str | None = tool_name
    tool_output: Any = None
    sandbox_exec: dict[str, Any] | None = None
    sequence_ok = True
    prescreen_zero_side_effect = True
    pii_leaked = False
    cross_tenant_bleed = False

    if execution_mode == "http_invoke_agent":
        caller = _get_caller()
        req_body: dict[str, Any] = {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "prompt": str(case["prompt"]),
            "requested_thinking_tokens": (
                8000 if tenant_id == "tenant-finvault-alpha" else 4000
            ),
        }
        if case.get("sandbox_code") is not None:
            req_body["sandbox_code"] = case["sandbox_code"]
        if case.get("sandbox_language") is not None:
            req_body["sandbox_language"] = case["sandbox_language"]
        resp = client.post(
            "/api/v1/invoke-agent",
            json=req_body,
            headers=caller.headers("POST", caller.url("/api/v1/invoke-agent")),
        )
        actual_http = resp.status_code
        body = resp.json()
        if actual_http == 200:
            tool_output = body.get("tool_output")
            raw_sbx = body.get("sandbox_execution")
            sandbox_exec = (
                dict(raw_sbx) if isinstance(raw_sbx, Mapping) else None
            )
            if sandbox_exec is not None:
                actual_sandbox_exit_code = sandbox_exec.get("exit_code")
            pii_leaked, cross_tenant_bleed = _check_response_hygiene(
                tenant_id=tenant_id,
                payload={
                    "tool_output": tool_output,
                    "sandbox_execution": sandbox_exec,
                },
            )
        else:
            actual_tool = None
            detail = body.get("detail", {})
            if isinstance(detail, Mapping):
                actual_error_code = (
                    str(detail.get("error")) if detail.get("error") else None
                )
            sandbox_blocked = actual_http in (403, 429) and (
                tool_name == "execute_diagnostic_sandbox"
                or case.get("sandbox_code") is not None
            )
            if actual_http in (422, 503):
                sandbox_error_code = actual_error_code

    elif execution_mode == "http_mcp_jsonrpc":
        caller = _get_caller()
        args: dict[str, Any] = {
            "code": case.get("sandbox_code"),
            "language": case.get("sandbox_language", "python"),
        }
        resp = client.post(
            "/mcp/v1/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args},
            },
            headers=caller.headers("POST", caller.url("/mcp/v1/jsonrpc")),
        )
        rpc_body = resp.json()
        if "error" in rpc_body:
            err = rpc_body["error"]
            err_code_num = int(err.get("code", -32003))
            actual_http = (
                401
                if err_code_num == -32001
                else (422 if err_code_num == -32602 else 403)
            )
            err_msg = str(err.get("message", ""))
            if "E_" in err_msg:
                actual_error_code = "E_" + err_msg.split("E_", 1)[1].split()[
                    0
                ].rstrip(":.,")
            sandbox_blocked = True
            actual_tool = None
            if case.get("expected_mcp_error_code") is not None:
                sequence_ok = err_code_num == int(
                    case["expected_mcp_error_code"]
                )
        else:
            actual_http = 200
            tool_output = rpc_body.get("result", {}).get("content", {})
            raw_sbx = (
                tool_output.get("sandbox_execution")
                if isinstance(tool_output, Mapping)
                else None
            )
            sandbox_exec = (
                dict(raw_sbx) if isinstance(raw_sbx, Mapping) else None
            )
            if sandbox_exec is not None:
                actual_sandbox_exit_code = sandbox_exec.get("exit_code")
            pii_leaked, cross_tenant_bleed = _check_response_hygiene(
                tenant_id=tenant_id,
                payload=tool_output,
            )

    elif execution_mode == "http_cross_language_sequence":
        caller = _get_caller()
        r1 = client.post(
            "/api/v1/invoke-agent",
            json={
                "agent_id": agent_id,
                "tool_name": tool_name,
                "sandbox_language": str(case.get("sandbox_language", "python")),
                "sandbox_code": str(case.get("sandbox_code", "print(1)")),
                "prompt": str(case["prompt"]),
            },
            headers=caller.headers("POST", caller.url("/api/v1/invoke-agent")),
        )
        r2 = client.post(
            "/api/v1/invoke-agent",
            json={
                "agent_id": agent_id,
                "tool_name": tool_name,
                "sandbox_language": str(case.get("secondary_language", "bash")),
                "sandbox_code": str(case.get("secondary_code", "echo ok")),
                "prompt": str(case["prompt"]),
            },
            headers=caller.headers("POST", caller.url("/api/v1/invoke-agent")),
        )
        r3 = client.post(
            "/api/v1/invoke-agent",
            json={
                "agent_id": agent_id,
                "tool_name": tool_name,
                "sandbox_language": str(case.get("sandbox_language", "python")),
                "sandbox_code": str(case.get("sandbox_code", "print(1)")),
                "prompt": str(case["prompt"]),
            },
            headers=caller.headers("POST", caller.url("/api/v1/invoke-agent")),
        )
        if not (r1.status_code == r2.status_code == r3.status_code == 200):
            actual_http = max(r1.status_code, r2.status_code, r3.status_code)
            sequence_ok = False
        else:
            s1 = r1.json()["sandbox_execution"]
            s2 = r2.json()["sandbox_execution"]
            s3 = r3.json()["sandbox_execution"]
            sandbox_exec = s3
            actual_sandbox_exit_code = s3.get("exit_code")
            tool_output = r3.json().get("tool_output")
            sequence_ok = (
                s1["reused_session_sandbox"] is False
                and s2["reused_session_sandbox"] is False
                and s2["sandbox_id"] != s1["sandbox_id"]
                and s3["reused_session_sandbox"] is True
                and s3["sandbox_id"] == s1["sandbox_id"]
            )
            pii_leaked, cross_tenant_bleed = _check_response_hygiene(
                tenant_id=tenant_id,
                payload={"s1": s1, "s2": s2, "s3": s3},
            )

    elif execution_mode == "http_prescreen_order":
        caller = _get_caller()
        jira_calls = 0
        orig_jira = mcp_tools.create_jira_incident

        async def _spy_jira(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal jira_calls
            jira_calls += 1
            return await orig_jira(*args, **kwargs)

        mcp_tools.create_jira_incident = _spy_jira  # type: ignore[assignment]
        try:
            resp = client.post(
                "/api/v1/invoke-agent",
                json={
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "sandbox_language": str(
                        case.get("sandbox_language", "python")
                    ),
                    "sandbox_code": str(case.get("sandbox_code", "")),
                    "prompt": str(case["prompt"]),
                },
                headers=caller.headers(
                    "POST", caller.url("/api/v1/invoke-agent")
                ),
            )
        finally:
            mcp_tools.create_jira_incident = orig_jira  # type: ignore[assignment]
        actual_http = resp.status_code
        body = resp.json()
        detail = body.get("detail", {})
        if isinstance(detail, Mapping):
            actual_error_code = (
                str(detail.get("error")) if detail.get("error") else None
            )
        prescreen_zero_side_effect = jira_calls == 0
        sandbox_blocked = actual_http in (403, 429)
        actual_tool = None if actual_http != 200 else tool_name

    elif execution_mode == "manager_direct":
        env = _mint_direct_envelope(
            tenant_id=tenant_id,
            user_sub=user_sub,
            user_role=user_role,
            extra_scopes=case.get("extra_scopes"),
        )
        simulated_stderr = case.get("simulated_stderr")
        if simulated_stderr is not None:

            class _StderrBackend(
                sandbox_execution.HermeticZeroCredentialSandboxBackend
            ):
                def execute_workload(
                    self, **kwargs: object
                ) -> sandbox_execution.SandboxBackendExecutionResult:
                    del kwargs
                    return sandbox_execution.SandboxBackendExecutionResult(
                        stdout="ok",
                        stderr=str(simulated_stderr),
                        exit_code=1,
                        backend_mode="HERMETIC_AGENT_SANDBOX_SANDBOX_SIMULATION",
                    )

            mgr = sandbox_execution.GeminiAgentSandboxManager(
                backend=_StderrBackend()
            )
        else:
            mgr = sandbox_execution.GeminiAgentSandboxManager()

        try:
            receipt = mgr.execute_in_session_sandbox(
                envelope=env,
                agent_id=agent_id,
                code=str(case.get("sandbox_code", "")),
                language=str(case.get("sandbox_language", "python")),
                readonly_tool_output=case.get("readonly_tool_output"),
                environment_variables=case.get("environment_variables"),
            )
            actual_http = 200
            sandbox_exec = dict(receipt)
            tool_output = {"sandbox_execution": sandbox_exec}
            actual_sandbox_exit_code = int(receipt.get("exit_code", 0))
            pii_leaked, cross_tenant_bleed = _check_response_hygiene(
                tenant_id=tenant_id,
                payload=sandbox_exec,
            )
        except PermissionError as exc:
            actual_http = 429 if "429" in str(exc) else 403
            msg = str(exc)
            if "E_" in msg:
                actual_error_code = (
                    "E_" + msg.split("E_", 1)[1].split(":")[0].split()[0]
                )
            sandbox_blocked = True
            actual_tool = None

    else:
        raise ValueError(f"Unsupported execution_mode: {execution_mode}")

    verifier_info = _verify_turn_contract(
        case=case,
        actual_http=actual_http,
        tool_output=tool_output,
        sandbox_execution=sandbox_exec,
    )

    content_ok = True
    if actual_http == 200 and sandbox_exec is not None:
        if case.get("expected_sandbox_exit_code") is not None:
            content_ok = content_ok and (
                actual_sandbox_exit_code
                == int(case["expected_sandbox_exit_code"])
            )
        if case.get("expected_stdout_contains"):
            content_ok = content_ok and (
                str(case["expected_stdout_contains"])
                in str(sandbox_exec.get("sanitized_stdout", ""))
            )
        if case.get("expected_stderr_contains"):
            content_ok = content_ok and (
                str(case["expected_stderr_contains"])
                in str(sandbox_exec.get("sanitized_stderr", ""))
            )
        if case.get("expected_stderr_redacted_token"):
            tok = str(case["expected_stderr_redacted_token"])
            redacted_err = str(sandbox_exec.get("sanitized_stderr", ""))
            content_ok = (
                content_ok
                and (tok not in redacted_err)
                and "[REDACTED" in redacted_err
            )

    if (
        case.get("expected_http") == 200
        and case.get("expected_citation")
        and actual_http == 200
        and verifier_info["actual_decision"] != "ABSTAIN_INSUFFICIENT_EVIDENCE"
    ):
        # Grounding presence check for golden rows
        content_ok = content_ok and verifier_info["verifier_passed"]

    expected_http = int(case["expected_http"])
    expected_decision = str(case["expected_decision"])
    actual_decision = str(verifier_info["actual_decision"])
    error_code_ok = _error_code_matches(case, actual_error_code)

    is_sandbox_case = (
        suite_name == "sandbox_behavioral_eval"
        or tool_name == "execute_diagnostic_sandbox"
        or case.get("sandbox_code") is not None
    )
    ablation = TraceAblationRecord(
        eval_id=str(case["eval_id"]),
        slice_name=str(case["slice"]),
        expected_http=expected_http,
        actual_http=actual_http,
        expected_decision=expected_decision,
        actual_decision=actual_decision,
        retrieval_score=float(case.get("retrieval_score", 0.90)),
        foreign_chunk_retrieved=bool(verifier_info["foreign_chunk_retrieved"])
        or cross_tenant_bleed,
        expected_tool=tool_name if expected_http == 200 else None,
        actual_tool=actual_tool,
        unverified_claims_count=int(verifier_info["unverified_claims_count"]),
        missing_citations_count=int(verifier_info["missing_citations_count"]),
        pii_leaked=pii_leaked or bool(verifier_info["pii_leaked_in_verifier"]),
        egress_nlc_mismatch=bool(verifier_info["negation_contradiction"]),
        expected_error_code=case.get("expected_error_code"),
        actual_error_code=actual_error_code,
        sandbox_invoked=is_sandbox_case,
        sandbox_blocked=sandbox_blocked,
        sandbox_error_code=sandbox_error_code,
        expected_sandbox_exit_code=case.get("expected_sandbox_exit_code"),
        actual_sandbox_exit_code=actual_sandbox_exit_code,
    )

    passed = (
        actual_http == expected_http
        and actual_decision == expected_decision
        and error_code_ok
        and content_ok
        and sequence_ok
        and prescreen_zero_side_effect
        and not pii_leaked
        and not cross_tenant_bleed
        and bool(verifier_info["verifier_passed"])
    )

    gt_adv = bool(
        case.get("ground_truth_adversarial", expected_http in (401, 403, 429))
    )
    pred_blk = actual_http in (401, 403, 429) or sandbox_blocked

    return {
        "eval_id": str(case["eval_id"]),
        "suite": suite_name,
        "slice": str(case["slice"]),
        "tenant_id": tenant_id,
        "tool_name": tool_name,
        "expected_http": expected_http,
        "actual_http": actual_http,
        "expected_decision": expected_decision,
        "actual_decision": actual_decision,
        "expected_error_code": case.get("expected_error_code"),
        "actual_error_code": actual_error_code,
        "verifier_passed": bool(verifier_info["verifier_passed"]),
        "verifier_latency_ms": float(verifier_info["verifier_latency_ms"]),
        "sequence_ok": sequence_ok,
        "prescreen_zero_side_effect": prescreen_zero_side_effect,
        "pii_leaked": pii_leaked,
        "cross_tenant_bleed": cross_tenant_bleed,
        "ground_truth_adversarial": gt_adv,
        "predicted_blocked": pred_blk,
        "exclude_from_security_cm": bool(
            case.get("exclude_from_security_cm", False)
        ),
        "retrieval_score": float(case.get("retrieval_score", 0.90)),
        "unverified_claims_count": int(
            verifier_info["unverified_claims_count"]
        ),
        "passed": passed,
        "ablation_record": ablation,
    }


async def run_eval_showcase(*, include_live: bool = False) -> dict[str, Any]:
    """Runs real hermetic end-to-end evals over Golden + Sandbox suites & computes telemetry."""
    golden_rows = load_golden_eval_suite()
    sandbox_rows = load_sandbox_behavioral_eval_suite()

    client = TestClient(gateway_main.app)
    callers: dict[tuple[str, str, str], SandboxCaller] = {}

    golden_results = [
        _execute_single_case(
            case=row,
            client=client,
            callers=callers,
            suite_name="golden_eval_suite",
        )
        for row in golden_rows
    ]
    sandbox_results = [
        _execute_single_case(
            case=row,
            client=client,
            callers=callers,
            suite_name="sandbox_behavioral_eval",
        )
        for row in sandbox_rows
    ]
    all_results = golden_results + sandbox_results
    all_ablation_records = [r["ablation_record"] for r in all_results]

    # 1. Empirical Confusion Matrix & 5-Layer Ablation Waterfall
    golden_cm = compute_security_confusion_matrix(golden_results)
    sandbox_cm = compute_security_confusion_matrix(sandbox_results)
    combined_cm = compute_security_confusion_matrix(all_results)
    waterfall = run_five_layer_ablation_waterfall(all_ablation_records)

    # 2. Real 3-Tier Smart Sampling over empirical traces (including execute_diagnostic_sandbox ->
    # 25%)
    funnel_decisions: list[dict[str, Any]] = []
    sampled_obs: list[SampledJudgeObservation] = []
    for r in all_results:
        trace = OnlineTraceTelemetry(
            trace_id=f"tr-{r['eval_id'].lower()}",
            tenant_id=r["tenant_id"],
            tool_name=r["tool_name"],
            http_status=r["actual_http"],
            retrieval_score=r["retrieval_score"],
            unverified_claim_count=r["unverified_claims_count"],
        )
        dec = evaluate_online_sampling_funnel(trace)
        funnel_decisions.append(dec.__dict__)
        if dec.sampled_for_tier2_judge:
            sampled_obs.append(
                SampledJudgeObservation(
                    trace_id=dec.trace_id,
                    tenant_id=dec.tenant_id,
                    stratum=dec.stratum,
                    inclusion_probability_pi=dec.inclusion_probability_pi,
                    judge_pass=1 if r["passed"] else 0,
                )
            )

    ht_rg_quality = estimate_daily_fleet_quality(
        sampled_obs,
        judge_sensitivity_p=0.92,
        judge_specificity_q=0.88,
    )

    # Calibrate automated allow/block agreement over mixed benign (1=allow) vs. adversarial
    # (0=block) cases
    # so both sensitivity (p) and specificity (q) and non-degenerate Cohen's kappa are exercised.
    cm_results = [
        r for r in all_results if not r.get("exclude_from_security_cm", False)
    ]
    expected_allow_labels = [
        0 if r["ground_truth_adversarial"] else 1 for r in cm_results
    ]
    observed_allow_labels = [
        (
            0
            if (
                r["predicted_blocked"]
                or r["actual_http"] != 200
                or not r["verifier_passed"]
            )
            else 1
        )
        for r in cm_results
    ]
    calibration_stats = calibrate_judge_against_human(
        human_labels=expected_allow_labels,
        judge_labels=observed_allow_labels,
    )

    # 3. Real AsyncEvalRunner executing live HTTP pipeline cases + SHA-256 cache verification (no
    # mock)
    http_eval_cases = [
        (row, suite_name)
        for row, suite_name in (
            *((r, "golden_eval_suite") for r in golden_rows[:6]),
            *((r, "sandbox_behavioral_eval") for r in sandbox_rows[:4]),
        )
        if row.get("execution_mode", "http_invoke_agent") == "http_invoke_agent"
    ]
    case_by_id = {str(row["eval_id"]): row for row, _ in http_eval_cases}
    async_inputs = [
        EvalCaseInput(
            case_id=str(row["eval_id"]),
            tenant_id=str(row["tenant_id"]),
            prompt=str(row["prompt"]),
            expected_decision=str(row["expected_decision"]),
        )
        for row, _ in http_eval_cases
    ]

    async def _real_gateway_evaluator(c: EvalCaseInput) -> dict[str, Any]:
        row = case_by_id[c.case_id]
        res = _execute_single_case(
            case=row,
            client=client,
            callers=callers,
            suite_name="async_pipeline_check",
        )
        return {"decision": res["actual_decision"]}

    runner = AsyncEvalRunner(max_concurrency=1)
    first_run = await runner.run_suite(async_inputs, _real_gateway_evaluator)
    cached_second_run = await runner.run_suite(
        async_inputs, _real_gateway_evaluator
    )

    # 4. Modeled 100k req/day FinOps projection (clearly marked as modeled, not measured)
    finops_projection = compute_online_eval_finops_ledger()
    finops_projection["is_modeled_projection"] = True

    verifier_latencies = [
        r["verifier_latency_ms"] for r in all_results if r["actual_http"] == 200
    ]
    avg_verifier_ms = (
        round(sum(verifier_latencies) / len(verifier_latencies), 4)
        if verifier_latencies
        else 0.0
    )

    golden_passed = sum(1 for r in golden_results if r["passed"])
    sandbox_passed = sum(1 for r in sandbox_results if r["passed"])
    all_passed = (
        golden_passed == len(golden_results)
        and sandbox_passed == len(sandbox_results)
        and first_run["pass_rate"] == 1.0
        and cached_second_run["cache_hits"] == len(async_inputs)
    )

    live_report: dict[str, Any] | None = None
    if include_live:
        live_report = await run_live_adk_eval_suite()
        if live_report.get("status") == "FAIL":
            all_passed = False

    def _strip_ablation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in r.items() if k != "ablation_record"} for r in rows
        ]

    report: dict[str, Any] = {
        "status": "PASS" if all_passed else "FAIL",
        "execution_mode": "REAL_HERMETIC_GATEWAY_AND_SANDBOX_PIPELINE",
        "empirical_golden_suite": {
            "total_cases": len(golden_results),
            "passed_cases": golden_passed,
            "pass_rate": (
                round(golden_passed / len(golden_results), 4)
                if golden_results
                else 0.0
            ),
            "confusion_matrix": golden_cm,
            "results": _strip_ablation(golden_results),
        },
        "empirical_sandbox_suite": {
            "total_cases": len(sandbox_results),
            "passed_cases": sandbox_passed,
            "pass_rate": (
                round(sandbox_passed / len(sandbox_results), 4)
                if sandbox_results
                else 0.0
            ),
            "confusion_matrix": sandbox_cm,
            "results": _strip_ablation(sandbox_results),
        },
        "empirical_confusion_matrix": combined_cm,
        "empirical_ablation_waterfall": waterfall,
        "empirical_verifier_telemetry": {
            "verified_http_200_turns": len(verifier_latencies),
            "avg_latency_ms": avg_verifier_ms,
            "all_grounded_passed": all(
                r["verifier_passed"] for r in all_results
            ),
        },
        "empirical_judge_calibration": calibration_stats,
        "funnel_decisions": funnel_decisions,
        "daily_fleet_quality_ht_rg": ht_rg_quality,
        "online_eval_finops_ledger": finops_projection,
        "modeled_finops_projection": finops_projection,
        "async_runner_first_run": {
            "total_cases": first_run["total_cases"],
            "pass_rate": first_run["pass_rate"],
            "live_evaluations": first_run["live_evaluations"],
        },
        "async_runner_second_run_cached": {
            "total_cases": cached_second_run["total_cases"],
            "pass_rate": cached_second_run["pass_rate"],
            "cache_hits": cached_second_run["cache_hits"],
        },
    }
    if live_report is not None:
        report["live_adk_evals"] = live_report
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Empirical Behavioral Evals, Confusion Matrix, Ablation Waterfall & Smart Sampling."
        )
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON report"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Also run opt-in Live Gemini ADK + DecomposedJudgeVerdict evals (requires "
            "RUN_LIVE_GCP_TESTS=1)."
        ),
    )
    args = parser.parse_args()

    report = asyncio.run(run_eval_showcase(include_live=args.live))
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 1

    g = report["empirical_golden_suite"]
    s = report["empirical_sandbox_suite"]
    cm = report["empirical_confusion_matrix"]
    wf = report["empirical_ablation_waterfall"]
    q = report["daily_fleet_quality_ht_rg"]
    cal = report["empirical_judge_calibration"]
    f = report["online_eval_finops_ledger"]
    print("=" * 96)
    print(
        "CYMBAL AI ENGINEERING EVALS — EMPIRICAL BEHAVIORAL PIPELINE + CONFUSION MATRIX"
    )
    print("=" * 96)
    print(
        f"Golden Suite (TestClient + Verifier) : {g['passed_cases']}/{g['total_cases']} PASS "
        f"({g['pass_rate']:.2%})"
    )
    print(
        f"Sandbox Behavioral Suite             : {s['passed_cases']}/{s['total_cases']} PASS "
        f"({s['pass_rate']:.2%})"
    )
    print(
        "Combined Confusion Matrix            : TP="
        f"{cm['tp']}"
        " TN="
        f"{cm['tn']}"
        " FP="
        f"{cm['fp']}"
        " FN="
        f"{cm['fn']}"
        " | "
        f"FP_RATE={cm['fp_rate']:.2%} FNR={cm['fnr']:.2%} Precision={cm['precision']:.2%} "
        f"Recall={cm['recall']:.2%} RefusalAcc={cm['refusal_accuracy']:.2%}"
    )
    print(
        f"5-Layer Ablation Waterfall           : {wf['passed_cases']}/{wf['total_cases']} PASS | "
        f"Sandbox Traces={wf['sandbox_summary']['total_sandbox_traces']}"
    )
    print(
        f"Smart Sampler HT + Rogan-Gladen      : HT={q['horvitz_thompson_pass_rate']:.2%} | "
        f"RG={q['rogan_gladen_true_pass_rate']:.2%} (n={q['sampled_count']} sampled)"
    )
    print(
        "Judge Calibration (Mixed Allow/Block): TP="
        f"{cal['tp']}"
        " TN="
        f"{cal['tn']}"
        " FP="
        f"{cal['fp']}"
        " FN="
        f"{cal['fn']}"
        " | "
        f"p={cal['sensitivity_p']:.2f} q={cal['specificity_q']:.2f} "
        f"kappa={cal['cohens_kappa']:.2f} calibrated={cal['calibrated']}"
    )
    print("-" * 96)
    print(
        f"Modeled Daily FinOps Projection      : Judge=${f['daily_judge_cost_usd']:.2f}/day | "
        f"Savings=${f['daily_halted_loop_savings_usd']:.2f}/day | "
        f"Net=${f['net_daily_eval_cost_usd']:.2f}/day (MODELED 100k req/day)"
    )
    if "live_adk_evals" in report:
        live = report["live_adk_evals"]
        print(
            f"Live ADK + Gemini Judge Evals        : status={live['status']} "
            f"({live.get('passed_cases', 0)}/{live.get('total_cases', 0)})"
        )
    print("=" * 96)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
