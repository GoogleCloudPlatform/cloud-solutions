# Corporate e-commerce return and abuse-prevention policy (`POL-REFUND-STD-V1`)

- **Policy ID:** `POL-REFUND-STD-V1`
- **Policy Name:** `Tiered Standard and VIP Refund Policy`
- **Version:** `1.0`
- **Status:** `ACTIVE`
- **Effective Date:** `2025-01-01T00:00:00Z`

## 1. Scope and semantic definitions

This policy governs all autonomous order refund mutations executed by the
customer support System of Action across `thelook_ecommerce` merchandise. All
metric definitions are governed in **Knowledge Catalog**
(`soa-business-glossary`):

- **Order Age in Days (`order-age-days`):** Elapsed days since delivery
  (`TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), orders.delivered_at, DAY)`). An order is
  eligible for autonomous return evaluation only when `orders.status =
  'Complete'` and `delivered_at IS NOT NULL`.
- **Rolling 100-Day Refund Count (`rolling-100d-refund-count`):** Count of
  distinct returned order items (`order_items.status = 'Returned'`) recorded for
  the customer across other orders (`orders.order_id != target_order_id`) over
  the trailing 100 days.
- **Customer Loyalty Tier (`customer-loyalty-tier`):** Authoritative customer
  tier stored in `users.customer_tier`, verified against the governed literals
  `'STANDARD'` and `'VIP'`.

## 2. Tiered eligibility conditions (`policy_conditions`)

Autonomous refund approval requires the target order to satisfy both the 30-day
delivery window and the tier-specific 100-day rolling return cap:

| Condition ID | Applicable tier (`applicable_tier`) | Return window (`return_window_days`) | Rolling 100-day cap (`max_refunds_100d`) | Threshold expression |
| :--- | :--- | :--- | :--- | :--- |
| `COND-REFUND-STD-100D-30D` | `STANDARD` | `30` days | `10` items | `prior_refund_count_100d < 10 AND target_order_age_days <= 30` |
| `COND-REFUND-VIP-100D-30D` | `VIP` | `30` days | `20` items | `prior_refund_count_100d < 20 AND target_order_age_days <= 30` |

## 3. Enforcement restriction (`policy_restrictions`)

- **Restriction ID:** `RES-DENY-AUTO-REFUND`
- **Action Code:** `DENY_AUTONOMOUS_REFUND`
- **Enforcement Rule:** When any precondition fails (`MISSING_ORDER_ID`,
  `ORDER_NOT_FOUND_OR_UNAUTHORIZED`, `ALREADY_RETURNED`, `ORDER_NOT_DELIVERED`,
  `RETURN_WINDOW_EXPIRED`, or `MAX_REFUNDS_EXCEEDED`), the workflow must block
  autonomous Cloud Spanner mutation (`BLOCK_SPANNER_MUTATION`) and record the
  rejection lineage trace in BigQuery (`soa_action_lineage.ActionLineageGraph`).
