# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
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
# # BigQuery Property Graph Creation, GQL Analytics, and Native Visualization
#
# This notebook demonstrates transforming tabular relational data from `thelook_ecommerce` into a **BigQuery Property Graph** (nodes and edges) and executing multi-hop network queries using the ISO-standard **GQL (Graph Query Language)**.
#
# ### Learning Objectives
# 1. **Graph Modeling**: Design and populate node tables (`Customer`, `Product`, `Location`, `DistributionCenter`) and directed edge tables (`ordered`, `lives_in`, `supplied_from`, `co_purchased_with`).
# 2. **Property Graph Declaration**: Declare a unified BigQuery Property Graph using DDL syntax.
# 3. **GQL Querying & Native Visualization**: Execute GQL pattern matches with `%%bigquery --graph display_only` to render interactive Force Layout network graphs directly inside the notebook.
# 4. **Console UI Validation**: Inspect the graphical schema topology in the BigQuery Studio console.
#

# %% [markdown]
# ## Step 1: Environment Setup
#
# Import the BigQuery client library and load authentication credentials.

# %%
# [Qwiklabs Environment] If you encounter an HTTP Error 401 (Invalid authentication credentials) during BigQuery magic execution,
# uncomment and run the line below to perform manual authentication:
# # !gcloud auth application-default login --no-launch-browser --quiet

# %load_ext google.cloud.bigquery

import google.auth
from google.auth.transport.requests import Request
from google.cloud import bigquery

credentials, PROJECT_ID = google.auth.default()
bq_client = bigquery.Client(project=PROJECT_ID)
try:
    LOCATION = bq_client.get_dataset("thelook_ecommerce").location
except Exception:
    LOCATION = "us-central1"
credentials.refresh(Request())

print(f"Google Cloud Project ID: {PROJECT_ID}")

# %% [markdown]
# ## Step 2: Build Node and Edge Tables for Property Graph
#
# Create the network refinement dataset (`thelook_network`), followed by node tables (Customer, Product, Location, DC) and edge tables (ordered, co_purchased, lives_in, supplied_from).

# %%
from google.api_core.exceptions import Conflict

client = bigquery.Client()

# 0. Create refined network dataset if not present
dataset_id = f"{PROJECT_ID}.thelook_network"
dataset = bigquery.Dataset(dataset_id)
dataset.location = LOCATION

try:
    client.create_dataset(dataset, timeout=30)
    print(f"Dataset '{dataset_id}' created successfully.")
except Conflict:
    print(f"Dataset '{dataset_id}' already exists.")

# 1. SQL to create node and edge tables
setup_tables_sql = f"""
-- 1) Create Node Tables
CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.node_users` AS
SELECT id AS user_id, age, gender, traffic_source
FROM `{PROJECT_ID}.thelook_ecommerce.users`;

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.node_products` AS
SELECT id AS product_id, category, brand, name AS product_name, retail_price
FROM `{PROJECT_ID}.thelook_ecommerce.products`;

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.node_locations` AS
SELECT 
  ROW_NUMBER() OVER (ORDER BY country, city) AS location_id,
  city, country
FROM (
  SELECT DISTINCT city, country 
  FROM `{PROJECT_ID}.thelook_ecommerce.users`
  WHERE city IS NOT NULL AND country IS NOT NULL
);

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.node_distribution_centers` AS
SELECT id AS center_id, name AS center_name
FROM `{PROJECT_ID}.thelook_ecommerce.distribution_centers`;

-- 2) Create Edge Tables
CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.edge_ordered` AS
SELECT 
  id AS order_item_id, user_id, product_id, sale_price, status
FROM `{PROJECT_ID}.thelook_ecommerce.order_items`;

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.edge_lives_in` AS
SELECT 
  CONCAT(u.id, '_lives_in_', l.location_id) AS edge_id,
  u.id AS user_id,
  l.location_id
FROM `{PROJECT_ID}.thelook_ecommerce.users` u
JOIN `{PROJECT_ID}.thelook_network.node_locations` l
  ON u.city = l.city AND u.country = l.country;

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.edge_supplied_from` AS
SELECT 
  CONCAT(id, '_supplied_from_', distribution_center_id) AS edge_id,
  id AS product_id,
  distribution_center_id AS center_id
FROM `{PROJECT_ID}.thelook_ecommerce.products`;

-- Co-purchased edges
CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.edge_co_purchased` AS
WITH product_pairs AS (
  SELECT 
    a.product_id AS source_product_id,
    b.product_id AS target_product_id,
    COUNT(*) AS co_purchase_count
  FROM `{PROJECT_ID}.thelook_ecommerce.order_items` a
  JOIN `{PROJECT_ID}.thelook_ecommerce.order_items` b 
    ON a.order_id = b.order_id AND a.product_id < b.product_id
  GROUP BY 1, 2
)
SELECT 
  CONCAT(source_product_id, '_', target_product_id, '_copurchase') AS edge_id,
  source_product_id,
  target_product_id,
  co_purchase_count
FROM product_pairs
WHERE co_purchase_count >= 2;
"""

print("Creating node and edge tables...")
client.query(setup_tables_sql).result()
print("All node and edge tables created successfully.")

# %% [markdown]
# ## Step 3: Create BigQuery Property Graph
#
# Define relationships (Source/Destination Key mapping) across the created node and edge tables to register the `product_recommendation_graph` property graph.

# %%
create_graph_sql = f"""
CREATE OR REPLACE PROPERTY GRAPH `{PROJECT_ID}.thelook_network.product_recommendation_graph`
NODE TABLES (
  `{PROJECT_ID}.thelook_network.node_products` AS Product KEY (product_id)
    PROPERTIES (product_id, category, brand, product_name, retail_price),
  `{PROJECT_ID}.thelook_network.node_users` AS Customer KEY (user_id)
    PROPERTIES (user_id, age, gender, traffic_source),
  `{PROJECT_ID}.thelook_network.node_locations` AS Location KEY (location_id)
    PROPERTIES (city, country),
  `{PROJECT_ID}.thelook_network.node_distribution_centers` AS DistributionCenter KEY (center_id)
    PROPERTIES (center_id, center_name)
)
EDGE TABLES (
  `{PROJECT_ID}.thelook_network.edge_ordered` AS ordered
    KEY (order_item_id)
    SOURCE KEY (user_id) REFERENCES Customer (user_id)
    DESTINATION KEY (product_id) REFERENCES Product (product_id)
    PROPERTIES (order_item_id, sale_price, status),
  `{PROJECT_ID}.thelook_network.edge_co_purchased` AS co_purchased_with
    KEY (edge_id)
    SOURCE KEY (source_product_id) REFERENCES Product (product_id)
    DESTINATION KEY (target_product_id) REFERENCES Product (product_id)
    PROPERTIES (co_purchase_count),
  `{PROJECT_ID}.thelook_network.edge_lives_in` AS lives_in
    KEY (edge_id)
    SOURCE KEY (user_id) REFERENCES Customer (user_id)
    DESTINATION KEY (location_id) REFERENCES Location (location_id),
  `{PROJECT_ID}.thelook_network.edge_supplied_from` AS supplied_from
    KEY (edge_id)
    SOURCE KEY (product_id) REFERENCES Product (product_id)
    DESTINATION KEY (center_id) REFERENCES DistributionCenter (center_id)
)
"""

print("Creating property graph...")
client.query(create_graph_sql).result()
print("Property graph (product_recommendation_graph) registered successfully.")

# %% [markdown]
# ## Step 4: Network Analysis and Native Graph Visualization
#
# Analyze multi-dimensional relationships extending from a specific popular product (`product_id = 25346`): **[Distribution Center ➡️ Product ➡️ Customers ➡️ Customer Locations]**.
#
# Using Colab Enterprise native graph visualization (`--graph display_only`), visualize the star-shaped customer network surrounding the selected product inline.
#
# > [!NOTE]
# >
# > **BigQuery Graph & Editions**: Querying via native GQL (`GRAPH_TABLE(...)`)
# > requires a BigQuery **Enterprise** or **Enterprise Plus** edition
# > reservation (`SET @@reservation = '...';`).
# > In on-demand compute environments (such as standard Qwiklabs lab
# > environments), the relational multi-table `JOIN` query below formats the
# > nodes and edges according to BigQuery Studio's GQL JSON schema (`kind`,
# > `identifier`, `labels`, `properties`, `source_node_identifier`, `destination_node_identifier`),
# > allowing Colab Enterprise's native force-directed graph visualizer to render
# > the network graph directly without requiring an Enterprise reservation.

# %%
# %%bigquery --graph display_only
SELECT
  TO_JSON(STRUCT(
    'node' AS kind,
    CONCAT('customer_', CAST(u.user_id AS STRING)) AS identifier,
    ['Customer'] AS labels,
    STRUCT(
      u.user_id AS user_id,
      u.age AS age,
      u.gender AS gender,
      u.traffic_source AS traffic_source
    ) AS properties
  )) AS Customer_Node,
  TO_JSON(STRUCT(
    'node' AS kind,
    CONCAT('product_', CAST(p.product_id AS STRING)) AS identifier,
    ['Product'] AS labels,
    STRUCT(
      p.product_id AS product_id,
      p.category AS category,
      p.brand AS brand,
      p.product_name AS product_name,
      p.retail_price AS retail_price
    ) AS properties
  )) AS Product_Node,
  TO_JSON(STRUCT(
    'node' AS kind,
    CONCAT('dc_', CAST(dc.center_id AS STRING)) AS identifier,
    ['DistributionCenter'] AS labels,
    STRUCT(
      dc.center_id AS center_id,
      dc.center_name AS center_name
    ) AS properties
  )) AS DC_Node,
  TO_JSON(STRUCT(
    'node' AS kind,
    CONCAT('location_', CAST(l.location_id AS STRING)) AS identifier,
    ['Location'] AS labels,
    STRUCT(
      l.location_id AS location_id,
      l.city AS city,
      l.country AS country
    ) AS properties
  )) AS Location_Node,
  TO_JSON(STRUCT(
    'edge' AS kind,
    CONCAT('ordered_', CAST(o.order_item_id AS STRING)) AS identifier,
    ['ordered'] AS labels,
    CONCAT('customer_', CAST(u.user_id AS STRING)) AS source_node_identifier,
    CONCAT('product_', CAST(p.product_id AS STRING)) AS destination_node_identifier,
    STRUCT(
      o.order_item_id AS order_item_id,
      o.sale_price AS sale_price,
      o.status AS status
    ) AS properties
  )) AS Ordered_Edge,
  TO_JSON(STRUCT(
    'edge' AS kind,
    CONCAT('supplied_from_', CAST(sf.edge_id AS STRING)) AS identifier,
    ['supplied_from'] AS labels,
    CONCAT('product_', CAST(p.product_id AS STRING)) AS source_node_identifier,
    CONCAT('dc_', CAST(dc.center_id AS STRING)) AS destination_node_identifier,
    STRUCT(
      sf.edge_id AS edge_id
    ) AS properties
  )) AS Supplied_Edge,
  TO_JSON(STRUCT(
    'edge' AS kind,
    CONCAT('lives_in_', CAST(lives.edge_id AS STRING)) AS identifier,
    ['lives_in'] AS labels,
    CONCAT('customer_', CAST(u.user_id AS STRING)) AS source_node_identifier,
    CONCAT('location_', CAST(l.location_id AS STRING)) AS destination_node_identifier,
    STRUCT(
      lives.edge_id AS edge_id
    ) AS properties
  )) AS Lives_In_Edge
FROM thelook_network.node_products p
JOIN thelook_network.edge_supplied_from sf ON p.product_id = sf.product_id
JOIN thelook_network.node_distribution_centers dc ON sf.center_id = dc.center_id
JOIN thelook_network.edge_ordered o ON p.product_id = o.product_id
JOIN thelook_network.node_users u ON o.user_id = u.user_id
JOIN thelook_network.edge_lives_in lives ON u.user_id = lives.user_id
JOIN thelook_network.node_locations l ON lives.location_id = l.location_id
WHERE p.product_id = 25346
LIMIT 100;

# %% [markdown]
# ### Modern GQL Pattern Matching Equivalent (Enterprise Edition Reference)
#
# In BigQuery Enterprise or Enterprise Plus editions with an active reservation, the 7-table relational `JOIN` above can be expressed with concise ISO-standard GQL pattern matching syntax:
#
# ```sql
# SELECT
#   TO_JSON(c) AS Customer_Node,
#   TO_JSON(p) AS Product_Node,
#   TO_JSON(o) AS Ordered_Edge,
#   TO_JSON(dc) AS DC_Node,
#   TO_JSON(sf) AS Supplied_Edge,
#   TO_JSON(l) AS Location_Node,
#   TO_JSON(lives) AS Lives_In_Edge
# FROM GRAPH_TABLE(
#   thelook_network.product_recommendation_graph
#   MATCH (dc:DistributionCenter)<-[sf:supplied_from]-(p:Product)<-[o:ordered]-(c:Customer)-[lives:lives_in]->(l:Location)
#   WHERE p.product_id = 25346
#   RETURN c, p, o, dc, sf, l, lives
# )
# LIMIT 100;
# ```
#
# Notice how `MATCH (dc)<-[:supplied_from]-(p)<-[:ordered]-(c)-[:lives_in]->(l)` expresses the entire multi-hop traversal in a single, readable graph pattern.

# %% [markdown]
# ## Step 5: BigQuery UI Graphs Console Verification & GQL Advantages
#
# ### 1. Inspecting the Property Graph in BigQuery Studio Console
# In the BigQuery Studio Explorer panel, open the `thelook_network` dataset, select the **`Graphs`** tab, and click `product_recommendation_graph`:
# - **4 Node Types**: `Customer`, `Product`, `DistributionCenter`, `Location`
# - **4 Edge Types**: `co_purchased_with`, `lives_in`, `ordered`, `supplied_from`
# - The interactive schema canvas visually confirms table key bindings and relationship directions.
#
# ### 2. Practical Advantages of Property Graphs & GQL
# - **Eliminate Complex JOINs**: Instead of writing nested, computationally expensive SQL `JOIN` clauses, GQL expresses multi-hop paths concisely using intuitive ASCII art syntax (`MATCH (c:Customer)-[:ordered]->(p:Product)`).
# - **Multi-Hop Traversal**: Effortlessly query transitive connections, such as discovering common distribution center bottlenecks among co-purchased items across multiple geographical locations.
# - **Enterprise Use Cases**: Essential for fraud detection rings, real-time recommendation engines, supply chain dependency analysis, and social network clustering.
#
