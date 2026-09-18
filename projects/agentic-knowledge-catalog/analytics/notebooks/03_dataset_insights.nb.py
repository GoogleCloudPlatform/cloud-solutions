# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %%
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

# %% [markdown]
# # Dataset Insights: Holistic Dataset Summarization & Relationship Discovery
#
# This notebook expands beyond individual table boundaries to analyze the multi-table architecture of the entire `thelook_ecommerce` dataset, generating an overarching business summary and inferring cross-table entity relationships.
#
# ### Learning Objectives
# 1. **Dataset-Level Summarization**: Generate a high-level operational summary describing the entire dataset's business domain.
# 2. **Entity Relationship Inference**: Leverage LLMs to discover logical and physical foreign key relationships across disparate tables.
# 3. **Governance Integration**: Synchronize inferred relationship metadata into the BigQuery catalog to serve as contextual knowledge for conversational agents.
#
# ---
#
# ### [Pre-Execution Console Inspection]
# Before running this notebook, navigate to the `thelook_ecommerce` dataset in the BigQuery Studio Explorer panel and select the **Insights** tab:
# - Notice the placeholder message: "Insights have not yet been generated."
#

# %% [markdown]
# ## Step 1: Environment Setup

# %%
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
print("Environment initialized successfully!")

# %% [markdown]
# ## Step 2: Define Common API Helper Functions

# %%
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


# %% [markdown]
# ## Step 3: Manage Dataset DataScan and Extract Metadata

# %%
def get_or_create_dataset_datascan(dataset_id):
    """
    Retrieves the DATA_DOCUMENTATION DataScan for the target dataset, or creates a new one if not found.
    """
    scan_id = f"ds-{dataset_id}".lower().replace("_", "-")
    get_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans/{scan_id}"

    try:
        scan = make_rest_request(get_url, method="GET")
        print(f"  -> Found existing Dataset DataScan: {scan_id}")
        return scan_id
    except Exception as e:
        if "404" in str(e):
            print(f"  -> Creating new Dataset DataScan: {scan_id}...")
            create_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans?dataScanId={scan_id}"
            body = {
                "data": {
                    "resource": f"//bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{dataset_id}"
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
                            f"Dataset DataScan creation failed: {op_status['error']}"
                        )
                    break
                time.sleep(2)
            print(f"  -> Dataset DataScan created successfully: {scan_id}")
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
            raise Exception(f"DataScan Job error: {state}")

        time.sleep(10)


def fetch_dataset_generated_description(dataset_id):
    """
    Queries Knowledge Catalog Entry API to retrieve generated descriptions aspect data for the dataset.
    """
    entry_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{dataset_id}?view=ALL"
    entry_data = make_rest_request(entry_url, method="GET")

    aspects = entry_data.get("aspects", {})
    desc_key = [k for k in aspects.keys() if "descriptions" in k]
    if not desc_key:
        print(f"  -> [{dataset_id}] Descriptions aspect not found.")
        return None

    return aspects[desc_key[0]]["data"]


def apply_and_publish_dataset_description(dataset_id, desc_data):
    """
    Synchronizes generated descriptions into BigQuery dataset metadata,
    and attaches official publishing labels to the dataset.
    """
    if not desc_data:
        return

    dataset_ref = bq_client.dataset(dataset_id)
    dataset = bq_client.get_dataset(dataset_ref)

    # 1. Update dataset description
    dataset.description = desc_data.get("description", dataset.description)

    # 2. Add official documentation publishing labels
    labels = dict(dataset.labels or {})
    scan_id = f"ds-{dataset_id}".lower().replace("_", "-")
    labels["dataplex-data-documentation-published-scan"] = scan_id
    labels["dataplex-data-documentation-published-project"] = PROJECT_ID
    labels["dataplex-data-documentation-published-location"] = LOCATION
    dataset.labels = labels

    # 3. Commit updates to BigQuery
    bq_client.update_dataset(dataset, ["description", "labels"])
    print(
        f"  [SUCCESS] Successfully applied descriptions to dataset '{dataset_id}'!"
    )


# %% [markdown]
# ## Step 4: Extract Metadata and Synchronize to BigQuery

# %%
# Main execution pipeline
print(f"=== Automated Dataset Documentation Pipeline: {DATASET_ID} ===")

# 0. Inject English language directive
dataset_ref = bq_client.dataset(DATASET_ID)
dataset = bq_client.get_dataset(dataset_ref)
dataset.description = "Generate dataset descriptions using the English language"
bq_client.update_dataset(dataset, ["description"])
print(
    f"  -> Injected English generation directive into dataset '{DATASET_ID}'."
)

# 1. Create or retrieve Dataset DataScan
scan_id = get_or_create_dataset_datascan(DATASET_ID)

# 2. Run DataScan and wait for completion
run_datascan_and_wait(scan_id)

# 3. Fetch generated descriptions
desc_data = fetch_dataset_generated_description(DATASET_ID)

if desc_data:
    print(f"\n[Generated Dataset Description Summary]")
    print(f" - Description: {desc_data.get('description')}")

    # 4. Apply to BigQuery dataset
    apply_and_publish_dataset_description(DATASET_ID, desc_data)
else:
    print("Could not retrieve generated description data.")

print(f"\n=== Automated Dataset Documentation Completed: {DATASET_ID} ===")

# %% [markdown]
# ## Step 5: Post-Execution Console UI & Relationship Network Verification
#
# After notebook execution completes, refresh the **Insights** tab of the `thelook_ecommerce` dataset in BigQuery Studio to review:
#
# ### 1. Dataset Description (Holistic Business Summary)
# - Displays a comprehensive operational summary generated by the LLM detailing user acquisition, order fulfillment, inventory logistics, and data quality coverage.
#
# ### 2. Interactive Relationships Diagram
# - **7 Nodes & 9 Edges**: An interactive circular network visualization linking `users`, `orders`, `order_items`, `products`, `events`, `inventory_items`, and `distribution_centers`.
# - Drag, zoom, and explore node connections to intuitively understand cross-table data flows.
#
# ### 3. Relationship Table (Inferred Joins & Foreign Keys)
# The lower panel displays a structured breakdown of cross-table relationships:
# - `distribution_centers` <-> `products`: `distribution_centers.id = products.distribution_center_id` (Source: `LLM-inferred`)
# - `order_items` <-> `users`: `order_items.user_id = users.id` (Source: `LLM-inferred`)
# - `orders` <-> `users`: `orders.user_id = users.id` (Source: `LLM-inferred`)
# - `order_items` <-> `products`: `order_items.product_id = products.id` (Source: `LLM-inferred`)
#
# This inferred entity topology provides the foundational semantic graph required by Text-to-SQL agents to construct accurate multi-table joins without hallucinating column keys.
#
