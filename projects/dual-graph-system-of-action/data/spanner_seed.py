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

"""Idempotent 3-stage Cloud Spanner hydration and demo reset utilities."""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google.cloud import spanner

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent
POLICIES_PATH = DATA_DIR / "policies" / "u2g_policy_triples.json"
SLICE_PATH = DATA_DIR / "thelook_slice.json"

RESET_ORDER_IDS = [90124, 90588, 90910]
_SPANNER_DB_CACHE: dict[tuple[str | None, str, str], Any] = {}


def get_spanner_database() -> Any:
    """Returns a cached Cloud Spanner database handle from environment vars."""
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    )
    instance_id = os.getenv("SPANNER_INSTANCE_ID", "soa-graph-instance")
    database_id = os.getenv("SPANNER_DATABASE_ID", "thelook-soa-db")
    cache_key = (project_id, instance_id, database_id)
    is_real_client = getattr(spanner.Client, "__module__", "").startswith(
        "google.cloud"
    )
    if is_real_client and cache_key in _SPANNER_DB_CACHE:
        return _SPANNER_DB_CACHE[cache_key]
    client = spanner.Client(project=project_id)
    instance = client.instance(instance_id)
    db = instance.database(database_id)
    if is_real_client:
        _SPANNER_DB_CACHE[cache_key] = db
    return db


def _load_json(path: Path) -> dict[str, Any]:
    """Reads and parses a JSON file from disk."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_stage1_policy_rows() -> dict[str, list[tuple[Any, ...]]]:
    """Builds Stage 1 U2G policy, condition, and restriction tuples."""
    triples = _load_json(POLICIES_PATH)
    std_limit = int(os.getenv("MAX_REFUNDS_100D_LIMIT", "10"))
    vip_limit = int(os.getenv("VIP_MAX_REFUNDS_100D_LIMIT", "20"))

    policies_rows = [
        (
            row["policy_id"],
            row["name"],
            row["source_document_uri"],
            row["policy_version"],
            row["status"],
            row["valid_from"],
            row["valid_to"],
        )
        for row in triples["policies"]
    ]

    conditions_rows = []
    for cond in triples["policy_conditions"]:
        tier = cond["applicable_tier"]
        max_refunds = vip_limit if tier == "VIP" else std_limit
        window_days = int(cond["return_window_days"])
        expr = (
            f"prior_refund_count_100d < {max_refunds} "
            f"AND target_order_age_days <= {window_days}"
        )
        conditions_rows.append(
            (
                cond["condition_id"],
                cond["policy_id"],
                tier,
                max_refunds,
                window_days,
                expr,
            )
        )

    restrictions_rows = [
        (
            res["restriction_id"],
            res["policy_id"],
            res["action_code"],
            res["description"],
        )
        for res in triples["policy_restrictions"]
    ]

    return {
        "policies": policies_rows,
        "policy_conditions": conditions_rows,
        "policy_restrictions": restrictions_rows,
    }


def _iso_utc(dt: datetime) -> str:
    """Formats a datetime as an ISO-8601 UTC timestamp string."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_stage2_slice_rows(
    slice_data: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, list[tuple[Any, ...]]]:
    """Builds Stage 2 background catalog and storefront tuples."""
    ref_now = now or datetime.now(timezone.utc)
    user_created_ts = _iso_utc(ref_now - timedelta(days=365))
    inv_created_ts = _iso_utc(ref_now - timedelta(days=25))
    order_created_ts = _iso_utc(ref_now - timedelta(days=20))
    order_shipped_ts = _iso_utc(ref_now - timedelta(days=19))
    order_delivered_ts = _iso_utc(ref_now - timedelta(days=17))

    dc_rows = [
        (dc["id"], dc["name"], dc["latitude"], dc["longitude"])
        for dc in slice_data["distribution_centers"]
    ]
    product_rows = [
        (
            prod["id"],
            prod["cost"],
            prod["category"],
            prod["name"],
            prod["brand"],
            prod["retail_price"],
            prod["department"],
            prod["sku"],
            prod["distribution_center_id"],
            prod["policy_id"],
        )
        for prod in slice_data["products"]
    ]
    user_rows = [
        (
            u["id"],
            u["first_name"],
            u["last_name"],
            u["email"],
            u.get("customer_tier", "STANDARD"),
            u["age"],
            u["gender"],
            u["state"],
            u["street_address"],
            u["postal_code"],
            u["city"],
            u["country"],
            u["latitude"],
            u["longitude"],
            u["traffic_source"],
            user_created_ts,
        )
        for u in slice_data["users"]
    ]
    inv_rows = [
        (
            inv["id"],
            inv["product_id"],
            inv_created_ts,
            order_created_ts,
            inv["cost"],
            inv["product_category"],
            inv["product_name"],
            inv["product_brand"],
            inv["product_retail_price"],
            inv["product_department"],
            inv["product_sku"],
            inv["product_distribution_center_id"],
        )
        for inv in slice_data["inventory_items"]
    ]
    order_rows = [
        (
            o["order_id"],
            o["user_id"],
            o["status"],
            o["gender"],
            order_created_ts,
            o["returned_at"],
            order_shipped_ts,
            order_delivered_ts if o["delivered_at"] else None,
            o["num_of_item"],
        )
        for o in slice_data["orders"]
    ]
    order_item_rows = [
        (
            oi["id"],
            oi["order_id"],
            oi["user_id"],
            oi["product_id"],
            oi["inventory_item_id"],
            oi["status"],
            order_created_ts,
            order_shipped_ts,
            order_delivered_ts if oi["delivered_at"] else None,
            oi["returned_at"],
            oi["sale_price"],
            oi["refund_trace_id"],
        )
        for oi in slice_data["order_items"]
    ]
    return {
        "distribution_centers": dc_rows,
        "products": product_rows,
        "users": user_rows,
        "inventory_items": inv_rows,
        "orders": order_rows,
        "order_items": order_item_rows,
    }


def _build_stage3_demo_rows(
    products_by_id: dict[int, dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, list[tuple[Any, ...]]]:
    """Builds Stage 3 deterministic Customer A, B, and C rows."""
    ref_now = now or datetime.now(timezone.utc)
    demo_users = [
        (
            1001,
            "Alice",
            "Chen",
            "alice.chen@example.com",
            "STANDARD",
            31,
            "F",
            "California",
            "742 Evergreen Terrace",
            "94107",
            "San Francisco",
            "United States",
            37.7749,
            -122.4194,
            "Search",
            _iso_utc(ref_now - timedelta(days=365)),
        ),
        (
            2048,
            "Jordan",
            "Taylor",
            "jordan.taylor@example.com",
            "STANDARD",
            42,
            "M",
            "New York",
            "350 Fifth Avenue",
            "10118",
            "New York",
            "United States",
            40.7484,
            -73.9857,
            "Email",
            _iso_utc(ref_now - timedelta(days=400)),
        ),
        (
            3072,
            "Claire",
            "Vance",
            "claire.vance@example.com",
            "VIP",
            36,
            "F",
            "Texas",
            "600 Congress Ave",
            "78701",
            "Austin",
            "United States",
            30.2672,
            -97.7431,
            "Organic",
            _iso_utc(ref_now - timedelta(days=720)),
        ),
    ]

    product_ids = sorted(products_by_id.keys())
    inv_rows: list[tuple[Any, ...]] = []
    order_rows: list[tuple[Any, ...]] = []
    order_item_rows: list[tuple[Any, ...]] = []

    def add_order_bundle(
        order_id: int,
        user_id: int,
        gender: str,
        product_id: int,
        status: str,
        created_days_ago: int,
        delivered_days_ago: int | None,
        returned_days_ago: int | None,
    ) -> None:
        prod = products_by_id[product_id]
        created_ts = _iso_utc(ref_now - timedelta(days=created_days_ago))
        shipped_ts = _iso_utc(
            ref_now - timedelta(days=max(created_days_ago - 1, 1))
        )
        delivered_ts = (
            _iso_utc(ref_now - timedelta(days=delivered_days_ago))
            if delivered_days_ago is not None
            else None
        )
        returned_ts = (
            _iso_utc(ref_now - timedelta(days=returned_days_ago))
            if returned_days_ago is not None
            else None
        )

        inv_rows.append(
            (
                order_id,
                product_id,
                created_ts,
                created_ts,
                prod["cost"],
                prod["category"],
                prod["name"],
                prod["brand"],
                prod["retail_price"],
                prod["department"],
                prod["sku"],
                prod["distribution_center_id"],
            )
        )
        order_rows.append(
            (
                order_id,
                user_id,
                status,
                gender,
                created_ts,
                returned_ts,
                shipped_ts,
                delivered_ts,
                1,
            )
        )
        order_item_rows.append(
            (
                order_id,
                order_id,
                user_id,
                product_id,
                order_id,
                status,
                created_ts,
                shipped_ts,
                delivered_ts,
                returned_ts,
                prod["retail_price"],
                None,
            )
        )

    # Customer A (1001, STANDARD): 2 historical returns + 90124, 90125, 90126
    add_order_bundle(80001, 1001, "F", 502, "Returned", 50, 48, 45)
    add_order_bundle(80002, 1001, "F", 504, "Returned", 30, 28, 25)
    add_order_bundle(90124, 1001, "F", 501, "Complete", 17, 14, None)
    add_order_bundle(90125, 1001, "F", 505, "Complete", 49, 45, None)
    add_order_bundle(90126, 1001, "F", 508, "Shipped", 3, None, None)

    # Customer B (2048, STANDARD): 12 historical returns (81001..81012) + 90588
    for idx in range(12):
        oid = 81001 + idx
        ret_days = 90 - (idx * 6)
        prod_id = product_ids[idx % len(product_ids)]
        add_order_bundle(
            oid,
            2048,
            "M",
            prod_id,
            "Returned",
            ret_days + 5,
            ret_days + 2,
            ret_days,
        )
    add_order_bundle(90588, 2048, "M", 503, "Complete", 13, 10, None)

    # Customer C (3072, VIP): 12 historical returns (82001..82012) + 90910
    for idx in range(12):
        oid = 82001 + idx
        ret_days = 90 - (idx * 6)
        prod_id = product_ids[idx % len(product_ids)]
        add_order_bundle(
            oid,
            3072,
            "F",
            prod_id,
            "Returned",
            ret_days + 5,
            ret_days + 2,
            ret_days,
        )
    add_order_bundle(90910, 3072, "F", 507, "Complete", 10, 7, None)

    return {
        "users": demo_users,
        "inventory_items": inv_rows,
        "orders": order_rows,
        "order_items": order_item_rows,
    }


def _apply_hydration_batches(
    database: Any,
    now: datetime | None = None,
) -> None:
    """Writes Stage 1, Stage 2, and Stage 3 rows in foreign-key-safe order."""
    ref_now = now or datetime.now(timezone.utc)
    slice_data = _load_json(SLICE_PATH)
    products_by_id = {prod["id"]: prod for prod in slice_data["products"]}

    stage1 = _build_stage1_policy_rows()
    stage2 = _build_stage2_slice_rows(slice_data, now=ref_now)
    stage3 = _build_stage3_demo_rows(products_by_id, now=ref_now)

    with database.batch() as batch:
        batch.insert_or_update(
            table="policies",
            columns=(
                "policy_id",
                "name",
                "source_document_uri",
                "policy_version",
                "status",
                "valid_from",
                "valid_to",
            ),
            values=stage1["policies"],
        )
        batch.insert_or_update(
            table="policy_conditions",
            columns=(
                "condition_id",
                "policy_id",
                "applicable_tier",
                "max_refunds_100d",
                "return_window_days",
                "threshold_expression",
            ),
            values=stage1["policy_conditions"],
        )
        batch.insert_or_update(
            table="policy_restrictions",
            columns=(
                "restriction_id",
                "policy_id",
                "action_code",
                "description",
            ),
            values=stage1["policy_restrictions"],
        )
        batch.insert_or_update(
            table="distribution_centers",
            columns=("id", "name", "latitude", "longitude"),
            values=stage2["distribution_centers"],
        )
        batch.insert_or_update(
            table="products",
            columns=(
                "id",
                "cost",
                "category",
                "name",
                "brand",
                "retail_price",
                "department",
                "sku",
                "distribution_center_id",
                "policy_id",
            ),
            values=stage2["products"],
        )
        batch.insert_or_update(
            table="users",
            columns=(
                "id",
                "first_name",
                "last_name",
                "email",
                "customer_tier",
                "age",
                "gender",
                "state",
                "street_address",
                "postal_code",
                "city",
                "country",
                "latitude",
                "longitude",
                "traffic_source",
                "created_at",
            ),
            values=stage2["users"] + stage3["users"],
        )

    with database.batch() as batch:
        batch.insert_or_update(
            table="inventory_items",
            columns=(
                "id",
                "product_id",
                "created_at",
                "sold_at",
                "cost",
                "product_category",
                "product_name",
                "product_brand",
                "product_retail_price",
                "product_department",
                "product_sku",
                "product_distribution_center_id",
            ),
            values=stage2["inventory_items"] + stage3["inventory_items"],
        )
        batch.insert_or_update(
            table="orders",
            columns=(
                "order_id",
                "user_id",
                "status",
                "gender",
                "created_at",
                "returned_at",
                "shipped_at",
                "delivered_at",
                "num_of_item",
            ),
            values=stage2["orders"] + stage3["orders"],
        )
        batch.insert_or_update(
            table="order_items",
            columns=(
                "id",
                "order_id",
                "user_id",
                "product_id",
                "inventory_item_id",
                "status",
                "created_at",
                "shipped_at",
                "delivered_at",
                "returned_at",
                "sale_price",
                "refund_trace_id",
            ),
            values=stage2["order_items"] + stage3["order_items"],
        )


def seed_spanner_if_empty(database: Any = None) -> bool:
    """Seeds Cloud Spanner if empty, or refreshes drifted demo timestamps."""
    db = database or get_spanner_database()
    with db.snapshot() as snapshot:
        results = list(
            snapshot.execute_sql(
                "SELECT order_id, "
                "TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), delivered_at, DAY) "
                "FROM orders WHERE order_id = 90124"
            )
        )
        if results:
            row = results[0]
            age_days = (
                int(row[1]) if len(row) > 1 and row[1] is not None else 14
            )
            if age_days <= 15:
                logger.info(
                    "Cloud Spanner already seeded "
                    "(order_id=90124 age=%d days).",
                    age_days,
                )
                return False
            logger.info(
                "Cloud Spanner demo timestamps drifted (order_id=90124 age=%d "
                "days > 15); refreshing relative timestamps.",
                age_days,
            )

    logger.info("Seeding Cloud Spanner in 3 foreign-key-safe stages.")
    _apply_hydration_batches(db)
    return True


def reset_demo_orders(
    database: Any = None,
    now: datetime | None = None,
) -> list[int]:
    """Resets all demo orders and refreshes relative UTC timestamps."""
    db = database or get_spanner_database()
    _apply_hydration_batches(db, now=now)
    logger.info(
        "Reset demo orders %s to Complete status with fresh UTC timestamps.",
        RESET_ORDER_IDS,
    )
    return list(RESET_ORDER_IDS)
