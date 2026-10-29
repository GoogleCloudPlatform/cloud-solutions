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

"""BigQuery ActionLineageGraph buffered writer, DDL, and GQL runner."""

import functools
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.agent.catalog_client import (
    fetch_knowledge_catalog_aspect,
    get_query_templates,
)
from app.agent.spanner_client import (
    fetch_customer_orders,
    query_spanner_operational_context_graph,
)
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery

logger = logging.getLogger(__name__)

_APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = (
    _APP_DIR / "data"
    if (_APP_DIR / "data").exists()
    else PROJECT_ROOT / "data"
)
BQ_SCHEMA_PATH = _DATA_DIR / "bigquery_schema.sql"

TRACE_ID_RE = re.compile(r"^trace-[0-9a-fA-F-]+$")
GRAPH_TRACE_ID_EXTRACT_RE = re.compile(
    r"trace_id\s*(?::|=)\s*['\"]([^'\"]+)['\"]", re.IGNORECASE
)
READONLY_BQ_PREFIX_RE = re.compile(
    r"^\s*(?:SELECT|GRAPH_TABLE|WITH)\b", re.IGNORECASE
)
FORBIDDEN_BQ_DML_DDL_RE = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|"
    r"GRANT|REVOKE)\b",
    re.IGNORECASE,
)

STEP_ORDER_MAP: dict[str, tuple[int, str]] = {
    "IntentAgent": (1, "IntentAgent"),
    "intent_agent": (1, "IntentAgent"),
    "resolve_catalog_contract": (2, "resolve_catalog_contract"),
    "evaluate_spanner_policy": (3, "evaluate_spanner_policy"),
    "route_and_commit_action": (4, "route_and_commit_action"),
    "ResponseAgent": (5, "ResponseAgent"),
    "response_agent": (5, "ResponseAgent"),
}

_BQ_RUNTIME_STATE: dict[str, Any] = {
    "bq_tables_ready": False,
    "bq_graph_mode": "gql",
    "reset_cutoff_iso": None,
}
_MEMORY_TRACE_STORE: dict[str, dict[str, Any]] = {}
_LINEAGE_TABLE_NAMES: tuple[str, ...] = (
    "agent_sessions",
    "workflow_nodes",
    "policy_evaluations",
    "agent_actions",
)


def get_bq_runtime_state() -> dict[str, Any]:
    """Returns the current BigQuery table and property graph readiness state."""
    return dict(_BQ_RUNTIME_STATE)


def set_bq_graph_mode(mode: str) -> None:
    """Updates the active BigQuery execution mode ('gql' or 'sql_fallback')."""
    _BQ_RUNTIME_STATE["bq_graph_mode"] = mode


def clear_memory_trace_store() -> None:
    """Clears the in-process trace cache used for unit tests and fast reads."""
    _MEMORY_TRACE_STORE.clear()
    _BQ_RUNTIME_STATE["reset_cutoff_iso"] = None


def reset_bigquery_lineage(bq_client: Any = None) -> list[str]:
    """Clears in-memory trace cache and truncates BigQuery lineage tables."""
    _MEMORY_TRACE_STORE.clear()
    _BQ_RUNTIME_STATE["reset_cutoff_iso"] = datetime.now(
        timezone.utc
    ).isoformat()
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    )
    dataset_id = os.getenv("BIGQUERY_DATASET_ID", "soa_action_lineage")
    if project_id or bq_client is not None:
        try:
            client = bq_client or bigquery.Client(project=project_id)
            prefix = f"{project_id}.{dataset_id}" if project_id else dataset_id
            for table_name in _LINEAGE_TABLE_NAMES:
                job = client.query(f"TRUNCATE TABLE `{prefix}.{table_name}`")
                job.result(timeout=15.0)
        except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
            logger.warning(
                "BigQuery lineage truncation fell back to cutoff filter: %s",
                exc,
            )
    return list(_LINEAGE_TABLE_NAMES)


def validate_trace_id(trace_id: str) -> str:
    """Validates that a trace_id matches ^trace-[0-9a-fA-F-]+$."""
    cleaned = str(trace_id).strip()
    if not TRACE_ID_RE.match(cleaned):
        raise ValueError(f"Invalid trace_id format: {trace_id}")
    return cleaned


@functools.lru_cache(maxsize=1)
def _load_bq_ddl_statements() -> list[str]:
    """Loads and splits data/bigquery_schema.sql into executable statements."""
    raw_sql = BQ_SCHEMA_PATH.read_text(encoding="utf-8")
    statements: list[str] = []
    for part in raw_sql.split(";"):
        lines = [
            line
            for line in part.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    return statements


def _qualify_dataset_sql(sql: str) -> str:
    """Replaces `{dataset}` and default dataset references."""
    dataset_id = os.getenv("BIGQUERY_DATASET_ID", "soa_action_lineage")
    qualified = sql.replace("{dataset}", dataset_id)
    if dataset_id == "soa_action_lineage":
        return qualified
    return qualified.replace("soa_action_lineage.", f"{dataset_id}.")


def ensure_bigquery_schema(
    bq_client: Any = None,
) -> tuple[bool, str]:
    """Ensures the 4 BigQuery lineage tables and ActionLineageGraph exist."""
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    )
    if not project_id and bq_client is None:
        _BQ_RUNTIME_STATE["bq_tables_ready"] = True
        _BQ_RUNTIME_STATE["bq_graph_mode"] = "sql_fallback"
        return True, "sql_fallback"

    client = bq_client or bigquery.Client(project=project_id)
    statements = _load_bq_ddl_statements()
    table_stmts = [
        s for s in statements if "CREATE OR REPLACE PROPERTY GRAPH" not in s
    ]
    graph_stmts = [
        s for s in statements if "CREATE OR REPLACE PROPERTY GRAPH" in s
    ]

    for stmt in table_stmts:
        job = client.query(_qualify_dataset_sql(stmt))
        job.result(timeout=30.0)
    _BQ_RUNTIME_STATE["bq_tables_ready"] = True

    graph_mode = "gql"
    for stmt in graph_stmts:
        try:
            job = client.query(_qualify_dataset_sql(stmt))
            job.result(timeout=30.0)
        except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
            logger.warning(
                "BigQuery PROPERTY GRAPH DDL unavailable in current project "
                "edition (%s); falling back to sql_fallback mode.",
                exc,
            )
            graph_mode = "sql_fallback"

    _BQ_RUNTIME_STATE["bq_graph_mode"] = graph_mode
    return True, graph_mode


def _insert_rows_with_backoff(
    client: Any, table_id: str, rows: list[dict[str, Any]]
) -> None:
    """Streams rows to a BigQuery table with 3-attempt exponential backoff."""
    for attempt in range(3):
        try:
            errors = client.insert_rows_json(table_id, rows)
            if not errors:
                return
            logger.warning(
                "BigQuery insert_rows_json errors on %s (attempt %d): %s",
                table_id,
                attempt + 1,
                errors,
            )
        except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
            logger.warning(
                "BigQuery insert_rows_json exception on %s (attempt %d): %s",
                table_id,
                attempt + 1,
                exc,
            )
        if attempt < 2:
            time.sleep(0.2 * (2**attempt))


def stream_node_lineage_to_bigquery(
    ctx: Any,
    node_name: str,
    latency_ms: float,
    bq_client: Any = None,
) -> None:
    """Buffers node telemetry and flushes all 4 tables after Step 5."""
    state = ctx.state
    trace_id = str(state.get("trace_id", f"trace-{uuid4().hex[:8]}"))
    step_order, canonical_name = STEP_ORDER_MAP.get(
        node_name, (0, str(node_name))
    )
    now_iso = datetime.now(timezone.utc).isoformat()

    buffer = state.setdefault(
        "lineage_buffer",
        {
            "started_at": now_iso,
            "workflow_nodes": [],
        },
    )

    if canonical_name == "evaluate_spanner_policy":
        policy_eval = state.get("policy_eval") or {}
        node_exec_id = str(
            policy_eval.get("node_exec_id") or f"NODE-{uuid4().hex[:8]}"
        )
        if "policy_eval" in state and isinstance(state["policy_eval"], dict):
            state["policy_eval"]["node_exec_id"] = node_exec_id
    else:
        node_exec_id = f"NODE-{uuid4().hex[:8]}"

    buffer["workflow_nodes"].append(
        {
            "node_exec_id": node_exec_id,
            "trace_id": trace_id,
            "node_name": canonical_name,
            "step_order": step_order,
            "latency_ms": round(float(latency_ms), 2),
            "executed_at": now_iso,
        }
    )

    if step_order < 5:
        return

    policy_eval = dict(state.get("policy_eval") or {})
    action_outcome = dict(state.get("action_outcome") or {})
    step3_nodes = [
        n
        for n in buffer["workflow_nodes"]
        if n["node_name"] == "evaluate_spanner_policy"
    ]
    step3_exec_id = (
        step3_nodes[0]["node_exec_id"]
        if step3_nodes
        else str(policy_eval.get("node_exec_id") or f"NODE-{uuid4().hex[:8]}")
    )

    session_row = {
        "trace_id": trace_id,
        "customer_id": int(state.get("user_id", 1001)),
        "target_order_id": (
            int(state["order_id"])
            if state.get("order_id") is not None
            else None
        ),
        "user_prompt": str(state.get("user_prompt", "")),
        "started_at": str(buffer.get("started_at", now_iso)),
    }
    eval_id = str(policy_eval.get("eval_id") or f"EVAL-{uuid4().hex[:8]}")
    eval_row = {
        "eval_id": eval_id,
        "node_exec_id": step3_exec_id,
        "trace_id": trace_id,
        "catalog_term_id": str(
            policy_eval.get("catalog_term_id", "rolling-100d-refund-count")
        ),
        "policy_id": str(policy_eval.get("policy_id", "POL-REFUND-STD-V1")),
        "policy_name": str(
            policy_eval.get(
                "policy_name", "Tiered Standard and VIP Refund Policy"
            )
        ),
        "observed_refunds_100d": int(
            policy_eval.get("prior_refund_count_100d", 0)
        ),
        "max_refunds_100d": int(policy_eval.get("max_refunds_100d", 10)),
        "observed_order_age_days": (
            int(policy_eval["target_order_age_days"])
            if policy_eval.get("target_order_age_days") is not None
            else None
        ),
        "return_window_days": int(policy_eval.get("return_window_days", 30)),
        "evaluation_result": str(
            policy_eval.get("evaluation_result", "FAIL")
        ),
        "evaluated_at": now_iso,
    }
    action_row = {
        "action_id": str(
            action_outcome.get("action_id") or f"ACT-{uuid4().hex[:8]}"
        ),
        "eval_id": eval_id,
        "trace_id": trace_id,
        "action_type": str(
            action_outcome.get("action_type", "BLOCK_SPANNER_MUTATION")
        ),
        "decision_status": str(
            action_outcome.get("decision_status", "DENIED")
        ),
        "rejection_reason": action_outcome.get("rejection_reason"),
        "created_at": now_iso,
    }

    buffer["agent_session"] = session_row
    buffer["policy_evaluation"] = eval_row
    buffer["agent_action"] = action_row
    _MEMORY_TRACE_STORE[trace_id] = {
        "agent_session": session_row,
        "workflow_nodes": list(buffer["workflow_nodes"]),
        "policy_evaluation": eval_row,
        "agent_action": action_row,
    }

    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    )
    dataset_id = os.getenv("BIGQUERY_DATASET_ID", "soa_action_lineage")
    if not project_id and bq_client is None:
        return

    try:
        client = bq_client or bigquery.Client(project=project_id)
        prefix = f"{project_id}.{dataset_id}" if project_id else dataset_id
        _insert_rows_with_backoff(
            client, f"{prefix}.agent_sessions", [session_row]
        )
        _insert_rows_with_backoff(
            client, f"{prefix}.workflow_nodes", list(buffer["workflow_nodes"])
        )
        _insert_rows_with_backoff(
            client, f"{prefix}.policy_evaluations", [eval_row]
        )
        _insert_rows_with_backoff(
            client, f"{prefix}.agent_actions", [action_row]
        )
    except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
        logger.warning(
            "Failed to flush BigQuery lineage for trace_id=%s: %s",
            trace_id,
            exc,
        )


def list_recent_traces(bq_client: Any = None) -> list[dict[str, Any]]:
    """Returns up to 50 recent refund workflow traces from BQ or memory."""
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    )
    if project_id or bq_client is not None:
        try:
            client = bq_client or bigquery.Client(project=project_id)
            sql = _qualify_dataset_sql(
                get_query_templates()["bq_recent_traces_sql"]
            )
            job = client.query(sql)
            rows = list(job.result(timeout=15.0))
            cutoff_iso = _BQ_RUNTIME_STATE.get("reset_cutoff_iso")
            if rows:
                results = [
                    {
                        "trace_id": str(r[0]),
                        "customer_id": int(r[1]),
                        "target_order_id": (
                            int(r[2]) if r[2] is not None else None
                        ),
                        "decision_status": str(r[3]),
                        "evaluation_result": str(r[4]),
                        "observed_refunds_100d": int(r[5]),
                        "max_refunds_100d": int(r[6]),
                        "latency_ms": float(r[7]),
                        "started_at": (
                            r[8].isoformat()
                            if hasattr(r[8], "isoformat")
                            else str(r[8])
                        ),
                    }
                    for r in rows
                ]
                if cutoff_iso:
                    results = [
                        item
                        for item in results
                        if str(item["started_at"]) >= str(cutoff_iso)
                    ]
                if results or cutoff_iso:
                    return results
        except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
            logger.warning(
                "BigQuery trace listing fell back to memory: %s", exc
            )

    traces: list[dict[str, Any]] = []
    for trace_id, bundle in reversed(list(_MEMORY_TRACE_STORE.items())):
        session = bundle["agent_session"]
        pe = bundle["policy_evaluation"]
        act = bundle["agent_action"]
        step3 = [
            n
            for n in bundle["workflow_nodes"]
            if n["node_name"] == "evaluate_spanner_policy"
        ]
        latency = float(step3[0]["latency_ms"]) if step3 else 0.0
        traces.append(
            {
                "trace_id": trace_id,
                "customer_id": int(session["customer_id"]),
                "target_order_id": session["target_order_id"],
                "decision_status": str(act["decision_status"]),
                "evaluation_result": str(pe["evaluation_result"]),
                "observed_refunds_100d": int(pe["observed_refunds_100d"]),
                "max_refunds_100d": int(pe["max_refunds_100d"]),
                "latency_ms": latency,
                "started_at": str(session["started_at"]),
            }
        )
    return traces[:50]


def _fetch_trace_bundle(
    trace_id: str, bq_client: Any = None
) -> dict[str, Any]:
    """Fetches trace session, evaluation, action, and workflow nodes."""
    cleaned_id = validate_trace_id(trace_id)
    if cleaned_id in _MEMORY_TRACE_STORE:
        return _MEMORY_TRACE_STORE[cleaned_id]

    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    )
    client = bq_client or bigquery.Client(project=project_id)
    templates = get_query_templates()
    detail_sql = _qualify_dataset_sql(templates["bq_trace_detail_sql"])
    nodes_sql = _qualify_dataset_sql(templates["bq_trace_nodes_sql"])
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("trace_id", "STRING", cleaned_id)
        ]
    )
    detail_rows = list(
        client.query(detail_sql, job_config=job_config).result(timeout=15.0)
    )
    if not detail_rows:
        raise KeyError(f"Trace {cleaned_id} not found.")
    d_row = detail_rows[0]
    node_rows = list(
        client.query(nodes_sql, job_config=job_config).result(timeout=15.0)
    )
    return {
        "agent_session": {
            "trace_id": str(d_row[0]),
            "customer_id": int(d_row[1]),
            "target_order_id": int(d_row[2]) if d_row[2] is not None else None,
            "user_prompt": str(d_row[3]),
            "started_at": str(d_row[4]),
        },
        "policy_evaluation": {
            "eval_id": str(d_row[5]),
            "node_exec_id": str(d_row[6]),
            "catalog_term_id": str(d_row[7]),
            "policy_id": str(d_row[8]),
            "policy_name": str(d_row[9]),
            "observed_refunds_100d": int(d_row[10]),
            "max_refunds_100d": int(d_row[11]),
            "observed_order_age_days": (
                int(d_row[12]) if d_row[12] is not None else None
            ),
            "return_window_days": int(d_row[13]),
            "evaluation_result": str(d_row[14]),
        },
        "agent_action": {
            "action_id": str(d_row[15]),
            "action_type": str(d_row[16]),
            "decision_status": str(d_row[17]),
            "rejection_reason": (
                str(d_row[18]) if d_row[18] is not None else None
            ),
            "created_at": str(d_row[19]),
        },
        "workflow_nodes": [
            {
                "node_exec_id": str(n[0]),
                "node_name": str(n[1]),
                "step_order": int(n[2]),
                "latency_ms": float(n[3]),
                "executed_at": str(n[4]),
            }
            for n in node_rows
        ],
    }


def build_dual_graph_elements(
    trace_id: str,
    bq_client: Any = None,
    spanner_db: Any = None,
) -> dict[str, Any]:
    """Builds Cytoscape.js nodes and edges across R2G, U2G, and BQ layers."""
    bundle = _fetch_trace_bundle(trace_id, bq_client=bq_client)
    session = bundle["agent_session"]
    pe = bundle["policy_evaluation"]
    act = bundle["agent_action"]
    wf_nodes = bundle["workflow_nodes"]

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    session_trace_id = session["trace_id"]
    session_node_id = f"bq:session:{session_trace_id}"
    nodes.append(
        {
            "data": {
                "id": session_node_id,
                "label": f"AgentSession\n({session_trace_id})",
                "layer": "bq",
                "properties": session,
            }
        }
    )

    for wf in wf_nodes:
        wf_exec_id = wf["node_exec_id"]
        wf_step = wf["step_order"]
        wf_name = wf["node_name"]
        wf_id = f"bq:node:{wf_exec_id}"
        nodes.append(
            {
                "data": {
                    "id": wf_id,
                    "label": f"{wf_step}. {wf_name}",
                    "layer": "bq",
                    "properties": wf,
                }
            }
        )
        edges.append(
            {
                "data": {
                    "id": f"edge:{session_node_id}->{wf_id}",
                    "source": session_node_id,
                    "target": wf_id,
                    "label": "executed_node",
                }
            }
        )

    pe_eval_id = pe["eval_id"]
    pe_eval_result = pe["evaluation_result"]
    pe_node_exec_id = pe["node_exec_id"]
    pe_node_id = f"bq:eval:{pe_eval_id}"
    nodes.append(
        {
            "data": {
                "id": pe_node_id,
                "label": f"PolicyEvaluation\n({pe_eval_result})",
                "layer": "bq",
                "properties": pe,
            }
        }
    )
    step3_source = f"bq:node:{pe_node_exec_id}"
    edges.append(
        {
            "data": {
                "id": f"edge:{step3_source}->{pe_node_id}",
                "source": step3_source,
                "target": pe_node_id,
                "label": "evaluated_policy",
            }
        }
    )

    act_id = act["action_id"]
    act_status = act["decision_status"]
    act_node_id = f"bq:action:{act_id}"
    nodes.append(
        {
            "data": {
                "id": act_node_id,
                "label": f"AgentAction\n({act_status})",
                "layer": "bq",
                "properties": act,
            }
        }
    )
    edges.append(
        {
            "data": {
                "id": f"edge:{pe_node_id}->{act_node_id}",
                "source": pe_node_id,
                "target": act_node_id,
                "label": "triggered_action",
            }
        }
    )

    pe_policy_id = pe["policy_id"]
    policy_node_id = f"u2g:policy:{pe_policy_id}"
    nodes.append(
        {
            "data": {
                "id": policy_node_id,
                "label": f"Policy\n({pe_policy_id})",
                "layer": "u2g",
                "properties": {
                    "policy_id": pe_policy_id,
                    "policy_name": pe["policy_name"],
                    "catalog_term_id": pe["catalog_term_id"],
                },
            }
        }
    )
    edges.append(
        {
            "data": {
                "id": f"edge:{pe_node_id}->{policy_node_id}",
                "source": pe_node_id,
                "target": policy_node_id,
                "label": "references_policy",
            }
        }
    )

    customer_id = int(session["customer_id"])
    target_order_id = session.get("target_order_id")
    if target_order_id is not None:
        contract = fetch_knowledge_catalog_aspect()
        try:
            ctx_row = query_spanner_operational_context_graph(
                customer_id,
                int(target_order_id),
                contract,
                database=spanner_db,
            )
        except (GoogleAPICallError, ValueError, RuntimeError, OSError) as exc:
            logger.warning("Spanner graph enrichment skipped: %s", exc)
            ctx_row = {"order_found": False}

        try:
            orders = fetch_customer_orders(customer_id, database=spanner_db)
        except (
            GoogleAPICallError,
            ValueError,
            IndexError,
            RuntimeError,
            OSError,
        ):
            orders = []

        if ctx_row.get("order_found"):
            user_node_id = f"r2g:user:{customer_id}"
            tier = ctx_row.get("customer_tier", "STANDARD")
            nodes.append(
                {
                    "data": {
                        "id": user_node_id,
                        "label": f"User {customer_id}\n({tier})",
                        "layer": "r2g",
                        "properties": {
                            "user_id": customer_id,
                            "email": ctx_row.get("email"),
                            "customer_tier": tier,
                        },
                    }
                }
            )
            target_status = ctx_row.get("target_order_status")
            product_names = ctx_row.get("product_names")
            dc_names = ctx_row.get("distribution_center_names")
            restriction_action = ctx_row.get("restriction_action")
            order_node_id = f"r2g:order:{target_order_id}"
            nodes.append(
                {
                    "data": {
                        "id": order_node_id,
                        "label": f"Order {target_order_id}\n({target_status})",
                        "layer": "r2g",
                        "properties": {
                            "order_id": int(target_order_id),
                            "status": target_status,
                            "age_days": ctx_row.get("target_order_age_days"),
                            "sale_price": ctx_row.get("target_order_price"),
                        },
                    }
                }
            )
            edges.append(
                {
                    "data": {
                        "id": f"edge:{user_node_id}->{order_node_id}",
                        "source": user_node_id,
                        "target": order_node_id,
                        "label": "places",
                    }
                }
            )
            edges.append(
                {
                    "data": {
                        "id": f"edge:{session_node_id}->{order_node_id}",
                        "source": session_node_id,
                        "target": order_node_id,
                        "label": "targets_order",
                    }
                }
            )

            returned_orders = [
                o
                for o in orders
                if o["order_id"] != int(target_order_id)
                and o["status"] == "Returned"
            ][:3]
            for hist_o in returned_orders:
                hist_oid = hist_o["order_id"]
                h_id = f"r2g:order:{hist_oid}"
                nodes.append(
                    {
                        "data": {
                            "id": h_id,
                            "label": f"Order {hist_oid}\n(Returned)",
                            "layer": "r2g",
                            "properties": hist_o,
                        }
                    }
                )
                edges.append(
                    {
                        "data": {
                            "id": f"edge:{user_node_id}->{h_id}",
                            "source": user_node_id,
                            "target": h_id,
                            "label": "places",
                        }
                    }
                )

            item_node_id = f"r2g:item:{target_order_id}"
            prod_node_id = f"r2g:product:{target_order_id}"
            dc_node_id = f"r2g:dc:{target_order_id}"
            nodes.extend(
                [
                    {
                        "data": {
                            "id": item_node_id,
                            "label": f"InventoryItem\n(ORD-{target_order_id})",
                            "layer": "r2g",
                            "properties": {
                                "order_id": int(target_order_id),
                                "sale_price": ctx_row.get("target_order_price"),
                            },
                        }
                    },
                    {
                        "data": {
                            "id": prod_node_id,
                            "label": f"Product\n({product_names})",
                            "layer": "r2g",
                            "properties": {
                                "product_names": product_names,
                            },
                        }
                    },
                    {
                        "data": {
                            "id": dc_node_id,
                            "label": f"DistributionCenter\n({dc_names})",
                            "layer": "r2g",
                            "properties": {
                                "name": dc_names,
                            },
                        }
                    },
                ]
            )
            edges.extend(
                [
                    {
                        "data": {
                            "id": f"edge:{order_node_id}->{item_node_id}",
                            "source": order_node_id,
                            "target": item_node_id,
                            "label": "contains_item",
                        }
                    },
                    {
                        "data": {
                            "id": f"edge:{item_node_id}->{prod_node_id}",
                            "source": item_node_id,
                            "target": prod_node_id,
                            "label": "is_product",
                        }
                    },
                    {
                        "data": {
                            "id": f"edge:{prod_node_id}->{dc_node_id}",
                            "source": prod_node_id,
                            "target": dc_node_id,
                            "label": "supplied_by",
                        }
                    },
                    {
                        "data": {
                            "id": f"edge:{prod_node_id}->{policy_node_id}",
                            "source": prod_node_id,
                            "target": policy_node_id,
                            "label": "governed_by",
                        }
                    },
                ]
            )

            cond_id = str(
                ctx_row.get("condition_id", "COND-REFUND-STD-100D-30D")
            )
            cond_node_id = f"u2g:cond:{cond_id}"
            res_node_id = "u2g:res:RES-DENY-AUTO-REFUND"
            nodes.extend(
                [
                    {
                        "data": {
                            "id": cond_node_id,
                            "label": f"PolicyCondition\n({cond_id})",
                            "layer": "u2g",
                            "properties": {
                                "condition_id": cond_id,
                                "applicable_tier": tier,
                                "max_refunds_100d": ctx_row.get(
                                    "max_refunds_100d"
                                ),
                                "return_window_days": ctx_row.get(
                                    "return_window_days"
                                ),
                            },
                        }
                    },
                    {
                        "data": {
                            "id": res_node_id,
                            "label": (
                                f"PolicyRestriction\n({restriction_action})"
                            ),
                            "layer": "u2g",
                            "properties": {
                                "restriction_id": "RES-DENY-AUTO-REFUND",
                                "action_code": restriction_action,
                            },
                        }
                    },
                ]
            )
            edges.extend(
                [
                    {
                        "data": {
                            "id": f"edge:{policy_node_id}->{cond_node_id}",
                            "source": policy_node_id,
                            "target": cond_node_id,
                            "label": "requires_condition",
                        }
                    },
                    {
                        "data": {
                            "id": f"edge:{policy_node_id}->{res_node_id}",
                            "source": policy_node_id,
                            "target": res_node_id,
                            "label": "enforces_restriction",
                        }
                    },
                ]
            )

    return {"nodes": nodes, "edges": edges}


def _strip_sql_comments(query: str) -> str:
    """Strips SQL line (--) and block (/* */) comments for guard checks."""
    no_block = re.sub(r"/\*[\s\S]*?\*/", " ", query)
    return re.sub(r"--[^\n]*", " ", no_block).strip()


def validate_readonly_bq_query(query: str) -> str:
    """Enforces that a workbench BigQuery query is read-only."""
    cleaned = query.strip()
    uncommented = _strip_sql_comments(cleaned)
    if not uncommented:
        raise ValueError("Query string must not be empty.")
    if not READONLY_BQ_PREFIX_RE.match(uncommented):
        raise ValueError(
            "Only read-only SELECT, GRAPH_TABLE, or WITH queries are allowed."
        )
    if FORBIDDEN_BQ_DML_DDL_RE.search(uncommented):
        raise ValueError("Mutating DML or DDL statements are forbidden.")
    return cleaned


def _format_bq_rows(
    result: Any,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Formats BigQuery RowIterator results into columns and JSON-safe rows."""
    raw_rows = []
    for idx, row in enumerate(result):
        if idx >= 500:
            break
        raw_rows.append(row)
    columns = [field.name for field in result.schema] if result.schema else []
    if not columns and raw_rows and isinstance(raw_rows[0], dict):
        columns = list(raw_rows[0].keys())
    rows_out: list[dict[str, Any]] = []
    for row in raw_rows:
        if isinstance(row, dict):
            rows_out.append(
                {
                    k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in row.items()
                }
            )
        else:
            rows_out.append(
                {
                    col: (
                        row[idx].isoformat()
                        if hasattr(row[idx], "isoformat")
                        else row[idx]
                    )
                    for idx, col in enumerate(columns)
                }
            )
    return columns, rows_out


def _run_bq_sql_fallback_query(
    client: Any,
    cleaned: str,
    templates: dict[str, str],
    started: float,
) -> dict[str, Any]:
    """Executes the parameterized SQL JOIN fallback for a GRAPH_TABLE query."""
    uncommented = _strip_sql_comments(cleaned)
    match = GRAPH_TRACE_ID_EXTRACT_RE.search(uncommented)
    lower_query = uncommented.lower()
    is_denial_template = (
        "rejection_reason" in uncommented
        or "evaluation_result: 'fail'" in lower_query
        or "evaluation_result: \"fail\"" in lower_query
        or "evaluation_result = 'fail'" in lower_query
        or "evaluation_result = \"fail\"" in lower_query
    )
    template_key = (
        "bq_fallback_denial_sql"
        if is_denial_template
        else "bq_fallback_approval_sql"
    )
    sql_to_run = _qualify_dataset_sql(templates[template_key])
    query_params: list[bigquery.ScalarQueryParameter] = []
    if match:
        extracted_trace_id = validate_trace_id(match.group(1))
        query_params.append(
            bigquery.ScalarQueryParameter(
                "trace_id", "STRING", extracted_trace_id
            )
        )
    else:
        sql_to_run = re.sub(
            r"\s+WHERE\s+s\.trace_id\s*=\s*@trace_id\b",
            "",
            sql_to_run,
            flags=re.IGNORECASE,
        )
        sql_to_run = f"{sql_to_run} ORDER BY s.started_at DESC LIMIT 50"

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=100 * 1024 * 1024,
        job_timeout_ms=15000,
        query_parameters=query_params,
    )
    result = client.query(sql_to_run, job_config=job_config).result(
        timeout=15.0
    )
    columns, rows_out = _format_bq_rows(result)
    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    return {
        "columns": columns,
        "rows": rows_out,
        "execution_mode": "sql_fallback",
        "latency_ms": latency_ms,
    }


def execute_readonly_bigquery(
    query: str, bq_client: Any = None
) -> dict[str, Any]:
    """Executes a read-only BigQuery GQL/SQL query with sql_fallback."""
    cleaned = validate_readonly_bq_query(query)
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    )
    client = bq_client or bigquery.Client(project=project_id)
    mode = str(_BQ_RUNTIME_STATE.get("bq_graph_mode", "gql"))
    templates = get_query_templates()
    started = time.perf_counter()
    is_graph_table_query = "GRAPH_TABLE" in cleaned.upper()

    if mode == "sql_fallback" and is_graph_table_query:
        return _run_bq_sql_fallback_query(
            client, cleaned, templates, started
        )

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=100 * 1024 * 1024,
        job_timeout_ms=15000,
    )
    try:
        result = client.query(
            _qualify_dataset_sql(cleaned), job_config=job_config
        ).result(timeout=15.0)
    except GoogleAPICallError as exc:
        if is_graph_table_query and (
            "reservation" in str(exc).lower()
            or "enterprise" in str(exc).lower()
            or "property graph" in str(exc).lower()
        ):
            logger.warning(
                "GRAPH_TABLE execution requires Enterprise reservation (%s); "
                "switching to sql_fallback mode.",
                exc,
            )
            _BQ_RUNTIME_STATE["bq_graph_mode"] = "sql_fallback"
            return _run_bq_sql_fallback_query(
                client, cleaned, templates, started
            )
        raise
    columns, rows_out = _format_bq_rows(result)
    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    return {
        "columns": columns,
        "rows": rows_out,
        "execution_mode": mode,
        "latency_ms": latency_ms,
    }
