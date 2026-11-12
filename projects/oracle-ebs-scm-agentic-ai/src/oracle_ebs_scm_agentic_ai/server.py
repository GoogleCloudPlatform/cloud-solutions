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

"""A2A server that exposes the VoltGuard agent to Gemini Enterprise.

The module uses the ADK built-in A2A server. Only answer text and chart and
map images leave the service. Tool calls, tool results, and model thoughts
stay internal. The tools save chart and map images to a Cloud Storage bucket,
and conversations expire from memory after an idle period.
"""

import json
import logging
import time
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any, Final

from a2a.client.card_resolver import parse_agent_card
from a2a.types import AgentCard
from a2a.types import Part as A2APart
from google.adk.a2a.converters.part_converter import (
    convert_genai_part_to_a2a_part,
)
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.a2a.executor.config import A2aAgentExecutorConfig
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.artifacts import GcsArtifactService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types
from oracle_ebs_scm_agentic_ai.agent import build_agent
from oracle_ebs_scm_agentic_ai.config import get_settings
from starlette.applications import Starlette

AGENT_CARD_PATH: Final[Path] = Path(__file__).parent / "agent_card.json"
PACKAGE_LOGGER: Final[str] = "oracle_ebs_scm_agentic_ai"
# Conversations idle for 2 hours expire, and at most 100 stay in memory.
SESSION_TTL_SECONDS: Final[float] = 2 * 60 * 60
MAX_SESSIONS: Final[int] = 100


@cache
def agent_card_spec() -> dict[str, Any]:
    """Load the A2A agent card template that the deploy script shares.

    Returns:
        The agent card fields.
    """
    spec: dict[str, Any] = json.loads(
        AGENT_CARD_PATH.read_text(encoding="utf-8")
    )
    return spec


def build_agent_card(public_url: str) -> AgentCard:
    """Build the served agent card for the public Cloud Run URL.

    Args:
        public_url: The agent's public Cloud Run URL.

    Returns:
        The agent card.
    """
    return parse_agent_card({**agent_card_spec(), "url": public_url})


def user_visible_part(part: types.Part) -> A2APart | None:
    """Convert a model part to A2A only when the user should see it.

    Args:
        part: The model part.

    Returns:
        The A2A part for answer text and images, or None for thoughts, tool
        calls, tool results, and code.
    """
    hidden = (
        part.thought
        or part.function_call is not None
        or part.function_response is not None
        or part.executable_code is not None
        or part.code_execution_result is not None
    )
    return None if hidden else convert_genai_part_to_a2a_part(part)


def build_executor(runner: Runner) -> A2aAgentExecutor:
    """Create the A2A executor with the user-facing part filter.

    Args:
        runner: The ADK runner of the agent.

    Returns:
        The A2A agent executor.
    """
    return A2aAgentExecutor(
        runner=runner,
        config=A2aAgentExecutorConfig(gen_ai_part_converter=user_visible_part),
    )


class ExpiringSessionService(InMemorySessionService):
    """In-memory sessions that expire when idle, up to a session limit.

    Before each new conversation, the service deletes sessions idle for
    longer than ``ttl_seconds`` and the oldest sessions beyond
    ``max_sessions``. It uses only the public session service API.
    """

    def __init__(
        self,
        ttl_seconds: float,
        max_sessions: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Set the expiry limits.

        Args:
            ttl_seconds: How long a session can stay idle before it expires.
            max_sessions: The largest number of sessions to keep.
            clock: Returns the current time in seconds since the epoch.
        """
        super().__init__()
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._clock = clock

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
        """Evict expired sessions, then create the new one.

        Args:
            app_name: The ADK app name.
            user_id: The user ID.
            state: The initial session state.
            session_id: The session ID, or None for a generated ID.

        Returns:
            The new session.
        """
        await self.evict(app_name)
        return await super().create_session(
            app_name=app_name,
            user_id=user_id,
            state=state,
            session_id=session_id,
        )

    async def evict(self, app_name: str) -> None:
        """Delete idle sessions and the oldest ones beyond the limit.

        The new session that follows counts toward the limit, so the method
        keeps at most ``max_sessions - 1`` sessions.

        Args:
            app_name: The ADK app name.
        """
        listed = await self.list_sessions(app_name=app_name)
        newest_first = sorted(
            listed.sessions,
            key=lambda session: session.last_update_time,
            reverse=True,
        )
        cutoff = self._clock() - self._ttl_seconds
        for index, session in enumerate(newest_first):
            if index >= self._max_sessions - 1 or (
                session.last_update_time < cutoff
            ):
                await self.delete_session(
                    app_name=app_name,
                    user_id=session.user_id,
                    session_id=session.id,
                )


def create_app() -> Starlette:
    """Build the Starlette A2A application that uvicorn serves.

    Returns:
        The A2A application.
    """
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger(PACKAGE_LOGGER).setLevel(logging.INFO)
    settings = get_settings()
    agent = build_agent(settings)
    runner = Runner(
        app_name=agent.name,
        agent=agent,
        session_service=ExpiringSessionService(
            SESSION_TTL_SECONDS, MAX_SESSIONS
        ),
        artifact_service=GcsArtifactService(
            bucket_name=settings.artifact_bucket
        ),
    )
    return to_a2a(
        agent,
        agent_card=build_agent_card(str(settings.a2a_public_url)),
        runner=runner,
        agent_executor_factory=build_executor,
    )
