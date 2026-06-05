# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
# Copyright 2022 Google LLC
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

# %% [markdown] id="84442e6b"
# # Zero ETL for Operational AI: The Operational AI Leap - After Quick Deploy
#
# This notebook is the live execution companion for the **"Zero ETL for Operational AI: The Operational AI Leap"**
#
# ### Purpose
# This demo showcases using the **Google Data Cloud** to implement **"Zero ETL for Operational AI"**, deploying production-ready personalized recommendation agents entirely inside the database engine.
#
# ### Key Objectives:
#
# * **Zero-ETL Architecture:** Eliminating ETL pipelines by connecting ML environments directly to live operational data
# * **In-Database Generative AI:** Invoking Gemini LLM endpoints directly inside database SQL via secure IAM integration
# * **Multi-Index Optimization:** Fusing Dense Vectors, Sparse Vectors, and Full-Text Search into a single unified plan
# * **Lakehouse Federation:** Executing real-time, zero-copy joins between live databases and BigQuery Data Lakes
# * **Compute Isolation:** Offloading high-throughput AI workloads onto dynamically scaling Read Pools
#
# The demo proves that Zero-ETL workflows accelerate AI deployment cycles from months to hours while protecting primary application performance.
#
# ### Prerequisites
# This notebook assumes that the primary database setup, sample retail products data import, Gemini model registration, product copywriting batch job, and index creation steps have been completed by following the **Option 1: Quick Deploy via Terraform** section from the [Cymbal Shops StyleSearch AlloyDB AI Demo](https://github.com/paulramsey/stylesearch-alloydb-ai-demo)'s [README](https://github.com/paulramsey/stylesearch-alloydb-ai-demo/blob/main/README.md) document. If you haven't deployed the resources, please follow the README file first before starting this notebook.

# %% [markdown] id="a6d04f0c"
# ## Connection Setup & Environment Configuration
#
# Install the required Python packages with the `uv` command.

# %% colab={"base_uri": "https://localhost:8080/"} id="_vZlUwtCMBVv" outputId="793941d2-6fcf-419f-976a-87441b6c0df9"
# Install required python packages
# ! uv pip install \
#     asyncpg \
#     google-auth \
#     google-cloud-aiplatform \
#     google-cloud-alloydb-connector \
#     google-cloud-storage \
#     google-genai \
#     ipykernel \
#     jupyter-server \
#     pandas \
#     pillow \
#     pymilvus-model \
#     requests \
#     sqlalchemy \
#     tenacity \
#     greenlet \
#     python-dotenv

# %% [markdown]
# Define your connection variables to match your active AlloyDB and Google Cloud project configuration.

# %% colab={"base_uri": "https://localhost:8080/"} id="wj0_s5_ysbsu" outputId="8d408018-5ede-4dec-8fe7-7ea3a6681805"
# Update these variables to match your setup
project_id = "your-project"  # @param {type:"string"}
region = "us-central1"  # @param {type:"string"}
alloydb_cluster = "alloydb-retail-cluster"  # @param {type:"string"}
alloydb_instance = "alloydb-retail-primary"  # @param {type:"string"}
alloydb_database = "ecom_db"  # @param {type:"string"}
alloydb_password = "your-password"  # @param {type:"string"}

# %% [markdown] id="oSHcXT-uSAOO"
# Initialize SQL connection pool using Google Cloud AlloyDB Connector and define a SQL query helper function for convenient SQL execution

# %% colab={"base_uri": "https://localhost:8080/"} id="f93c0dfb" outputId="cb885993-1f28-42fa-8fdf-d68b21dae363"
import asyncio
import logging

import asyncpg
import pandas as pd
import sqlalchemy
from google.cloud.alloydb.connector import AsyncConnector, IPTypes
from sqlalchemy import exc, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Configure basic logging
logging.basicConfig(level=logging.WARNING)

# Initialize SQL connection pool using Google Cloud AlloyDB Connector


async def init_connection_pool(
    connector: AsyncConnector, db_name: str, pool_size: int = 5
) -> AsyncEngine:
    connection_string = f"projects/{project_id}/locations/{region}/clusters/{alloydb_cluster}/instances/{alloydb_instance}"

    async def getconn() -> asyncpg.Connection:
        conn: asyncpg.Connection = await connector.connect(
            connection_string,
            "asyncpg",
            user="postgres",
            password=alloydb_password,
            db=db_name,
            ip_type=IPTypes.PRIVATE,
        )
        return conn

    pool = create_async_engine(
        "postgresql+asyncpg://",
        async_creator=getconn,
        pool_size=pool_size,
        max_overflow=0,
        isolation_level="AUTOCOMMIT",
    )
    return pool


# Updated query execution helper to capture PostgreSQL RAISE NOTICE statements in real-time


async def run_query(pool, sql: str, params=None, output_as_df: bool = True):
    sql_lower_stripped = sql.strip().lower()
    is_select_with = sql_lower_stripped.startswith(("select", "with"))
    is_explain = sql_lower_stripped.startswith("explain")
    is_data_returning = is_select_with or is_explain
    effective_output_as_df = output_as_df and is_select_with
    is_bulk_operation = (
        isinstance(params, (list, tuple))
        and len(params) > 0
        and isinstance(params[0], (dict, tuple, list))
    )

    def handle_notice(connection, message):
        print(f"{message.severity}: {message.message}")

    async with pool.connect() as conn:
        raw_conn = await conn.get_raw_connection()
        driver_conn = getattr(raw_conn, "driver_connection", None)

        has_listener = driver_conn is not None and hasattr(
            driver_conn, "add_log_listener"
        )
        if has_listener:
            driver_conn.add_log_listener(handle_notice)

        try:
            if params:
                result = await conn.execute(text(sql), params)
            else:
                result = await conn.execute(text(sql))

            if is_data_returning:
                if is_explain:
                    try:
                        plan_rows = result.fetchall()
                        query_plan = "\n".join(
                            [str(row[0]) for row in plan_rows]
                        )
                        return query_plan
                    except Exception as e:
                        logging.error(f"Error fetching EXPLAIN: {e}")
                        return None
                else:
                    if effective_output_as_df:
                        try:
                            rows = result.fetchall()
                            column_names = result.keys()
                            return pd.DataFrame(rows, columns=column_names)
                        except Exception as e:
                            logging.error(f"Error converting DataFrame: {e}")
                            return result
                    else:
                        return result
            else:
                await conn.commit()
                operation_type = sql.strip().split()[0].upper()
                row_count = result.rowcount
                if is_bulk_operation:
                    print(
                        f"Bulk {operation_type} executed. Result rowcount: {row_count}"
                    )
                else:
                    print(
                        f"{operation_type} executed. {row_count} row(s) affected."
                    )
                return result

        except exc.ProgrammingError as e:
            logging.error(f"SQL Error: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected Error: {e}")
            raise
        finally:
            if has_listener:
                try:
                    driver_conn.remove_log_listener(handle_notice)
                except Exception:
                    pass


# Create connector and connection pools
connector = AsyncConnector()
ecom_db_pool = await init_connection_pool(connector, alloydb_database)
print("Connection pool to live AlloyDB database established successfully.")

# %% [markdown] id="7496bd07"
# ## Step 1: Breaking Down Data Silos (Direct Live Querying)
#
# Verify direct access to live database records with 0ms synchronization lag. Let's query the row count of the `products` table and sample a few active items directly from the database.

# %% colab={"base_uri": "https://localhost:8080/", "height": 89} id="1862185d" outputId="43ce15af-63b4-49de-dc51-e30cf4feec3b"
# Get live row counts and size details
sql_metrics = """
SELECT 'products' AS table_name,
       COUNT(*) AS row_count,
       pg_size_pretty(pg_relation_size('products')) AS table_size
FROM products;
"""
metrics_df = await run_query(ecom_db_pool, sql_metrics)
display(metrics_df)

# %% colab={"base_uri": "https://localhost:8080/", "height": 143} id="7Gss0h5Xvkl0" outputId="936d434c-0129-427d-b566-5947b25571cd"
# Select a few live records
sql_sample = """
SELECT id, name, brand, category, retail_price
FROM products
LIMIT 3;
"""
sample_df = await run_query(ecom_db_pool, sql_sample)
display(sample_df)

# %% [markdown] id="21ac8558"
# ## Step 2: Mapped AI-Native Models & Vector Capabilities
#
# Validate the `google_ml_integration` settings by:
# 1.  Register an ML model using `google_ml.create_model` function
# 2.  Viewing registered models inside `google_ml.model_info_view`.
# 3.  Verifying in-database vector generation with `embedding()`.
# 4.  Verifying prompt completions with `ai.generate()`.

# %% id="fPKPiQ0f0AMT"
sql_create_model = f"""
CALL
  google_ml.create_model(
    model_id => 'gemini-2.5-flash-lite-global',
    model_type => 'llm',
    model_provider => 'google',
    model_qualified_name => 'gemini-2.5-flash-lite',
    model_request_url =>  'https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/global/publishers/google/models/gemini-2.5-flash-lite:generateContent',
    model_auth_type => 'alloydb_service_agent_iam'
);
"""
await run_query(ecom_db_pool, sql_create_model)

# %% colab={"base_uri": "https://localhost:8080/", "height": 89} id="77f0c651" outputId="c69779c5-80fe-44f7-fa0e-f3d4badc631e"
# 1. View registered model endpoints inside database
sql_models = """
SELECT model_id, model_qualified_name, model_type, model_availability
FROM google_ml.model_info_view
WHERE model_availability = 'USER_REGISTERED';"""
models_df = await run_query(ecom_db_pool, sql_models)
display(models_df)

# %% colab={"base_uri": "https://localhost:8080/", "height": 106} id="I8Nw9YlbCYgC" outputId="b2680e92-79f0-4bfc-c1ff-7255f3c9e710"
# 2. Run native embedding generation inside AlloyDB
sql_embed = """
SELECT embedding('gemini-embedding-001',
'AlloyDB AI provides Zero-ETL embeddings') AS vector_sample;
"""
embed_df = await run_query(ecom_db_pool, sql_embed)
display(embed_df)
print(
    f"Successfully generated text embedding vector. Dimensions: {len(embed_df['vector_sample'].iloc[0])}"
)

# %% colab={"base_uri": "https://localhost:8080/", "height": 89} id="RldfidT_CYWC" outputId="2f063bf8-ade7-4070-c049-e12e229f52fb"
# 3. Run direct SQL text generation using the registered Gemini endpoint
sql_gen = """
SELECT
ai.generate('Say hello from database-native SQL!',
model_id => 'gemini-2.5-flash-lite-global') AS response;
"""
gen_df = await run_query(ecom_db_pool, sql_gen)
display(gen_df)

# %% [markdown] id="4a89259b"
# ## Step 3: Viewing In-Database Generative Features
#
# Showcase how standard SQL queries access the generated marketing descriptions written directly to table columns via batch `UPDATE` DML routines.

# %% colab={"base_uri": "https://localhost:8080/", "height": 143} id="8ef7e5ff" outputId="715c4ea1-3bbc-41a8-e4c7-e202c9bf684d"
# Query newly populated product description columns
sql_desc = """
SELECT id, name, category, product_description
FROM products
WHERE product_description IS NOT NULL
LIMIT 3;
"""
desc_df = await run_query(ecom_db_pool, sql_desc)
display(desc_df)

# %% [markdown] id="84d0714f"
# ## Step 4: Querying Individual Search Models
#
# Verify both dense semantic similarity search (pgvector index matching) and weighted PostgreSQL full-text matching individually in SQL.

# %% colab={"base_uri": "https://localhost:8080/", "height": 161} id="32e1de68" outputId="4c9873d2-d647-4628-caca-46ea8368e466"
query_term = "silver sunglasses"

# 1. Execute Dense Vector Cosine Similarity search
sql_dense = f"""
SELECT id, name, brand, retail_price,
       product_embedding <=> embedding('gemini-embedding-001',
       '{query_term}')::vector AS distance
FROM products
ORDER BY distance ASC
LIMIT 3;
"""
print("--- Dense Vector Semantic Search Results ---")
dense_results = await run_query(ecom_db_pool, sql_dense)
display(dense_results)

# %% colab={"base_uri": "https://localhost:8080/", "height": 178} id="VpL4e9io5C_D" outputId="cbbca228-b951-44f8-8992-98d13f13d942"
# 2. Execute Weighted PostgreSQL Full-Text keyword search
sql_fts = f"""
SELECT id, name,
ts_rank(fts_document, plainto_tsquery('english', '{query_term}')) AS rank_score
FROM products
WHERE fts_document @@ plainto_tsquery('english', '{query_term}')
ORDER BY rank_score DESC
LIMIT 3;
"""
print("\n--- PostgreSQL Full-Text Search Results ---")
fts_results = await run_query(ecom_db_pool, sql_fts)
display(fts_results)

# %% [markdown] id="a2d166ca"
# ## Step 5: Reciprocal Rank Fusion (RRF) in SQL
#
# Combine multiple indexing streams (SKU/relational, FTS, Sparse vector BM25, and Dense Vector similarity) and re-rank results natively in a single SQL transaction.

# %% colab={"base_uri": "https://localhost:8080/", "height": 143} id="8bad28d9" outputId="25cc47c8-ca65-4d41-e105-866eb2775544"
# In standard testing we also have fitted BM25 parameters. Let's execute the unified RRF query.
query_term = "silver sunglasses"
mock_sparse = "{2:3.5}/46696"

sql_rrf = f"""
WITH fts_search AS (
  SELECT id, name, ts_rank(fts_document, plainto_tsquery('english', '{query_term}')) AS fts_score,
         RANK() OVER (ORDER BY ts_rank(fts_document, plainto_tsquery('english', '{query_term}')) DESC) as fts_rank
  FROM products WHERE fts_document @@ plainto_tsquery('english', '{query_term}') LIMIT 20
),
bm25_search AS (
  SELECT id, name, sparse_embedding <#> '{mock_sparse}'::sparsevec AS bm25_dist,
         RANK() OVER (ORDER BY sparse_embedding <#> '{mock_sparse}'::sparsevec) AS bm25_rank
  FROM products WHERE sparse_embedding <#> '{mock_sparse}'::sparsevec < 1 LIMIT 20
),
vector_search AS (
  SELECT id, name, product_embedding <=> embedding('gemini-embedding-001', '{query_term}')::vector AS distance,
         RANK() OVER (ORDER BY product_embedding <=> embedding('gemini-embedding-001', '{query_term}')::vector) AS vector_rank
  FROM products LIMIT 20
)
SELECT
  COALESCE(v.id, f.id, b.id) AS id,
  COALESCE(v.name, f.name, b.name) AS name,
  (COALESCE(1.0 / (60 + v.vector_rank), 0.0) +
   COALESCE(1.0 / (60 + f.fts_rank), 0.0) +
   COALESCE(1.0 / (60 + b.bm25_rank), 0.0)) AS rrf_score
FROM vector_search v
FULL OUTER JOIN fts_search f ON v.id = f.id
FULL OUTER JOIN bm25_search b ON COALESCE(v.id, f.id) = b.id
ORDER BY rrf_score DESC LIMIT 3;
"""
rrf_df = await run_query(ecom_db_pool, sql_rrf)
display(rrf_df)

# %% [markdown] id="e31f2d28"
# ## Step 6: Lakehouse Joins & Instant SQL Inference
#
# Execute the "Magic Moment" by writing a single query that:
# 1.  Performs a local operational vector similarity search.
# 2.  Federates a direct, zero-copy join against BigQuery historical user order counts.
# 3.  Pipes the resulting contextual text directly to Gemini (`ai.generate`) in-database to return a fully personalized recommendation summary.

# %% [markdown] id="FUNYG2vtVjh6"
# Configure the required IAM Roles for the AlloyDB Service Account to support `bigquery_fdw` (BigQuery Foreign Data Wrapper)

# %% colab={"base_uri": "https://localhost:8080/"} id="4_NirsICwzyD" outputId="ae3fa9b8-1f8e-4560-f5e4-5f3f0edcadae"
# Check the service account that AlloyDB uses
alloydb_serviceaccount =! gcloud beta alloydb clusters describe {alloydb_cluster} \
    --region={region} \
    --project={project_id} \
    --format="value(serviceAccountEmail)"
alloydb_serviceaccount = alloydb_serviceaccount[0]
print(f"alloydb_serviceaccount = {alloydb_serviceaccount}")

# %% id="UyvNKFXslAjh"
# IAM Roles required for access BigQuery from AlloyDB
roles_array = [
    "roles/bigquery.dataViewer",
    "roles/bigquery.readSessionUser",
    "roles/bigquery.jobUser",
    "roles/storage.objectViewer",
]

# Add IAM Roles to the Alloy DB service account
for r in roles_array:
  # ! gcloud projects add-iam-policy-binding {project_id} \
#       --member="serviceAccount:{alloydb_serviceaccount}" \
#       --role="{r}" \
#       --no-user-output-enabled

# %% colab={"base_uri": "https://localhost:8080/"} id="u5XwQBPxFXpz" outputId="58919f8e-340a-4959-cea0-50a08921e186"
# Get the list of IAM roles assigned to the AlloyDB service account
sa_roles = ! gcloud projects get-iam-policy {project_id} \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:{alloydb_serviceaccount}" \
  --format="value(bindings.role)"

for r in sa_roles:
  if r in roles_array:
    print(r)

# %% [markdown] id="Lo7T9wLwVY81"
# Add `bigquery_fdw.enabled` database flag to AlloyDB Cluster

# %% id="DHNiX4j50MN8"
# Add bigquery_fdw database flag
# ! gcloud alloydb instances update {alloydb_instance} \
#     --region={region} \
#     --cluster={alloydb_cluster} \
#     --database-flags="password.enforce_complexity=on,bigquery_fdw.enabled=on"

# %% colab={"base_uri": "https://localhost:8080/"} id="yuIGgo_m28uA" outputId="44b3e616-0c0d-4fb7-f83a-ad12e8bbcd98"
# Check database flags from the Alloy DB Cluster
# ! gcloud beta alloydb instances describe {alloydb_instance} \
#     --region={region} \
#     --cluster={alloydb_cluster} \
#     --format="value(databaseFlags)"

# %% [markdown] id="anct1cmSV5S5"
# Create the `bigquery_fdw` extension

# %% colab={"base_uri": "https://localhost:8080/"} id="mrDZT_YOzWHo" outputId="023982a8-5d3f-4876-a1c9-cc4d6632e478"
sql = "CREATE EXTENSION IF NOT EXISTS bigquery_fdw"
await run_query(ecom_db_pool, sql)

# %% [markdown] id="RkfsTovDWPEV"
# Create a foreign server to define the connection parameters for the remote BigQuery dataset.

# %% colab={"base_uri": "https://localhost:8080/"} id="1VLfLuawyTRs" outputId="3fbc39b6-0882-4e5e-d754-be4fffb4c0cc"
sql_array = []
sql_array.append("DROP SERVER IF EXISTS bq_server CASCADE")
sql_array.append("CREATE SERVER bq_server FOREIGN DATA WRAPPER bigquery_fdw")

for sql in sql_array:
    await run_query(ecom_db_pool, sql)

# %% [markdown] id="OXOXIdp1Wgah"
# Create the user mapping that maps a local PostgreSQL user(`postgres`) to the foreign server.

# %% colab={"base_uri": "https://localhost:8080/"} id="fqaY3iuc9RpY" outputId="2b29b804-6563-467c-c744-beae41b25728"
sql_array = []
sql_array.append("DROP USER MAPPING IF EXISTS FOR postgres SERVER bq_server")
sql_array.append("CREATE USER MAPPING FOR postgres SERVER bq_server")

for sql in sql_array:
    await run_query(ecom_db_pool, sql)

# %% [markdown] id="ijs3vhIDWvoH"
# Define the foreign table structure to access the remote `order_items` table in BigQuery.

# %% colab={"base_uri": "https://localhost:8080/"} id="-RhE1NmM98Y-" outputId="81fce62b-e35d-40e1-d288-49edef25e7c5"
sql_array = []
sql_array.append("DROP SCHEMA IF EXISTS bq_ecom CASCADE")
sql_array.append("CREATE SCHEMA IF NOT EXISTS bq_ecom")
# bigquery_fdw requires manual table definition with the 'project' option
sql_array.append(f"""
CREATE FOREIGN TABLE IF NOT EXISTS bq_ecom.order_items (
  id INTEGER,
  order_id INTEGER,
  user_id INTEGER,
  product_id INTEGER,
  inventory_item_id INTEGER,
  status TEXT,
  created_at TIMESTAMP,
  shipped_at TIMESTAMP,
  delivered_at TIMESTAMP,
  returned_at TIMESTAMP,
  sale_price FLOAT8
)
SERVER bq_server
OPTIONS (project '{project_id}', dataset 'thelook_ecommerce', table 'order_items');
""")

for sql in sql_array:
    await run_query(ecom_db_pool, sql)

# %% [markdown] id="EvFsc5EzXFk8"
# Test the configured BigQuery Foreign Data Wrapper using a simple SQL query against the foreign table.

# %% colab={"base_uri": "https://localhost:8080/", "height": 313} id="DIsgQOFyJLRq" outputId="6ccae38c-32c0-4bb7-df14-df149306d40d"
sql_test_bq = "SELECT * FROM bq_ecom.order_items LIMIT 5"
bq_test_df = await run_query(ecom_db_pool, sql_test_bq)
display(bq_test_df)

# %% [markdown] id="DNcXVJw3Xmw-"
# **Lakehouse Joins & Instant SQL Inference**
#
# A query example that combines vector search, live data federation, and generative AI. Here's a breakdown:
#
# 1. `hybrid_search` **(CTE)**: It uses the `embedding()` function to convert your search term ('winter coat') into a vector and finds the top 5 most similar products using the `<=>` (cosine distance) operator.
# 2. `enriched_search` **(CTE)**: This is the 'Lakehouse' step. It performs a zero-copy join between your local AlloyDB products and a remote BigQuery table (`bq_ecom.order_items`) to calculate the real-time popularity (order count) of those items.
# 3. `context_builder` **(CTE)**: It aggregates the product names, brands, prices, and popularity into a single text string to serve as context for the LLM.
# 4. `ai.generate()`: The final `SELECT` sends that context to the Gemini 2.5 Flash model directly from the database, asking it to write a personalized shopping recommendation.
# 5. **Display**: Finally, the Python code executes the query using run_query and displays the generated summary using Markdown formatting.

# %% colab={"base_uri": "https://localhost:8080/", "height": 100} id="b69cbf26" outputId="e92dc83b-d31b-40d0-e425-12b3a8ab32a9"
query_val = "winter coat"

# The SQL query is defined without leading comments to ensure run_query returns a DataFrame
sql_magic = f"""
WITH hybrid_search AS (
  SELECT id, name, brand, retail_price, product_description,
         product_embedding <=> embedding('gemini-embedding-001', '{query_val}')::vector AS distance
  FROM products
  ORDER BY distance ASC
  LIMIT 5
),
enriched_search AS (
  SELECT
    h.*,
    COALESCE(a.order_count, 0) as popularity
  FROM hybrid_search h
  LEFT JOIN (
    SELECT product_id, COUNT(*) as order_count
    FROM bq_ecom.order_items
    GROUP BY 1
  ) a ON h.id = a.product_id
  ORDER BY popularity DESC
  LIMIT 3
),
context_builder AS (
  SELECT string_agg(
    'Product: ' || name || ' (Brand: ' || COALESCE(brand, 'N/A') || ', Price: $' || retail_price || ', Popularity: ' || popularity || ' orders)\nDescription: ' || COALESCE(product_description, 'N/A'),
    '\\n\\n'
  ) AS search_results_context
  FROM enriched_search
)
SELECT
  ai.generate(
    'You are a helpful shopping assistant. Based on the following search results for "' || '{query_val}' || '", which include live popularity data from our BigQuery data lakehouse, write a short, engaging summary recommending the best option for the customer.\\n\\n' || search_results_context,
    model_id => 'gemini-2.5-flash-lite-global'
  ) AS personalized_summary
FROM context_builder;
"""

# Execute the query
magic_result = await run_query(ecom_db_pool, sql_magic)

# Check if result is a DataFrame and extract the summary
if isinstance(magic_result, pd.DataFrame) and not magic_result.empty:
    summary_text = magic_result["personalized_summary"].iloc[0]
    from IPython.display import Markdown, display

    display(
        Markdown(
            f"### Generated personalized recommendation summary:\n\n{summary_text}"
        )
    )
else:
    print("Error: Query did not return a valid DataFrame result.")
