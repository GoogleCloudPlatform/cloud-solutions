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

"""Shared fixtures: environment settings and lightweight ADK context fakes.

The fakes implement only the attributes the callbacks and chart tools use,
so unit tests run without Gemini, the MCP Toolbox, Oracle EBS, or BigQuery.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from google.adk.events import Event, EventActions
from google.genai import types
from oracle_ebs_scm_agentic_ai.config import (
    Settings,
    get_settings,
    load_settings,
)

# Public example URL signing secret from the Google Maps Platform URL signing
# documentation, never a real one.
DOCS_URL_SIGNER = "vNIXE0xscrmjlyV-12Nj_BvUPaw="

TEST_ENVIRONMENT: dict[str, str] = {
    "GOOGLE_CLOUD_PROJECT": "test-project",
    "GEMINI_MODEL": "gemini-test-flash",
    "GEMINI_FALLBACK_MODELS": "gemini-test-fallback, gemini-test-lite",
    "GEMINI_LOCATION": "global",
    "MCP_SERVER_URL": "https://ebs-mcp-toolbox.example.run.app/mcp",
    "A2A_PUBLIC_URL": "https://voltguard-scm-agent.example.run.app",
    "MCP_TIMEOUT_SECONDS": "60",
    "MAPS_STATIC_API_KEY": "test-maps-static-key",
    "MAPS_STATIC_SIGNING_SECRET": DOCS_URL_SIGNER,
    "ARTIFACT_BUCKET": "test-project-voltguard-artifacts",
}

HUB_ROWS: list[dict[str, Any]] = [
    {"organization_code": "ATL", "available_to_transact_qty": 40},
    {"organization_code": "ORD", "available_to_transact_qty": 40},
    {"organization_code": "DAL", "available_to_transact_qty": 250},
    {"organization_code": "MIA", "available_to_transact_qty": 190},
    {"organization_code": "EWR", "available_to_transact_qty": 25},
    {"organization_code": "PHX", "available_to_transact_qty": 150},
]


def user_message(text: str) -> types.Content:
    """Build a user message content."""
    return types.Content(role="user", parts=[types.Part(text=text)])


@dataclass
class FakeSession:
    """Session holding the events of the conversation."""

    events: list[Event] = field(default_factory=list)


@dataclass
class FakeContext:
    """Stand-in for ADK ToolContext and CallbackContext."""

    user_content: types.Content | None = None
    invocation_id: str = "inv-1"
    session: FakeSession = field(default_factory=FakeSession)
    artifacts: dict[str, list[types.Part]] = field(default_factory=dict)
    state: Any = field(default_factory=dict)

    async def save_artifact(self, filename: str, artifact: types.Part) -> int:
        versions = self.artifacts.setdefault(filename, [])
        versions.append(artifact)
        version = len(versions) - 1
        self.session.events.append(
            Event(
                author="voltguard_scm_agent",
                invocation_id=self.invocation_id,
                actions=EventActions(artifact_delta={filename: version}),
            )
        )
        return version

    async def load_artifact(
        self, filename: str, version: int | None = None
    ) -> types.Part | None:
        versions = self.artifacts.get(filename, [])
        if not versions:
            return None
        return versions[-1 if version is None else version]


@dataclass
class FakeTool:
    """Stand-in for an ADK tool with a name."""

    name: str


@pytest.fixture(name="settings")
def fixture_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Provide test settings through the environment."""
    for name, value in TEST_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield load_settings(TEST_ENVIRONMENT)
    get_settings.cache_clear()


@pytest.fixture(name="hub_rows_json")
def fixture_hub_rows_json() -> str:
    """ATT by hub rows as returned by the SQL tool."""
    return json.dumps(HUB_ROWS)
