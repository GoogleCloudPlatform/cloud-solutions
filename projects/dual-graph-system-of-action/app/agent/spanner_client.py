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

"""Cloud Spanner Graph ISO GQL queries and transactional mutation client."""

import os
import re
import time
from typing import Any
from uuid import uuid4

from app.agent.catalog_client import get_query_templates
from data.spanner_seed import get_spanner_database
from google.cloud.spanner_v1 import param_types

READONLY_SPANNER_PREFIX_RE = re.compile(
    r"^\s*(?:GRAPH\s+OperationalContextGraph|SELECT)\b",
    re.IGNORECASE,
)
FORBIDDEN_DML_DDL_RE = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def default_policy_eval_baseline() -> dict[str, Any]:
    """Returns fallback policy evaluation attributes when order is missing."""
    return {
        "order_found": False,
        "policy_id": "POL-REFUND-STD-V1",
        "policy_name": "Tiered Standard and VIP Refund Policy",
        "condition_id": "COND-REFUND-STD-100D-30D",
        "customer_tier": "STANDARD",
        "prior_refund_count_100d": 0,
        "max_refunds_100d": int(os.getenv("MAX_REFUNDS_100D_LIMIT", "10")),
        "return_window_days": 30,
        "target_order_age_days": None,
        "target_order_status": None,
        "target_order_price": None,
        "product_names": None,
        "distribution_center_names": None,
    }


def classify_policy_failure(
    eval_data: dict[str, Any],
    catalog_contract: dict[str, Any],
    order_id: int | None,
) -> tuple[str, str | None, str]:
    """Classifies eligibility in Priority 1-6 order and resolves term ID."""
    primary_term = str(
        catalog_contract.get("catalog_term_id", "rolling-100d-refund-count")
    )
    secondary_term = str(
        catalog_contract.get("secondary_term_id", "order-age-days")
    )
    tier_term = str(
        catalog_contract.get("tier_term_id", "customer-loyalty-tier")
    )
    returned_status = str(catalog_contract.get("returned_status", "Returned"))
    eligible_status = str(
        catalog_contract.get("eligible_order_status", "Complete")
    )
    vip_tier = str(catalog_contract.get("vip_tier", "VIP"))
    std_limit = int(os.getenv("MAX_REFUNDS_100D_LIMIT", "10"))

    if order_id is None:
        return "FAIL", "MISSING_ORDER_ID", primary_term
    if not eval_data.get("order_found", False):
        return "FAIL", "ORDER_NOT_FOUND_OR_UNAUTHORIZED", primary_term
    target_status = eval_data.get("target_order_status")
    if target_status == returned_status:
        return "FAIL", "ALREADY_RETURNED", primary_term
    age_days = eval_data.get("target_order_age_days")
    if target_status != eligible_status or age_days is None:
        return "FAIL", "ORDER_NOT_DELIVERED", secondary_term
    if int(age_days) > int(eval_data.get("return_window_days", 30)):
        return "FAIL", "RETURN_WINDOW_EXPIRED", secondary_term
    prior_count = int(eval_data.get("prior_refund_count_100d", 0))
    max_allowed = int(eval_data.get("max_refunds_100d", std_limit))
    if prior_count >= max_allowed:
        return "FAIL", "MAX_REFUNDS_EXCEEDED", primary_term

    if eval_data.get("customer_tier") == vip_tier and prior_count >= std_limit:
        return "PASS", None, tier_term
    return "PASS", None, primary_term


def _format_candidate_order(cand: dict[str, Any]) -> str:
    """Formats a single candidate order entry for clarification prompts."""
    oid = cand["order_id"]
    prod = cand["product_name"]
    price = float(cand["sale_price"])
    status = cand["status"]
    return f"ORD-{oid} ({prod}, ${price:.2f}, {status})"


def format_rejection_reason(
    failure_code: str | None,
    order_id: int | None,
    user_id: int,
    eval_data: dict[str, Any],
    candidate_orders: list[dict[str, Any]] | None = None,
) -> str | None:
    """Formats the deterministic rejection reason template for a failure."""
    if failure_code is None:
        return None
    candidates = candidate_orders or []
    summary = ", ".join(_format_candidate_order(c) for c in candidates)
    if failure_code == "MISSING_ORDER_ID":
        if summary:
            return (
                "Which order would you like to refund? Please select or "
                f"reply with one of your active orders: {summary}."
            )
        return (
            "Please provide a valid 5-digit order number "
            "(for example, ORD-90124) to request a refund."
        )
    if failure_code == "ORDER_NOT_FOUND_OR_UNAUTHORIZED":
        if summary:
            return (
                f"Order {order_id} was not found for user {user_id}. "
                f"Did you mean one of your active orders: {summary}?"
            )
        return f"Order {order_id} was not found for user {user_id}."
    if failure_code == "ALREADY_RETURNED":
        return (
            f"Order {order_id} has already been returned "
            "(reset demo data to re-test)."
        )
    if failure_code == "ORDER_NOT_DELIVERED":
        status = eval_data.get("target_order_status")
        return (
            f"Order {order_id} has status '{status}' "
            "and has not been delivered yet."
        )
    if failure_code == "RETURN_WINDOW_EXPIRED":
        age = eval_data.get("target_order_age_days")
        window = eval_data.get("return_window_days", 30)
        return (
            f"Order was delivered {age} days ago, "
            f"exceeding the {window}-day return window."
        )
    if failure_code == "MAX_REFUNDS_EXCEEDED":
        tier = eval_data.get("customer_tier", "STANDARD")
        count = eval_data.get("prior_refund_count_100d", 0)
        limit = eval_data.get("max_refunds_100d", 10)
        return (
            f"Customer ({tier} tier) already has {count} returned items "
            f"in the last 100 days (limit: {limit})."
        )
    return f"Refund request denied ({failure_code})."


def _parse_gql_row(row: Any) -> dict[str, Any]:
    """Maps a 16-column OperationalContextGraph GQL row into a dictionary."""
    return {
        "order_found": True,
        "user_id": int(row[0]),
        "email": str(row[1]),
        "customer_tier": str(row[2]),
        "target_order_id": int(row[3]),
        "target_order_status": str(row[4]),
        "product_names": str(row[5]) if row[5] is not None else "",
        "distribution_center_names": str(row[6]) if row[6] is not None else "",
        "target_order_price": float(row[7]) if row[7] is not None else 0.0,
        "target_order_age_days": int(row[8]) if row[8] is not None else None,
        "prior_refund_count_100d": int(row[9]),
        "policy_id": str(row[10]),
        "policy_name": str(row[11]),
        "condition_id": str(row[12]),
        "max_refunds_100d": int(row[13]),
        "return_window_days": int(row[14]),
        "restriction_action": str(row[15]),
    }


def query_spanner_operational_context_graph(
    user_id: int,
    target_order_id: int,
    catalog_contract: dict[str, Any],
    database: Any = None,
) -> dict[str, Any]:
    """Executes the two-stage ISO GQL OperationalContextGraph traversal."""
    db = database or get_spanner_database()
    gql_query = get_query_templates()["spanner_eligibility_gql"]
    params = {
        "user_id": int(user_id),
        "target_order_id": int(target_order_id),
        "returned_status": str(
            catalog_contract.get("returned_status", "Returned")
        ),
        "rolling_window_days": int(
            catalog_contract.get("rolling_window_days", 100)
        ),
        "standard_tier": str(catalog_contract.get("standard_tier", "STANDARD")),
        "vip_tier": str(catalog_contract.get("vip_tier", "VIP")),
    }
    types = {
        "user_id": param_types.INT64,
        "target_order_id": param_types.INT64,
        "returned_status": param_types.STRING,
        "rolling_window_days": param_types.INT64,
        "standard_tier": param_types.STRING,
        "vip_tier": param_types.STRING,
    }
    with db.snapshot() as snapshot:
        rows = list(
            snapshot.execute_sql(gql_query, params=params, param_types=types)
        )
    if not rows:
        return default_policy_eval_baseline()
    return _parse_gql_row(rows[0])


def commit_spanner_order_refund(
    user_id: int,
    order_id: int,
    trace_id: str,
    catalog_contract: dict[str, Any],
    policy_eval: dict[str, Any],
    database: Any = None,
) -> dict[str, Any]:
    """Re-verifies eligibility under a Spanner RW lock and commits refund."""
    db = database or get_spanner_database()
    templates = get_query_templates()
    gql_query = templates["spanner_eligibility_gql"]
    update_order_sql = templates["spanner_update_order_sql"]
    update_items_sql = templates["spanner_update_order_items_sql"]

    params = {
        "user_id": int(user_id),
        "target_order_id": int(order_id),
        "returned_status": str(
            catalog_contract.get("returned_status", "Returned")
        ),
        "rolling_window_days": int(
            catalog_contract.get("rolling_window_days", 100)
        ),
        "standard_tier": str(catalog_contract.get("standard_tier", "STANDARD")),
        "vip_tier": str(catalog_contract.get("vip_tier", "VIP")),
    }
    types = {
        "user_id": param_types.INT64,
        "target_order_id": param_types.INT64,
        "returned_status": param_types.STRING,
        "rolling_window_days": param_types.INT64,
        "standard_tier": param_types.STRING,
        "vip_tier": param_types.STRING,
    }

    def _tx_unit(transaction: Any) -> dict[str, Any]:
        rows = list(
            transaction.execute_sql(gql_query, params=params, param_types=types)
        )
        live_eval = (
            _parse_gql_row(rows[0]) if rows else default_policy_eval_baseline()
        )
        eval_res, failure_code, term_id = classify_policy_failure(
            live_eval, catalog_contract, order_id
        )
        if eval_res != "PASS":
            policy_eval.update(live_eval)
            policy_eval["evaluation_result"] = "FAIL"
            policy_eval["failure_code"] = failure_code
            policy_eval["catalog_term_id"] = term_id
            reason = format_rejection_reason(
                failure_code, order_id, user_id, policy_eval
            )
            return {
                "action_id": f"ACT-{uuid4().hex[:8]}",
                "eval_id": policy_eval["eval_id"],
                "action_type": "BLOCK_SPANNER_MUTATION",
                "decision_status": "DENIED",
                "rejection_reason": reason,
            }

        transaction.execute_update(
            update_order_sql,
            params={
                "returned_status": params["returned_status"],
                "order_id": int(order_id),
                "user_id": int(user_id),
            },
            param_types={
                "returned_status": param_types.STRING,
                "order_id": param_types.INT64,
                "user_id": param_types.INT64,
            },
        )
        transaction.execute_update(
            update_items_sql,
            params={
                "returned_status": params["returned_status"],
                "trace_id": str(trace_id),
                "order_id": int(order_id),
            },
            param_types={
                "returned_status": param_types.STRING,
                "trace_id": param_types.STRING,
                "order_id": param_types.INT64,
            },
        )
        return {
            "action_id": f"ACT-{uuid4().hex[:8]}",
            "eval_id": policy_eval["eval_id"],
            "action_type": "COMMIT_SPANNER_REFUND",
            "decision_status": "APPROVED",
            "rejection_reason": None,
        }

    return db.run_in_transaction(_tx_unit)


def fetch_storefront_products(database: Any = None) -> list[dict[str, Any]]:
    """Returns thelook_ecommerce products and fulfillment centers for UI 1."""
    db = database or get_spanner_database()
    sql = get_query_templates()["spanner_products_sql"]
    with db.snapshot() as snapshot:
        rows = list(snapshot.execute_sql(sql))
    return [
        {
            "id": int(r[0]),
            "name": str(r[1]),
            "brand": str(r[2]),
            "category": str(r[3]),
            "department": str(r[4]),
            "retail_price": float(r[5]),
            "distribution_center_name": str(r[6]),
            "policy_id": str(r[7]),
        }
        for r in rows
    ]


def fetch_persona_customers(database: Any = None) -> list[dict[str, Any]]:
    """Returns Customer A (1001), Customer B (2048), and Customer C (3072)."""
    db = database or get_spanner_database()
    sql = get_query_templates()["spanner_customers_sql"]
    with db.snapshot() as snapshot:
        rows = list(snapshot.execute_sql(sql))
    return [
        {
            "user_id": int(r[0]),
            "first_name": str(r[1]),
            "last_name": str(r[2]),
            "email": str(r[3]),
            "customer_tier": str(r[4]),
            "prior_refund_count_100d": int(r[5]),
            "max_refunds_100d": int(r[6]),
        }
        for r in rows
    ]


def fetch_customer_orders(
    user_id: int, database: Any = None
) -> list[dict[str, Any]]:
    """Returns orders and nested order_items for a specific customer ID."""
    db = database or get_spanner_database()
    sql = get_query_templates()["spanner_customer_orders_sql"]
    with db.snapshot() as snapshot:
        rows = list(
            snapshot.execute_sql(
                sql,
                params={"user_id": int(user_id)},
                param_types={"user_id": param_types.INT64},
            )
        )
    orders_map: dict[int, dict[str, Any]] = {}
    for row in rows:
        if len(row) != 10:
            continue
        oid = int(row[0])
        if oid not in orders_map:
            orders_map[oid] = {
                "order_id": oid,
                "status": str(row[1]),
                "created_at": str(row[2]) if row[2] is not None else None,
                "delivered_at": str(row[3]) if row[3] is not None else None,
                "returned_at": str(row[4]) if row[4] is not None else None,
                "items": [],
            }
        orders_map[oid]["items"].append(
            {
                "id": int(row[5]),
                "product_name": str(row[6]),
                "sale_price": float(row[7]),
                "status": str(row[8]),
                "refund_trace_id": str(row[9]) if row[9] is not None else None,
            }
        )
    return list(orders_map.values())


def _strip_sql_comments(query: str) -> str:
    """Strips SQL line (--) and block (/* */) comments for guard checks."""
    no_block = re.sub(r"/\*[\s\S]*?\*/", " ", query)
    return re.sub(r"--[^\n]*", " ", no_block).strip()


def validate_readonly_spanner_query(query: str) -> str:
    """Enforces that a workbench Spanner query is a read-only GRAPH/SELECT."""
    cleaned = query.strip()
    uncommented = _strip_sql_comments(cleaned)
    if not uncommented:
        raise ValueError("Query string must not be empty.")
    if not READONLY_SPANNER_PREFIX_RE.match(uncommented):
        raise ValueError(
            "Only read-only GRAPH OperationalContextGraph or SELECT "
            "queries are allowed."
        )
    if FORBIDDEN_DML_DDL_RE.search(uncommented):
        raise ValueError("Mutating DML or DDL statements are forbidden.")
    return cleaned


def execute_readonly_spanner_query(
    query: str, database: Any = None
) -> dict[str, Any]:
    """Executes a read-only guarded ISO GQL or SQL query in Cloud Spanner."""
    cleaned = validate_readonly_spanner_query(query)
    db = database or get_spanner_database()
    started = time.perf_counter()
    with db.snapshot() as snapshot:
        result_set = snapshot.execute_sql(cleaned, timeout=15.0)
        raw_rows = []
        for idx, row in enumerate(result_set):
            if idx >= 500:
                break
            raw_rows.append(list(row))
        fields = [field.name for field in result_set.fields]
    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    rows_out = [
        {
            col: (
                val.isoformat()
                if hasattr(val, "isoformat")
                else val
            )
            for col, val in zip(fields, row)
        }
        for row in raw_rows
    ]
    return {
        "columns": fields,
        "rows": rows_out,
        "latency_ms": latency_ms,
    }
