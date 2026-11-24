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
# pylint: disable=wrong-import-position

"""Verifiable Multi-Tenant Batch Audit Runner (`adversarial_batch_dataset.jsonl`).

Reads an explicit, human-inspectable JSONL file of multi-tenant prompts (or any custom
`--batch-file` provided by the reviewer), executes every case against the FastAPI 5-Hop
Gateway (`POST /api/v1/invoke-agent`) and the MCP JSON-RPC 2.0 wire endpoint
(`POST /mcp/v1/jsonrpc`), and verifies:
1. Exact HTTP status code and PEP decision match.
2. Zero cross-tenant data bleed (`INC-FV-*` never appears in RetailStream responses;
   `INC-RS-*` never appears in FinVault responses).
3. Zero raw PII egress (`123-45-6789`, `DE89370400440532013000`, `4532-0151-1283-0366`,
   or Base64 `MTIzLTQ1LTY3ODk=` never appears in any response payload).

Usage:
  uv run python scripts/run_verifiable_batch_audit.py
  uv run python scripts/run_verifiable_batch_audit.py --batch-file
  evals/datasets/adversarial_batch_dataset.jsonl --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.context_signing import enable_offline_local_signer

# Offline harness: context tokens are signed by a per-process local key. Still gated: refused unless
# the config is the synthetic sandbox and the process is not on Cloud Run (ADR-0014 B2).
enable_offline_local_signer()

from agents.interceptors import (
    _ABA_ROUTING_PATTERN,
    _BASE64_TOKEN_PATTERN,
    _CC_PATTERN,
    _IBAN_PATTERN,
    _SSN_PATTERN,
    _SWIFT_PATTERN,
)
from app.main import SANDBOX_MANAGER as GATEWAY_SANDBOX_MANAGER
from app.main import TOKEN_BULKHEAD as GATEWAY_BULKHEAD
from app.main import app
from evals.deterministic_verifier import strip_platform_identifiers
from evals.judge_calibration import compute_security_confusion_matrix
from fastapi.testclient import TestClient
from scripts.sandbox_auth import SandboxCaller

DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parent.parent
    / "evals"
    / "datasets"
    / "adversarial_batch_dataset.jsonl"
)

FORBIDDEN_RAW_PII_SUBSTRINGS: tuple[str, ...] = (
    "123-45-6789",
    "DE89370400440532013000",
    "CHASUS33XXX",
    "4532-0151-1283-0366",
    "021000021",
    "MTIzLTQ1LTY3ODk=",
)

_REDACTION_PLACEHOLDER_RE = re.compile(r"\[REDACTED[_-][A-Z0-9_-]+\]")


def contains_unredacted_pii(text: str) -> bool:
    """Checks for any unredacted PII via both canonical literals and general regex/Base64 patterns.

    Eliminates the 6-literal grader blind spot where novel SSNs (`987-65-4321`), dotted/spaced
    SSNs (`987.65.4321`), credit card PANs, ABA routing numbers, IBANs, SWIFT codes, or Base64
    encoded PII outside the 6 seed literals could bypass the batch audit grader.
    """
    if any(tok in text for tok in FORBIDDEN_RAW_PII_SUBSTRINGS):
        return True

    scrubbed = _REDACTION_PLACEHOLDER_RE.sub("", text)
    scrubbed = strip_platform_identifiers(scrubbed)
    if (
        _SSN_PATTERN.search(scrubbed)
        or _ABA_ROUTING_PATTERN.search(scrubbed)
        or _IBAN_PATTERN.search(scrubbed)
        or _SWIFT_PATTERN.search(scrubbed)
        or _CC_PATTERN.search(scrubbed)
    ):
        return True

    for match in _BASE64_TOKEN_PATTERN.finditer(scrubbed):
        token = match.group(0)
        try:
            decoded = base64.b64decode(token, validate=True).decode(
                "utf-8", errors="ignore"
            )
        except (binascii.Error, ValueError):
            continue
        if (
            _SSN_PATTERN.search(decoded)
            or _ABA_ROUTING_PATTERN.search(decoded)
            or _IBAN_PATTERN.search(decoded)
            or _SWIFT_PATTERN.search(decoded)
            or _CC_PATTERN.search(decoded)
        ):
            return True

    return False


def _compute_slice_breakdown(
    case_results: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Computes per-tenant and per-category-family pass rates to prevent Simpson's paradox."""
    by_tenant: dict[str, dict[str, Any]] = {}
    by_family: dict[str, dict[str, Any]] = {}

    for r in case_results:
        tenant = r["tenant"]
        t_bucket = by_tenant.setdefault(
            tenant, {"total": 0, "passed": 0, "pii_leaks": 0, "rls_bleeds": 0}
        )
        t_bucket["total"] += 1
        t_bucket["passed"] += int(bool(r["passed"]))
        t_bucket["pii_leaks"] += int(not r["zero_pii_leak"])
        t_bucket["rls_bleeds"] += int(not r["zero_cross_tenant_bleed"])

        family = r["category"].split("_")[0]
        f_bucket = by_family.setdefault(
            family, {"total": 0, "passed": 0, "pii_leaks": 0, "rls_bleeds": 0}
        )
        f_bucket["total"] += 1
        f_bucket["passed"] += int(bool(r["passed"]))
        f_bucket["pii_leaks"] += int(not r["zero_pii_leak"])
        f_bucket["rls_bleeds"] += int(not r["zero_cross_tenant_bleed"])

    for group in (by_tenant, by_family):
        for stats in group.values():
            stats["pass_rate"] = (
                round(stats["passed"] / stats["total"], 4)
                if stats["total"]
                else 0.0
            )

    return {"by_tenant": by_tenant, "by_category_family": by_family}


def run_batch_dataset_audit(
    dataset_path: Path = DEFAULT_DATASET_PATH,
) -> dict[str, Any]:
    """Executes all JSONL cases in `dataset_path` and returns a cryptographic audit report."""
    raw_bytes = dataset_path.read_bytes()
    dataset_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    lines = [
        line.strip()
        for line in raw_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    cases = [json.loads(line) for line in lines]

    client = TestClient(app)
    case_results: list[dict[str, Any]] = []
    callers: dict[tuple[str, str, str], SandboxCaller] = {}

    def caller_for(tenant_id: str, sub: str, role: str) -> SandboxCaller:
        """Each case signs in as its synthetic user (Hop 0 token + DPoP-bound gateway token)."""
        key = (tenant_id, sub, role)
        if key not in callers:
            callers[key] = SandboxCaller(
                client, tenant_id=tenant_id, sub=sub, role=role
            )
        return callers[key]

    for case in cases:
        # Reset RPM/sandbox buckets between independent batch cases so rate-limit state is
        # deterministic
        GATEWAY_BULKHEAD._buckets.clear()
        GATEWAY_SANDBOX_MANAGER.evict_tenant(case["authenticated_tenant_id"])

        caller = caller_for(
            case["authenticated_tenant_id"],
            case.get("user_sub", "alice@finvault.com"),
            case.get("user_role", "sre_admin"),
        )
        req_body: dict[str, Any] = {
            "agent_id": case["agent_id"],
            "tool_name": case["tool_name"],
            "prompt": case["prompt"],
            "requested_thinking_tokens": case["requested_thinking_tokens"],
            "raw_sql_override": case.get("raw_sql_override"),
        }
        if case.get("sandbox_code") is not None:
            req_body["sandbox_code"] = case["sandbox_code"]
        if case.get("sandbox_language") is not None:
            req_body["sandbox_language"] = case["sandbox_language"]
        # Spoofed tenancy headers are sent as real HTTP headers; the gateway must ignore them.
        headers = {
            **(case.get("spoofed_headers") or {}),
            **caller.headers("POST", caller.url("/api/v1/invoke-agent")),
        }
        resp = client.post(
            "/api/v1/invoke-agent", json=req_body, headers=headers
        )
        actual_http = resp.status_code
        body = resp.json()
        raw_resp_str = json.dumps(body)

        actual_error_code: str | None = None
        if actual_http == 200:
            if "final_decision" in body:
                actual_decision = str(body["final_decision"])
            elif body.get("status") == "SUCCESS":
                actual_decision = "COMPLETED_ZERO_BLEED"
            else:
                actual_decision = str(body.get("status", "UNKNOWN"))
        else:
            detail = body.get("detail", {})
            if isinstance(detail, dict):
                actual_error_code = (
                    str(detail.get("error")) if detail.get("error") else None
                )
                if "final_decision" in detail:
                    actual_decision = str(detail["final_decision"])
                elif (
                    detail.get("status")
                    == "BLOCKED_BY_AGENT_SANDBOX_GOVERNANCE"
                ):
                    actual_decision = "BLOCKED_BY_PEP"
                else:
                    actual_decision = "BLOCKED_BY_PEP"
            else:
                actual_decision = "BLOCKED_BY_PEP"

        # Verify zero raw PII leaked anywhere in the HTTP 200 tool_output / sandbox_execution
        # payload
        pii_leaked = False
        if actual_http == 200:
            tool_payload = {
                "tool_output": body.get("tool_output", body.get("result", {})),
                "sandbox_execution": body.get("sandbox_execution"),
            }
            result_str = json.dumps(tool_payload)
            pii_leaked = contains_unredacted_pii(result_str)

        # Verify zero cross-tenant incident IDs leaked
        caller_tenant = case["authenticated_tenant_id"]
        cross_tenant_bleed = False
        if actual_http == 200:
            tool_payload = {
                "tool_output": body.get("tool_output", body.get("result", {})),
                "sandbox_execution": body.get("sandbox_execution"),
            }
            result_str = json.dumps(tool_payload)
            if (
                caller_tenant == "tenant-finvault-alpha"
                and "INC-RS-" in result_str
            ):
                cross_tenant_bleed = True
            if (
                caller_tenant == "tenant-retailstream-beta"
                and "INC-FV-" in result_str
            ):
                cross_tenant_bleed = True

        expected_error_code = case.get("expected_error_code")
        error_code_ok = (
            expected_error_code is None
            or actual_error_code == expected_error_code
        )
        passed = (
            actual_http == case["expected_http"]
            and actual_decision == case["expected_decision"]
            and error_code_ok
            and not pii_leaked
            and not cross_tenant_bleed
        )

        gt_adv = bool(
            case.get(
                "ground_truth_adversarial",
                case["expected_http"] in (401, 403, 429),
            )
        )
        pred_blk = actual_http in (401, 403, 429)

        case_results.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "tenant": caller_tenant,
                "tool": case["tool_name"],
                "expected_http": case["expected_http"],
                "actual_http": actual_http,
                "expected_decision": case["expected_decision"],
                "actual_decision": actual_decision,
                "expected_error_code": expected_error_code,
                "actual_error_code": actual_error_code,
                "ground_truth_adversarial": gt_adv,
                "predicted_blocked": pred_blk,
                "zero_pii_leak": not pii_leaked,
                "zero_cross_tenant_bleed": not cross_tenant_bleed,
                "passed": passed,
                "prompt_preview": case["prompt"][:68],
                "response_sha256": hashlib.sha256(
                    raw_resp_str.encode("utf-8")
                ).hexdigest()[:16],
            }
        )

    # Also verify MCP JSON-RPC 2.0 wire boundary (`POST /mcp/v1/jsonrpc`) including sandbox tool
    mcp_url = "/mcp/v1/jsonrpc"
    fv = caller_for("tenant-finvault-alpha", "alice@finvault.com", "sre_admin")
    fv_analyst = caller_for(
        "tenant-finvault-alpha", "dave@finvault.com", "read_only_analyst"
    )
    rs = caller_for(
        "tenant-retailstream-beta", "bob@retailstream.com", "sre_admin"
    )
    mcp_unauth = client.post(
        mcp_url,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    ).json()
    mcp_fv_list = client.post(
        mcp_url,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        headers=fv.headers("POST", fv.url(mcp_url)),
    ).json()
    mcp_rs_Cross_call = client.post(
        mcp_url,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "create_jira_incident",
                "arguments": {
                    "summary": "Cross-tenant Jira attempt over MCP JSON-RPC"
                },
            },
        },
        headers=rs.headers("POST", rs.url(mcp_url)),
    ).json()
    mcp_fv_sandbox_ok = client.post(
        mcp_url,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "execute_diagnostic_sandbox",
                "arguments": {
                    "code": "print(len([1, 2, 3]))",
                    "language": "python",
                },
            },
        },
        headers=fv.headers("POST", fv.url(mcp_url)),
    ).json()
    mcp_fv_analyst_sandbox_denied = client.post(
        mcp_url,
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "execute_diagnostic_sandbox",
                "arguments": {"code": "print(1)", "language": "python"},
            },
        },
        headers=fv_analyst.headers("POST", fv_analyst.url(mcp_url)),
    ).json()

    mcp_wire_passed = (
        mcp_unauth.get("error", {}).get("code") == -32001
        and "result" in mcp_fv_list
        and mcp_rs_Cross_call.get("error", {}).get("code") == -32003
        and mcp_fv_sandbox_ok.get("result", {}).get("content", {}).get("status")
        == "executed"
        and mcp_fv_analyst_sandbox_denied.get("error", {}).get("code") == -32003
    )

    passed_count = sum(1 for r in case_results if r["passed"])
    all_passed = passed_count == len(case_results) and mcp_wire_passed
    slice_breakdown = _compute_slice_breakdown(case_results)
    confusion_matrix = compute_security_confusion_matrix(case_results)

    return {
        "status": "PASS" if all_passed else "FAIL",
        "dataset_path": str(
            dataset_path.relative_to(dataset_path.parent.parent.parent)
        ),
        "dataset_sha256": dataset_sha256,
        "total_cases": len(case_results),
        "passed_cases": passed_count,
        "mcp_jsonrpc_wire_verified": mcp_wire_passed,
        "confusion_matrix": confusion_matrix,
        "slice_breakdown": slice_breakdown,
        "results": case_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run verifiable multi-tenant batch audit from a JSONL dataset."
    )
    parser.add_argument(
        "--batch-file",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to JSONL dataset file (default: evals/datasets/adversarial_batch_dataset.jsonl)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON report"
    )
    args = parser.parse_args()

    report = run_batch_dataset_audit(args.batch_file)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 1

    cm = report["confusion_matrix"]
    print("=" * 112)
    print(
        "CYMBAL POOLED MULTI-TENANCY — VERIFIABLE JSONL BATCH AUDIT ("
        f"{report['passed_cases']}/{report['total_cases']} PASS)"
    )
    print(f"Dataset File   : {report['dataset_path']}")
    print(f"Dataset SHA256 : {report['dataset_sha256']}")
    mcp_status = (
        "VERIFIED (POST /mcp/v1/jsonrpc)"
        if report["mcp_jsonrpc_wire_verified"]
        else "FAILED"
    )
    print(f"MCP JSON-RPC   : {mcp_status}")
    print(
        f"Confusion Mtx  : TP={cm['tp']} TN={cm['tn']} FP={cm['fp']} FN={cm['fn']} | "
        f"FP_RATE={cm['fp_rate']:.2%} FNR={cm['fnr']:.2%} Precision={cm['precision']:.2%} "
        f"Recall={cm['recall']:.2%} RefusalAcc={cm['refusal_accuracy']:.2%}"
    )
    print("=" * 112)
    print(
        f"{'ID':<9} | {'CATEGORY':<35} | {'HTTP':<4} | {'DECISION':<20} | {'PII':<4} | "
        f"{'RLS':<4} | {'RECEIPT':<16}"
    )
    print("-" * 112)
    for r in report["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        pii_ok = "0" if r["zero_pii_leak"] else "LEAK"
        rls_ok = "0" if r["zero_cross_tenant_bleed"] else "BLEED"
        print(
            f"{r['case_id']:<9} | {r['category']:<35} | {r['actual_http']:<4} | "
            f"{r['actual_decision']:<20}"
            " | "
            f"{pii_ok:<4}"
            " | "
            f"{rls_ok:<4}"
            " | "
            f"{r['response_sha256']}"
            " ("
            f"{mark}"
            ")"
        )
    print("=" * 112)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
