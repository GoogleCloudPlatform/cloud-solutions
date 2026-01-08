"""Financial analyst agent."""

# Copyright 2025 Google LLC
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

import os

import google
import vertexai
from google.adk.agents import LlmAgent
from google.adk.planners import BuiltInPlanner
from google.adk.tools import AgentTool
from google.genai.types import ThinkingConfig

from . import prompt
from .sub_agents.data_analyst import data_analyst_agent
from .sub_agents.execution_analyst import execution_analyst_agent
from .sub_agents.forecasting_agent import forecasting_agent
from .sub_agents.news_analyst import (
    is_finnhub_api_key_defined,
    news_analyst_agent,
)
from .sub_agents.order_agent import order_agent
from .sub_agents.risk_analyst import risk_analyst_agent
from .sub_agents.sentiment_analyst import sentiment_analyst_agent
from .sub_agents.trading_analyst import trading_analyst_agent
from .sub_agents.watchlist_agent import watchlist_agent
from .utils import is_env_flag_enabled

LOCATION = "us-central1"

credentials, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", LOCATION)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
os.environ.setdefault("SHOW_THOUGHTS", "True")

vertexai.init(project=project_id, location=LOCATION)

MODEL = "gemini-2.5-pro"

financial_coordinator = LlmAgent(
    name="financial_coordinator",
    model=MODEL,
    description=(
        "guide users through a structured process to receive financial "
        "advice by orchestrating a series of expert subagents. help them "
        "analyze a market ticker, develop trading strategies, define "
        "execution plans, and evaluate the overall risk."
    ),
    instruction=prompt.FINANCIAL_COORDINATOR_PROMPT,
    output_key="financial_coordinator_output",
    planner=BuiltInPlanner(
        thinking_config=ThinkingConfig(
            include_thoughts=is_env_flag_enabled("SHOW_THOUGHTS")
        )
    ),
    tools=[
        AgentTool(agent=watchlist_agent),
        AgentTool(agent=data_analyst_agent),
        AgentTool(agent=trading_analyst_agent),
        AgentTool(agent=execution_analyst_agent),
        AgentTool(agent=risk_analyst_agent),
        AgentTool(agent=forecasting_agent),
        AgentTool(agent=order_agent),
        AgentTool(agent=sentiment_analyst_agent),
    ],
)

if is_finnhub_api_key_defined():
    financial_coordinator.tools.append(AgentTool(agent=news_analyst_agent))

root_agent = financial_coordinator
