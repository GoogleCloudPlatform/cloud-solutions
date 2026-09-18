# BigQuery Agent Verification Guide & Metadata Reference

This document provides a comprehensive verification guideline and metadata
reference for Dataplex Catalog Custom Aspect **`sql-mapping` (SQL Mapping
Ruleset)** definitions, designed to evaluate conversational data agents
(Text-to-SQL models).

---

## 1. Custom Aspect Schema & Definitions

Each term in the Business Glossary contains structured Custom Aspect metadata
beyond standard natural language descriptions, enabling conversational agents to
execute accurate data retrieval and metadata guidance.

### 1.1. `sql-mapping` Aspect (SQL Mapping Ruleset)

Defines physical table bindings and SQL condition/expression snippets to ensure
deterministic Text-to-SQL translation:

| Field Name       | Type     | Required | Description & Usage                                                                        |
| :--------------- | :------- | :------- | :----------------------------------------------------------------------------------------- |
| **`type`**       | `string` | **Yes**  | Mapping classification (`SQL_Filter`, `Node_Attribute`, `SQL_Expression`, `Web_Analytics`) |
| **`table`**      | `string` | No       | Target BigQuery physical table (e.g., `thelook_ecommerce.users`)                           |
| **`condition`**  | `string` | No       | WHERE clause SQL filter condition applied for `SQL_Filter` types                           |
| **`expression`** | `string` | No       | Aggregation expression snippet applied for `SQL_Expression` / `Web_Analytics` types        |
| **`attribute`**  | `string` | No       | Mapped column name for target table (e.g., `traffic_source`)                               |

---

## 2. Key Terms Custom Aspect Reference Table

### 2.1. SQL Mapping Aspect Table (`sql-mapping`)

| Term ID                         | Display Name                 | Mapping Type (`type`) | Target Table (`table`)          | Mapping Rules (`condition` / `expression` / `attribute`)                                                                                                                                                                                                                   |
| :------------------------------ | :--------------------------- | :-------------------- | :------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`vip-customer`**              | VIP Customer                 | `SQL_Filter`          | `thelook_ecommerce.users`       | `condition`: `id IN (SELECT user_id FROM thelook_ecommerce.order_items GROUP BY user_id HAVING SUM(sale_price) >= 500 OR COUNT(DISTINCT order_id) >= 5)`                                                                                                                   |
| **`traffic-source`**            | Acquisition Channel          | `Node_Attribute`      | `thelook_ecommerce.users`       | `attribute`: `traffic_source`                                                                                                                                                                                                                                              |
| **`churned-customer`**          | Churned Customer             | `SQL_Filter`          | `thelook_ecommerce.users`       | `condition`: `id NOT IN (SELECT DISTINCT user_id FROM thelook_ecommerce.orders WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY))`                                                                                                                   |
| **`newly-registered-customer`** | Newly Registered Customer    | `SQL_Filter`          | `thelook_ecommerce.users`       | `condition`: `created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)`                                                                                                                                                                                           |
| **`cart-abandonment-rate`**     | Cart Abandonment Rate        | `Web_Analytics`       | `thelook_ecommerce.events`      | `expression`: `COUNT(DISTINCT CASE WHEN event_type = 'Cart' AND session_id NOT IN (SELECT DISTINCT session_id FROM thelook_ecommerce.events WHERE event_type = 'Purchase') THEN session_id END) / COUNT(DISTINCT CASE WHEN event_type = 'Cart' THEN session_id END) * 100` |
| **`profit-margin-rate`**        | Profit Margin Rate           | `SQL_Expression`      | `thelook_ecommerce.products`    | `expression`: `(retail_price - cost) / retail_price * 100`                                                                                                                                                                                                                 |
| **`returned-cancelled-items`**  | Returned/Cancelled Items     | `SQL_Filter`          | `thelook_ecommerce.order_items` | `condition`: `status IN ('Returned', 'Cancelled')`                                                                                                                                                                                                                         |
| **`avg-shipping-lead-time`**    | Average Shipping Lead Time   | `SQL_Expression`      | `thelook_ecommerce.orders`      | `expression`: `AVG(TIMESTAMP_DIFF(delivered_at, shipped_at, DAY))`                                                                                                                                                                                                         |
| **`return-rate`**               | Cancellation and Return Rate | `SQL_Expression`      | `thelook_ecommerce.order_items` | `expression`: `COUNTIF(status IN ('Returned', 'Cancelled')) / COUNT(*) * 100`                                                                                                                                                                                              |

---

## 3. Conversational Analytics Agent Validation Scenarios

### 3.1. Text-to-SQL Translation Validation (Relational DB Queries)

#### Q1. [Synonym Reverse-Mapping & SQL Filter Combination] Top Customer Aggregation

- **Natural Language Prompt:**
  "How many top customers had orders in the last month?"
- **Agent Resolution Path:**
    1.  Map `"top customer"` $\rightarrow$ `"VIP Customer"` (Term ID:
        `vip-customer`) via synonym taxonomy.
    1.  Extract `sql-mapping` (`SQL_Filter`) attached to `vip-customer`.
    1.  Inject `condition` snippet into the query as a subquery filter.
- **Expected Generated SQL:**

    ```sql
    SELECT COUNT(DISTINCT u.id) AS vip_user_count
    FROM `your-project-id.thelook_ecommerce.users` u
    JOIN `your-project-id.thelook_ecommerce.orders` o ON u.id = o.user_id
    WHERE u.id IN (
      -- VIP customer definition filter injected
      SELECT user_id
      FROM `your-project-id.thelook_ecommerce.order_items`
      GROUP BY user_id
      HAVING SUM(sale_price) >= 500 OR COUNT(DISTINCT order_id) >= 5
    )
    AND o.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY);
    ```

#### Q2. [Web Log Analytics & Marketing Attribute Combination] Cart Abandonment Trend by Channel

- **Natural Language Prompt:**
  "Calculate the cart abandonment rate by acquisition marketing channel and sort
  in descending order."
- **Agent Resolution Path:**
    1.  Map `"cart abandonment"` $\rightarrow$ `"Cart Abandonment Rate"` (Term
        ID: `cart-abandonment-rate`).
    1.  Map `"marketing channel"` $\rightarrow$ `"Acquisition Channel"` (Term
        ID: `traffic-source`) $\rightarrow$ resolve `users.traffic_source`
        column attribute.
    1.  Formulate aggregation query using the `expression` formula defined on
        `cart-abandonment-rate`.
- **Expected Generated SQL:**

    ```sql
    SELECT
      u.traffic_source AS marketing_channel,
      -- Cart abandonment rate calculation formula injected
      COUNT(DISTINCT CASE WHEN e.event_type = 'Cart' AND e.session_id NOT IN (
        SELECT DISTINCT session_id
        FROM `your-project-id.thelook_ecommerce.events`
        WHERE event_type = 'Purchase'
      ) THEN e.session_id END) /
      COUNT(DISTINCT CASE WHEN e.event_type = 'Cart' THEN e.session_id END) * 100 AS cart_abandonment_rate
    FROM `your-project-id.thelook_ecommerce.events` e
    JOIN `your-project-id.thelook_ecommerce.users` u ON e.user_id = u.id
    GROUP BY marketing_channel
    ORDER BY cart_abandonment_rate DESC;
    ```

#### Q3. [Composite Rule Combination] Product Margin & Refund Rate Correlation Analysis

- **Natural Language Prompt:**
  "For women's apparel with a product margin of 40% or higher, calculate the
  refund rate by brand."
- **Agent Resolution Path:**
    1.  Map `"product margin"` $\rightarrow$ `"Profit Margin Rate"` (Term ID:
        `profit-margin-rate`) $\rightarrow$ extract `expression` formula.
    1.  Map `"refund rate"` $\rightarrow$ `"Cancellation and Return Rate"` (Term
        ID: `return-rate`) $\rightarrow$ extract `expression` formula.
    1.  Combine both formula expressions into a single query with category
        filtering.
- **Expected Generated SQL:**

    ```sql
    SELECT
      p.brand,
      -- Cancellation and return rate formula applied
      COUNTIF(oi.status IN ('Returned', 'Cancelled')) / COUNT(*) * 100 AS refund_rate
    FROM `your-project-id.thelook_ecommerce.order_items` oi
    JOIN `your-project-id.thelook_ecommerce.products` p ON oi.product_id = p.id
    WHERE p.category = 'Women'
      -- Profit margin formula filter applied
      AND ((p.retail_price - p.cost) / p.retail_price * 100) >= 40
    GROUP BY p.brand
    ORDER BY refund_rate DESC;
    ```

#### Q4. [Negative Condition & Attribute Combination] Dormant User Acquisition Ingestion

- **Natural Language Prompt:**
  "What were the top 3 acquisition channels for users who are currently
  dormant?"
- **Agent Resolution Path:**
    1.  Map `"dormant user"` $\rightarrow$ `"Churned Customer"` (Term ID:
        `churned-customer`) $\rightarrow$ inject negative subquery `condition`.
    1.  Map `"acquisition channel"` $\rightarrow$ `"Acquisition Channel"` (Term
        ID: `traffic-source`) $\rightarrow$ resolve `users.traffic_source`
        column attribute.
- **Expected Generated SQL:**

    ```sql
    SELECT
      traffic_source AS signup_channel,
      COUNT(*) AS user_count
    FROM `your-project-id.thelook_ecommerce.users`
    WHERE id NOT IN (
      -- Churned customer filter: no orders in past 90 days
      SELECT DISTINCT user_id
      FROM `your-project-id.thelook_ecommerce.orders`
      WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
    )
    GROUP BY signup_channel
    ORDER BY user_count DESC
    LIMIT 3;
    ```
