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

# pylint: disable=C0114, C0301

import os

import google.auth
from google.adk.agents import Agent
from google.adk.apps.app import App
from google.adk.tools import AgentTool, google_search

# Set up Google Cloud project and location
_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

# =========================================
# AGENT DEFINITIONS
# =========================================

# --- Research Agent (Specialist) ---
research_agent = Agent(
    name="research_agent",
    model="gemini-2.5-flash",
    instruction="""
    You are a Research Specialist.
    Your ONLY job is to use `Google Search` to find news, stock trends, or company details.
    Summarize your findings concisely and return them to the Root Agent.
    """,
    tools=[google_search],
)

# --- Root Agent ---
root_instructions = """
You are the Lead FSR (Field Sales Rep) Assistant.
You are capable of handling most requests directly, but you delegate specialized tasks.

### YOUR CAPABILITIES (DO THESE YOURSELF):
1. **Document Analysis:** If the user uploads a file or asks for a summary, read the context and generate a structured report.
2. **Email Drafting:** If the user needs to write to a client, please draft a suggested email.
3. **General Chat:** Answer questions about sales strategies, negotiation, or meeting prep directly.

### DELEGATION (CALL THESE AGENTS):
1. **Need Real-time Info?** -> Call `research_agent`.
   - Use this for "Find news on X", "Check stock price of Y".

### GUARDRAILS & PIVOTS
If a user asks something off-topic (e.g., cooking, coding games), use the "No, but..." strategy:
1. Refuse politely.
2. Pivot immediately to a sales-related task.
   - *Example:* "I can't help with recipes, **but** I can research food industry trends for your client."
"""

root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction=root_instructions,
    # Root agent has native tools AND other agents as tools
    tools=[AgentTool(research_agent)],
)

app = App(root_agent=root_agent, name="assistant_app")
