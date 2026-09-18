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
# # Declarative High-Level AI Functions in BigQuery
#
# This notebook explores BigQuery's built-in **High-Level Declarative AI Functions**, enabling powerful natural language processing, semantic search, and cost-optimized batch inference directly in SQL without creating ML model objects or fine-tuning prompts.
#
# ### Learning Objectives
# 1. **`AI.CLASSIFY`**: Categorize unstructured product titles into candidate target taxonomies zero-shot.
# 2. **`AI.SIMILARITY`**: Compute semantic similarity scores between text strings on a continuous scale from -1 to 1.
# 3. **`AI.IF`**: Evaluate natural language Boolean conditions (e.g., "Is this item a winter outerwear jacket?") over tabular data.
# 4. **`AI.SEARCH` & Autonomous Embeddings**: Configure auto-generated embedding columns (`STORED OPTIONS( asynchronous = TRUE )`) that automatically calculate vector representations upon insertion.
# 5. **`AI.COUNT_TOKENS` & `optimization_mode`**: Measure prompt token consumption for cost auditing and leverage Just-In-Time (JIT) knowledge distillation to reduce latency and execution spend.
#

# %% [markdown]
# ## Step 1: Environment Setup
#
# Initialize authentication and BigQuery client. High-Level AI Functions run through BigQuery internal default channels without requiring manual model creation or connection setup.

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

# %% [markdown]
# ## Step 2: Text Classification & Semantic Similarity (`AI.CLASSIFY` & `AI.SIMILARITY`)
#
# Execute classification and similarity comparisons directly using BigQuery built-in declarative SQL functions without creating custom prompts.
#
# ### 1. `AI.CLASSIFY`
# - **Syntax**: `ai.classify(text, categories)`
# - **Use Case**: Classify product information, customer inquiries, or reviews into candidate categories.
#
# ### 2. `AI.SIMILARITY`
# - **Syntax**: `ai.similarity(text1, text2)`
# - **Use Case**: Compute semantic distance (similarity) between two texts on a scale from `-1` to `1` (typically `0` to `1`).

# %%
# %%bigquery
-- 1. Automated text classification (AI.CLASSIFY)
WITH sample_products AS (
  SELECT id, name, category
  FROM thelook_ecommerce.products
  WHERE id IN (120, 5600, 15000, 20000)
)
SELECT 
  id AS product_id,
  name AS product_name,
  category AS original_category,
  ai.classify(name, ['Clothing', 'Footwear', 'Accessories', 'Electronics', 'Home']) AS predicted_category
FROM sample_products;

# %%
# %%bigquery
-- 2. Semantic similarity calculation between search query and product concepts (AI.SIMILARITY)
WITH queries AS (
  SELECT 'warm winter coat' AS user_query, 'red leather shoes' AS target_concept
)
SELECT 
  user_query,
  ai.similarity(user_query, 'Heavy wool jacket for cold weather') AS match_jacket_score,
  ai.similarity(user_query, 'Light cotton summer t-shirt') AS match_tshirt_score,
  
  target_concept,
  ai.similarity(target_concept, 'crimson leather footwear') AS match_shoes_score,
  ai.similarity(target_concept, 'blue denim pants') AS match_pants_score
FROM queries;

# %% [markdown]
# ## Step 3: Natural Language Condition Evaluation (`AI.IF`)
#
# The `AI.IF` function evaluates whether a given text satisfies a natural language condition and returns a boolean (**`TRUE`** or **`FALSE`**).
#
# - **Syntax**: `ai.if(condition, text)`
# - **Use Case**: Content moderation, sentiment analysis, or category verification.

# %%
# %%bigquery
-- 3. Contextual condition evaluation with AI.IF
WITH sample_data AS (
  SELECT 
    'Heavy goose down parka with fleece lining' AS description,
    'This fabric is way too thin to wear in the winter. Shipping also took over a week.' AS review
)
SELECT 
  -- 1) Determine if product description describes warm winter clothing
  ai.if(('Does this product description describe warm winter clothing? ', description)) AS is_winter_apparel,
  
  -- 2) Determine if customer review expresses dissatisfaction or negative feedback
  ai.if(('Does this customer review express dissatisfaction or negative feedback? ', review)) AS is_negative_review
FROM sample_data;

# %% [markdown]
# ## Step 4: Autonomous Embeddings and Semantic Search (`AI.SEARCH`)
#
# `AI.SEARCH` simplifies semantic search by managing embedding generation automatically:
#
# 1. **Autonomous Embedding Column**: Define a stored generated column (`STRUCT<result ARRAY<FLOAT64>, status STRING>`) using `AI.EMBED` with `STORED OPTIONS(asynchronous = TRUE)` so embeddings update in the background when text columns change.
# 2. **Declarative `AI.SEARCH`**: Pass the table, raw source text column name, and natural language query; BigQuery handles query embedding and vector distance calculation automatically.

# %%
# 1. Create table with autonomous embedding column and load test data
create_auto_embed_query = f"""
-- 1. Create table with auto-embedding column
CREATE OR REPLACE TABLE thelook_ecommerce.products_auto_embed (
  product_id INT64,
  name STRING,
  description STRING,
  description_embedding STRUCT<result ARRAY<FLOAT64>, status STRING>
    GENERATED ALWAYS AS (AI.EMBED(
      description,
      connection_id => '{PROJECT_ID}.{LOCATION}.vertex-connection',
      endpoint => 'text-embedding-005'
    ))
    STORED OPTIONS( asynchronous = TRUE )
);

-- 2. Insert sample product data
INSERT INTO thelook_ecommerce.products_auto_embed (product_id, name, description) VALUES
  (101, "Summer Linen Shirt", "Light and breathable short-sleeve shirt made of 100% linen, perfect for hot summer days."),
  (102, "Hiking Waterproof Windbreaker", "Windproof and waterproof functional jacket, ideal for hiking and outdoor activities in bad weather."),
  (103, "Business Casual Slacks", "Slim fit formal dress pants, clean and comfortable for office workers daily wear.");
"""

print("Creating auto-embedding table and loading sample data...")
query_job = bq_client.query(create_auto_embed_query)
query_job.result()
print("Auto-embedding table and sample data loaded successfully!")

# %% [markdown]
# > [!IMPORTANT]
# >
# > Because `asynchronous = TRUE` is enabled on the embedding column, vector embeddings generate in the background over several seconds after insertion. Wait 5-10 seconds after inserting data before executing the search cell below.
#
# ### 3. Run Semantic Search with `AI.SEARCH`
#
# The query below passes a natural language search query (`'comfortable jacket for hiking and outdoor activities'`) to find the most relevant product. Note that the `column_to_search` parameter specifies the **raw source text column (`'description'`)**, not the embedding column.

# %%
# %%bigquery
-- 3. Semantic search using AI.SEARCH
SELECT 
  base.product_id,
  base.name AS product_name,
  base.description,
  ROUND(distance, 4) AS distance
FROM AI.SEARCH(
  TABLE thelook_ecommerce.products_auto_embed,
  'description',
  
  # Select a test query to run:
  'comfortable jacket for hiking and outdoor activities', # Matches: Hiking Waterproof Windbreaker
  # 'clean formal pants for office wear',                # Matches: Business Casual Slacks
  # 'cool short-sleeve shirt for hot summer days',        # Matches: Summer Linen Shirt
  
  top_k => 2
);

# %% [markdown]
# ## Step 5: Cost Metering and Optimization (Token Metering & Knowledge Distillation)
#
# Calling LLM APIs for every row on large datasets introduces latency and expense. BigQuery provides optimization mechanisms to estimate costs in advance and accelerate large-scale evaluations.
#
# ### 1. Token Metering with `AI.COUNT_TOKENS`
# Measure prompt token volume and predict cost before sending requests to remote models:
# - **Syntax**: `ai.count_tokens(text, endpoint => 'gemini-2.5-flash')`
#
# ### 2. Cost Minimization with Knowledge Distillation (`optimization_mode => 'MINIMIZE_COST'`)
# When evaluating large datasets (at least 3,000 rows recommended) with `AI.IF` or `AI.CLASSIFY`:
# - **How it works**:
#   1. BigQuery samples a small subset of rows and labels them using the remote Gemini model.
#   2. It uses pre-computed text embeddings and LLM labels to train a lightweight local distilled model Just-In-Time (JIT).
#   3. Once validation passes, the local distilled model evaluates the remaining rows rapidly at a fraction of the cost.

# %%
# %%bigquery
-- 1. Meter prompt tokens and calculate estimated cost
WITH target_prompts AS (
  SELECT 
    u.id AS user_id,
    CONCAT(
      "You are a friendly marketing specialist at the fashion eCommerce store 'TheLook'. Write a personalized promotional discount email in English to re-engage a customer who has not made a purchase recently. ",
      "Customer Name: ", u.first_name, ". ",
      "Last purchased item: Brand '", p.brand, "', Category '", p.category, "', Product '", p.name, "'. ",
      "Offer this customer a 20% discount coupon (Code: MISSYOU20) for items in the same brand or category."
    ) AS prompt
  FROM thelook_ecommerce.users u
  JOIN thelook_ecommerce.order_items oi ON u.id = oi.user_id
  JOIN thelook_ecommerce.products p ON oi.product_id = p.id
  WHERE u.id IN (367, 100, 500, 1000)
  QUALIFY ROW_NUMBER() OVER(PARTITION BY u.id ORDER BY oi.created_at DESC) = 1
),
prompt_tokens AS (
  SELECT
    user_id,
    prompt,
    ai.count_tokens(prompt, endpoint => 'gemini-2.5-flash').result AS input_token_count
  FROM target_prompts
)
SELECT 
  user_id,
  input_token_count,
  -- Cost simulation based on $0.075 per 1 Million input tokens (USD)
  ROUND((input_token_count / 1000000.0) * 0.075, 8) AS predicted_cost_usd,
  prompt
FROM prompt_tokens;

# %%
# %%bigquery
-- 2. Just-In-Time (JIT) Knowledge Distillation Optimization Mode
-- Evaluates 3,100 rows using a locally trained distilled model to reduce LLM calls and latency.
SELECT 
  name,
  category,
  AI.IF(
    ('Does this product belong to the Clothing category? ', name),
    embeddings => AI.EMBED(name, endpoint => 'text-embedding-005').result,
    optimization_mode => 'MINIMIZE_COST'
  ) AS is_clothing
FROM thelook_ecommerce.products
LIMIT 3100;
