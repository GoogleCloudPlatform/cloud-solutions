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

"""Private Self-Service "Agent Alpha" — FinVault Bank Regulatory Escalation Agent.

Strictly entitled to Tenant Alpha (`tenant-finvault-alpha`, Enterprise Tier).
- Runs Claude Sonnet on Vertex AI Model Garden (hot-swappable model configuration)
- Entitled to 8,000 thinking-token budget and 3LO Google Workspace (Drive/Calendar/Gmail) + Jira
- Direct API or discovery calls from Tenant Beta (`tenant-retailstream-beta`) return `403 Forbidden`
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from agents.interceptors import enforce_tenant_isolation_interceptor
from mcp_server import server as mcp_tools

AGENT_ALPHA_INSTRUCTION = (
    "You are Agent Alpha, FinVault Bank's Private Regulatory Escalation Agent.\n"
    "You assess high-severity core banking incidents against OCC/FDIC regulatory reporting "
    "thresholds,\n"
    "draft executive incident briefs via 3LO Google Workspace delegation, schedule Calendar "
    "post-mortems,\n"
    "and file regulatory notices. Strictly enforce `temp:tenant_id == 'tenant-finvault-alpha'`.\n"
)


@dataclass(frozen=True)
class AgentAlphaSpec:
    """Declarative ADK 2.0 specification for FinVault Bank's private Agent Alpha."""

    name: str
    model: str
    owner_tenant_id: str
    instruction: str
    tools: list[Any]
    before_agent_callback: Any


def build_agent_alpha(model_override: str | None = None) -> Any:
    """Builds FinVault Bank's private Regulatory Escalation Agent with hot-swappable model
    config.
    """
    model_name = model_override or os.getenv(
        "FINVAULT_AGENT_ALPHA_MODEL", "claude-3-7-sonnet@20250219"
    )
    tools = [
        mcp_tools.query_telemetry_rls,
        mcp_tools.read_runbook,
        mcp_tools.execute_diagnostic_sandbox,
        mcp_tools.create_jira_incident,
        mcp_tools.send_gmail_brief,
        mcp_tools.schedule_calendar_postmortem,
        mcp_tools.escalate_regulatory_filing,
    ]
    try:
        from google.adk.agents import Agent  # type: ignore[import-untyped]

        return Agent(
            name="finvault_regulatory_escalation_agent",
            model=model_name,
            instruction=AGENT_ALPHA_INSTRUCTION,
            tools=tools,
            before_agent_callback=enforce_tenant_isolation_interceptor,
        )
    except (ImportError, TypeError, ValueError):
        return AgentAlphaSpec(
            name="finvault_regulatory_escalation_agent",
            model=model_name,
            owner_tenant_id="tenant-finvault-alpha",
            instruction=AGENT_ALPHA_INSTRUCTION,
            tools=tools,
            before_agent_callback=enforce_tenant_isolation_interceptor,
        )


agent_alpha = build_agent_alpha()
