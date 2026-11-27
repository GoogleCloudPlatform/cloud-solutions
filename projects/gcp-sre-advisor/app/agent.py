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

"""Root ADK coordinator agent and App instance definition."""

from google.adk.agents import LlmAgent
from google.adk.apps import App

from . import config, prompts
from .sub_agents import (
    build_specialist_agents,
    cap_specialist_tool_response,
    strip_tool_response_schemas,
)
from .tools.catalog_tools import (
    activate_live_catalog_application,
    activate_zero_profile_discovery,
    get_active_profile_drift_baseline,
    list_workload_profiles,
    select_workload_profile,
)
from .tools.mcp_registry import (
    build_external_catalog_mcp,
    build_managed_mcp_toolsets,
)
from .tools.sweep_tool import waf_six_pillar_parallel_sweep

root_agent = LlmAgent(
    name="gcp_sre_advisor",
    model=config.ORCHESTRATOR_MODEL,
    generate_content_config=config.ORCHESTRATOR_GEN_CONFIG,
    description=(
        "Multi-agent Site Reliability Engineering and Cloud Architecture "
        "advisor aligned with the six pillars of the Google Cloud "
        "Architecture Framework across live application catalogs, declarative "
        "workload profiles, and live Google Cloud project discovery."
    ),
    instruction=prompts.ORCHESTRATOR_INSTRUCTION,
    sub_agents=build_specialist_agents(),
    tools=[
        list_workload_profiles,
        select_workload_profile,
        activate_zero_profile_discovery,
        activate_live_catalog_application,
        get_active_profile_drift_baseline,
        waf_six_pillar_parallel_sweep,
        *build_managed_mcp_toolsets("resourcemanager"),
        *build_external_catalog_mcp(),
    ],
    before_model_callback=strip_tool_response_schemas,
    after_tool_callback=cap_specialist_tool_response,
)

app = App(
    name="app",
    root_agent=root_agent,
)
