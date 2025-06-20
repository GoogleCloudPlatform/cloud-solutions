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

"""Utility functions for interacting with Google BigQuery."""

from utils.const import SOLUTION_TAG
from google.api_core.client_info import ClientInfo
from google.cloud import bigquery

def execute_bq_query(sql_query: str) -> list[dict]:
    """
    Executes a SQL query against a BigQuery dataset
    and returns the results as a list of dictionaries.

    Args:
        sql_query: The SQL query string to execute.
    Returns:
        A list of dictionaries, where each dictionary represents a row and
        keys are column names, or an empty list if an error
        occurs or no results.
    """
    client = bigquery.Client(
        client_info=ClientInfo(user_agent=SOLUTION_TAG)
    )

    if "```" in sql_query:
        sql_query = sql_query.lstrip("```sql").rstrip("```")
    try:
        query_job = client.query(sql_query)  # API request

        # Wait for the query to complete
        results = query_job.result()  # Waits for job to complete.

        # Fetch results and convert to a list of dictionaries
        rows_as_dicts = []
        for row in results:
            rows_as_dicts.append(dict(row))

        print(
            f"Query executed successfully. Fetched {len(rows_as_dicts)} rows."
        )
        return rows_as_dicts

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error executing BigQuery query: {e}")
        print(f"Query: {sql_query}")
        return []
