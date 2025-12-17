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

"""The watchlist agent"""

import os

from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient, auth_methods


def is_env_flag_enabled(var_name: str) -> bool:
    """
    Checks if an environment variable is set to a "true" value.

    This is a case-insensitive check for the values 'true' or '1'.

    Args:
      var_name: The name of the environment variable to check.

    Returns:
      True if the variable is set to 'true' or '1', False otherwise.
    """
    value = os.getenv(var_name)

    if not value:
        return False

    return value.lower() in ("true", "1")


URL = os.getenv("TOOLS_URL")
if is_env_flag_enabled("ENABLE_WATCHLIST_AGENT_ID_TOKEN_AUTH"):
    # Support for Cloud Run authentication
    auth_token_provider = auth_methods.aget_google_id_token(URL)
    toolbox = ToolboxSyncClient(
        URL, client_headers={"Authorization": auth_token_provider}
    )
else:
    toolbox = ToolboxSyncClient(URL)

# Load all the tools
bq_tools = toolbox.load_toolset("my_bq_toolset")
alloy_db_tools = toolbox.load_toolset("my_alloy_toolset")
tools = bq_tools + alloy_db_tools

watchlist_agent = Agent(
    name="watchlist_agent",
    model="gemini-2.5-flash",
    description=(
        "Agent to answer questions about which stocks are "
        "held within the users portfolio."
    ),
    instruction=(
        "You are a helpful agent who can manage the users "
        "portfolio watchlist, you may list, "
        "add, remove, and update items in the watchlist."
    ),
    tools=tools,
)
