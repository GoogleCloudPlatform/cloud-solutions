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

"""Six Google Cloud Architecture Framework specialist sub-agents."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent

from . import config, prompts
from .tools.mcp_registry import (
    build_database_toolbox_mcp,
    build_external_catalog_mcp,
    build_external_observability_mcp,
    build_managed_mcp_toolsets,
)


@dataclass(frozen=True)
class PillarSpec:
    """Specification binding one Architecture Framework pillar to MCP tools."""

    pillar_key: str
    agent_name: str
    sweep_name: str
    description: str
    instruction: Callable[[Any], str]
    mcp_keys: tuple[str, ...]
    include_database_toolbox: bool = False


PILLAR_SPECS: tuple[PillarSpec, ...] = (
    PillarSpec(
        pillar_key="operational_excellence",
        agent_name="operational_excellence_agent",
        sweep_name="ops_sweep_reviewer",
        description=(
            "Google Cloud Architecture Framework Operational Excellence "
            "specialist. Analyzes application and access logs, distributed "
            "traces, GKE, Cloud Run, and Compute Engine runtime health, "
            "alerting policy coverage, runbooks, App Hub topology, and "
            "inventory drift."
        ),
        instruction=prompts.OPS_INSTRUCTION,
        mcp_keys=(
            "logging",
            "monitoring",
            "cloudrun",
            "cloudtrace",
            "cloudasset",
            "discoveryengine",
            "gcloud_cli",
            "developerknowledge",
        ),
    ),
    PillarSpec(
        pillar_key="security_compliance",
        agent_name="security_compliance_agent",
        sweep_name="security_sweep_reviewer",
        description=(
            "Google Cloud Architecture Framework Security, Privacy, and "
            "Compliance specialist. Audits IAM least privilege, service "
            "account bindings, organization policies, Cloud Storage exposure "
            "controls, Cloud Run ingress, and edge security configurations."
        ),
        instruction=prompts.SECURITY_INSTRUCTION,
        mcp_keys=(
            "resourcemanager",
            "iam",
            "orgpolicy",
            "cloudasset",
            "storage",
            "cloudrun",
            "logging",
            "gcloud_cli",
            "developerknowledge",
        ),
    ),
    PillarSpec(
        pillar_key="reliability",
        agent_name="reliability_agent",
        sweep_name="reliability_sweep_reviewer",
        description=(
            "Google Cloud Architecture Framework Reliability specialist. "
            "Evaluates high-availability topology, database backup and "
            "replication health, Pub/Sub and asynchronous worker continuity, "
            "and load-balancer health check readiness."
        ),
        instruction=prompts.RELIABILITY_INSTRUCTION,
        mcp_keys=(
            "sqladmin",
            "compute",
            "cloudrun",
            "pubsub",
            "monitoring",
            "logging",
            "discoveryengine",
            "gcloud_cli",
            "developerknowledge",
        ),
        include_database_toolbox=True,
    ),
    PillarSpec(
        pillar_key="performance_optimization",
        agent_name="performance_optimization_agent",
        sweep_name="performance_sweep_reviewer",
        description=(
            "Google Cloud Architecture Framework Performance Optimization "
            "specialist. Investigates database schemas, indexes, query "
            "statistics, and replicas alongside BigQuery, Cloud Run "
            "concurrency, Pub/Sub throughput, caching, and autoscaling."
        ),
        instruction=prompts.PERFORMANCE_INSTRUCTION,
        mcp_keys=(
            "monitoring",
            "logging",
            "sqladmin",
            "bigquery",
            "cloudrun",
            "pubsub",
            "cloudtrace",
            "gcloud_cli",
            "developerknowledge",
        ),
        include_database_toolbox=True,
    ),
    PillarSpec(
        pillar_key="cost_optimization",
        agent_name="cost_optimization_agent",
        sweep_name="cost_sweep_reviewer",
        description=(
            "Google Cloud Architecture Framework Cost Optimization "
            "specialist. Analyzes Cloud Logging sink routing and exclusion "
            "filters, telemetry ingestion volume, FinOps label compliance, "
            "idle capacity, and financial efficiency across cloud services."
        ),
        instruction=prompts.COST_INSTRUCTION,
        mcp_keys=(
            "logging",
            "monitoring",
            "compute",
            "cloudrun",
            "storage",
            "bigquery",
            "pubsub",
            "gcloud_cli",
            "developerknowledge",
        ),
    ),
    PillarSpec(
        pillar_key="sustainability",
        agent_name="sustainability_agent",
        sweep_name="sustainability_sweep_reviewer",
        description=(
            "Google Cloud Architecture Framework Sustainability specialist. "
            "Evaluates compute hardware generations, serverless idle "
            "allocations, reserved resource requests versus measured "
            "utilization, and regional carbon-free energy characteristics."
        ),
        instruction=prompts.SUSTAINABILITY_INSTRUCTION,
        mcp_keys=(
            "compute",
            "cloudrun",
            "monitoring",
            "logging",
            "gcloud_cli",
            "developerknowledge",
        ),
    ),
)


MAX_MCP_RESPONSE_CHARS = 40_000

_PAGE_SIZE_CAPS: dict[str, tuple[int, int]] = {
    "monitoring_list_metric_descriptors": (40, 50),
    "monitoring_list_timeseries": (40, 80),
    "monitoring_list_alert_policies": (30, 50),
    "monitoring_list_alerts": (30, 50),
    "monitoring_list_dashboards": (25, 40),
    "logging_list_log_entries": (20, 40),
    "cloudasset_list_assets": (40, 80),
}


def bound_specialist_tool_args(
    tool: Any, args: dict[str, Any], _tool_context: Any
) -> dict[str, Any] | None:
    """Clamps oversized MCP list query arguments before execution."""
    tool_name = getattr(tool, "name", "")
    if tool_name == "monitoring_list_metric_descriptors":
        args.setdefault("activeOnly", True)
    if tool_name in _PAGE_SIZE_CAPS:
        default_sz, max_sz = _PAGE_SIZE_CAPS[tool_name]
        raw_sz = args.get("pageSize")
        try:
            parsed_sz = int(raw_sz) if raw_sz is not None else default_sz
        except (TypeError, ValueError):
            parsed_sz = default_sz
        args["pageSize"] = max(1, min(parsed_sz, max_sz))
    return None


def cap_specialist_tool_response(
    _tool: Any,
    _args: dict[str, Any],
    _tool_context: Any,
    tool_response: Any,
) -> dict[str, Any] | None:
    """Truncates large MCP tool responses to keep LLM context bounded."""
    if not isinstance(tool_response, dict):
        return None

    serialized = json.dumps(tool_response, ensure_ascii=False, default=str)
    if len(serialized) <= MAX_MCP_RESPONSE_CHARS:
        return None

    text_chunks: list[str] = []
    content = tool_response.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_chunks.append(item["text"])
    raw_preview = "\n".join(text_chunks) if text_chunks else serialized
    clipped = (
        f"{raw_preview[:MAX_MCP_RESPONSE_CHARS]}\n"
        f"...[truncated at {MAX_MCP_RESPONSE_CHARS} chars; "
        "narrow filter or pageSize if needed]"
    )
    return {
        "content": [{"type": "text", "text": clipped}],
        "isError": bool(tool_response.get("isError", False)),
    }


def strip_tool_response_schemas(
    _callback_context: Any, llm_request: Any
) -> Any:
    """Clears MCP output schemas so Vertex AI avoids unsupported nesting."""
    req_config = getattr(llm_request, "config", None)
    tools = (
        getattr(req_config, "tools", None) if req_config is not None else None
    )
    if not tools:
        return None
    for tool_entry in tools:
        for decl in getattr(tool_entry, "function_declarations", None) or []:
            decl.response = None
            decl.response_json_schema = None
    return None


def _build_agent_from_spec(
    spec: PillarSpec, *, sweep_mode: bool = False
) -> LlmAgent:
    tools = list(build_managed_mcp_toolsets(*spec.mcp_keys))
    if spec.include_database_toolbox:
        tools.extend(build_database_toolbox_mcp())
    tools.extend(build_external_observability_mcp(pillar_key=spec.pillar_key))
    if not sweep_mode:
        tools.extend(build_external_catalog_mcp())
    return LlmAgent(
        name=spec.sweep_name if sweep_mode else spec.agent_name,
        model=config.SPECIALIST_MODEL,
        generate_content_config=config.SPECIALIST_GEN_CONFIG,
        description=spec.description,
        instruction=spec.instruction,
        tools=tools,
        before_model_callback=strip_tool_response_schemas,
        before_tool_callback=bound_specialist_tool_args,
        after_tool_callback=cap_specialist_tool_response,
    )


def build_specialist_agents() -> list[LlmAgent]:
    """Builds the six interactive pillar specialist sub-agents."""
    return [
        _build_agent_from_spec(spec, sweep_mode=False) for spec in PILLAR_SPECS
    ]


def build_sweep_reviewers() -> list[tuple[str, LlmAgent]]:
    """Builds isolated specialist reviewers used during parallel sweeps."""
    return [
        (spec.pillar_key, _build_agent_from_spec(spec, sweep_mode=True))
        for spec in PILLAR_SPECS
    ]
