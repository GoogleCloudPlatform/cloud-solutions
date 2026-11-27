# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Concurrent six-pillar Architecture Framework sweep orchestration tool."""

import asyncio
from typing import Any

from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.tool_context import ToolContext

from .. import config
from ..app_utils.profile_loader import (
    list_available_profiles,
    resolve_active_target_metadata,
)
from ..sub_agents import build_sweep_reviewers


def build_sweep_agent_tools() -> list[tuple[str, AgentTool]]:
    """Wraps each pillar reviewer agent as an isolated AgentTool."""
    return [
        (pillar_key, AgentTool(agent=reviewer, include_plugins=False))
        for pillar_key, reviewer in build_sweep_reviewers()
    ]


_RETRY_DELAY_SECONDS = 3.0


def _is_transient_rate_limit(exc: BaseException) -> bool:
    msg = f"{type(exc).__name__}: {exc}".upper()
    return (
        "429" in msg
        or "RESOURCE_EXHAUSTED" in msg
        or "RESOURCEEXHAUSTED" in msg
    )


async def waf_six_pillar_parallel_sweep(
    assessment_scope: str = (
        "Comprehensive six-pillar Google Cloud Architecture Framework "
        "assessment"
    ),
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Runs all six Architecture Framework specialists concurrently."""
    if tool_context is None:
        raise ValueError(
            "tool_context is required to execute waf_six_pillar_parallel_sweep."
        )

    default_scope = (
        "Comprehensive six-pillar Google Cloud Architecture Framework "
        "assessment"
    )
    prompt = (assessment_scope or "").strip() or default_scope

    meta = resolve_active_target_metadata(tool_context)
    if meta["mode"] == "unselected":
        return {
            "assessment_scope": prompt,
            "pillar_count": 0,
            "completed_pillars": [],
            "failed_pillars": [],
            "findings_by_pillar": {},
            "error": (
                "No Workload Profile, live catalog application, or target GCP "
                "project is selected in this session. Call "
                "select_workload_profile, activate_live_catalog_application, "
                "or activate_zero_profile_discovery first."
            ),
            "available_profile_ids": [
                p["profile_id"] for p in list_available_profiles()
            ],
        }

    pillar_tools = build_sweep_agent_tools()
    concurrency = max(1, int(getattr(config, "SWEEP_CONCURRENCY_LIMIT", 3)))
    sem = asyncio.Semaphore(concurrency)
    sweep_prompt = (
        f"{prompt}\n"
        "Execute one parallel batch of essential read-only MCP calls for "
        "your pillar and synthesize immediately."
    )

    async def _run_single_pillar(
        pillar_key: str, agent_tool: AgentTool
    ) -> tuple[str, str]:
        async with sem:
            response = await agent_tool.run_async(
                args={"request": sweep_prompt},
                tool_context=tool_context,
            )
            return pillar_key, str(response or "").strip()

    outcomes = list(
        await asyncio.gather(
            *(
                _run_single_pillar(pillar_key, tool)
                for pillar_key, tool in pillar_tools
            ),
            return_exceptions=True,
        )
    )

    retry_indices = [
        idx
        for idx, outcome in enumerate(outcomes)
        if isinstance(outcome, BaseException)
        and _is_transient_rate_limit(outcome)
    ]
    if retry_indices:
        await asyncio.sleep(_RETRY_DELAY_SECONDS)
        fresh_map = dict(build_sweep_agent_tools())
        retry_results = await asyncio.gather(
            *(
                _run_single_pillar(
                    pillar_tools[idx][0],
                    fresh_map.get(pillar_tools[idx][0], pillar_tools[idx][1]),
                )
                for idx in retry_indices
            ),
            return_exceptions=True,
        )
        for idx, retry_outcome in zip(
            retry_indices, retry_results, strict=True
        ):
            outcomes[idx] = retry_outcome

    findings: dict[str, str] = {}
    errors: dict[str, str] = {}
    for (pillar_key, _), outcome in zip(pillar_tools, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            if not _is_transient_rate_limit(outcome) and not isinstance(
                outcome, Exception
            ):
                raise outcome
            err_msg = f"{type(outcome).__name__}: {outcome}"
            errors[pillar_key] = err_msg
            findings[pillar_key] = f"Pillar assessment failed: {err_msg}"
        else:
            _, text = outcome
            if not text:
                err_msg = "Empty response returned by specialist reviewer"
                errors[pillar_key] = err_msg
                findings[pillar_key] = f"Pillar assessment failed: {err_msg}"
            elif text.startswith("Error: agent "):
                errors[pillar_key] = text
                findings[pillar_key] = f"Pillar assessment failed: {text}"
            else:
                findings[pillar_key] = text

    return {
        "assessment_scope": prompt,
        "pillar_count": len(findings),
        "completed_pillars": [k for k in findings if k not in errors],
        "failed_pillars": list(errors.keys()),
        "findings_by_pillar": findings,
    }
