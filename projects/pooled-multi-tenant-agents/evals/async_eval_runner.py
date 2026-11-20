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

"""Production-Ready Async Evaluation Harness with SHA-256 Cache & JSONL Checkpointing.

Implements Study Guide Chapter 8 Evaluation Runner Engineering:
1. Bounded concurrency (`asyncio.Semaphore(max_concurrency)`) so evaluation bursts never trip
   provider 429 RPM/TPM limits.
2. Content-addressed SHA-256 evaluation cache (`compute_eval_cache_key`) keyed by
   `(case_id, prompt, model_id, rubric_version)` so unchanged test cases execute in 0ms at $0.
3. Incremental JSONL checkpointing (`checkpoint_path`) so interrupted 1,000-case runs resume
   cleanly from the exact completed set.
4. Discriminated retry policy: exponential backoff on transient infrastructure timeouts while
   never retrying `PermissionError` (terminal security/policy blocks).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCaseInput:
    """Single evaluation case input for `AsyncEvalRunner`."""

    case_id: str
    tenant_id: str
    prompt: str
    expected_decision: str
    metadata: dict[str, Any] | None = None


def compute_eval_cache_key(
    *,
    case_id: str,
    tenant_id: str,
    prompt: str,
    model_id: str,
    rubric_version: str,
) -> str:
    """Computes a deterministic SHA-256 content-addressed digest for an evaluation item."""
    canonical = json.dumps(
        {
            "case_id": case_id,
            "tenant_id": tenant_id,
            "prompt": prompt,
            "model_id": model_id,
            "rubric_version": rubric_version,
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class AsyncEvalRunner:
    """Bounded-concurrency async evaluation harness with SHA-256 caching and JSONL resumption."""

    def __init__(
        self,
        *,
        model_id: str = "gemini-4-hydrogen-judge",
        rubric_version: str = "v1.0-binary-4check",
        max_concurrency: int = 10,
        max_transient_retries: int = 2,
        base_backoff_seconds: float = 0.01,
        checkpoint_path: Path | None = None,
    ) -> None:
        self.model_id = model_id
        self.rubric_version = rubric_version
        self.max_concurrency = max_concurrency
        self.max_transient_retries = max_transient_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.checkpoint_path = checkpoint_path
        self._cache: dict[str, dict[str, Any]] = {}
        self.cache_hits: int = 0
        self.live_evaluations: int = 0

    def _load_existing_checkpoints(self) -> dict[str, dict[str, Any]]:
        if self.checkpoint_path is None or not self.checkpoint_path.is_file():
            return {}
        completed: dict[str, dict[str, Any]] = {}
        for line in self.checkpoint_path.read_text(
            encoding="utf-8"
        ).splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            completed[row["cache_key"]] = row
            self._cache[row["cache_key"]] = row
        return completed

    def _append_checkpoint(self, record: dict[str, Any]) -> None:
        if self.checkpoint_path is None:
            return
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with self.checkpoint_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    async def _evaluate_single_with_retry(
        self,
        case: EvalCaseInput,
        evaluator_fn: Callable[[EvalCaseInput], Awaitable[dict[str, Any]]],
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any]:
        cache_key = compute_eval_cache_key(
            case_id=case.case_id,
            tenant_id=case.tenant_id,
            prompt=case.prompt,
            model_id=self.model_id,
            rubric_version=self.rubric_version,
        )
        if cache_key in self._cache:
            self.cache_hits += 1
            cached = dict(self._cache[cache_key])
            cached["from_cache"] = True
            return cached

        async with semaphore:
            attempt = 0
            while True:
                try:
                    self.live_evaluations += 1
                    raw_res = await evaluator_fn(case)
                    actual_decision = str(raw_res.get("decision", ""))
                    passed = actual_decision == case.expected_decision
                    record = {
                        "case_id": case.case_id,
                        "tenant_id": case.tenant_id,
                        "cache_key": cache_key,
                        "expected_decision": case.expected_decision,
                        "actual_decision": actual_decision,
                        "passed": passed,
                        "attempts": attempt + 1,
                        "from_cache": False,
                    }
                    self._cache[cache_key] = record
                    self._append_checkpoint(record)
                    return record
                except PermissionError as exc:
                    # Terminal policy/security blocks are NEVER retried
                    record = {
                        "case_id": case.case_id,
                        "tenant_id": case.tenant_id,
                        "cache_key": cache_key,
                        "expected_decision": case.expected_decision,
                        "actual_decision": "BLOCKED_POLICY",
                        "passed": case.expected_decision == "BLOCKED_POLICY",
                        "attempts": attempt + 1,
                        "from_cache": False,
                        "terminal_error": str(exc),
                    }
                    self._cache[cache_key] = record
                    self._append_checkpoint(record)
                    return record
                except (TimeoutError, ConnectionError) as exc:
                    if attempt >= self.max_transient_retries:
                        raise RuntimeError(
                            f"Case '{case.case_id}' exhausted {self.max_transient_retries} "
                            f"transient retries: {exc}"
                        ) from exc
                    attempt += 1
                    await asyncio.sleep(
                        self.base_backoff_seconds * (2 ** (attempt - 1))
                    )

    async def run_suite(
        self,
        cases: list[EvalCaseInput],
        evaluator_fn: Callable[[EvalCaseInput], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Executes `cases` concurrently under `Semaphore(max_concurrency)` with cache & resume."""
        self._load_existing_checkpoints()
        semaphore = asyncio.Semaphore(self.max_concurrency)
        results = await asyncio.gather(
            *(
                self._evaluate_single_with_retry(c, evaluator_fn, semaphore)
                for c in cases
            )
        )
        passed_count = sum(1 for r in results if r["passed"])
        return {
            "total_cases": len(results),
            "passed_cases": passed_count,
            "pass_rate": (
                round(passed_count / len(results), 4) if results else 0.0
            ),
            "cache_hits": self.cache_hits,
            "live_evaluations": self.live_evaluations,
            "results": list(results),
        }
