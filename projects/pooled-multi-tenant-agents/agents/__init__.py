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

# pylint: disable=line-too-long,undefined-all-variable

"""Cymbal SaaS Multi-Tenant Pooled Agents Package (Pattern A).

`root_agent` (the ADK entry point) is loaded lazily (PEP 562), so lightweight services that import
only a few modules from this package (e.g. the credential broker, ADR-0014 B4) never load ADK or
the agent code. Import agents from their modules (`agents.shared_diagnostic_agent`,
`agents.agent_alpha`).
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = ["root_agent"]


def __getattr__(name: str) -> Any:
    if name != "root_agent":
        raise AttributeError(f"module 'agents' has no attribute {name!r}")
    value = importlib.import_module(
        "agents.shared_diagnostic_agent"
    ).shared_diagnostic_agent
    globals()["root_agent"] = value
    return value
