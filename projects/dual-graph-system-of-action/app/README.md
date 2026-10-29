# Unified Cloud Run application and REST API (`app/`)

This directory contains the unified Cloud Run application
(`soa-refund-agent-app`) serving both web interfaces (`/shop` and `/console`)
and the FastAPI backend API that runs the Google Agent Development Kit 2.0 (ADK
2.0) refund workflow.

## Directory layout

The `app/` directory contains the FastAPI entrypoint, dependencies, ADK 2.0
agent package, web frontend views, and unit tests:

```text
app/
├── README.md          # FastAPI backend and REST API specification (this file)
├── __init__.py        # Package initializer
├── Dockerfile         # Multi-stage, non-root container build for FastAPI and UIs
├── requirements.in    # Top-level Python dependencies with major-version pins (~=)
├── requirements.txt   # Hash-locked Python dependencies (--generate-hashes)
├── main.py            # FastAPI server serving /shop, /console, and /api/*
├── agent/             # Google ADK 2.0 refund workflow and deterministic node functions
│   ├── README.md      # ADK 2.0 workflow, security guardrails, and BigQuery callbacks
│   ├── __init__.py    # Agent package initializer
│   ├── workflow.py    # ADK 2.0 Workflow graph and BigQuery lineage callbacks
│   ├── spanner_client.py # Cloud Spanner Graph parameterized ISO GQL queries and mutations
│   ├── bq_lineage.py  # BigQuery ActionLineageGraph writer and GQL runner
│   └── catalog_client.py # Knowledge Catalog glossary client with JSON fallback
├── frontend/          # HTML, JS, Tailwind CSS, and Cytoscape.js views for /shop and /console
│   ├── README.md      # UI 1 and UI 2 component specifications
│   ├── shop.html      # UI 1: Mockup thelook_ecommerce storefront and ADK 2.0 chat widget
│   ├── console.html   # UI 2: Data engineer trace feed, Cytoscape.js graph, GQL workbench, and modals
│   └── static/
│       ├── shop.js    # Client controller for persona switching, orders, and refund chat
│       ├── console.js # Client controller for Cytoscape.js rendering, 3-tab GQL runner, and modals
│       └── products/  # 8 locally hosted unbranded AI-generated studio product photos (256x256 PNG)
└── tests/             # Python unit tests for workflow logic and FastAPI endpoints
    ├── __init__.py    # Test package initializer
    ├── test_workflow.py
    └── test_api.py
```

`app/requirements.in` pins top-level dependencies using `~=`:
`fastapi~=0.162`, `uvicorn~=0.54`, `google-adk~=2.13`,
`google-genai~=2.33`, `google-cloud-spanner~=3.51`,
`google-cloud-bigquery~=3.29`, `google-cloud-dataplex~=2.6`,
`httpx~=0.28`, and `pydantic~=2.12`.

## Sub-component documentation

Each sub-directory provides its own detailed specification:

- **ADK 2.0 agent runtime:** See [agent/README.md](agent/README.md) for the
  `RefundSystemOfActionWorkflow` specification (`workflow.py`,
  `spanner_client.py`, `bq_lineage.py`, and `catalog_client.py`).
- **Dual web interfaces:** See [frontend/README.md](frontend/README.md) for the
  **UI 1 (`TheLook Shopping Mall and Chat App`, `/shop`)** and **UI 2 (`Data
  Engineer Investigation Console`, `/console`)** specifications.
- **Database and lineage schemas:** See [data/README.md](../data/README.md) for
  the Cloud Spanner and BigQuery property graph schemas.

## Backend REST API contract (`main.py`)

The FastAPI backend serves both web interfaces and exposes the following JSON
API endpoints:

| HTTP method and path | Used by | Request and response contract |
| :--- | :--- | :--- |
| `GET /api/health` | Cloud Run and Terraform | Awaits the `asyncio.Lock`-guarded `ensure_bootstrapped()` lifespan task (which runs `seed_spanner_if_empty()` so scale-out or cold-start instances never overwrite existing demo orders). Requires Cloud Spanner seeding and the four BigQuery lineage tables to succeed, while treating `CREATE OR REPLACE PROPERTY GRAPH` Data Definition Language (DDL) errors in on-demand `gcpfree` projects as non-blocking. Returns `{"status": "ok", "spanner_seeded": true, "bq_tables_ready": true, "bq_graph_mode": "gql" \| "sql_fallback", "catalog_ready": true}`. |
| `GET /api/products` | UI 1 (`/shop`) | Returns `{"products": [{"id": int, "name": str, "brand": str, "category": str, "department": str, "retail_price": float, "distribution_center_name": str, "policy_id": str}]}` from Cloud Spanner. |
| `GET /api/customers` | UI 1 (`/shop`) | Returns `{"customers": [{"user_id": int, "first_name": str, "last_name": str, "email": str, "customer_tier": "STANDARD" \| "VIP", "prior_refund_count_100d": int, "max_refunds_100d": int}]}` for personas `1001` (`STANDARD`), `2048` (`STANDARD`), and `3072` (`VIP`). |
| `GET /api/customers/{user_id}/orders` | UI 1 (`/shop`) | Validates `user_id` as `int` and returns `{"orders": [{"order_id": int, "status": str, "created_at": str, "delivered_at": str \| null, "returned_at": str \| null, "items": [{"id": int, "product_name": str, "sale_price": float, "status": str, "refund_trace_id": str \| null}]}]}`. |
| `POST /api/chat/refund` | UI 1 (`/shop`) | Accepts `{"user_id": int, "message": str, "confirmed": bool, "pending_order_id": int \| null}`. Binds `user_id` outside the LLM prompt, generates a UUID `trace_id` (`trace-<uuid>`), executes the compiled `google.adk.Workflow` (`refund_system_of_action.adk_workflow`) via `google.adk.runners.InMemoryRunner` (`require_confirmation=True`), and returns `{"trace_id": str, "order_id": int \| null, "resolution_mode": str, "unmatched_product": str \| null, "candidate_orders": list[dict], "pending_confirmation": dict \| null, "reply": str, "decision_status": "APPROVED" \| "DENIED" \| "PENDING_CONFIRMATION" \| "ORDER_LIST" \| "ORDER_INFO" \| "POLICY_INFO", "failure_code": str \| null, "policy_eval": dict, "action_outcome": dict}` (see [agent/README.md](agent/README.md) for the `policy_eval` and `action_outcome` field schemas). |
| `POST /api/chat/refund/stream` | UI 1 (`/shop`) | Accepts the same `RefundChatRequest` JSON body (`{"user_id": int, "message": str, "confirmed": bool, "pending_order_id": int \| null}`) and returns a `StreamingResponse` (`application/x-ndjson`) that emits real-time per-node step events (`{"type": "step", "step_index": 1..5, "total_steps": 5, "node_name": str, "phase": "start" \| "end", "latency_ms": float \| null, "detail_en": str, "detail_ko": str}`) as each of the 5 ADK 2.0 workflow nodes starts and finishes, followed by the final `{"type": "result", "data": dict}` payload. |
| `POST /api/demo/reset` | UI 1 and UI 2 | Accepts `{}`. Calls `reset_demo_orders()` in `data/spanner_seed.py` to refresh all three hydration stages with fresh relative UTC timestamps (`datetime.now(timezone.utc)`) and reset `order_id: 90124`, `order_id: 90588`, and `order_id: 90910` in Cloud Spanner (`orders.status = 'Complete'`, `orders.returned_at = NULL`, `order_items.status = 'Complete'`, `order_items.returned_at = NULL`, `order_items.refund_trace_id = NULL`), clears pending customer confirmation and conversation memory state (`clear_pending_confirmations()`), and clears BigQuery `soa_action_lineage` trace tables (`reset_bigquery_lineage()`). Returns `{"status": "reset", "reset_order_ids": [90124, 90588, 90910], "bigquery_lineage_cleared": bool}`. |
| `GET /api/traces` | UI 2 (`/console`) | Queries BigQuery (joining `agent_sessions`, `workflow_nodes` on `n.node_name = 'evaluate_spanner_policy'`, `policy_evaluations`, and `agent_actions`) to return up to 50 recent refund workflow traces: `{"traces": [{"trace_id": str, "customer_id": int, "target_order_id": int \| null, "decision_status": str, "evaluation_result": str, "observed_refunds_100d": int, "max_refunds_100d": int, "latency_ms": float, "started_at": str}]}`. |
| `GET /api/traces/{trace_id}/graph` | UI 2 (`/console`) | Queries the four BigQuery trace tables (using parameterized SQL in `sql_fallback` mode or `GRAPH_TABLE` in `gql` mode) and Cloud Spanner (`OperationalContextGraph`, skipping the target-order traversal when `target_order_id is None`) for `trace_id`, links `AgentSession` to `orders` (`targets_order`) and `PolicyEvaluation` to `policies` (`references_policy`), and returns Cytoscape.js elements: `{"nodes": [{"data": {"id": str, "label": str, "layer": "r2g" \| "u2g" \| "bq", "properties": dict}}], "edges": [{"data": {"id": str, "source": str, "target": str, "label": str}}]}`. |
| `GET /api/governance` | UI 2 (`/console`) | Returns `{"catalog_contract": dict, "glossary_terms": list[dict], "policy_document_markdown": str, "u2g_triples": dict}` combining the resolved Knowledge Catalog semantic contract, the three governed business glossary term definitions (`rolling-100d-refund-count`, `order-age-days`, and `customer-loyalty-tier` with `sql_mapping` from `data/policies/business_glossary.json`), the source `return_policy_v1.md` Markdown document, and pre-compiled U2G triples (`POL-REFUND-STD-V1` with `STANDARD` and `VIP` conditions). |
| `POST /api/query/spanner` | UI 2 (`/console`) | Accepts `{"query": str}`. Strips leading `--` and `/* ... */` comments (`_strip_sql_comments`), enforces a read-only `GRAPH` / `SELECT` guard, executes the ISO Graph Query Language (GQL) or SQL query inside a Cloud Spanner read-only snapshot (`database.snapshot()`, `timeout = 15s`, `max_rows = 500`), and returns `{"columns": [str], "rows": [dict], "latency_ms": float}`. |
| `POST /api/query/bigquery` | UI 2 (`/console`) | Accepts `{"query": str}`. Strips leading `--` and `/* ... */` comments (`_strip_sql_comments`), enforces a read-only `SELECT` / `GRAPH_TABLE` / `WITH` statement guard, configures `QueryJobConfig(maximum_bytes_billed=100 * 1024 * 1024, job_timeout_ms=15000)`, caps output at 500 rows, and maps the built-in `ActionLineageGraph` `GRAPH_TABLE` preset templates to their parameterized relational SQL `JOIN` equivalents (supporting both single-trace queries via `WHERE s.trace_id = ...` / `{trace_id: '...'}` and all-trace scans ordered by `s.started_at DESC LIMIT 50` when `trace_id` is omitted or commented out) when `bq_graph_mode == "sql_fallback"`. Returns `{"columns": [str], "rows": [dict], "execution_mode": "gql" \| "sql_fallback", "latency_ms": float}`. |

## Runtime environment variables

Terraform (`main.tf`) passes the following environment variables to the Cloud
Run service:

| Environment variable | Default or example | Description |
| :--- | :--- | :--- |
| `GCP_PROJECT_ID` | `${local.gcp_project_id}` | Active Google Cloud project ID. |
| `GCP_REGION` | `us-central1` | Active deployment region (`us-central1`, `us-west1`, `us-west4`, `us-east1`, `us-east4`). |
| `SPANNER_INSTANCE_ID` | `soa-graph-instance` | Cloud Spanner Enterprise instance identifier. |
| `SPANNER_DATABASE_ID` | `thelook-soa-db` | Cloud Spanner database hosting `OperationalContextGraph`. |
| `BIGQUERY_DATASET_ID` | `soa_action_lineage` | BigQuery dataset hosting `ActionLineageGraph`. |
| `SPANNER_CONNECTION_ID` | `${local.gcp_project_id}.${var.gcp_region}.spanner-data-boost` | BigQuery Cloud Spanner Data Boost connection ID used in `EXTERNAL_QUERY`. |
| `DATAPLEX_GLOSSARY_ID` | `soa-business-glossary` | Knowledge Catalog Business Glossary ID in `location = "global"`. |
| `DATAPLEX_ASPECT_TYPE_ID` | `refund-metric-contract` | Knowledge Catalog Aspect Type ID in `location = "global"`. |
| `GOOGLE_GENAI_USE_VERTEXAI` | `"True"` | Configures `google-adk` and `google-genai` to authenticate using Vertex AI Application Default Credentials (ADC) (`soa-app-sa`). |
| `GOOGLE_CLOUD_PROJECT` | `${local.gcp_project_id}` | Project ID read by `google-adk` and `google-genai`. |
| `GOOGLE_CLOUD_LOCATION` | `global` | Vertex AI location read by `google-adk` and `google-genai`. |
| `ADK_MODEL_NAME` | `gemini-3-flash-preview` | Vertex AI Gemini model configured for `IntentAgent` and `ResponseAgent` (`_generate_gemini_text_fast` with `ThinkingLevel.MINIMAL`). |
| `VERTEX_LLM_TIMEOUT_MS` | `4000` | Per-call HTTP timeout in milliseconds configured on `google.genai.Client` (`HttpOptions` with `HttpRetryOptions(attempts=1)`). |
| `MAX_REFUNDS_100D_LIMIT` | `10` | Standard tier refund policy threshold passed from `var.max_refunds_100d_limit` to `data/spanner_seed.py`. |
| `VIP_MAX_REFUNDS_100D_LIMIT` | `20` | VIP tier refund policy threshold passed from `var.vip_max_refunds_100d_limit` to `data/spanner_seed.py`. |
| `APP_BUILD_HASH` | `"${module.cli.wait}-${sha256(jsonencode(local.app_build_triggers))}"` | Composite SHA-256 build hash of backend, frontend, policy, and product image files used to trigger a new Cloud Run revision whenever application assets change. |

## API security, parameterization, and container standards

The backend enforces four security and container engineering invariants:

- **Parameterized query binding:** All database queries in `spanner_client.py`
  and `bq_lineage.py` cast non-null identifiers to Python integers
  (`int(user_id)` and `int(order_id)` when `order_id is not None`) or validated
  `trace_id` strings matching `^trace-[0-9a-fA-F-]+$` and bind them using Cloud
  Spanner typed parameters (`params={"user_id": ...}`,
  `param_types={"user_id": param_types.INT64}`) and BigQuery
  `ScalarQueryParameter` objects without string interpolation.
- **In-memory SQL/GQL template and Spanner session caching:** The backend loads
  multi-line SQL and ISO GQL templates into memory at startup so HTTP requests
  do not read template files from disk, and `get_spanner_database()` in
  `data/spanner_seed.py` caches the `(project_id, instance_id, database_id)`
  Cloud Spanner `Database` instance in `_SPANNER_DB_CACHE` across requests.
- **Sanitized error responses and structured logging:** All modules use Python's
  standard `logging` library (`logger.info()`, `logger.warning()`,
  `logger.error()`). FastAPI exception handlers catch Google Cloud client and
  validation exceptions, log details server-side, and return user-safe JSON
  error messages without exposing stack traces.
- **Reproducible multi-stage non-root container (`Dockerfile`):** `scripts/qwiklab.sh`
  stages `data/` into `app/data` and builds `app/Dockerfile` using `app/` as the
  Docker build context (matching `kokoro/ci-tasks/04-unit-tests`) so the image
  includes both `app/` and `data/`. Developers compile `requirements.txt` from
  `requirements.in` (`~=`) using `uv pip compile --generate-hashes`, and
  `app/Dockerfile` installs those hash-locked packages inside a multi-stage
  `python:3.12-slim` image with `pip install --no-cache-dir --require-hashes -r
  requirements.txt` and runs the server as a non-root user (`USER 1000`).
