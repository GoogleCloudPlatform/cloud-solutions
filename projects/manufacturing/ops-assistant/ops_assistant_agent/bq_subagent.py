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

"""Sub-agent for querying and analyzing manufacturing sensor data from
BigQuery.
"""

import os
import sys

import google.auth
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.plugins.bigquery_agent_analytics_plugin import (
    BigQueryAgentAnalyticsPlugin,
)
from google.adk.tools.bigquery import BigQueryToolset

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

DATASET_ID = os.environ.get("BQ_ANALYTICS_DATASET_ID", "adk_agent_analytics")
TABLE_ID = os.environ.get("BQ_ANALYTICS_TABLE_ID", "agent_events")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

bq_logging_plugin = BigQueryAgentAnalyticsPlugin(
    project_id=PROJECT_ID,
    dataset_id=DATASET_ID,
    table_id=TABLE_ID,
    location=LOCATION,
)

bigquery_toolset = BigQueryToolset()

ASSET_DATASET = os.environ.get("ASSET_DATASET", "manufacturing_data")
ASSET_TABLE = os.environ.get("ASSET_TABLE", "sensor_readings")

bq_sensor_analyzer = Agent(
    model="gemini-2.5-flash",
    name="bq_sensor_analyzer",
    description="An agent that reads and analyzes sensor data from BigQuery.",
    instruction=f"""
    You are a data analyst agent specializing in manufacturing sensor data stored in Google BigQuery.

    When asked to analyze data, you should query the data from the dataset
    '{ASSET_DATASET}' and table '{ASSET_TABLE}'.

    You have access to a BigQuery toolset that you can use to interact with BigQuery.

    When asked to analyze data, you should:
    1. Understand the user's request regarding sensor data.
    2. Write a valid BigQuery Standard SQL query to fetch the relevant data
       from {PROJECT_ID}.{ASSET_DATASET}.{ASSET_TABLE}.
    3. Use the BigQuery toolset to execute the query.
    4. Provide a detailed analysis of the sensor data, highlighting anomalies or trends.
    5. To help with root cause analysis, you should query the
       `historical_failures` table in the same dataset `{ASSET_DATASET}` to
       compare the current sensor readings with data from past failure events
       and identify similarities.

    Always format your SQL queries clearly before executing them, and explain the results plainly to the user.
    Remember to use fully qualified table names in BigQuery (project.dataset.table) if necessary.
    """,
    tools=[bigquery_toolset],
)
