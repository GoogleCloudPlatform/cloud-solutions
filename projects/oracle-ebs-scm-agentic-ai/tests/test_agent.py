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

"""Tests for the agent wiring, MCP authentication, and answer completion."""

import asyncio
import threading
from typing import cast

import pytest
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import Event, EventActions
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.tool_context import ToolContext
from google.auth.transport.requests import Request
from google.genai import types
from oracle_ebs_scm_agentic_ai import agent, charts, guardrails, telemetry
from oracle_ebs_scm_agentic_ai.config import Settings
from oracle_ebs_scm_agentic_ai.failover import FailoverGemini
from tests.conftest import FakeContext


def test_build_agent_wires_framework_tools_and_guardrails(
    settings: Settings,
) -> None:
    root = agent.build_agent(settings)
    assert root.name == agent.AGENT_NAME
    assert isinstance(root.model, FailoverGemini)
    assert root.model.model == "gemini-test-flash"
    assert root.model.fallback_models == (
        "gemini-test-fallback",
        "gemini-test-lite",
    )
    assert root.model.client_kwargs == {
        "vertexai": True,
        "project": "test-project",
        "location": "global",
    }
    toolbox = root.tools[0]
    assert isinstance(toolbox, McpToolset)
    assert toolbox.tool_filter == list(guardrails.MCP_TOOLS)
    assert tuple(root.tools[1:4]) == charts.CHART_TOOLS
    assert [getattr(tool, "__name__", None) for tool in root.tools[4:]] == [
        "render_zone_map",
        "render_heatmap",
        "render_lane_map",
    ]
    assert root.before_agent_callback is guardrails.before_agent
    assert root.before_tool_callback is guardrails.before_tool
    assert root.after_tool_callback is guardrails.after_tool
    assert root.on_tool_error_callback is guardrails.on_tool_error
    assert root.before_model_callback is telemetry.start_model_call
    assert root.after_model_callback == [
        telemetry.log_model_call,
        agent.complete_answer,
    ]
    assert root.on_model_error_callback is guardrails.on_model_error
    config = root.generate_content_config
    assert config is not None
    assert config.temperature == 0.0
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW


def test_instruction_includes_rules_and_semantic_maps() -> None:
    text = agent.agent_instruction(cast(ReadonlyContext, FakeContext()))
    assert text.startswith("# VoltGuard supply chain resiliency agent")
    assert "## Semantic maps" in text
    assert "APPS.VW_SCM_NET_AVAILABILITY" in text
    assert "Confirmed" in text


class FakeIdTokenCredentials:
    """Stand-in for google-auth ID token credentials."""

    def __init__(self) -> None:
        self.token: str | None = None
        self.valid = False
        self.refresh_threads: list[threading.Thread] = []

    def refresh(self, request: Request) -> None:
        del request
        self.refresh_threads.append(threading.current_thread())
        self.token = f"token-{len(self.refresh_threads)}"
        self.valid = True


async def test_mcp_auth_headers_cache_and_refresh_the_oidc_token() -> None:
    audiences: list[str] = []
    credentials = FakeIdTokenCredentials()

    def factory(audience: str, request: Request) -> agent.IdTokenCredentials:
        del request
        audiences.append(audience)
        return credentials

    headers = agent.McpAuthHeaders(
        "https://toolbox.example.run.app", credentials_factory=factory
    )
    context = cast(ReadonlyContext, FakeContext())
    first = await asyncio.gather(*(headers(context) for _ in range(5)))
    credentials.valid = False
    expired = await headers(context)
    assert first == [{"Authorization": "Bearer token-1"}] * 5
    assert expired == {"Authorization": "Bearer token-2"}
    assert audiences == ["https://toolbox.example.run.app"]
    assert threading.main_thread() not in credentials.refresh_threads


def model_answer(*parts: types.Part, partial: bool = False) -> LlmResponse:
    """Build a model response with the given parts."""
    return LlmResponse(
        content=types.Content(role="model", parts=list(parts)),
        partial=partial,
    )


async def render_hub_chart(context: FakeContext, rows: str) -> None:
    """Render one chart in the context's current turn."""
    await charts.render_bar_chart(
        rows,
        "organization_code",
        "available_to_transact_qty",
        title="ATT by hub",
        tool_context=cast(ToolContext, context),
    )


async def test_complete_answer_adds_this_turn_images(
    hub_rows_json: str,
) -> None:
    context = FakeContext(invocation_id="turn-2")
    context.session.events.append(
        Event(
            author="voltguard_scm_agent",
            invocation_id="turn-1",
            actions=EventActions(artifact_delta={"old_chart.png": 0}),
        )
    )
    await render_hub_chart(context, hub_rows_json)
    response = await agent.complete_answer(
        cast(CallbackContext, context),
        model_answer(types.Part(text="### ATT by hub")),
    )
    assert response is not None and response.content is not None
    parts = response.content.parts
    assert parts is not None and len(parts) == 2
    assert parts[0].text == "### ATT by hub"
    blob = parts[1].inline_data
    assert blob is not None and blob.mime_type == "image/png"


async def test_complete_answer_keeps_charts_with_the_same_title(
    hub_rows_json: str,
) -> None:
    context = FakeContext(invocation_id="turn-1")
    await render_hub_chart(context, hub_rows_json)
    await render_hub_chart(context, hub_rows_json)
    response = await agent.complete_answer(
        cast(CallbackContext, context),
        model_answer(types.Part(text="### ATT by hub")),
    )
    assert response is not None and response.content is not None
    parts = response.content.parts
    assert parts is not None and len(parts) == 3


@pytest.mark.parametrize(
    "response",
    [
        model_answer(
            types.Part(function_call=types.FunctionCall(name="ebs_execute_sql"))
        ),
        model_answer(types.Part(text="### Partial"), partial=True),
        LlmResponse(),
    ],
)
async def test_complete_answer_keeps_tool_calls_and_partial_answers(
    hub_rows_json: str, response: LlmResponse
) -> None:
    context = FakeContext()
    await render_hub_chart(context, hub_rows_json)
    assert (
        await agent.complete_answer(cast(CallbackContext, context), response)
        is None
    )


async def test_complete_answer_skips_turns_without_text_or_charts() -> None:
    response = await agent.complete_answer(
        cast(CallbackContext, FakeContext()),
        model_answer(types.Part(text="### No charts")),
    )
    assert response is None


def tool_call_event(invocation_id: str, *parts: types.Part) -> Event:
    """Build a model event that calls a writeback tool next to the parts."""
    call = types.FunctionCall(name="ebs_update_safety_stock", args={})
    return Event(
        author="voltguard_scm_agent",
        invocation_id=invocation_id,
        content=types.Content(
            role="model", parts=[*parts, types.Part(function_call=call)]
        ),
    )


async def test_complete_answer_keeps_text_written_next_to_tool_calls() -> None:
    context = FakeContext(invocation_id="turn-2")
    context.session.events.extend(
        [
            tool_call_event("turn-1", types.Part(text="Old plan")),
            tool_call_event(
                "turn-2",
                types.Part(text="Checking the hub", thought=True),
                types.Part(text="### Plan\n1. Raise safety stock to 240"),
            ),
            tool_call_event("turn-2"),
        ]
    )
    response = await agent.complete_answer(
        cast(CallbackContext, context),
        model_answer(types.Part(text="Reply **Confirmed** to run the plan.")),
    )
    assert response is not None and response.content is not None
    parts = response.content.parts
    assert parts is not None
    assert [part.text for part in parts] == [
        "### Plan\n1. Raise safety stock to 240",
        "Reply **Confirmed** to run the plan.",
    ]
