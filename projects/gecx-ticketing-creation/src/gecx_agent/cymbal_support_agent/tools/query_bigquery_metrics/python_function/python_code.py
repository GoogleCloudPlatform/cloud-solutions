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

"""Module containing GECX python code logic."""

# pylint: skip-file

import json
from typing import Any, Dict


def query_bigquery_metrics() -> Dict[str, Any]:
    """
    Queries table robertortega-ai-demo.ds1.t1 by retrieving a short-lived
    OAuth2 token from the Google Cloud Metadata Server Bridge at runtime.
    """
    try:
        proj_res = ces_requests.get(
            url="http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
        )
        if proj_res.status_code == 200 and proj_res.text.strip():
            PROJECT_ID = proj_res.text.strip()
        else:
            return {
                "status": "PROJECT_RESOLUTION_ERROR",
                "details": "Could not determine GCP project ID from metadata server.",
            }
    except Exception as e:
        return {
            "status": "METADATA_CONNECT_ERROR",
            "details": f"Failed to connect to GCP metadata server: {e}",
        }

    DATASET_ID = "ds1"
    TABLE_ID = "t1"

    # 1. Fetch Ephemeral Access Token from the Metadata Server
    # Access tokens require the standard 'cloud-platform' authorization scope
    token_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
    token_headers = {"Metadata-Flavor": "Google"}

    try:
        token_response = ces_requests.get(url=token_url, headers=token_headers)
        if token_response.status_code != 200:
            return {
                "status": "METADATA_AUTH_FAILURE",
                "details": "Failed to retrieve sandbox execution identity token.",
            }

        access_token = token_response.json().get("access_token")
    except Exception as token_err:
        return {
            "status": "METADATA_SERVER_EXCEPTION",
            "error_msg": str(token_err),
        }

    # 2. Formulate BigQuery Job Request
    bq_url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT_ID}/queries"

    bq_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    sql_string = f"SELECT c1, c2, c3 FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` ORDER BY c3 DESC LIMIT 1"

    payload = {
        "query": sql_string,
        "useLegacySql": False,
        "maxResults": 1,
        "timeoutMs": 5000,
        "defaultDataset": {"datasetId": DATASET_ID, "projectId": PROJECT_ID},
    }

    # 3. Authenticated Egress Execution
    try:
        response = ces_requests.post(
            url=bq_url, headers=bq_headers, data=json.dumps(payload)
        )

        if response.status_code != 200:
            return {
                "status": "UPSTREAM_API_FAILURE",
                "http_status_code": response.status_code,
                "error_details": response.text,
            }

        return parse_bigquery_matrix(response.json())

    except Exception as e:
        return {"status": "SYSTEM_EXCEPTION", "error_msg": str(e)}


def parse_bigquery_matrix(bq_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely transforms the nested BigQuery REST API table array row schema
    into a clean flat-mapped dictionary format for direct agent consumption.
    """
    if "errors" in bq_json:
        return {"status": "SQL_EXECUTION_ERROR", "errors": bq_json["errors"]}

    if int(bq_json.get("totalRows", 0)) == 0:
        return {"status": "NO_RECORD_FOUND", "data": {}}

    columns = [field["name"] for field in bq_json["schema"]["fields"]]
    raw_cells = bq_json["rows"][0]["f"]
    parsed_record = {columns[i]: cell["v"] for i, cell in enumerate(raw_cells)}

    return {"status": "SUCCESS", "data": parsed_record}
