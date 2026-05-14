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

"""Main entry point and configuration for the Ops Assistant Agent."""

import os
import sys

import google.auth
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App

# Import sub-agents and plugins
from ops_assistant_agent.bq_subagent import (
    bq_logging_plugin,
    bq_sensor_analyzer,
)
from ops_assistant_agent.workorder_subagent import work_order_creator

load_dotenv()

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

credentials, PROJECT_ID = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

if not PROJECT_ID:
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

if not PROJECT_ID:
    print(
        "Warning: Could not determine GOOGLE_CLOUD_PROJECT from credentials "
        "or environment. Agent may fail.",
        file=sys.stderr,
    )

plugins = [bq_logging_plugin]

root_agent = Agent(
    model="gemini-2.5-flash",
    name="ops_assistant_agent",
    description=(
        "A top-level agent in a manufacturing setting that coordinates "
        "sensor analysis and work order creation."
    ),
    sub_agents=[bq_sensor_analyzer, work_order_creator],
    instruction="""
    You are the main Operations Assistant agent in a manufacturing facility.
    Your job is to help users monitor asset health, perform root cause analysis, and create work orders.

    You have access to two specialized sub-agents:
    1. `bq_sensor_analyzer`: Use this agent to read and analyze sensor data from BigQuery.
    2. `work_order_creator`: Use this agent to create work orders based on templates.

    Follow this workflow:
    1. If the user wants to check asset status or analyze sensor data, delegate to `bq_sensor_analyzer`.
    2. Based on the analysis provided by `bq_sensor_analyzer` (or details provided by the user), help the user perform root cause analysis. Ask clarifying questions to narrow down the problem.
    3. Once the root cause is identified and a solution is proposed, delegate to `work_order_creator` to create a work order.

    Do not answer technical questions about BigQuery or work order templates yourself; always delegate to the appropriate sub-agent.
    """,
)

app = App(
    name="ops_assistant_agent",
    root_agent=root_agent,
    plugins=plugins,
)
