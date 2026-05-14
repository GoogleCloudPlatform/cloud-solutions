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

"""Deployment script for the Ops Assistant Agent on Vertex AI Agent Engine."""

import os
import sys

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# pylint: disable=wrong-import-position
import logging

import vertexai
from dotenv import load_dotenv, set_key
from ops_assistant_agent.agent import root_agent
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

# pylint: enable=wrong-import-position

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
STAGING_BUCKET = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

ENV_FILE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)

vertexai.init(
    project=GOOGLE_CLOUD_PROJECT,
    location=GOOGLE_CLOUD_LOCATION,
    staging_bucket=STAGING_BUCKET,
)


# Function to update the .env file
def update_env_file(agent_engine_id, env_file_path):
    """Updates the .env file with the agent engine ID."""
    try:
        set_key(env_file_path, "AGENT_ENGINE_ID", agent_engine_id)
        print(
            f"Updated AGENT_ENGINE_ID in {env_file_path} to {agent_engine_id}"
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error updating .env file: {e}")


logger.info("deploying app...")

app = AdkApp(
    agent=root_agent,
    enable_tracing=True,
)

logging.debug("deploying agent to agent engine:")

remote_app = agent_engines.create(
    app,
    display_name="ops-assistant",
    requirements=[
        "google-cloud-aiplatform[adk,agent_engine]>=1.93.0",
        "google-cloud-bigquery>=3.20.0",
        "pydantic>=2.7.0",
        "google-auth>=2.30.0",
        "python-dotenv>=1.0.0",
    ],
    env_vars={
        "GOOGLE_GENAI_USE_VERTEXAI": os.getenv("GOOGLE_GENAI_USE_VERTEXAI"),
        "ASSET_DATASET": os.getenv("ASSET_DATASET"),
        "ASSET_TABLE": os.getenv("ASSET_TABLE"),
    },
)

# log remote_app
logging.info(
    "Deployed agent to Vertex AI Agent Engine successfully, "
    "resource name: %s",
    remote_app.resource_name,
)
