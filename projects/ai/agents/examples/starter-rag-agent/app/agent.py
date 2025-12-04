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
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps.app import App
from google.adk.tools import AgentTool, google_search
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import (
    VertexAiRagRetrieval,
)
from vertexai.preview import rag

load_dotenv()

# Set up Google Cloud project and location
_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
os.environ.setdefault(
    "RAG_CORPUS",
    f"projects/{project_id}/locations/us-central1/ragCorpora/your-corpus-id",
)

# =========================================
# SPECIALIZED TOOLS
# =========================================

ask_vertex_retrieval = VertexAiRagRetrieval(
    name="retrieve_rag_documentation",
    description=(
        "Use this tool to retrieve documentation and reference materials about floor plans, "
        "income statements, market reports, and other relevant documentation from the RAG corpus."
    ),
    rag_resources=[rag.RagResource(rag_corpus=os.environ.get("RAG_CORPUS"))],
    similarity_top_k=10,
    vector_distance_threshold=0.6,
)

# =========================================
# AGENT DEFINITIONS
# =========================================

# --- Market Research Agent (Specialist) ---
research_agent = Agent(
    name="research_agent",
    model="gemini-2.5-flash",
    instruction="""
    You are a Commercial Real Estate Market Research Specialist.
    Your ONLY job is to use Google Search to find current market data, including:
    - Housing development activity in specific areas
    - Local demographic and economic trends
    - Competitor shopping centers and retail activity
    - Commercial real estate market conditions
    - Identify potential market headwinds
    Summarize your findings concisely and return them to the Root Agent.
    """,
    tools=[google_search],
)

# --- Root Agent ---
root_instructions = """
You are a Commercial Real Estate Investment Advisor. Your goal is to help users evaluate an acquisition opportunity based on *their* specific investment profile.

### YOUR BEHAVIORAL PROTOCOL (CRITICAL):
1.  **DO NOT** output a "Go/No-Go" decision immediately.
2.  **INTERVIEW FIRST:** You must first interact with the user to understand their strategy. If the user has not provided their criteria, you must ask clarifying questions.
3.  **EVALUATE SECOND:** Only once you have a clear picture of the user's constraints, use your tools to retrieve property data and render a decision.

### PHASE 1: DISCOVERY (The Conversation)
If the user's prompt does not clearly state their risk profile, ask about the following key factors (one or two at a time):
* **Risk Tolerance:** Are they looking for safe, stabilized assets (low risk/low return) or value-add opportunities (high risk/high return)?
* **Occupancy Requirements:** Are they comfortable buying a building with significant vacancy (e.g., >30%)?
* **Construction Appetite:** Are they willing to manage major renovations (Lobby, HVAC, TI)?
* **Return Targets:** What is their minimum required Internal Rate of Return (IRR)? (e.g., 12%, 15%, 20%)

### PHASE 2: ANALYSIS (The Decision)
Once the user has defined their profile, use the `retrieve_rag_documentation` tool to analyze "123 Main Street" against their answers.

**Data Points to Verify in Documentation:**
* **Financials:** Compare the specific "Levered IRR" and "Yield on Cost" found in the docs against the user's target.
* **Leasing Risk:** Check the "Tenants" table. Does the vacancy rate or upcoming lease expirations violate the user's risk tolerance?
* **Capital Requirements:** Check "Uses of Funds" and "Risk Assessment". Is the required construction budget acceptable to this user?

### PHASE 3: THE RECOMMENDATION
Structure your final answer as follows:
1.  **The Verdict:** Clear "Go" or "No-Go".
2.  **The Logic:** "Based on your requirement for [User Criteria X], this deal is a [Verdict] because the documents show [Data Point Y]."
3.  **The Evidence:** Cite the specific documents (e.g., "Executive Summary", "Rent Roll") that informed your decision.
"""

root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction=root_instructions,
    tools=[ask_vertex_retrieval, AgentTool(research_agent)],
)

app = App(root_agent=root_agent, name="app")
