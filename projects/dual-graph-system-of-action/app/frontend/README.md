# Dual web interfaces (`app/frontend/`)

`app/frontend/` implements the two browser interfaces served by FastAPI using
HTML templates, JavaScript modules, Tailwind CSS, and Cytoscape.js:

1.  **UI 1 (`TheLook Shopping Mall and Chat App`, `/shop`):** Mockup
    `thelook_ecommerce` shopping mall and customer support chat application
    (`shopping_mall_url`).
1.  **UI 2 (`Data Engineer Investigation Console`, `/console`):** Data engineer
    observability and graph investigation console (`data_engineer_console_url`).

## Directory layout

The `app/frontend/` directory contains the HTML templates and client-side
JavaScript controllers:

```text
app/frontend/
├── README.md          # UI 1 and UI 2 component specification (this file)
├── shop.html          # UI 1: Mockup thelook_ecommerce storefront and ADK 2.0 chat widget
├── console.html       # UI 2: Data engineer trace feed, Cytoscape.js graph, GQL workbench, and modals
└── static/
    ├── shop.js        # Client controller for persona switching, orders, and refund chat
    ├── console.js     # Client controller for Cytoscape.js rendering, 3-tab GQL runner, and modals
    └── products/      # 8 locally hosted unbranded AI-generated studio product photos (256x256 PNG)
        ├── jacket.png
        ├── pullover.png
        ├── shoes.png
        ├── jeans.png
        ├── sunglasses.png
        ├── shirt.png
        ├── blazer.png
        └── beanie.png
```

## UI 1: TheLook Shopping Mall and Chat App (`/shop`)

**UI 1 (`TheLook Shopping Mall and Chat App`, `shopping_mall_url`)** simulates
an e-commerce storefront backed by the `thelook_ecommerce` operational schema in
Cloud Spanner (using Light theme as the fixed default):

- **TheLook product catalog and warehouse view:** Displays products, locally
  hosted unbranded AI-generated studio product thumbnails (`getProductPhotoUrl`
  mapping to `/static/products/{jacket,pullover,shoes,jeans,sunglasses,shirt,blazer,beanie}.png`
  for clean license management), brands, departments, retail prices, and
  fulfillment distribution centers hydrated from `thelook_ecommerce` (`GET
  /api/products`).
- **Persona switcher:** Allows students to switch between three pre-populated
  customer profiles (`GET /api/customers`), displaying each customer's loyalty
  tier badge (`STANDARD` vs. `VIP`) and 100-day return counter:
    - **Customer A (`user_id: 1001`, `alice.chen@example.com`, `STANDARD`
      tier):** Customer with 2 prior returned items (`status = 'Returned'`) in
      the last 100 days (limit: 10), an eligible delivered order (`order_id:
      90124`, **Alpine Gore-Tex Waterproof Shell Jacket**, `$129.00`, `status =
      'Complete'`, delivered 14 days ago), and two edge-case orders (`order_id:
      90125`, **Polarized Aviator Titanium Sunglasses**, `$165.00`, delivered 45
      days ago and `order_id: 90126`, **Cashmere Ribbed Winter Beanie**, `$58.00`
      in `'Shipped'` status).
    - **Customer B (`user_id: 2048`, `jordan.taylor@example.com`, `STANDARD`
      tier):** Customer with 12 prior returned items (`status = 'Returned'`)
      across distinct orders in the last 100 days (exceeding the `STANDARD`
      limit of 10) and a recent delivered order (`order_id: 90588`, **CloudStride
      Trail Running Shoes**, `$148.00`, `status = 'Complete'`, delivered 10 days
      ago).
    - **Customer C (`user_id: 3072`, `claire.vance@example.com`, `VIP` tier):**
      VIP customer with 12 prior returned items (`status = 'Returned'`) in the
      last 100 days (within the `VIP` limit of 20) and a recent delivered order
      (`order_id: 90910`, **Tailored Italian Wool Travel Blazer**, `$210.00`,
      `status = 'Complete'`, delivered 7 days ago).
- **Bilingual UI toggle (`EN` / `한국어`) with automatic demo reset:** Both UI 1
  (`/shop`) and UI 2 (`/console`) include a language toggle button
  (`#lang-toggle-btn`, persisted via `localStorage.getItem('soa_ui_lang')`) in
  the top navigation bar. Clicking the language button opens
  `#reset-progress-modal` with a bilingual confirmation notice informing the user
  that switching languages resets the demo dataset (`POST /api/demo/reset`) and
  clears persisted chat/trace history (`soa_chat_history_by_user`,
  `soa_pending_order_by_user`, and `soa_active_user_id`) so all orders,
  timestamps, prompt chips, and BigQuery `soa_action_lineage` traces start
  cleanly in the selected language.
- **Order history and two-step animated demo reset modal:** Displays the selected
  customer's `thelook` orders, locally hosted product thumbnails, inventory item
  IDs, sale prices, delivery timestamps, and live statuses (`Complete`,
  `Returned`, `Processing`, `Shipped`, `Cancelled`) from `GET
  /api/customers/{user_id}/orders`. Clicking **Reset Demo Data** (`#reset-demo-btn`,
  `POST /api/demo/reset` in either UI 1 or UI 2) opens `#reset-progress-modal`,
  which first displays a confirmation dialog (`#reset-confirm-panel` with
  `#reset-cancel-btn` and `#reset-confirm-btn`) and then transitions to a 4-stage
  animated progress view (`#reset-running-panel`) while refreshing relative UTC
  timestamps, resetting `order_id: 90124`, `order_id: 90588`, and `order_id:
  90910` in Cloud Spanner, clearing BigQuery `soa_action_lineage` traces, and
  clearing persisted chat state in `localStorage`.
- **ADK 2.0 customer support chat:** Embeds a sticky scrollable chat assistant
  (`#chat-messages`, streaming from `POST /api/chat/refund/stream` with fallback
  to `POST /api/chat/refund`) with per-persona chat history
  (`chatHistoryByUser[userId]`), pending Turn 1 confirmation state
  (`pendingOrderByUser[userId]`), and the active customer persona
  (`activeUserId`) persisted across `/shop` and `/console` navigation via
  `localStorage` (`soa_chat_history_by_user`, `soa_pending_order_by_user`, and
  `soa_active_user_id` managed by `loadPersistedChatState`,
  `savePersistedChatState`, and `clearPersistedChatState`), an active persona
  badge (`#chat-persona-label`), and a **Clear Chat** button (`#clear-chat-btn`)
  where customers ask questions or request refunds in natural language (using
  `90124`, `ORD-90124`, conversational cues, or storefront items they never
  purchased via `unmatched_product` detection) or through **1-click persona-aware
  prompt chips** (`ORD-90124`, `ORD-90125`, and `ORD-90126` for Customer A;
  `ORD-90588` for Customer B; `ORD-90910` for Customer C, sending localized
  English or Korean prompts matching the active UI language). Prompt chips with
  an explicit `ORD-<id>` resolve Step 1 (`IntentAgent`) directly and reserve the
  live `gemini-3-flash-preview` (`ThinkingLevel.MINIMAL` and a 4-second timeout)
  call for Step 5 (`ResponseAgent`), while natural-language prompts execute live
  Gemini calls in both Step 1 and Step 5. While the backend workflow runs,
  `consumeRefundStream` and `updateAgentLoadingStep` stream live `[1/5]..[5/5]`
  per-node status and elapsed milliseconds into `#agent-loading-step` inside
  `#agent-loading-indicator`, disable duplicate submissions, and automatically
  restore keyboard focus (`chatInput.focus({preventScroll: true})`) after prompt
  submission. Each agent reply displays the natural-language explanation inside
  a status-tinted `.agent-reply-callout` box above the `Workflow Telemetry &
  Lineage Metadata` block, renders product thumbnails on confirmation/verdict
  cards and synchronized `.candidate-order-chip` selection buttons, and provides
  an **Inspect in Data Engineer Console** deep link (`/console?trace_id=...`).
  Both interfaces share an identical top navigation bar for switching between
  `/shop` and `/console`.

## UI 2: Data Engineer Investigation Console (`/console`)

**UI 2 (`Data Engineer Investigation Console`, `data_engineer_console_url`)**
provides an operational monitoring and forensic investigation workbench:

- **Live refund request feed:** Lists incoming customer refund requests (`GET
  /api/traces`), ADK 2.0 execution trace IDs (`trace_id`), customer IDs, target
  order IDs, policy verdicts (`APPROVED`, `DENIED`, `PENDING_CONFIRMATION`,
  `ORDER_LIST`, `ORDER_INFO`, or `POLICY_INFO`), and Spanner Graph Query Language
  (GQL) execution latencies (`latency_ms`). At initial lab launch, before a
  student submits a refund request, `soa_action_lineage` starts empty and
  displays a guided banner with a link to `/shop`, while keeping the **Cloud
  Spanner Context Graph** workbench and **Policy Document (U2G) and Knowledge
  Catalog Inspector** ready for inspection.
- **Interactive dual-graph visualizer and stacked node inspector (Cytoscape.js):**
  Queries both graph engines through `GET /api/traces/{trace_id}/graph` and
  renders the refund evaluation subgraph across three color-coded node layers:
    1.  **Cloud Spanner Relational-to-Graph (R2G) nodes:** `users`, `orders`
        (target order and historical returned orders when `target_order_id` is
        present), `inventory_items`, `products`, and `distribution_centers`
        connected by `places`, `contains_item`, `is_product`, and `supplied_by`
        edges.
    1.  **Cloud Spanner Unstructured-to-Graph (U2G) policy nodes:** `policies`,
        tier-matched `policy_conditions` (`COND-REFUND-STD-100D-30D` or
        `COND-REFUND-VIP-100D-30D`), and `policy_restrictions` connected by
        `governed_by`, `requires_condition`, and `enforces_restriction` edges.
    1.  **BigQuery Action Lineage nodes:** `AgentSession`, `WorkflowNode`,
        `PolicyEvaluation`, and `AgentAction` connected by `executed_node`,
        `evaluated_policy`, and `triggered_action` edges, and joined across
        engines by `targets_order` (`AgentSession` to `orders`) and
        `references_policy` (`PolicyEvaluation` to `policies`).

  Clicking any node or edge populates the full-width **Node Property Inspector**
  panel (`#node-inspector`, stacked below `#cy-canvas`) with formatted JSON
  (`highlightJson`) showing its Cloud Spanner or BigQuery attributes.
- **Policy document (U2G) and Knowledge Catalog inspector with interactive
  modals:** Displays the Knowledge Catalog semantic contract (`#catalog-contract-view`)
  and extracted U2G policy triples (`#u2g-triples-view`, `POL-REFUND-STD-V1`
  with `STANDARD` and `VIP` condition nodes) from `GET /api/governance` with JSON
  color formatting, paired with two expanded explanatory headers and modal
  dialogs:
    1.  **Knowledge Catalog Semantic Contract (`#preview-catalog-contract-btn`
        opening `#catalog-contract-modal`):** Explains how **Knowledge Catalog**
        binds abstract policy terms (`ReturnPolicy` thresholds) to canonical
        SQL/GQL expressions on **Cloud Spanner** (`OperationalContextGraph`).
        Clicking **Preview Glossary & Contract** opens a modal with a **Semantic
        Governance Flow** pipeline banner and two tabs: **Overview & Governed
        Terms** (`#catalog-contract-overview-view`, detailing what the contract
        is, its purpose in preventing LLM metric drift, how Step 2, Step 3, and
        Step 4 consume it, and cards for the three governed glossary terms
        `rolling-100d-refund-count`, `order-age-days`, and
        `customer-loyalty-tier` with their target tables and SQL/GQL
        expressions) and **Raw Glossary JSON** (`#catalog-contract-raw-view`).
    1.  **Policy Document (U2G) & Extracted Triples (`#preview-policy-doc-btn`
        opening `#policy-doc-modal`):** Explains how corporate policy prose in
        `data/policies/return_policy_v1.md` is compiled into structured U2G
        nodes (`policies`, `policy_conditions`, `policy_restrictions`) in
        `data/policies/u2g_policy_triples.json`. Clicking **Preview
        return_policy_v1.md** opens a modal with an **Unstructured-to-Graph
        (U2G) Conversion Pipeline** banner and two tabs: **Rendered Policy**
        (`#policy-doc-rendered-view`) and **Raw Markdown (.md)**
        (`#policy-doc-raw-view`).
- **Built-in 3-tab GQL query workbench (read-only guarded):** Provides runnable
  query templates across three tabs, pre-filling the active `GCP_PROJECT_ID`,
  `GCP_REGION`, `SPANNER_CONNECTION_ID`, and selected `trace_id`, with
  structured `-- Purpose / Target Engine / How It Works / Information Gathered`
  header comments and live SQL/ISO GQL keyword coloring (`#query-highlight-view`,
  `highlightSqlGql`) (see
  [docs/demo-walkthrough.md](../../docs/demo-walkthrough.md)):
    1.  **Cloud Spanner Context Graph (`OperationalContextGraph`):** Runs ISO
        GQL inside a Cloud Spanner read-only snapshot (`database.snapshot()`)
        through `POST /api/query/spanner`.
    1.  **BigQuery Action Lineage Graph (`ActionLineageGraph`):** Runs ISO GQL
        with a read-only `SELECT` / `GRAPH_TABLE` statement guard (with a preset
        SQL `JOIN` template toggle, automatic single-trace vs. all-denials
        scoping in `buildBqGqlDenialPreset`, and preset fallback mapping when
        `bq_graph_mode == "sql_fallback"`) through `POST /api/query/bigquery`.
    1.  **Federated Spanner Data Boost audit (`spanner-data-boost`):** Uses
        `EXTERNAL_QUERY` over the `spanner-data-boost` connection to push a
        scoped Cloud Spanner `OperationalContextGraph` GQL query to Spanner Data
        Boost compute and join the operational results with BigQuery
        `soa_action_lineage` traces through `POST /api/query/bigquery`.
