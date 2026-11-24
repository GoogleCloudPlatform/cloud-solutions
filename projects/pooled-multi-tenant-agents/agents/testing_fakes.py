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

"""Lightweight hermetic ADK callback/tool carriers for offline simulations and unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MockADKCallbackContext:
    """Hermetic carrier matching the ADK 2.0 `CallbackContext` / `ToolContext` state contract.

    Attributes:
        state: Mutable session/invocation state dictionary (`temp:*`, `user:*`, `app:*`).
        agent: Active ADK agent descriptor or instance under test.
        active_tools: Optional list of active tool definitions exposed on the turn.
    """

    state: dict[str, object]
    agent: object
    active_tools: list[object] = field(default_factory=list)
