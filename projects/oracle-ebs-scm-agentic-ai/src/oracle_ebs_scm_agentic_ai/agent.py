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

"""VoltGuard root agent built on the Oracle EBS Gemini Enterprise MCP framework.

The agent reaches Oracle EBS and BigQuery only through the framework Model
Context Protocol (MCP) Toolbox server, authenticates to it with Cloud Run
OpenID Connect (OIDC) tokens like the framework EBS_SQL_Agent, renders charts
with the framework graph tools and Google maps with the Maps Static API, and
grounds Gemini NL2SQL in the framework semantic maps.
"""

import asyncio
import logging
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Final, Protocol

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.auth.transport.requests import Request
from google.genai import types
from google.oauth2 import id_token
from oracle_ebs_scm_agentic_ai import guardrails, telemetry
from oracle_ebs_scm_agentic_ai.charts import CHART_TOOLS
from oracle_ebs_scm_agentic_ai.config import Settings
from oracle_ebs_scm_agentic_ai.failover import FailoverGemini
from oracle_ebs_scm_agentic_ai.maps import build_map_tools
from oracle_ebs_scm_agentic_ai.semantic_mapping import build_semantic_context

logger = logging.getLogger(__name__)


class IdTokenCredentials(Protocol):
    """The part of google-auth ID token credentials that the agent uses."""

    token: str | None

    @property
    def valid(self) -> bool:
        """Whether the cached token is present and not about to expire."""

    def refresh(self, request: Request) -> None:
        """Fetch a new ID token.

        Args:
            request: The HTTP transport for the token request.
        """


CredentialsFactory = Callable[[str, Request], IdTokenCredentials]

AGENT_NAME: Final[str] = "voltguard_scm_agent"
AGENT_DESCRIPTION: Final[str] = (
    "Supply chain resiliency agent for Oracle E-Business Suite: attention "
    "scan, demand sensing, SLA reservation audits, transfer simulation, "
    "executive charts, zone exposure maps, and confirmed Oracle EBS "
    "writebacks."
)
INSTRUCTIONS_PATH: Final[Path] = Path(__file__).parent / "instructions.txt"


@cache
def instruction_text() -> str:
    """Read the agent instruction and add the semantic map context once.

    Returns:
        The instruction followed by the semantic maps.
    """
    instructions = INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    return f"{instructions}\n## Semantic maps\n\n{build_semantic_context()}"


def agent_instruction(context: ReadonlyContext) -> str:
    """Provide the agent instruction to ADK.

    An instruction provider bypasses ADK session-state templating, so the
    braces in the semantic map examples reach Gemini unchanged.

    Args:
        context: The ADK context, which the instruction doesn't depend on.

    Returns:
        The agent instruction.
    """
    del context
    return instruction_text()


class McpAuthHeaders:
    """Cloud Run OIDC headers for the MCP Toolbox server.

    The provider caches the ID token and refreshes it only when it's missing
    or about to expire (google-auth refreshes a few minutes before the
    ``exp`` claim). The refresh runs in a worker thread, so it never blocks
    the event loop, and a lock keeps concurrent tool calls from refreshing at
    the same time. A token failure propagates as a tool error.
    """

    def __init__(
        self,
        audience: str,
        credentials_factory: CredentialsFactory = (
            id_token.fetch_id_token_credentials
        ),
    ) -> None:
        """Prepare the token cache for one audience.

        Args:
            audience: The MCP Toolbox URL that the ID token targets.
            credentials_factory: Creates ID token credentials for an
                audience.
        """
        self._audience = audience
        self._credentials_factory = credentials_factory
        self._credentials: IdTokenCredentials | None = None
        self._request = Request()
        self._lock = asyncio.Lock()

    async def __call__(self, context: ReadonlyContext) -> dict[str, str]:
        """Return the Authorization header with a valid ID token.

        Args:
            context: The ADK context of the tool call, which isn't needed.

        Returns:
            The bearer Authorization header for the MCP Toolbox request.
        """
        del context
        async with self._lock:
            credentials = self._credentials
            if credentials is None or not credentials.valid:
                credentials = await asyncio.to_thread(self._refreshed)
                self._credentials = credentials
            return {"Authorization": f"Bearer {credentials.token}"}

    def _refreshed(self) -> IdTokenCredentials:
        """Create the credentials once, then refresh their ID token.

        Returns:
            The credentials with a fresh ID token.
        """
        credentials = self._credentials or self._credentials_factory(
            self._audience, self._request
        )
        credentials.refresh(self._request)
        return credentials


def build_toolbox(settings: Settings) -> McpToolset:
    """Connect to the framework MCP Toolbox server over Streamable HTTP.

    Args:
        settings: The agent settings.

    Returns:
        The toolset with the SQL, forecast, Google Maps Platform, and
        writeback tools.
    """
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=str(settings.mcp_server_url),
            timeout=settings.mcp_timeout_seconds,
        ),
        tool_filter=list(guardrails.MCP_TOOLS),
        header_provider=McpAuthHeaders(settings.mcp_audience),
    )


def turn_text(callback_context: CallbackContext) -> list[types.Part]:
    """Collect the text that the model wrote next to its tool calls this turn.

    Gemini sometimes writes a plan in the same response as the writeback
    calls that record it, and then ends the turn with a short line.

    Args:
        callback_context: The ADK callback context of the turn.

    Returns:
        One text part with that text, or an empty list.
    """
    texts: list[str] = []
    for event in callback_context.session.events:
        content = event.content
        if (
            event.invocation_id != callback_context.invocation_id
            or content is None
            or not content.parts
            or not any(part.function_call for part in content.parts)
        ):
            continue
        for part in content.parts:
            if part.text and not part.thought:
                texts.append(part.text)
    return [types.Part(text="\n\n".join(texts))] if texts else []


async def turn_images(callback_context: CallbackContext) -> list[types.Part]:
    """Load the chart and map images that the tools saved this turn.

    Args:
        callback_context: The ADK callback context of the turn.

    Returns:
        The PNG image parts, in the order that the tools saved them.
    """
    saved = [
        (filename, version)
        for event in callback_context.session.events
        if event.invocation_id == callback_context.invocation_id
        for filename, version in event.actions.artifact_delta.items()
    ]
    images: list[types.Part] = []
    for filename, version in saved:
        artifact = await callback_context.load_artifact(
            filename=filename, version=version
        )
        if artifact is not None and artifact.inline_data is not None:
            images.append(artifact)
    return images


async def complete_answer(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    """Add the turn's earlier text and its images to the final answer.

    The ADK A2A executor publishes only the last message of a turn. Without
    this callback, text that the model wrote next to its tool calls, such as
    a plan that it wrote with the writeback calls that record it, and the
    chart and map images that the tools saved would never reach the planner.

    Args:
        callback_context: The ADK callback context of the turn.
        llm_response: The model response.

    Returns:
        The final answer with the earlier text before it and the images
        after it, or None to keep the response unchanged.
    """
    content = llm_response.content
    if llm_response.partial or content is None or not content.parts:
        return None
    if any(part.function_call is not None for part in content.parts):
        return None
    earlier = turn_text(callback_context)
    images = await turn_images(callback_context)
    if not earlier and not images:
        return None
    logger.info(
        "Completing the answer with %d earlier text parts and %d images",
        len(earlier),
        len(images),
    )
    answer = types.Content(
        role="model", parts=[*earlier, *content.parts, *images]
    )
    return llm_response.model_copy(update={"content": answer})


def build_agent(settings: Settings) -> LlmAgent:
    """Assemble the root agent with its tools and guardrail callbacks.

    Args:
        settings: The agent settings.

    Returns:
        The root agent.
    """
    return LlmAgent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=FailoverGemini(
            model=settings.gemini_model,
            fallback_models=settings.gemini_fallback_models,
            client_kwargs={
                "vertexai": True,
                "project": settings.project_id,
                "location": settings.gemini_location,
            },
        ),
        instruction=agent_instruction,
        tools=[
            build_toolbox(settings),
            *CHART_TOOLS,
            *build_map_tools(settings),
        ],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.0,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.LOW
            ),
        ),
        before_agent_callback=guardrails.before_agent,
        before_tool_callback=guardrails.before_tool,
        after_tool_callback=guardrails.after_tool,
        on_tool_error_callback=guardrails.on_tool_error,
        before_model_callback=telemetry.start_model_call,
        after_model_callback=[telemetry.log_model_call, complete_answer],
        on_model_error_callback=guardrails.on_model_error,
    )
