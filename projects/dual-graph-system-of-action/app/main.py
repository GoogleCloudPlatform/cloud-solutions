# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""FastAPI backend serving /shop, /console, and /api/* endpoints."""

import asyncio
import functools
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from app.agent.bq_lineage import (
    build_dual_graph_elements,
    ensure_bigquery_schema,
    execute_readonly_bigquery,
    get_bq_runtime_state,
    list_recent_traces,
    reset_bigquery_lineage,
)
from app.agent.catalog_client import (
    fetch_knowledge_catalog_aspect,
    load_glossary_bundle,
    load_governance_artifacts,
)
from app.agent.spanner_client import (
    execute_readonly_spanner_query,
    fetch_customer_orders,
    fetch_persona_customers,
    fetch_storefront_products,
)
from app.agent.workflow import (
    clear_pending_confirmations,
    run_refund_workflow,
)
from data.spanner_seed import reset_demo_orders, seed_spanner_if_empty
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from google.api_core.exceptions import GoogleAPICallError
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

_BOOTSTRAP_LOCK = asyncio.Lock()
_RUNTIME_TASKS: dict[str, Any] = {"bootstrap": None}
_BOOTSTRAP_STATE: dict[str, Any] = {
    "bootstrapped": False,
    "spanner_seeded": False,
    "bq_tables_ready": False,
    "bq_graph_mode": "gql",
    "catalog_ready": False,
}


class ChatRefundRequest(BaseModel):
    """Request payload for POST /api/chat/refund."""

    user_id: int = Field(..., description="Active persona user ID")
    message: str = Field(..., min_length=1, max_length=2000)
    confirmed: bool = Field(
        default=False,
        description="Customer acknowledgement flag for order and item",
    )
    pending_order_id: int | None = Field(
        default=None,
        description="Client-side pending order ID awaiting confirmation",
    )


class QueryRequest(BaseModel):
    """Request payload for POST /api/query/spanner and /api/query/bigquery."""

    query: str = Field(..., min_length=1, max_length=20000)


@functools.lru_cache(maxsize=1)
def _load_html_template(filename: str) -> str:
    """Loads and caches an HTML template from app/frontend/ at startup."""
    template_path = FRONTEND_DIR / filename
    return template_path.read_text(encoding="utf-8")


async def ensure_bootstrapped() -> dict[str, Any]:
    """Runs idempotent Spanner seeding and BigQuery schema initialization."""
    if _BOOTSTRAP_STATE["bootstrapped"]:
        bq_state = get_bq_runtime_state()
        _BOOTSTRAP_STATE["bq_graph_mode"] = bq_state["bq_graph_mode"]
        return dict(_BOOTSTRAP_STATE)

    async with _BOOTSTRAP_LOCK:
        if _BOOTSTRAP_STATE["bootstrapped"]:
            return dict(_BOOTSTRAP_STATE)

        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
            "GOOGLE_CLOUD_PROJECT"
        )
        try:
            if project_id:
                await asyncio.to_thread(seed_spanner_if_empty)
            _BOOTSTRAP_STATE["spanner_seeded"] = True
        except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
            logger.error("Spanner bootstrap failed: %s", exc)
            _BOOTSTRAP_STATE["spanner_seeded"] = False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Spanner bootstrap failed: %s", exc)
            _BOOTSTRAP_STATE["spanner_seeded"] = False

        try:
            bq_ok, bq_mode = await asyncio.to_thread(ensure_bigquery_schema)
            _BOOTSTRAP_STATE["bq_tables_ready"] = bq_ok
            _BOOTSTRAP_STATE["bq_graph_mode"] = bq_mode
        except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
            logger.error("BigQuery bootstrap failed: %s", exc)
            _BOOTSTRAP_STATE["bq_tables_ready"] = False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("BigQuery bootstrap failed: %s", exc)
            _BOOTSTRAP_STATE["bq_tables_ready"] = False

        try:
            contract = await asyncio.to_thread(fetch_knowledge_catalog_aspect)
            _BOOTSTRAP_STATE["catalog_ready"] = bool(contract)
        except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
            logger.error("Knowledge Catalog bootstrap failed: %s", exc)
            _BOOTSTRAP_STATE["catalog_ready"] = False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Knowledge Catalog bootstrap failed: %s", exc)
            _BOOTSTRAP_STATE["catalog_ready"] = False

        if (
            _BOOTSTRAP_STATE["spanner_seeded"]
            and _BOOTSTRAP_STATE["bq_tables_ready"]
        ):
            _BOOTSTRAP_STATE["bootstrapped"] = True
        return dict(_BOOTSTRAP_STATE)


async def _await_startup_bootstrap() -> None:
    """Awaits startup bootstrap completion on Cloud Run before serving data."""
    task = _RUNTIME_TASKS.get("bootstrap")
    if task is not None and not task.done():
        await asyncio.shield(task)
        return
    if (
        not _BOOTSTRAP_STATE["bootstrapped"]
        and (os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT"))
        and os.getenv("DISABLE_VERTEX_LLM", "").lower()
        not in ("1", "true", "yes")
    ):
        await ensure_bootstrapped()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Starts non-blocking database and catalog bootstrap on server startup."""
    bootstrap_task = asyncio.create_task(ensure_bootstrapped())
    _RUNTIME_TASKS["bootstrap"] = bootstrap_task
    yield
    if not bootstrap_task.done():
        bootstrap_task.cancel()


app = FastAPI(
    title="Dual-Graph System of Action API",
    version="1.0.0",
    lifespan=lifespan,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def disable_ui_and_static_cache(
    request: Request, call_next: Any
) -> Response:
    """Sets no-cache headers on HTML and static JS routes to avoid stale UI."""
    response = await call_next(request)
    path = request.url.path
    if path in ("/shop", "/console") or path.startswith("/static/"):
        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )
    return response


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    """Redirects root requests to UI 1 (/shop)."""
    return RedirectResponse(url="/shop")


@app.get("/shop", response_class=HTMLResponse, include_in_schema=False)
async def serve_shop_ui() -> HTMLResponse:
    """Serves UI 1 (TheLook Shopping Mall and Chat App)."""
    return HTMLResponse(content=_load_html_template("shop.html"))


@app.get("/console", response_class=HTMLResponse, include_in_schema=False)
async def serve_console_ui() -> HTMLResponse:
    """Serves UI 2 (Data Engineer Investigation Console)."""
    return HTMLResponse(content=_load_html_template("console.html"))


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """Awaits bootstrap completion and reports readiness for Cloud Run/TF."""
    state = await ensure_bootstrapped()
    ready = bool(state["spanner_seeded"] and state["bq_tables_ready"])
    payload = {
        "status": "ok" if ready else "initializing",
        "spanner_seeded": bool(state["spanner_seeded"]),
        "bq_tables_ready": bool(state["bq_tables_ready"]),
        "bq_graph_mode": str(state["bq_graph_mode"]),
        "catalog_ready": bool(state["catalog_ready"]),
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@app.get("/api/products")
async def get_products() -> dict[str, Any]:
    """Returns storefront products and fulfillment centers from Spanner."""
    try:
        await _await_startup_bootstrap()
        products = await asyncio.to_thread(fetch_storefront_products)
        return {"products": products}
    except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
        logger.error("Failed to fetch products: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to load storefront products."
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error fetching products: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to load storefront products."
        ) from exc


@app.get("/api/customers")
async def get_customers() -> dict[str, Any]:
    """Returns Customer A (1001), Customer B (2048), and Customer C (3072)."""
    try:
        await _await_startup_bootstrap()
        customers = await asyncio.to_thread(fetch_persona_customers)
        return {"customers": customers}
    except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
        logger.error("Failed to fetch customers: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to load customer personas."
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error fetching customers: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to load customer personas."
        ) from exc


@app.get("/api/customers/{user_id}/orders")
async def get_customer_orders(user_id: int) -> dict[str, Any]:
    """Returns order history and item statuses for a customer ID."""
    try:
        await _await_startup_bootstrap()
        orders = await asyncio.to_thread(fetch_customer_orders, int(user_id))
        return {"orders": orders}
    except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
        logger.error("Failed to fetch orders for user_id=%s: %s", user_id, exc)
        raise HTTPException(
            status_code=500, detail="Unable to load customer order history."
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Unexpected error fetching orders for user_id=%s: %s", user_id, exc
        )
        raise HTTPException(
            status_code=500, detail="Unable to load customer order history."
        ) from exc


@app.post("/api/chat/refund")
async def post_chat_refund(payload: ChatRefundRequest) -> dict[str, Any]:
    """Executes the ADK 2.0 RefundSystemOfActionWorkflow for a customer."""
    try:
        await _await_startup_bootstrap()
        return await asyncio.to_thread(
            run_refund_workflow,
            int(payload.user_id),
            payload.message,
            require_confirmation=True,
            confirmed=bool(payload.confirmed),
            pending_order_id=payload.pending_order_id,
        )
    except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
        logger.error("Refund workflow error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Unable to process refund workflow request.",
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected refund workflow error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Unable to process refund workflow request.",
        ) from exc


@app.post("/api/chat/refund/stream")
async def post_chat_refund_stream(
    payload: ChatRefundRequest,
) -> StreamingResponse:
    """Streams real-time NDJSON step events and the final workflow result."""
    await _await_startup_bootstrap()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def _on_step(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def _worker() -> None:
        try:
            result = await asyncio.to_thread(
                run_refund_workflow,
                int(payload.user_id),
                payload.message,
                require_confirmation=True,
                confirmed=bool(payload.confirmed),
                pending_order_id=payload.pending_order_id,
                step_observer=_on_step,
            )
            await queue.put({"type": "result", "data": result})
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unexpected refund stream error: %s", exc)
            await queue.put(
                {
                    "type": "error",
                    "detail": "Unable to process refund workflow request.",
                }
            )
        finally:
            await queue.put(None)

    async def _event_generator() -> AsyncIterator[str]:
        task = asyncio.create_task(_worker())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield json.dumps(item, ensure_ascii=False) + "\n"
        finally:
            await task

    return StreamingResponse(
        _event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/demo/reset")
async def post_demo_reset() -> dict[str, Any]:
    """Resets demo orders in Cloud Spanner and clears BigQuery lineage."""
    try:
        clear_pending_confirmations()
        reset_ids = await asyncio.to_thread(reset_demo_orders)
        bq_tables = await asyncio.to_thread(reset_bigquery_lineage)
        return {
            "status": "reset",
            "reset_order_ids": reset_ids,
            "bq_tables_cleared": bq_tables,
        }
    except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
        logger.error("Demo reset failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to reset demo orders."
        ) from exc


@app.get("/api/traces")
async def get_traces() -> dict[str, Any]:
    """Returns recent ADK 2.0 refund workflow traces from BigQuery."""
    try:
        traces = await asyncio.to_thread(list_recent_traces)
        return {"traces": traces}
    except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
        logger.error("Failed to list traces: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to load workflow traces."
        ) from exc


@app.get("/api/traces/{trace_id}/graph")
async def get_trace_graph(trace_id: str) -> dict[str, Any]:
    """Returns Cytoscape.js nodes and edges for a workflow trace_id."""
    try:
        return await asyncio.to_thread(build_dual_graph_elements, trace_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Trace not found.") from exc
    except (GoogleAPICallError, RuntimeError, OSError) as exc:
        logger.error("Failed to build graph for trace %s: %s", trace_id, exc)
        raise HTTPException(
            status_code=500, detail="Unable to build dual-graph elements."
        ) from exc


@app.get("/api/governance")
async def get_governance() -> dict[str, Any]:
    """Returns the Knowledge Catalog contract, policy doc, and U2G triples."""
    try:
        contract = await asyncio.to_thread(fetch_knowledge_catalog_aspect)
        artifacts = load_governance_artifacts()
        project_id = (
            os.getenv("GCP_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or "your-project-id"
        )
        region = os.getenv("GCP_REGION", "us-central1")
        spanner_conn = os.getenv(
            "SPANNER_CONNECTION_ID",
            f"{project_id}.{region}.spanner-data-boost",
        )
        bq_state = get_bq_runtime_state()
        glossary_bundle = load_glossary_bundle()
        return {
            "catalog_contract": contract,
            "glossary_terms": glossary_bundle.get("terms", []),
            "policy_document_markdown": artifacts["policy_document_markdown"],
            "u2g_triples": artifacts["u2g_triples"],
            "runtime_config": {
                "gcp_project_id": project_id,
                "gcp_region": region,
                "spanner_connection_id": spanner_conn,
                "bq_graph_mode": bq_state["bq_graph_mode"],
            },
        }
    except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
        logger.error("Failed to load governance metadata: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to load governance metadata."
        ) from exc


@app.post("/api/query/spanner")
async def post_query_spanner(payload: QueryRequest) -> dict[str, Any]:
    """Executes a read-only guarded ISO GQL or SQL query in Cloud Spanner."""
    try:
        return await asyncio.to_thread(
            execute_readonly_spanner_query, payload.query
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GoogleAPICallError, RuntimeError, OSError) as exc:
        logger.error("Spanner workbench query failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Cloud Spanner query execution failed.",
        ) from exc


@app.post("/api/query/bigquery")
async def post_query_bigquery(payload: QueryRequest) -> dict[str, Any]:
    """Executes a read-only guarded BigQuery GQL or SQL query."""
    try:
        return await asyncio.to_thread(execute_readonly_bigquery, payload.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GoogleAPICallError, RuntimeError, OSError) as exc:
        logger.error("BigQuery workbench query failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="BigQuery query execution failed.",
        ) from exc
