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

"""A2A Protocol v0.3.0 compliant Agent Card and Skill definitions."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_SPEC_PATH = Path(__file__).with_name("agent_card_spec.json")


class AgentSkill(BaseModel):
    """A2A protocol agent skill specification."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class AgentCapabilities(BaseModel):
    """A2A protocol capabilities flags."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    streaming: bool = False
    push_notifications: bool = Field(default=False, alias="pushNotifications")


class AgentCard(BaseModel):
    """A2A Protocol v0.3.0 Agent Card."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    description: str
    url: str
    version: str = "1.0.0"
    protocol_version: str = Field(default="0.3.0", alias="protocolVersion")
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    default_input_modes: list[str] = Field(
        default_factory=lambda: ["text/plain"],
        alias="defaultInputModes",
    )
    default_output_modes: list[str] = Field(
        default_factory=lambda: [
            "application/json",
            "text/plain",
        ],
        alias="defaultOutputModes",
    )
    skills: list[AgentSkill] = Field(default_factory=list)


@lru_cache
def _load_agent_card_spec() -> dict[str, Any]:
    """Load standard Agent Card specification from disk once."""
    return dict(json.loads(_SPEC_PATH.read_text(encoding="utf-8")))


def create_workflow_agent_card(base_url: str | None = None) -> AgentCard:
    """Factory creating the certified Oracle EBS Workflow Agent Card."""
    spec = dict(_load_agent_card_spec())
    if base_url:
        spec["url"] = base_url
    return AgentCard.model_validate(spec)
