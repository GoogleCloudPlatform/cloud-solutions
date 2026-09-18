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
# # In-Engine Generative AI & Machine Learning with BigQuery ML and Vertex AI
#
# This notebook demonstrates performing large-scale **LLM inference, text embedding generation, and high-speed vector search** directly inside BigQuery using standard SQL queries, eliminating external ETL data movement.
#
# ### Learning Objectives
# 1. **Vertex AI Remote Connection**: Configure BigQuery external model connections (`vertex-connection`) to invoke Gemini and Text Embedding endpoints.
# 2. **`ML.GENERATE_TEXT`**: Generate personalized churn-prevention promotional emails for at-risk VIP customers.
# 3. **JSON Mode & SQL Struct Parsing**: Enforce structured JSON schema outputs from Gemini and parse them into tabular BigQuery rows using `PARSE_JSON`.
# 4. **`ML.GENERATE_EMBEDDING`**: Convert unstructured product descriptions into 768-dimensional dense vector embeddings.
# 5. **`VECTOR_SEARCH`**: Build a semantic similarity search engine using cosine distance matching over product embeddings.
#

# %% [markdown]
# ## Step 1: Environment Setup & Remote Model Creation

# %%
# [Qwiklabs Environment] If you encounter an HTTP Error 401 (Invalid authentication credentials) during BigQuery API calls,
# uncomment and run the line below to perform manual authentication:
# # !gcloud auth application-default login --no-launch-browser --quiet

import google.auth
from google.cloud import bigquery

_, PROJECT_ID = google.auth.default()
bq_client = bigquery.Client(project=PROJECT_ID)

try:
    LOCATION = bq_client.get_dataset("thelook_ecommerce").location
except Exception:
    LOCATION = "us-central1"

print(f"Active Project ID: {PROJECT_ID}, Location: {LOCATION}")

# %%
# 1. Create Gemini Text and Embedding models (Dynamic Project ID binding via Python client)
create_models_query = f"""
-- 1. Create Gemini Text Model
CREATE OR REPLACE MODEL thelook_ecommerce.gemini_flash
REMOTE WITH CONNECTION `{PROJECT_ID}.{LOCATION}.vertex-connection`
OPTIONS(ENDPOINT = 'gemini-2.5-flash');

-- 2. Create Text Embedding Model
CREATE OR REPLACE MODEL thelook_ecommerce.text_embedding
REMOTE WITH CONNECTION `{PROJECT_ID}.{LOCATION}.vertex-connection`
OPTIONS(ENDPOINT = 'text-embedding-004');
"""

print("Executing remote model creation queries...")
query_job = bq_client.query(create_models_query)
query_job.result()
print("Remote models (gemini_flash, text_embedding) created successfully!")

# %% [markdown]
# ## Step 2: Generate Personalized Churn-Prevention Emails (`ML.GENERATE_TEXT`)
#
# Identify churn-risk VIP customers (e.g., customers with high prior spend but no recent purchases) and generate **personalized promotional discount emails** based on their last purchased brand and category.
#
# Using `ML.GENERATE_TEXT` with the remote Gemini model inside BigQuery SQL, dynamically assemble customer context into prompts and produce ready-to-send marketing copy.

# %%
email_query = """
-- Generate personalized promotional emails for churn-risk VIP customers
WITH target_users AS (
  SELECT 
    u.id AS user_id,
    u.first_name,
    u.email,
    -- Last purchased product details
    p.brand AS last_bought_brand,
    p.category AS last_bought_category,
    p.name AS last_bought_product
  FROM thelook_ecommerce.users u
  JOIN thelook_ecommerce.order_items oi ON u.id = oi.user_id
  JOIN thelook_ecommerce.products p ON oi.product_id = p.id
  WHERE u.id IN (367, 100, 500, 1000)
  QUALIFY ROW_NUMBER() OVER(PARTITION BY u.id ORDER BY oi.created_at DESC) = 1
),
prompts AS (
  SELECT
    user_id,
    first_name,
    email,
    CONCAT(
      "You are a friendly marketing specialist at the fashion eCommerce store 'TheLook'. Write a personalized promotional discount email in English to re-engage a customer who has not made a purchase recently. ",
      "Customer Name: ", first_name, ". ",
      "Last purchased item: Brand '", last_bought_brand, "', Category '", last_bought_category, "', Product '", last_bought_product, "'. ",
      "Offer this customer a 20% discount coupon (Code: MISSYOU20) applicable to items in the same brand or category to encourage a repeat purchase. ",
      "The subject line MUST begin with '[TheLook]', and the body should be polite, warm, and concise. Do NOT leave placeholders like [Name] in the output; generate complete ready-to-send text."
    ) AS prompt
  FROM target_users
)
SELECT 
  user_id,
  email,
  ml_generate_text_llm_result AS generated_email
FROM ML.GENERATE_TEXT(
  MODEL thelook_ecommerce.gemini_flash,
  (SELECT * FROM prompts),
  STRUCT(0.3 AS temperature, 1000 AS max_output_tokens, TRUE AS flatten_json_output)
);
"""

print("Generating personalized promotional emails using Gemini...")
email_df = bq_client.query(email_query).to_dataframe()
print(f"Generated {len(email_df)} personalized emails:\n")

for idx, row in email_df.iterrows():
    print("=" * 80)
    print(f"✉️  Email #{idx + 1} | Recipient: {row['email']} (User ID: {row['user_id']})")
    print("-" * 80)
    print(row["generated_email"].strip())
    print("=" * 80 + "\n")

# %% [markdown]
# ## Step 3: Product Feature & Keyword Tag Extraction (JSON Mode)
#
# Analyze product names and metadata to generate concise marketing titles and extract **product search keyword tags** in structured JSON format.
#
# Enforcing Gemini **JSON Mode** produces predictable, schema-compliant JSON objects that BigQuery can parse into discrete columns using `JSON_VALUE` and `JSON_QUERY`.

# %%
# %%bigquery
-- Extract marketing titles and search keyword tags (Prompt-based JSON)
WITH target_products AS (
  SELECT 
    id AS product_id,
    name AS english_name,
    brand,
    category,
    retail_price
  FROM thelook_ecommerce.products
  WHERE id IN (19666, 18458, 21572, 22000)
),
prompts AS (
  SELECT
    product_id,
    english_name,
    CONCAT(
      "Analyze the product information to generate a concise marketing title and extract 3 search keyword tags representing style, material, or fit. ",
      "Product Name: '", english_name, "', Brand: '", brand, "', Category: '", category, "'. ",
      "The output MUST be a single JSON object with exactly two fields: 'marketing_title' (string) and 'tags' (array of strings, e.g., ['cotton', 'casual', 'slim-fit']). ",
      "Do NOT use markdown code blocks or additional text. Return pure JSON only."
    ) AS prompt
  FROM target_products
)
SELECT 
  product_id,
  english_name,
  JSON_VALUE(ml_generate_text_llm_result, '$.marketing_title') AS marketing_title,
  JSON_QUERY(ml_generate_text_llm_result, '$.tags') AS search_tags,
  ml_generate_text_llm_result AS raw_json
FROM ML.GENERATE_TEXT(
  MODEL thelook_ecommerce.gemini_flash,
  (SELECT * FROM prompts),
  STRUCT(
    0.2 AS temperature,
    TRUE AS flatten_json_output
  )
);

# %% [markdown]
# ## Step 4: Generate Product Embeddings (`ML.GENERATE_EMBEDDING`) and Vector Search (`VECTOR_SEARCH`)
#
# Build a semantic **Vector Search** engine that matches natural language user queries (for example, "comfortable summer cotton t-shirt" or "formal dress pants") with the most relevant catalog items.
#
# 1. Use `ML.GENERATE_EMBEDDING` to produce 768-dimensional text embeddings combining product names, brands, and categories into a persistent table.
# 2. Use the `VECTOR_SEARCH` function to compute cosine similarity and retrieve the top 5 nearest products efficiently.

# %%
# %%bigquery
-- 1. Create product catalog embedding table (sample 100 products)
CREATE OR REPLACE TABLE thelook_ecommerce.product_embeddings AS
SELECT 
  id AS product_id,
  name AS product_name,
  brand,
  category,
  ml_generate_embedding_result AS product_embedding
FROM ML.GENERATE_EMBEDDING(
  MODEL thelook_ecommerce.text_embedding,
  (
    SELECT 
      id,
      name,
      brand,
      category,
      CONCAT("Product Name: ", name, ", Brand: ", brand, ", Category: ", category) AS content
    FROM thelook_ecommerce.products
    LIMIT 100
  ),
  STRUCT(TRUE AS flatten_json_output)
);

# %%
# %%bigquery
-- 2. Semantic vector search using query embedding
WITH query_embedding AS (
  SELECT ml_generate_embedding_result AS q_embedding
  FROM ML.GENERATE_EMBEDDING(
    MODEL thelook_ecommerce.text_embedding,
    (SELECT 'comfortable summer cotton t-shirt' AS content),
    STRUCT(TRUE AS flatten_json_output)
  )
)
SELECT 
  base.product_id,
  base.product_name,
  base.brand,
  base.category,
  ROUND(distance, 4) AS cosine_distance
FROM VECTOR_SEARCH(
  TABLE thelook_ecommerce.product_embeddings,
  'product_embedding',
  TABLE query_embedding,
  'q_embedding',
  top_k => 5,
  distance_type => 'COSINE'
);
