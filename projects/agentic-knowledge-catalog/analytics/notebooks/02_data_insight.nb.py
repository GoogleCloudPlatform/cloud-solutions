# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% id="0577165b"
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

# %% [markdown] id="238c405e"
# # Automated Table & Column Documentation via BigQuery Data Insights
#
# This notebook leverages **Gemini in BigQuery (Data Insights)** automation APIs to automatically generate comprehensive natural language descriptions for all tables and columns in `thelook_ecommerce` and synchronize them with the BigQuery catalog.
#
# ### Learning Objectives
# 1. **Data Insights Generation**: Use LLMs to analyze table schemas and data distributions, generating concise natural language descriptions.
# 2. **Catalog Synchronization**: Automatically push generated descriptions into BigQuery table and column metadata fields.
# 3. **Recommended Queries**: Discover AI-generated analytical SQL queries tailored to uncover key patterns in the underlying dataset.
# 4. **Governance Labeling**: Attach standardized metadata labels (`dataplex-dp-*`, `dataplex-dq-*`, `dataplex-data-*-published-*`) to track documentation lifecycle states.
#
# ---
#
# ### [Pre-Execution Console Inspection]
# Before running this notebook, inspect the `users` table in the BigQuery Studio console:
# - **Schema Tab**: Notice that the Description field for all columns is empty.
# - **Insights Tab**: Displays "Insights have not yet been generated" with an unpopulated recommendation view.
#

# %% [markdown] id="c62f90c4"
# ## Step 1: Environment Setup

# %% id="391f2a80"
# [Qwiklabs Environment] If you encounter an HTTP Error 401 (Invalid authentication credentials) during Dataplex API calls,
# uncomment and run the line below to perform manual authentication:
# # !gcloud auth application-default login --no-launch-browser --quiet

import json
import ssl
import time
import urllib.error
import urllib.request

import google.auth
from google.auth.transport.requests import AuthorizedSession, Request
from google.cloud import bigquery

_, PROJECT_ID = google.auth.default()
DATASET_ID = "thelook_ecommerce"

bq_client = bigquery.Client(project=PROJECT_ID)
try:
    LOCATION = bq_client.get_dataset(DATASET_ID).location
except Exception:
    LOCATION = "us-central1"

credentials, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
authed_session = AuthorizedSession(credentials)

print(
    f"Active Project ID: {PROJECT_ID}, Dataset: {DATASET_ID}, Location: {LOCATION}"
)
print("Environment and authentication initialized successfully!")

# %% [markdown] id="f7791da4"
# ## Step 2: Define Common API Helper Functions

# %% id="5af169f8"
# [Common Utility] Knowledge Catalog REST API request helper


def make_rest_request(url, method="GET", body_dict=None, max_retries=5):
    retries = 0
    backoff = 2

    while True:
        try:
            if method == "GET":
                response = authed_session.get(url, timeout=60)
            elif method == "POST":
                response = authed_session.post(url, json=body_dict, timeout=60)
            elif method == "DELETE":
                response = authed_session.delete(url, timeout=60)
            else:
                response = authed_session.request(
                    method, url, json=body_dict, timeout=60
                )

            if response.status_code >= 400:
                if response.status_code == 429 and retries < max_retries:
                    print(
                        f"  [429 Quota Exceeded] Retrying in {backoff}s (Attempt {retries + 1}/{max_retries})..."
                    )
                    time.sleep(backoff)
                    retries += 1
                    backoff *= 2
                    continue
                raise Exception(
                    f"HTTP Error {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            if "HTTP Error" in str(e):
                raise e
            if retries < max_retries:
                time.sleep(backoff)
                retries += 1
                backoff *= 2
                continue
            raise e


# %% [markdown] id="e918d816"
# ## Step 3: Manage and Monitor Knowledge Catalog DataScans

# %% id="a0303cad"
def get_or_create_datascan(table_id):
    """
    Retrieves the DATA_DOCUMENTATION DataScan for the target table, or creates a new one if not found.
    """
    scan_id = f"ds-thelook-{table_id}".lower().replace("_", "-")
    get_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans/{scan_id}"

    try:
        scan = make_rest_request(get_url, method="GET")
        print(f"  -> Found existing DataScan: {scan_id}")
        return scan_id
    except Exception as e:
        if "404" in str(e):
            print(f"  -> Creating new DataScan: {scan_id}...")
            create_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans?dataScanId={scan_id}"
            body = {
                "data": {
                    "resource": f"//bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{DATASET_ID}/tables/{table_id}"
                },
                "executionSpec": {"trigger": {"onDemand": {}}},
                "type": "DATA_DOCUMENTATION",
                "dataDocumentationSpec": {"catalogPublishingEnabled": True},
            }
            operation = make_rest_request(
                create_url, method="POST", body_dict=body
            )
            op_name = operation["name"]

            while True:
                op_status = make_rest_request(
                    f"https://dataplex.googleapis.com/v1/{op_name}",
                    method="GET",
                )
                if op_status.get("done"):
                    if "error" in op_status:
                        raise Exception(
                            f"DataScan creation failed: {op_status['error']}"
                        )
                    break
                time.sleep(2)
            print(f"  -> DataScan created successfully: {scan_id}")
            return scan_id
        else:
            raise e


def run_datascan_and_wait(scan_id):
    """
    Runs a DataScan job and polls status until completion.
    """
    run_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans/{scan_id}:run"
    print(f"  -> Requesting DataScan execution...")
    run_res = make_rest_request(run_url, method="POST")

    job_name = run_res["job"]["name"]
    job_id = run_res["job"]["uid"]
    print(f"  -> Execution Job ID: {job_id} (Waiting for completion...)")

    job_url = f"https://dataplex.googleapis.com/v1/{job_name}?view=FULL"
    while True:
        job = make_rest_request(job_url, method="GET")
        state = job.get("state")
        print(f"     [Polling] Current state: {state}")

        if state == "SUCCEEDED":
            print("  -> Descriptions generated successfully!")
            break
        elif state in ["FAILED", "CANCELLED"]:
            raise Exception(f"DataScan Job failed: {state}")

        time.sleep(10)


def trigger_datascan(scan_id):
    """
    Triggers a DataScan execution job and immediately returns the job name without waiting.
    """
    run_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans/{scan_id}:run"
    run_res = make_rest_request(run_url, method="POST")
    return run_res["job"]["name"]


# %% [markdown] id="7e726ccd"
# ## Step 4: Extract Metadata and Synchronize to BigQuery

# %% id="c14cb5e1"
def fetch_generated_descriptions(table_id):
    """
    Queries Knowledge Catalog Entry API to retrieve generated descriptions aspect data.
    """
    entry_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{DATASET_ID}/tables/{table_id}?view=ALL"
    entry_data = make_rest_request(entry_url, method="GET")

    aspects = entry_data.get("aspects", {})
    desc_key = [k for k in aspects.keys() if "descriptions" in k]
    if not desc_key:
        print(f"  -> [{table_id}] Descriptions aspect not found.")
        return None

    return aspects[desc_key[0]]["data"]


def apply_and_publish_descriptions(table_id, desc_data):
    """
    Synchronizes generated descriptions into BigQuery table and column metadata,
    and attaches official publishing labels to the table.
    """
    if not desc_data:
        return

    table_ref = bq_client.dataset(DATASET_ID).table(table_id)
    table = bq_client.get_table(table_ref)

    # 1. Update table description
    table.description = desc_data.get("description", table.description)

    # 2. Update column descriptions
    fields_desc = {
        f["name"]: f["description"] for f in desc_data.get("fields", [])
    }
    new_schema = []

    for field in table.schema:
        description = fields_desc.get(field.name, field.description)
        new_field = bigquery.SchemaField(
            name=field.name,
            field_type=field.field_type,
            mode=field.mode,
            description=description,
            fields=field.fields,
        )
        new_schema.append(new_field)

    table.schema = new_schema

    # 3. Add official documentation publishing labels
    labels = dict(table.labels or {})
    scan_id = f"ds-thelook-{table_id}".lower().replace("_", "-")
    labels["dataplex-data-documentation-published-scan"] = scan_id
    labels["dataplex-data-documentation-published-project"] = PROJECT_ID
    labels["dataplex-data-documentation-published-location"] = LOCATION
    table.labels = labels

    # 4. Commit updates to BigQuery
    bq_client.update_table(table, ["description", "schema", "labels"])
    print(
        f"  [SUCCESS] Successfully applied descriptions to table '{table_id}'!"
    )


# %% [markdown] id="a0060963"
# ## Step 5: Single Table Test & Verification

# %% id="13be97e6"
# Test table for single execution verification
TEST_TABLE = "distribution_centers"

print(f"=== [{TEST_TABLE}] Data Insights Description Generation Test ===")

# 1. Reset existing descriptions and inject English generation directive
t_ref = bq_client.dataset(DATASET_ID).table(TEST_TABLE)
table = bq_client.get_table(t_ref)
table.description = (
    "Generate table and column descriptions using the English language"
)
new_schema = []
for field in table.schema:
    new_schema.append(
        bigquery.SchemaField(
            name=field.name,
            field_type=field.field_type,
            mode=field.mode,
            description=None,
            fields=field.fields,
        )
    )
table.schema = new_schema
bq_client.update_table(table, ["description", "schema"])
print(f"  -> Reset column descriptions on {TEST_TABLE} (Ready for test)")

# 2. Retrieve or create DataScan resource
scan_id = get_or_create_datascan(TEST_TABLE)

# 3. Execute DataScan and wait for completion (approx. 1 min)
run_datascan_and_wait(scan_id)

# 4. Fetch generated descriptions from Knowledge Catalog Aspect
desc_data = fetch_generated_descriptions(TEST_TABLE)

# 5. Apply descriptions and labels to BigQuery
apply_and_publish_descriptions(TEST_TABLE, desc_data)

print("\nTest completed! Check the schema and descriptions in BigQuery Studio.")

# %% [markdown] id="8abee0ce"
# ## Step 6: Batch Execution Pipeline

# %% id="48cfb403"
# [Main Pipeline] Batch Data Insights execution across all tables
# Triggers DataScan jobs concurrently across all tables and synchronizes descriptions into BigQuery.

ALL_TABLES = [
    "users",
    "orders",
    "order_items",
    "products",
    "events",
    "inventory_items",
]

print(
    "=== [Batch Pipeline: Generate English Data Insights Descriptions (Async)] ==="
)

active_jobs = {}  # {job_name: table_id}

for t_id in ALL_TABLES:
    print(f"\n=====================[ Preparing: {t_id} ]=====================")
    try:
        # 1. Inject English Language Guide directive into table description
        t_ref = bq_client.dataset(DATASET_ID).table(t_id)
        table = bq_client.get_table(t_ref)
        table.description = (
            "Generate table and column descriptions using the English language"
        )
        bq_client.update_table(table, ["description"])

        # 2. Retrieve or create DataScan resource
        scan_id = get_or_create_datascan(t_id)

        # 3. Trigger asynchronous execution
        job_name = trigger_datascan(scan_id)
        active_jobs[job_name] = t_id

        print(f"  -> '{t_id}' table description generation job triggered.")
        time.sleep(3)

    except Exception as e:
        print(f"  [Error] Failed to trigger '{t_id}': {e}")

total_triggered = len(active_jobs)
print(
    f"\nTriggered {total_triggered} data insight scan jobs concurrently. Starting progress monitoring."
)
print(
    "(Notifications display upon completion; progress summaries print every 30 seconds.)\n"
)

completed_tables = []

while active_jobs:
    status_summary = {
        "PENDING": 0,
        "RUNNING": 0,
        "SUCCEEDED": 0,
        "FAILED": 0,
        "CANCELLED": 0,
    }

    for job_name in list(active_jobs.keys()):
        job_url = f"https://dataplex.googleapis.com/v1/{job_name}"
        try:
            job = make_rest_request(job_url, method="GET")
            state = job.get("state", "UNKNOWN")

            status_summary[state] = status_summary.get(state, 0) + 1

            if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                t_id = active_jobs[job_name]
                print(
                    f"  [Done] '{t_id}' description generation completed (Result: {state})"
                )

                if state == "SUCCEEDED":
                    completed_tables.append(t_id)

                del active_jobs[job_name]
        except Exception as e:
            pass

    if active_jobs:
        running_cnt = status_summary.get("RUNNING", 0) + status_summary.get(
            "PENDING", 0
        )
        succeeded_cnt = (
            total_triggered
            - len(active_jobs)
            - status_summary.get("FAILED", 0)
            - status_summary.get("CANCELLED", 0)
        )

        print(
            f"[Status] Running: {running_cnt} | Succeeded: {succeeded_cnt} | Failed: {status_summary.get('FAILED', 0)}",
            end="\r",
        )
        time.sleep(30)

print(
    "\n\n=== [All table descriptions generated. Starting BigQuery metadata synchronization.] ==="
)

# 4 & 5. Fetch generated descriptions and apply to BigQuery
for t_id in completed_tables:
    try:
        print(
            f" -> [{t_id}] Fetching generated descriptions and applying to BigQuery schema..."
        )
        desc_data = fetch_generated_descriptions(t_id)
        apply_and_publish_descriptions(t_id, desc_data)
    except Exception as e:
        print(f"  [Error] [{t_id}] Schema update failed: {e}")

print(
    "\n=== [Batch Data Insights Generation and BigQuery Synchronization Completed] ==="
)

# %% [markdown]
# ## Step 5: Post-Execution Console UI & Metadata Verification
#
# After notebook execution completes, return to the BigQuery Studio console and refresh the `users` table details to verify the following:
#
# ### 1. Schema & Column Descriptions
# - **Table Description**: An overarching summary detailing that the table contains demographic, geographic, and behavioral data for eCommerce customers.
# - **View Column Descriptions**: Every column (`id`, `first_name`, `email`, `age`, `gender`, etc.) now contains an accurate description explaining its business context.
#
# ### 2. Recommended Analytical Queries in the Insights Tab
# Navigate to the **Insights** tab of the `users` table to review the automatically synthesized exploratory queries:
# - **Query 1**: Analyzes covariance between age and latitude across acquisition traffic sources.
# - **Query 2**: Evaluates the Pearson correlation between user creation timestamp and longitude to analyze geographical adoption trends over time.
#
# ### 3. Details Tab Metadata Labels
# - **Description**: The table description is permanently persisted in the Table Info section.
# - **Labels Section**:
#   - `dataplex-dp-published-scan`: `dp-thelook-users` (links the profile scan to BigQuery Studio's **Data Profile** tab)
#   - `dataplex-dq-published-scan`: `dq-thelook-users` (links the quality scan to BigQuery Studio's **Data Quality** tab)
#   - `dataplex-data-documentation-published-scan`: Generated Data Documentation scan ID
#   - `dataplex-*-published-location`: Target deployment region
#   - `dataplex-*-published-project`: Google Cloud project ID
#   - These labels serve as verifiable signals confirming that the table has undergone complete automated governance profiling and catalog publishing.
#
