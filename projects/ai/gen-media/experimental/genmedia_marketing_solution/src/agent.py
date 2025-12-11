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

"""
GenMedia Marketing Solution.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Application-specific imports
from .context.betty_context import load_merchant_profile
from .marketing_solutions.generate_trends.get_bakery_trends import (
    get_bakery_trends,
)
from .prompt import MARKETING_AGENT_INSTRUCTION
from .tools import cmo_tools, state_tools

# ====================================================================
# 1. CONFIGURATION & SETUP
# ====================================================================

# --- Load Environment Variables ---
load_dotenv()

# --- Model & Critical Configuration ---
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME")
if not MODEL_NAME:
    print(
        "CRITICAL ERROR: GEMINI_MODEL_NAME environment variable not set.",
        file=sys.stderr,
    )
    sys.exit(1)

# --- Logging Configuration ---
APP_LOG_FILE = os.getenv("APP_LOG_FILE", "app.log")
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(
    level=LOG_LEVEL, format=LOG_FORMAT, filename=APP_LOG_FILE, filemode="w"
)

logger = logging.getLogger(__name__)

# ====================================================================
# 2. MARKETING AGENT
# ====================================================================


class MarketingAgent:
    """
    The MarketingAgent is the main orchestrator of the marketing workflow.

    This agent is responsible for executing a series of marketing tasks,
    including:
    - Analyzing market trends
    - Generating marketing collateral (images, video/Music, and text content)
    - Creating customer segments and outreach strategies
    - Compiling all generated assets into a final marketing document.

    The agent leverages a set of tools to perform these tasks and interacts
    with the user for approval at key stages of the process.
    """

    DEFAULT_USER_NAME = "Betty"
    DEFAULT_BUSINESS_NAME = "Betty's Bakery"

    def __init__(self):
        """
        Initializes the MarketingAgent, setting up the core LLM agent with
        its configuration.

        This constructor configures the `LlmAgent` with a specific model,
        instructions, and a suite of tools necessary for the marketing
        workflow. Each tool is a Python function decorated to be callable
        by the agent.

        **Tools Available to the Agent:**
        - `get_bakery_trends`: Scans a BigQuery dataset for emerging
          bakery trends.
        - `generate_marketing_image`: Creates a promotional image using
          a Nano Banana or Imagen 4.
        - `generate_marketing_video`: Produces a short promotional video
          using Veo for video and Lyria for music.
        - `generate_marketing_content`: Drafts compelling marketing copy,
          including social media posts and email campaigns.
        - `create_customer_segment`: Analyzes business data to identify and
          define a target customer segment.
        - `generate_outreach_strategy`: Formulates a strategy for engaging
          the defined customer segment.
        - `create_marketing_document`: Compiles all generated assets and
          strategies into a cohesive PDF marketing plan.
        - `draft_and_send_email`: Composes and dispatches an email to the
          user for notification or approval.
        - `update_state`: A utility tool for the agent to save, update, or
          remove data from its internal state.
        """
        self.agent = LlmAgent(
            name="MarketingAgent",
            model=MODEL_NAME,
            description=(
                "A marketing agent that can generate trends, images, videos,"
                "and content."
            ),
            instruction=MARKETING_AGENT_INSTRUCTION,
            tools=[
                get_bakery_trends,
                cmo_tools.generate_marketing_image,
                cmo_tools.generate_marketing_video,
                cmo_tools.generate_marketing_content,
                cmo_tools.create_customer_segment,
                cmo_tools.generate_outreach_strategy,
                cmo_tools.create_marketing_document,
                cmo_tools.draft_and_send_email,
                state_tools.update_state,
            ],
            before_agent_callback=self.before_agent_starts_callback,
            after_agent_callback=self.after_agent_completes_callback,
        )

        self._runner = Runner(
            agent=self.agent,
            app_name="MarketingAgentApp",
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            artifact_service=InMemoryArtifactService(),
        )

    async def _extract_business_details(
        self, profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Safely extracts and transforms key business details from a raw
        profile data dictionary.

        Args:
            profile_data: A dictionary, typically loaded from a JSON or
                          similar source, containing the merchant's profile
                          information. Expected keys include
                          `merchant_account`, `owner_profile`, and
                          `business_profile`.

        Returns:
            A dictionary containing cleanly extracted business details:
            - `user_name`: The first name of the business owner
              (e.g., "Betty").
            - "business_name": The registered name of the business
              (e.g., "Betty's Bakery").
            - `merchant_id`: The unique identifier for the merchant account.
            - `website`: The official website URL of the business.
        """
        merchant_account = profile_data.get("merchant_account", {})
        owner_profile = merchant_account.get("owner_profile", {})
        business_details = merchant_account.get("business_profile", {})

        return {
            "user_name": owner_profile.get(
                "first_name", self.DEFAULT_USER_NAME
            ),
            "business_name": business_details.get(
                "doing_business_as", self.DEFAULT_BUSINESS_NAME
            ),
            "merchant_id": merchant_account.get("merchant_id"),
            "website": business_details.get("website"),
        }

    async def before_agent_starts_callback(
        self, callback_context: CallbackContext
    ) -> None:
        """Injects context into the state before the agent runs."""
        state = callback_context.state

        PROFILE_KEY = "business_profile_data"
        if PROFILE_KEY not in state:
            profile = load_merchant_profile()
            state[PROFILE_KEY] = profile
            logger.info(
                "User profile loaded for session: %s",
                callback_context.session.id
            )

        extracted_details = await self._extract_business_details(
            state[PROFILE_KEY]
        )
        state.update(extracted_details)

        state["current_datetime"] = datetime.now().isoformat()

    async def after_agent_completes_callback(
        self, callback_context: CallbackContext
    ) -> Dict[str, Any]:
        """Placeholder for logic after the agent completes its turn."""
        logger.info("MarketingAgent turn completed.")
        return callback_context.state

# ====================================================================
# 3. INSTANCE CREATION
# ====================================================================

marketing_agent_instance = MarketingAgent()
root_agent = marketing_agent_instance.agent
