# Google ADK 2.0 refund workflow (`app/agent/`)

This directory contains the **Google Agent Development Kit 2.0 (ADK 2.0)**
([https://adk.dev/2.0/](https://adk.dev/2.0/)) workflow runtime, Cloud Spanner
Graph ISO Graph Query Language (GQL) client, Knowledge Catalog semantic
contract resolver, and BigQuery Action Lineage callback writer.

## Directory layout

The `app/agent/` package contains the following modules:

```text
app/agent/
├── README.md          # ADK 2.0 workflow and node specification (this file)
├── __init__.py        # Package initializer
├── workflow.py        # ADK 2.0 Workflow graph and BigQuery lineage callbacks
├── spanner_client.py  # Cloud Spanner Graph ISO GQL queries and mutations
├── bq_lineage.py      # BigQuery ActionLineageGraph buffered writer and GQL runner
└── catalog_client.py  # Knowledge Catalog glossary and aspect lookup client
```

## ADK 2.0 hybrid workflow design (`workflow.py`)

`workflow.py` compiles a `google.adk.Workflow` (`AdkWorkflow`) that uses
`google.adk.Agent` (`AdkAgent`) nodes for natural language intent extraction and
response synthesis, and wraps catalog lookups, Spanner GQL evaluations, and
transaction commits in `google.adk.workflow.FunctionNode` step nodes.

Before starting the workflow, the FastAPI handler (`POST /api/chat/refund` or
`POST /api/chat/refund/stream`) binds `ctx.state["user_id"]`,
`ctx.state["trace_id"]`, an optional `ctx.state["_step_observer"]` callback, and
an empty `ctx.state["lineage_buffer"]` outside the LLM prompt, and
`Workflow.run(ctx)` executes `refund_system_of_action.adk_workflow` via
`google.adk.runners.InMemoryRunner`. The workflow executes five sequential
nodes:

| `step_order` | Canonical `node_name` | Node type | Input `ctx.state` keys | Output `ctx.state` keys | Execution and fallback behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `1` | `IntentAgent` | `google.adk.Agent` (`before_agent_callback`, `gemini-3-flash-preview`) + hybrid order resolver | `user_prompt`, `user_id`, `trace_id`, `confirmed`, `pending_order_id` | `order_id` (`int \| None`), `resolution_mode` (`str`), `unmatched_product` (`str \| None`), `candidate_orders` (`list[dict]`), `inferred_order` (`dict \| None`), `refund_reason` (`str`) | Runs `google.adk.Agent` (`intent_agent.adk_agent`) via `before_agent_callback` against the `GOOGLE_CLOUD_LOCATION = "global"` Vertex AI endpoint (`_generate_gemini_text_fast` with `ThinkingLevel.MINIMAL`, `max_output_tokens = 250`, `timeout = 4000` ms, and `attempts = 1`). When `confirmed=True` or an explicit 5-digit `ORD-<id>` is present in the prompt (such as 1-click prompt chips), Step 1 resolves `order_id` directly and skips the Step 1 LLM call to conserve Qwiklabs RPM quota for Step 5. On natural-language prompts without an explicit `ORD-<id>`, it invokes `_try_gemini_intent_extraction` + `_apply_gemini_intent_decision` first with full multi-turn conversation context (`candidate_orders`, `list_orders_pool`, `focused_order`, `pending_order`, `awaiting_order`) to classify structured intents (`REFUND_REQUEST`, `ORDER_INFO`, `ORDER_LIST`, `POLICY_INFO`, `CONFIRM_REFUND`, `DECLINE_CONFIRMATION`, `CANCEL_REFUND`), resolve `order_id`, `list_limit`, and `status_filter`, and detect unpurchased storefront items (`unmatched_product` matched against `STOREFRONT_CATALOG_PRODUCTS`, evaluated before falling back to `focused_order`). Falls back to deterministic regex/keyword inference (`_infer_order_from_candidates`, `_detect_unmatched_product`, `_filter_orders_by_prompt_status`, `SINGLE_ORDER_SELECTOR_CUES`, `NEGATED_REFUND_REGEX`) when Vertex AI is disabled or raises `google.genai.errors.APIError`. |
| `2` | `resolve_catalog_contract` | `google.adk.workflow.FunctionNode` | `trace_id` | `catalog_contract` (`dict`) | Calls `fetch_knowledge_catalog_aspect()` to resolve the governed contract for `rolling-100d-refund-count`, `order-age-days`, and `customer-loyalty-tier` from Knowledge Catalog (or the 5-minute in-memory cache / local JSON fallback). |
| `3` | `evaluate_spanner_policy` | `google.adk.workflow.FunctionNode` | `user_id`, `order_id`, `resolution_mode`, `catalog_contract` | `eval_id` (`str`), `policy_eval` (`dict`) | If `order_id is None` and `resolution_mode` is `"list_orders"`, `"policy_info"`, or `"cancelled"`, sets `evaluation_result = "INFO"` and `failure_code = None`. If `order_id is None` on an unconfirmed refund request (`"clarify"`), sets `failure_code = "MISSING_ORDER_ID"` and `evaluation_result = "FAIL"`. Otherwise calls `query_spanner_operational_context_graph()` (which matches `cond.applicable_tier = u.customer_tier` in GQL) and classifies eligibility against the six deterministic failure codes below (or `evaluation_result = "INFO"` when `resolution_mode == "order_info"`). |
| `4` | `route_and_commit_action` | `google.adk.workflow.FunctionNode` | `user_id`, `order_id`, `trace_id`, `eval_id`, `resolution_mode`, `unmatched_product`, `require_confirmation`, `confirmed`, `catalog_contract`, `policy_eval` | `action_outcome` (`dict`) | Routes read-only informational modes to `ORDER_LIST` (`LIST_CUSTOMER_ORDERS`), `ORDER_INFO` (`SHOW_ORDER_DETAILS`), or `POLICY_INFO` (`SHOW_POLICY_AND_ORDERS`). When `require_confirmation=True`, enforces a universal two-turn customer confirmation gate: Turn 1 pauses at `decision_status = "PENDING_CONFIRMATION"` (`action_type = "AWAIT_CUSTOMER_CONFIRMATION"`) whenever a valid order is resolved (`order_found == True`, whether `PASS` or `FAIL`) or when `order_id is None` (`"clarify"`, enriched with `unmatched_product` when the customer asked for an item they never purchased, or `"cancelled"`). On Turn 2 (`confirmed=True`), executes `commit_spanner_order_refund()` inside a Cloud Spanner read-write transaction if `evaluation_result == "PASS"`, or returns `decision_status = "DENIED"` (`"BLOCK_SPANNER_MUTATION"`) if `evaluation_result == "FAIL"`. |
| `5` | `ResponseAgent` | `google.adk.Agent` (`before_agent_callback`, `gemini-3-flash-preview`) + template fallback & card sync | `user_prompt`, `policy_eval`, `action_outcome`, `unmatched_product`, `candidate_orders`, `trace_id` | `final_response` (`str`), `candidate_orders` (`list[dict]`) | Runs `google.adk.Agent` (`response_agent.adk_agent`) via `before_agent_callback`. Invokes `_try_gemini_response_generation` (`_generate_gemini_text_fast` with `ThinkingLevel.MINIMAL`, `max_output_tokens = 300`, `timeout = 4000` ms, and `attempts = 1`) across all `decision_status` outcomes (`PENDING_CONFIRMATION`, `APPROVED`, `DENIED`, `ORDER_INFO`, `ORDER_LIST`, `POLICY_INFO`) to synthesize grounded replies (including unpurchased product explanations when `unmatched_product` is set) with a deterministic bilingual template fallback (`_format_bilingual_fallback_response`), and runs `_sync_candidate_orders_with_response()` on `ORDER_LIST` and `POLICY_INFO` turns so `ctx.state["candidate_orders"]` and `_LAST_SHOWN_ORDERS` match the `ORD-<id>` order IDs cited in `final_response`. |

### Fast Vertex AI Gemini execution and Qwiklabs quota resilience (`_get_genai_client` and `_generate_gemini_text_fast`)

`workflow.py` configures the Vertex AI Gemini client for low latency and bounded
failure recovery in shared Qwiklabs (`gcpfree`) projects:

- **Single-attempt 4-second HTTP client (`_get_genai_client`):** Passes
  `types.HttpOptions(timeout=int(os.getenv("VERTEX_LLM_TIMEOUT_MS", "4000")),
  retry_options=types.HttpRetryOptions(attempts=1))` to `genai.Client`. By
  default, `google-genai` sets `timeout=None` and retries `429`/`503`/`504`
  responses up to 5 times with 60-second exponential backoff, which can stall a
  Cloud Run request until the 300-second container timeout under Qwiklabs
  Dynamic Shared Quota contention. Setting a 4-second timeout with `attempts=1`
  bounds every LLM call and fails over immediately to the deterministic fallback
  if Vertex AI throttles a request.
- **Minimal thinking budget (`_generate_gemini_text_fast`):** Uses
  `ADK_MODEL_NAME = "gemini-3-flash-preview"` with
  `ThinkingConfig(thinking_level=ThinkingLevel.MINIMAL)` (falling back to
  `ThinkingLevel.LOW` if a custom model override rejects `MINIMAL`) and caps
  `max_output_tokens` at `250..300`, completing each Gemini call in 1.1 to 1.5
  seconds.
- **Single-LLM-call quota conservation (`_run_intent_node`):** When `confirmed`
  is `True` or `ORDER_ID_REGEX` extracts an explicit 5-digit order ID from the
  prompt (such as 1-click prompt chips `"Please refund my order ORD-90124."`),
  Step 1 resolves the order ID directly without calling Gemini, cutting per-turn
  RPM consumption in half so Step 5 (`ResponseAgent`) consistently executes a
  live Gemini call. Natural-language prompts without an explicit order ID execute
  live Gemini calls in both Step 1 and Step 5.

### Deterministic failure classification rules (`evaluate_spanner_policy`)

`evaluate_spanner_policy` (and `commit_spanner_order_refund` under the
read-write transaction lock) evaluates conditions in strict priority order and
sets `evaluation_result = "PASS"` only when `failure_code is None`:

| Priority | `failure_code` | Trigger condition | Rejection reason template (`route_and_commit_action`) |
| :--- | :--- | :--- | :--- |
| `1` | `MISSING_ORDER_ID` | `ctx.state["order_id"] is None` (and `resolution_mode` not in `{"list_orders", "policy_info", "cancelled"}`) | `"Which order would you like to refund? Select one of your active orders below: ..."` (or `"Please provide a valid 5-digit order number..."` when no active orders exist) |
| `2` | `ORDER_NOT_FOUND_OR_UNAUTHORIZED` | `not eval_result["order_found"]` | `"Order {order_id} was not found for user {user_id}."` |
| `3` | `ALREADY_RETURNED` | `target_order_status == contract["returned_status"]` (`'Returned'`) | `"Order {order_id} has already been returned (reset demo data to re-test)."` |
| `4` | `ORDER_NOT_DELIVERED` | `target_order_status != contract["eligible_order_status"]` (`'Complete'`) or `target_order_age_days is None` | `"Order {order_id} has status '{target_order_status}' and has not been delivered yet."` |
| `5` | `RETURN_WINDOW_EXPIRED` | `target_order_age_days > eval_result["return_window_days"]` (`30`) | `"Order was delivered {target_order_age_days} days ago, exceeding the {return_window_days}-day return window."` |
| `6` | `MAX_REFUNDS_EXCEEDED` | `prior_refund_count_100d >= eval_result["max_refunds_100d"]` (`10` for `STANDARD`, `20` for `VIP`) | `"Customer ({customer_tier} tier) already has {prior_refund_count_100d} returned items in the last 100 days (limit: {max_refunds_100d})."` |

### State dictionary schemas (`policy_eval` and `action_outcome`)

Step 3 (`evaluate_spanner_policy`) writes `ctx.state["policy_eval"]` with the
following keys:

- `eval_id` (`str`): `f"EVAL-{uuid4().hex[:8]}"`.
- `node_exec_id` (`str`): The execution ID of Step 3
  (`evaluate_spanner_policy`), which `bq_lineage.py` writes to
  `soa_action_lineage.policy_evaluations.node_exec_id`.
- `catalog_term_id` (`str`): `"order-age-days"` when `failure_code` is
  `"RETURN_WINDOW_EXPIRED"` or `"ORDER_NOT_DELIVERED"`,
  `"customer-loyalty-tier"` when `evaluation_result == "PASS"` and
  `customer_tier == catalog_contract["vip_tier"]` (`"VIP"`) with
  `prior_refund_count_100d >= int(os.getenv("MAX_REFUNDS_100D_LIMIT", "10"))`,
  and `"rolling-100d-refund-count"` otherwise.
- `policy_id` (`str`), `policy_name` (`str`), `condition_id` (`str`,
  `"COND-REFUND-STD-100D-30D"` or `"COND-REFUND-VIP-100D-30D"`),
  `customer_tier` (`"STANDARD" | "VIP"`), `order_found` (`bool`),
  `target_order_status` (`str | None`), `product_names` (`str`), and
  `target_order_price` (`float`).
- `target_order_age_days` (`int | None`) and `return_window_days` (`int`),
  where `bq_lineage.py` maps `target_order_age_days` to
  `observed_order_age_days`.
- `prior_refund_count_100d` (`int`) and `max_refunds_100d` (`int`, `10` for
  `STANDARD` or `20` for `VIP`), where `bq_lineage.py` maps
  `prior_refund_count_100d` to `observed_refunds_100d`.
- `evaluation_result` (`"PASS" | "FAIL" | "INFO"`) and `failure_code` (`str | None`).

Step 4 (`route_and_commit_action`) writes `ctx.state["action_outcome"]` with the
keys `action_id` (`f"ACT-{uuid4().hex[:8]}"`), `eval_id`
(`policy_eval["eval_id"]`), `action_type` (`"COMMIT_SPANNER_REFUND"`,
`"BLOCK_SPANNER_MUTATION"`, `"AWAIT_CUSTOMER_CONFIRMATION"`,
`"LIST_CUSTOMER_ORDERS"`, `"SHOW_ORDER_DETAILS"`, or `"SHOW_POLICY_AND_ORDERS"`),
`decision_status` (`"APPROVED"`, `"DENIED"`, `"PENDING_CONFIRMATION"`,
`"ORDER_LIST"`, `"ORDER_INFO"`, or `"POLICY_INFO"`), and `rejection_reason`
(`str | None`).

### ADK 2.0 workflow wiring (`workflow.py`)

`workflow.py` imports the canonical ADK 2.0 graph primitives (`AdkAgent`,
`AdkContext`, `AdkWorkflow`, `FunctionNode`, and `InMemoryRunner`), compiles the
five nodes and the `stream_node_lineage_to_bigquery(ctx: Context, node_name:
str, latency_ms: float)` callback into `refund_system_of_action.adk_workflow`,
emits real-time per-node `"start"` and `"end"` telemetry events via
`_build_step_event` and `_notify_step_observer` whenever `step_observer` is
bound on `ctx.state["_step_observer"]`, and executes each session turn through
`InMemoryRunner.run_async(...)` (using a `contextvars.ContextVar` `_ACTIVE_CTX`
so live Spanner/BigQuery clients and `ctx.state["lineage_buffer"]` persist
across ADK node events while recording emitted `google.adk.events.Event` records
in `ctx.adk_events`):

```python
from google.adk import Agent as AdkAgent
from google.adk import Context as AdkContext
from google.adk import Workflow as AdkWorkflow
from google.adk.runners import InMemoryRunner
from google.adk.workflow import FunctionNode

refund_system_of_action = Workflow(
    name="RefundSystemOfActionWorkflow",
    edges=[
        ("START", intent_agent),
        (intent_agent, resolve_catalog_contract),
        (resolve_catalog_contract, evaluate_spanner_policy),
        (evaluate_spanner_policy, route_and_commit_action),
        (route_and_commit_action, response_agent),
    ],
    after_node_callbacks=[stream_node_lineage_to_bigquery],
)
```

## Cloud Spanner Graph client and transactional mutation contract (`spanner_client.py`)

`spanner_client.py` encapsulates all read and write operations against Cloud
Spanner (`OperationalContextGraph`):

- **`query_spanner_operational_context_graph(user_id: int, target_order_id: int,
  catalog_contract: dict) -> dict`:**
    - Executes the two-stage ISO GQL `OperationalContextGraph` traversal inside
      a Cloud Spanner read-only snapshot (`database.snapshot()`), binding the
      six query parameters `@user_id` (`INT64`), `@target_order_id` (`INT64`),
      `@returned_status` (`STRING`, `'Returned'`), `@rolling_window_days`
      (`INT64`, `100`), `@standard_tier` (`STRING`, `'STANDARD'`), and
      `@vip_tier` (`STRING`, `'VIP'`) resolved from `catalog_contract`:

      ```sql
      -- Purpose: Parameterized two-stage ISO GQL policy evaluation traversal
      --   executed by Step 3 (evaluate_spanner_policy) at runtime.
      -- Target Engine: Cloud Spanner (thelook-soa-db -> OperationalContextGraph).
      -- How It Works:
      --   Stage 1 (MATCH): Binds @user_id, @target_order_id, @standard_tier, and
      --     @vip_tier to traverse R2G (users -> orders -> inventory_items ->
      --     products -> distribution_centers) and U2G (products -> policies ->
      --     policy_conditions / policy_restrictions) for the customer's tier.
      --   Stage 2 (NEXT + OPTIONAL MATCH): Binds @returned_status ('Returned') and
      --     @rolling_window_days (100) to count prior returned items across other
      --     orders within the rolling window.
      -- Information Gathered: Customer tier, target order status/age/price, product
      --   and fulfillment center names, active policy/condition IDs, max_refunds_100d,
      --   return_window_days, restriction_action, and prior_refund_count_100d.
      GRAPH OperationalContextGraph
      MATCH (u:users {id: @user_id})
              -[:places]->(target_o:orders {order_id: @target_order_id})
              -[target_oi:contains_item]->(ii:inventory_items)-[:is_product]->(p:products)
              -[:supplied_by]->(dc:distribution_centers),
            (p)-[:governed_by]->(pol:policies {status: 'ACTIVE'})
              -[:requires_condition]->(cond:policy_conditions),
            (pol)-[:enforces_restriction]->(res:policy_restrictions)
      WHERE u.customer_tier IN (@standard_tier, @vip_tier)
        AND cond.applicable_tier = u.customer_tier
      RETURN
        u.id AS user_id,
        u.email AS email,
        u.customer_tier AS customer_tier,
        target_o.order_id AS target_order_id,
        target_o.status AS target_order_status,
        TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), target_o.delivered_at, DAY) AS target_order_age_days,
        ROUND(SUM(target_oi.sale_price), 2) AS target_order_price,
        STRING_AGG(DISTINCT p.name, ', ') AS product_names,
        STRING_AGG(DISTINCT dc.name, ', ') AS distribution_center_names,
        pol.policy_id AS policy_id,
        pol.name AS policy_name,
        cond.condition_id AS condition_id,
        cond.max_refunds_100d AS max_refunds_100d,
        cond.return_window_days AS return_window_days,
        res.action_code AS restriction_action
      GROUP BY
        user_id, email, customer_tier, target_order_id, target_order_status,
        target_order_age_days, policy_id, policy_name, condition_id,
        max_refunds_100d, return_window_days, restriction_action
      NEXT
      -- Stage 2: Count prior returned items in the rolling 100-day window
      OPTIONAL MATCH (u2:users)-[:places]->(hist_o:orders)-[hist_oi:contains_item]->(:inventory_items)
      WHERE u2.id = user_id
        AND hist_o.order_id != target_order_id
        AND hist_oi.status = @returned_status
        AND COALESCE(hist_oi.returned_at, hist_o.returned_at, hist_o.created_at)
            >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @rolling_window_days DAY)
      RETURN
        user_id,
        email,
        customer_tier,
        target_order_id,
        target_order_status,
        product_names,
        distribution_center_names,
        target_order_price,
        target_order_age_days,
        COUNT(DISTINCT hist_oi.id) AS prior_refund_count_100d,
        policy_id,
        policy_name,
        condition_id,
        max_refunds_100d,
        return_window_days,
        restriction_action
      GROUP BY
        user_id, email, customer_tier, target_order_id, target_order_status,
        product_names, distribution_center_names, target_order_price,
        target_order_age_days, policy_id, policy_name, condition_id,
        max_refunds_100d, return_window_days, restriction_action
      ```

    - All seeded products in `thelook-soa-db` link to `POL-REFUND-STD-V1`, and
      filtering `cond.applicable_tier = u.customer_tier` guarantees a strict
      `1:1` condition match (`COND-REFUND-STD-100D-30D` with `max_refunds_100d =
      10` for `STANDARD` users, and `COND-REFUND-VIP-100D-30D` with
      `max_refunds_100d = 20` for `VIP` users).
    - When the traversal returns zero rows (or when `evaluate_spanner_policy`
      short-circuits on `MISSING_ORDER_ID`), the function sets `order_found =
      False` and populates baseline fallback values (`policy_id =
      "POL-REFUND-STD-V1"`, `policy_name = "Tiered Standard and VIP Refund
      Policy"`, `condition_id = "COND-REFUND-STD-100D-30D"`, `customer_tier =
      "STANDARD"`, `prior_refund_count_100d = 0`, `max_refunds_100d =
      int(os.getenv("MAX_REFUNDS_100D_LIMIT", "10"))`, `return_window_days =
      30`, `target_order_age_days = None`, `target_order_status = None`) so all
      `NOT NULL` columns in `soa_action_lineage.policy_evaluations` remain
      populated.
- **`commit_spanner_order_refund(user_id: int, order_id: int, trace_id: str,
  catalog_contract: dict, policy_eval: dict) -> dict`:**
    - Executes inside a Cloud Spanner read-write transaction
      (`database.run_in_transaction()`) to prevent time-of-check to time-of-use
      (TOCTOU) race conditions.
    - Re-verifies under the transaction lock (binding `@user_id`, `@order_id`,
      `@eligible_order_status`, `@returned_status`, `@rolling_window_days`,
      `@standard_tier`, and `@vip_tier`) that `orders.user_id == @user_id`,
      `users.customer_tier IN (@standard_tier, @vip_tier)`, `orders.status ==
      catalog_contract["eligible_order_status"]`, `target_order_age_days <=
      policy_eval["return_window_days"]`, and `prior_refund_count_100d <
      policy_eval["max_refunds_100d"]`. If a concurrent transaction modified the
      order or exceeded a threshold between Step 3 and Step 4, the transaction
      aborts the mutation, re-runs the Priority 2 to 6 failure classification to
      update `policy_eval` in place (`evaluation_result = "FAIL"`,
      `failure_code`, and `catalog_term_id` recomputed for the failure code),
      and returns `{"action_id": f"ACT-{uuid4().hex[:8]}", "eval_id":
      policy_eval["eval_id"], "action_type": "BLOCK_SPANNER_MUTATION",
      "decision_status": "DENIED", "rejection_reason": formatted_reason}`.
    - When preconditions hold, updates `orders` (`SET status = @returned_status,
      returned_at = CURRENT_TIMESTAMP() WHERE order_id = @order_id AND user_id =
      @user_id`) and `order_items` (`SET status = @returned_status, returned_at
      = CURRENT_TIMESTAMP(), refund_trace_id = @trace_id WHERE order_id =
      @order_id`), and returns `{"action_id": f"ACT-{uuid4().hex[:8]}",
      "eval_id": policy_eval["eval_id"], "action_type":
      "COMMIT_SPANNER_REFUND", "decision_status": "APPROVED",
      "rejection_reason": None}`.

## BigQuery Action Lineage callback contract (`bq_lineage.py`)

`stream_node_lineage_to_bigquery` populates the four property graph tables of
`soa_action_lineage.ActionLineageGraph` (defined in
[data/README.md](../../data/README.md)). During Steps 1 through 4, the callback
buffers each node's telemetry in `ctx.state["lineage_buffer"]` to keep per-node
BigQuery network calls out of the Step 3-to-Step 4 transaction window. When
Step 5 (`ResponseAgent`) finishes, the callback flushes all four tables in a
single batched `client.insert_rows_json()` sequence with 3-attempt exponential
backoff. If a transient BigQuery streaming error occurs after Step 4 commits in
Cloud Spanner, `order_items.refund_trace_id` is the durable Spanner-side
reconciliation identifier linking the order mutation to `trace_id`:

1.  **`agent_sessions` (1 row per turn):** Records `trace_id`, `customer_id =
    ctx.state["user_id"]`, `target_order_id = ctx.state["order_id"]` (`NULL`
    when omitted), `user_prompt`, and `started_at` when Step 1 (`IntentAgent`)
    completes.
1.  **`workflow_nodes` (5 rows per turn):** Records `node_exec_id`, `trace_id`,
    `node_name`, `step_order`, `latency_ms`, and `executed_at` after each of the
    five nodes (`step_order` `1..5`: `IntentAgent`, `resolve_catalog_contract`,
    `evaluate_spanner_policy`, `route_and_commit_action`, `ResponseAgent`)
    finishes.
1.  **`policy_evaluations` (1 row per turn):** Records `eval_id`,
    `node_exec_id` (always bound to the `node_exec_id` of Step 3,
    `evaluate_spanner_policy`), `trace_id`, `catalog_term_id`, `policy_id`,
    `policy_name`, `observed_refunds_100d` (from `prior_refund_count_100d`),
    `max_refunds_100d`, `observed_order_age_days` (from
    `target_order_age_days`), `return_window_days`, `evaluation_result`, and
    `evaluated_at` from `ctx.state["policy_eval"]`, including any concurrent
    conflict detected during Step 4.
1.  **`agent_actions` (1 row per turn):** Records `action_id`, `eval_id`,
    `trace_id`, `action_type`, `decision_status`, `rejection_reason`, and
    `created_at` from `ctx.state["action_outcome"]`.

## Knowledge Catalog client with local JSON fallback (`catalog_client.py`)

`fetch_knowledge_catalog_aspect()` queries the Knowledge Catalog API
(`projects/{project}/locations/global/glossaries/soa-business-glossary`, aspect
type `refund-metric-contract`) provisioned by Terraform via
`get_glossary()` and `list_glossary_terms()` to resolve the live governed term
IDs (`rolling-100d-refund-count`, `order-age-days`, and
`customer-loyalty-tier`), merges the metric threshold parameters from
`business_glossary.json`, and caches the resolved contract dictionary in memory
with a 5-minute time-to-live (TTL):

```json
{
  "catalog_term_id": "rolling-100d-refund-count",
  "secondary_term_id": "order-age-days",
  "tier_term_id": "customer-loyalty-tier",
  "returned_status": "Returned",
  "eligible_order_status": "Complete",
  "rolling_window_days": 100,
  "standard_tier": "STANDARD",
  "vip_tier": "VIP"
}
```

The workflow passes `returned_status`, `rolling_window_days`, `standard_tier`,
and `vip_tier` into the Step 3 read-only GQL traversal, checks
`eligible_order_status` and tier membership in Step 3 Python logic and Step 4's
read-write transaction lock, and records the governing term ID in
`soa_action_lineage.policy_evaluations` (`"order-age-days"` when
`RETURN_WINDOW_EXPIRED` or `ORDER_NOT_DELIVERED` triggers,
`"customer-loyalty-tier"` when a `VIP` customer is approved with
`prior_refund_count_100d >= 10`, and `"rolling-100d-refund-count"` otherwise).
If the Knowledge Catalog API is unreachable or propagating Identity and Access
Management (IAM) bindings, `catalog_client.py` loads
`data/policies/business_glossary.json` so workflow execution continues without
blocking on API availability.

## Conversational agent security and identity binding

The ADK 2.0 workflow enforces a three-layer defense against prompt injection,
role spoofing, and unauthorized order access:

1.  **Tier 1: Session identity binding and order ownership:**
    - In this lab, `POST /api/chat/refund` accepts `user_id` (`1001`, `2048`, or
      `3072`) as a structured JSON field from the UI 1 Persona Switcher outside
      the natural language chat message so students can switch between Customer
      A, Customer B, and Customer C. FastAPI binds `ctx.state["user_id"]` before
      the workflow starts, preventing prompt text in `message` from overriding
      `user_id` or spoofing VIP status (because `customer_tier` is read directly
      from `users.customer_tier` in Cloud Spanner for `@user_id`).
    - In `evaluate_spanner_policy` and `commit_spanner_order_refund`, Cloud
      Spanner binds `@user_id` and `@target_order_id` as typed `INT64`
      parameters along `(u:users {id: @user_id})-[:places]->(target_o:orders
      {order_id: @target_order_id})`. If Customer B requests a refund for
      Customer A's order (`order_id: 90124`) or Customer C's order (`order_id:
      90910`), the traversal returns zero rows and fails closed with
      `ORDER_NOT_FOUND_OR_UNAUTHORIZED`.
1.  **Tier 2: Pre-execution negative role boundaries and anti-spoofing:**
    - `IntentAgent` and `ResponseAgent` system instructions forbid the LLM from
      modifying `user_id`, `customer_tier`, or policy thresholds, calling
      database mutation tools, honoring user claims of VIP or administrator
      override privileges in chat text, or exposing internal `ctx.state`
      variable names.
1.  **Tier 3: Deterministic policy and mutation gate (`spanner_client.py`):**
    - Neither `IntentAgent` nor `ResponseAgent` has tool access to mutate Cloud
      Spanner. Only the deterministic Python step `route_and_commit_action` can
      call `commit_spanner_order_refund()`, and only when
      `evaluate_spanner_policy` returns `evaluation_result == "PASS"`.
