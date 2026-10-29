# Database schemas, property graphs, and seed hydration (`data/`)

This directory contains the Cloud Spanner Enterprise Data Definition Language
(DDL) schema (`OperationalContextGraph`), the BigQuery Action Lineage DDL schema
(`ActionLineageGraph`), the pre-compiled Unstructured-to-Graph (U2G) policy
artifacts (`data/policies/`), and the idempotent seed script
(`spanner_seed.py`).

## Directory layout

The `data/` directory contains the database DDL files, seed script, and policy
artifacts:

```text
data/
├── README.md             # Database schemas and seed hydration specification (this file)
├── spanner_schema.sql    # Cloud Spanner Enterprise DDL (thelook_ecommerce R2G and U2G)
├── spanner_seed.py       # Hydrates bundled thelook_ecommerce slice and Customer A/B/C orders
├── thelook_slice.json    # Bundled referentially coherent slice of thelook_ecommerce
├── bigquery_schema.sql   # BigQuery ActionLineageGraph DDL
└── policies/             # Pre-compiled return policy document, U2G triples, and glossary JSON
    ├── return_policy_v1.md        # Source corporate return and abuse-prevention policy document
    ├── u2g_policy_triples.json    # Pre-compiled U2G policy, condition, and restriction triples
    └── business_glossary.json     # Local fallback contract for Knowledge Catalog terms
```

## Cloud Spanner `thelook_ecommerce` and U2G schema (`spanner_schema.sql`)

Cloud Spanner Graph requires **Spanner Enterprise Edition** (`edition =
"ENTERPRISE"`, `processing_units = 100` for Qwiklabs quota compliance).
`spanner_schema.sql` defines the six Relational-to-Graph (R2G) operational order
and fulfillment tables of Google Cloud's `thelook_ecommerce` dataset alongside
three U2G policy tables and two composite secondary indexes:

| Table or index name | Layer and graph role | Primary key / index key | Foreign keys and columns |
| :--- | :--- | :--- | :--- |
| `policies` | U2G node table (`policies`) | `PRIMARY KEY (policy_id)` (`STRING(64) NOT NULL`) | `name STRING(256) NOT NULL`, `source_document_uri STRING(512)`, `policy_version STRING(32)`, `status STRING(32) NOT NULL`, `valid_from TIMESTAMP NOT NULL`, `valid_to TIMESTAMP` |
| `policy_conditions` | U2G node (`policy_conditions`) and edge (`requires_condition`) | `PRIMARY KEY (condition_id)` (`STRING(64) NOT NULL`) | `FK (policy_id) REFERENCES policies (policy_id)`, `applicable_tier STRING(32) NOT NULL` (`'STANDARD'` or `'VIP'`), `max_refunds_100d INT64 NOT NULL`, `return_window_days INT64 NOT NULL`, `threshold_expression STRING(256) NOT NULL` |
| `policy_restrictions` | U2G node (`policy_restrictions`) and edge (`enforces_restriction`) | `PRIMARY KEY (restriction_id)` (`STRING(64) NOT NULL`) | `FK (policy_id) REFERENCES policies (policy_id)`, `action_code STRING(64) NOT NULL`, `description STRING(512)` |
| `distribution_centers` | R2G node table (`distribution_centers`) | `PRIMARY KEY (id)` (`INT64 NOT NULL`) | `name STRING(256)`, `latitude FLOAT64`, `longitude FLOAT64` |
| `users` | R2G node table (`users`) | `PRIMARY KEY (id)` (`INT64 NOT NULL`) | `first_name STRING(128)`, `last_name STRING(128)`, `email STRING(256)`, `customer_tier STRING(32) NOT NULL` (`'STANDARD'` or `'VIP'`), `age INT64`, `gender STRING(32)`, `state STRING(128)`, `street_address STRING(256)`, `postal_code STRING(64)`, `city STRING(128)`, `country STRING(128)`, `latitude FLOAT64`, `longitude FLOAT64`, `traffic_source STRING(128)`, `created_at TIMESTAMP` |
| `products` | R2G node (`products`) and edges (`supplied_by`, `governed_by`) | `PRIMARY KEY (id)` (`INT64 NOT NULL`) | `FK (distribution_center_id) REFERENCES distribution_centers (id) NOT NULL`, `FK (policy_id) REFERENCES policies (policy_id) NOT NULL`, `cost FLOAT64`, `category STRING(128)`, `name STRING(256)`, `brand STRING(128)`, `retail_price FLOAT64`, `department STRING(128)`, `sku STRING(128)` |
| `inventory_items` | R2G node (`inventory_items`) and edge (`is_product`) | `PRIMARY KEY (id)` (`INT64 NOT NULL`) | `FK (product_id) REFERENCES products (id) NOT NULL`, `FK (product_distribution_center_id) REFERENCES distribution_centers (id)`, `created_at TIMESTAMP`, `sold_at TIMESTAMP`, `cost FLOAT64`, `product_category STRING(128)`, `product_name STRING(256)`, `product_brand STRING(128)`, `product_retail_price FLOAT64`, `product_department STRING(128)`, `product_sku STRING(128)` |
| `orders` | R2G node (`orders`) and edge (`places`) | `PRIMARY KEY (order_id)` (`INT64 NOT NULL`) | `FK (user_id) REFERENCES users (id) NOT NULL`, `status STRING(64) NOT NULL`, `gender STRING(32)`, `created_at TIMESTAMP NOT NULL`, `returned_at TIMESTAMP`, `shipped_at TIMESTAMP`, `delivered_at TIMESTAMP`, `num_of_item INT64` |
| `order_items` | R2G edge table (`contains_item`) | `PRIMARY KEY (id)` (`INT64 NOT NULL`) | `FK (order_id) REFERENCES orders (order_id) NOT NULL`, `FK (user_id) REFERENCES users (id) NOT NULL`, `FK (product_id) REFERENCES products (id) NOT NULL`, `FK (inventory_item_id) REFERENCES inventory_items (id) NOT NULL`, `status STRING(64) NOT NULL`, `created_at TIMESTAMP NOT NULL`, `shipped_at TIMESTAMP`, `delivered_at TIMESTAMP`, `returned_at TIMESTAMP`, `sale_price FLOAT64 NOT NULL`, `refund_trace_id STRING(128)` |
| `idx_orders_user_created` | Secondary index on `orders` | `(user_id, created_at DESC) STORING (status, returned_at, delivered_at)` | Accelerates per-customer order history lookups and 100-day rolling window traversals. |
| `idx_order_items_order_status` | Secondary index on `order_items` | `(order_id, status) STORING (inventory_item_id, sale_price, returned_at, refund_trace_id)` | Accelerates `contains_item` edge filtering on `status = 'Returned'`. |

### Property graph definition (`OperationalContextGraph`)

`spanner_schema.sql` registers the unified R2G and U2G property graph with the
following DDL statement:

```sql
-- Purpose: Define the unified OperationalContextGraph property graph in Cloud Spanner.
-- Target Engine: Cloud Spanner DDL (thelook-soa-db).
-- How It Works: Maps 5 Relational-to-Graph (R2G) commerce tables and 3
--   Unstructured-to-Graph (U2G) policy tables as NODE TABLES, and binds their
--   foreign-key relationships into 7 labeled EDGE TABLES.
-- Information Gathered: Enables native ISO GQL traversals (GRAPH OperationalContextGraph
--   MATCH ...) across customer orders, products, fulfillment centers, and active
--   refund policies in a single read snapshot or Spanner Data Boost pushdown.
CREATE PROPERTY GRAPH OperationalContextGraph
  NODE TABLES (
    users,
    products,
    orders,
    distribution_centers,
    inventory_items,
    policies,
    policy_conditions,
    policy_restrictions
  )
  EDGE TABLES (
    orders AS places
      SOURCE KEY (user_id) REFERENCES users (id)
      DESTINATION KEY (order_id) REFERENCES orders (order_id)
      LABEL places,
    order_items AS contains_item
      SOURCE KEY (order_id) REFERENCES orders (order_id)
      DESTINATION KEY (inventory_item_id) REFERENCES inventory_items (id)
      LABEL contains_item,
    inventory_items AS is_product
      SOURCE KEY (id) REFERENCES inventory_items (id)
      DESTINATION KEY (product_id) REFERENCES products (id)
      LABEL is_product,
    products AS supplied_by
      SOURCE KEY (id) REFERENCES products (id)
      DESTINATION KEY (distribution_center_id) REFERENCES distribution_centers (id)
      LABEL supplied_by,
    products AS governed_by
      SOURCE KEY (id) REFERENCES products (id)
      DESTINATION KEY (policy_id) REFERENCES policies (policy_id)
      LABEL governed_by,
    policy_conditions AS requires_condition
      SOURCE KEY (policy_id) REFERENCES policies (policy_id)
      DESTINATION KEY (condition_id) REFERENCES policy_conditions (condition_id)
      LABEL requires_condition,
    policy_restrictions AS enforces_restriction
      SOURCE KEY (policy_id) REFERENCES policies (policy_id)
      DESTINATION KEY (restriction_id) REFERENCES policy_restrictions (restriction_id)
      LABEL enforces_restriction
  );
```

## BigQuery Action Lineage Graph schema (`bigquery_schema.sql`)

The BigQuery dataset `soa_action_lineage` stores four append-only execution
trace tables that define `ActionLineageGraph`:

| Table name | Graph node / edge role | Primary key (`NOT ENFORCED`) | Columns and nullability rules |
| :--- | :--- | :--- | :--- |
| `soa_action_lineage.agent_sessions` | Node `AgentSession` | `PRIMARY KEY (trace_id)` | `trace_id STRING NOT NULL`, `customer_id INT64 NOT NULL`, `target_order_id INT64` (nullable when user omits an order ID), `user_prompt STRING NOT NULL`, `started_at TIMESTAMP NOT NULL` |
| `soa_action_lineage.workflow_nodes` | Node `WorkflowNode`, edge `executed_node` (`AgentSession` to `WorkflowNode`) | `PRIMARY KEY (node_exec_id)` | `node_exec_id STRING NOT NULL`, `trace_id STRING NOT NULL`, `node_name STRING NOT NULL`, `step_order INT64 NOT NULL`, `latency_ms FLOAT64 NOT NULL`, `executed_at TIMESTAMP NOT NULL` |
| `soa_action_lineage.policy_evaluations` | Node `PolicyEvaluation`, edge `evaluated_policy` (`WorkflowNode` to `PolicyEvaluation`) | `PRIMARY KEY (eval_id)` | `eval_id STRING NOT NULL`, `node_exec_id STRING NOT NULL`, `trace_id STRING NOT NULL`, `catalog_term_id STRING NOT NULL`, `policy_id STRING NOT NULL`, `policy_name STRING NOT NULL`, `observed_refunds_100d INT64 NOT NULL`, `max_refunds_100d INT64 NOT NULL` (populated with baseline policy defaults when `order_found == False` or `order_id is None`), `observed_order_age_days INT64` (nullable when order is not delivered yet or not found), `return_window_days INT64 NOT NULL`, `evaluation_result STRING NOT NULL`, `evaluated_at TIMESTAMP NOT NULL` |
| `soa_action_lineage.agent_actions` | Node `AgentAction`, edge `triggered_action` (`PolicyEvaluation` to `AgentAction`) | `PRIMARY KEY (action_id)` | `action_id STRING NOT NULL`, `eval_id STRING NOT NULL`, `trace_id STRING NOT NULL`, `action_type STRING NOT NULL`, `decision_status STRING NOT NULL`, `rejection_reason STRING` (nullable on `APPROVED`), `created_at TIMESTAMP NOT NULL` |

### Property graph DDL (`bigquery_schema.sql`)

While ISO Graph Query Language (GQL) pushdown to Spanner Data Boost uses
`EXTERNAL_QUERY('${SPANNER_CONNECTION_ID}', ...)` over the `spanner-data-boost`
connection, `bigquery_schema.sql` defines
`soa_action_lineage.ActionLineageGraph` over the four trace tables:

```sql
-- Purpose: Define the ActionLineageGraph property graph over the four append-only
--   agent execution trace tables in BigQuery.
-- Target Engine: BigQuery DDL (soa_action_lineage dataset).
-- How It Works: Registers agent_sessions, workflow_nodes, policy_evaluations, and
--   agent_actions as NODE TABLES and links them via executed_node, evaluated_policy,
--   and triggered_action EDGE TABLES.
-- Information Gathered: Enables ISO GQL GRAPH_TABLE(soa_action_lineage.ActionLineageGraph
--   MATCH ...) queries to audit end-to-end ADK 2.0 agent decisions and policy evaluations.
CREATE OR REPLACE PROPERTY GRAPH `soa_action_lineage.ActionLineageGraph`
  NODE TABLES (
    `soa_action_lineage.agent_sessions` AS AgentSession KEY (trace_id),
    `soa_action_lineage.workflow_nodes` AS WorkflowNode KEY (node_exec_id),
    `soa_action_lineage.policy_evaluations` AS PolicyEvaluation KEY (eval_id),
    `soa_action_lineage.agent_actions` AS AgentAction KEY (action_id)
  )
  EDGE TABLES (
    `soa_action_lineage.workflow_nodes` AS executed_node
      KEY (node_exec_id)
      SOURCE KEY (trace_id) REFERENCES AgentSession (trace_id)
      DESTINATION KEY (node_exec_id) REFERENCES WorkflowNode (node_exec_id),
    `soa_action_lineage.policy_evaluations` AS evaluated_policy
      KEY (eval_id)
      SOURCE KEY (node_exec_id) REFERENCES WorkflowNode (node_exec_id)
      DESTINATION KEY (eval_id) REFERENCES PolicyEvaluation (eval_id),
    `soa_action_lineage.agent_actions` AS triggered_action
      KEY (action_id)
      SOURCE KEY (eval_id) REFERENCES PolicyEvaluation (eval_id)
      DESTINATION KEY (action_id) REFERENCES AgentAction (action_id)
  );
```

## Pre-compiled policy and glossary artifacts (`data/policies/`)

`data/policies/` stores three files used during container startup and UI 2
governance inspection:

1.  **`return_policy_v1.md`:** Source corporate return policy document defining
    the 30-day delivery return window (`order-age-days <= 30`), the Standard
    tier 100-day rolling return cap (`rolling-100d-refund-count < 10` for
    `applicable_tier = 'STANDARD'`), and the VIP tier 100-day rolling return cap
    (`rolling-100d-refund-count < 20` for `applicable_tier = 'VIP'`).
1.  **`u2g_policy_triples.json`:** Pre-compiled U2G entity and relationship
    triples with top-level keys `{"policies": [...], "policy_conditions": [...],
    "policy_restrictions": [...]}` loaded by `spanner_seed.py` into `policies`,
    `policy_conditions` (`COND-REFUND-STD-100D-30D` and
    `COND-REFUND-VIP-100D-30D`), and `policy_restrictions` and returned by `GET
    /api/governance` for UI 2 (`/console`).
1.  **`business_glossary.json`:** Governed semantic contract (adapting the
    glossary schema pattern from `projects/agentic-knowledge-catalog`) containing
    both top-level contract fields (`catalog_term_id =
    "rolling-100d-refund-count"`, `secondary_term_id = "order-age-days"`,
    `tier_term_id = "customer-loyalty-tier"`, `returned_status = "Returned"`,
    `eligible_order_status = "Complete"`, `rolling_window_days = 100`,
    `standard_tier = "STANDARD"`, `vip_tier = "VIP"`) and the `"terms"` array
    defining the three governed glossary terms (`rolling-100d-refund-count`,
    `order-age-days`, and `customer-loyalty-tier` with `display_name`,
    `category`, `description`, and `sql_mapping` for `table` and `expression`),
    used by `catalog_client.py` as a local fallback if the Knowledge Catalog API
    is unreachable and returned as `glossary_terms` by `GET /api/governance` for
    the UI 2 **Preview Glossary & Contract** modal.

## `thelook_ecommerce` hydration and deterministic seed data (`spanner_seed.py`)

Because the Qwiklabs Terraform runner container does not pre-install Python
database client libraries, `data/spanner_seed.py` exposes three entrypoints used
by the Cloud Run service:

- **`get_spanner_database()` (shared database client cache):** Caches the
  `(project_id, instance_id, database_id)` Cloud Spanner `Database` instance in
  `_SPANNER_DB_CACHE` across `spanner_seed.py` and `app/agent/spanner_client.py`
  so runtime graph queries reuse an active Spanner session pool (`~187 ms`
  `evaluate_spanner_policy` latency) without creating duplicate background
  Cloud Monitoring metric export threads.
- **`seed_spanner_if_empty()` (called by `ensure_bootstrapped()` on startup):**
  Checks whether `order_id = 90124` already exists in `orders` and measures
  `TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), delivered_at, DAY)` on `ORD-90124`. If
  present and `age_days <= 15`, it returns immediately so Cloud Run scale-out or
  cold-start instances never overwrite a student's committed refund mid-lab. If
  the database is empty or `age_days > 15` (indicating stale relative timestamps
  on a long-lived deployment), it runs all three hydration stages below with
  fresh relative UTC timestamps.
- **`reset_demo_orders()` (called only by `POST /api/demo/reset`):** Refreshes
  all three hydration stages (`_build_stage1_policy_rows`,
  `_build_stage2_slice_rows`, and `_build_stage3_demo_rows`) with fresh relative
  UTC timestamps (`datetime.now(timezone.utc)`) and resets `order_id: 90124`,
  `order_id: 90588`, and `order_id: 90910` in `orders` and `order_items` to
  `status = 'Complete'`, `returned_at = NULL`, and `refund_trace_id = NULL`
  (paired with `reset_bigquery_lineage()` in `app/agent/bq_lineage.py` and
  `clear_pending_confirmations()` in `app/agent/workflow.py`).

Initial hydration populates Cloud Spanner (`thelook-soa-db`) in three
foreign-key-ordered stages:

1.  **Stage 1: U2G policy node hydration (`policies`, `policy_conditions`,
    `policy_restrictions`):**
    - Seeds the active policy graph first so `products.policy_id` foreign keys
      succeed on insertion:
        - `policies`: `policy_id = 'POL-REFUND-STD-V1'`, `name = 'Tiered
          Standard and VIP Refund Policy'`, `source_document_uri =
          'data/policies/return_policy_v1.md'`, `policy_version = '1.0'`,
          `status = 'ACTIVE'`, `valid_from = TIMESTAMP '2025-01-01T00:00:00Z'`,
          `valid_to = NULL`.
        - `policy_conditions` (2 tier-specific condition rows referencing
          `POL-REFUND-STD-V1`):
            - Standard tier row: `condition_id = 'COND-REFUND-STD-100D-30D'`,
              `policy_id = 'POL-REFUND-STD-V1'`, `applicable_tier = 'STANDARD'`,
              `max_refunds_100d = int(os.getenv("MAX_REFUNDS_100D_LIMIT",
              "10"))`, `return_window_days = 30`, `threshold_expression =
              'prior_refund_count_100d < 10 AND target_order_age_days <= 30'`.
            - VIP tier row: `condition_id = 'COND-REFUND-VIP-100D-30D'`,
              `policy_id = 'POL-REFUND-STD-V1'`, `applicable_tier = 'VIP'`,
              `max_refunds_100d = int(os.getenv("VIP_MAX_REFUNDS_100D_LIMIT",
              "20"))`, `return_window_days = 30`, `threshold_expression =
              'prior_refund_count_100d < 20 AND target_order_age_days <= 30'`.
        - `policy_restrictions`: `restriction_id = 'RES-DENY-AUTO-REFUND'`,
          `policy_id = 'POL-REFUND-STD-V1'`, `action_code =
          'DENY_AUTONOMOUS_REFUND'`, `description = 'Block autonomous Spanner
          refund mutation and log rejection trace to BigQuery'`.
1.  **Stage 2: Referentially coherent `thelook_ecommerce` catalog and
    storefront hydration (`data/thelook_slice.json`):**
    - Reads `data/thelook_slice.json` (which contains top-level keys
      `{"distribution_centers": [...], "products": [...], "users": [...],
      "inventory_items": [...], "orders": [...], "order_items": [...]}` with IDs
      `< 80000`, excluding reserved `users.id` `1001`, `2048`, and `3072`).
    - Loads all 10 rows of `thelook_ecommerce.distribution_centers`, such as
      `Memphis TN`, `Chicago IL`, `Houston TX`, and `Savannah GA`, along with
      `products` (`distribution_center_id NOT NULL`, `policy_id =
      'POL-REFUND-STD-V1'`), `users` (`customer_tier = 'STANDARD'`),
      `inventory_items`, `orders`, and `order_items` so UI 1 (`/shop`) displays
      `thelook` merchandise, categories, brands, and distribution centers.
1.  **Stage 3: Deterministic demo personas with relative timestamps (IDs `>=
    80000`):**
    - Generates all demo order timestamps (`created_at`, `shipped_at`,
      `delivered_at`, and `returned_at`) relative to `CURRENT_TIMESTAMP()` using
      `thelook_ecommerce` status values (`'Complete'`, `'Returned'`, and
      `'Shipped'`). For each demo order below, `spanner_seed.py` inserts 1
      `orders` row (`num_of_item = 1`), 1 `inventory_items` row (`id =
      order_id`, referencing a Stage 2 `products.id`), and 1 `order_items` row
      (`id = order_id`, `inventory_item_id = order_id`, `refund_trace_id =
      NULL`):
    - **Customer A (`user_id: 1001`, `alice.chen@example.com`, `customer_tier =
      'STANDARD'`):**
        - 2 historical returned order items (`order_id: 80001` and `80002`) with
          `created_at` and `returned_at` set to
          `TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 45 DAY)` and `INTERVAL 25
          DAY`, and `orders.status = 'Returned'` and `order_items.status =
          'Returned'`.
        - 1 primary eligible target order (`order_id: 90124`) delivered at
          `TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)` with
          `orders.status = 'Complete'` and `order_items.status = 'Complete'`.
        - 2 additional edge-case orders for student testing:
            - `order_id: 90125` delivered at `TIMESTAMP_SUB(CURRENT_TIMESTAMP(),
              INTERVAL 45 DAY)` with `orders.status = 'Complete'` (tests 30-day
              return window expiration).
            - `order_id: 90126` created at `TIMESTAMP_SUB(CURRENT_TIMESTAMP(),
              INTERVAL 3 DAY)` with `orders.status = 'Shipped'` and
              `delivered_at = NULL` (tests non-delivered order status
              rejection).
    - **Customer B (`user_id: 2048`, `jordan.taylor@example.com`, `customer_tier
      = 'STANDARD'`):**
        - 12 historical returned order items (`order_id: 81001` through `81012`)
          with `created_at` and `returned_at` distributed between
          `TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)` and `INTERVAL 15
          DAY`, and `orders.status = 'Returned'` and `order_items.status =
          'Returned'`.
        - 1 active target order (`order_id: 90588`) delivered at
          `TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 DAY)` with
          `orders.status = 'Complete'` and `order_items.status = 'Complete'`.
    - **Customer C (`user_id: 3072`, `claire.vance@example.com`, `customer_tier
      = 'VIP'`):**
        - 12 historical returned order items (`order_id: 82001` through `82012`)
          with `created_at` and `returned_at` distributed between
          `TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)` and `INTERVAL 15
          DAY`, and `orders.status = 'Returned'` and `order_items.status =
          'Returned'` (identical 100-day return count to Customer B).
        - 1 active target order (`order_id: 90910`) delivered at
          `TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)` with
          `orders.status = 'Complete'` and `order_items.status = 'Complete'`
          (eligible under VIP condition `COND-REFUND-VIP-100D-30D` where
          `max_refunds_100d = 20`).
