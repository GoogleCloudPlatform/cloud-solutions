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

"""Unit tests for ADK 2.0 RefundSystemOfActionWorkflow and database clients."""

import os
import unittest
from typing import Any
from unittest.mock import patch

from app.agent.bq_lineage import (
    clear_memory_trace_store,
    ensure_bigquery_schema,
    list_recent_traces,
)
from app.agent.catalog_client import (
    clear_catalog_cache,
    fetch_knowledge_catalog_aspect,
)
from app.agent.workflow import (
    Context,
    _sync_candidate_orders_with_response,
    _try_gemini_intent_extraction,
    _try_gemini_response_generation,
    clear_pending_confirmations,
    intent_agent,
    refund_system_of_action,
    response_agent,
    run_refund_workflow,
)
from data.spanner_seed import reset_demo_orders, seed_spanner_if_empty
from google.adk import Agent as AdkAgent
from google.adk import Workflow as AdkWorkflow
from google.genai import errors as genai_errors


class FakeSpannerSnapshot:
    """Mock Cloud Spanner read-only snapshot context manager."""

    def __init__(self, rows_to_return: list[tuple[Any, ...]]) -> None:
        """Initializes snapshot with canned rows."""
        self._rows = rows_to_return

    def __enter__(self) -> "FakeSpannerSnapshot":
        """Enters snapshot context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exits snapshot context."""

    def execute_sql(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        param_types: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> list[tuple[Any, ...]]:
        """Returns canned GQL or SQL rows."""
        _ = (sql, params, param_types, timeout)
        return list(self._rows)


class FakeSpannerTransaction:
    """Mock Cloud Spanner read-write transaction object."""

    def __init__(self, rows_to_return: list[tuple[Any, ...]]) -> None:
        """Initializes transaction with canned rows."""
        self._rows = rows_to_return
        self.updates: list[str] = []

    def execute_sql(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        param_types: dict[str, Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        """Returns canned rows inside the transaction lock."""
        _ = (sql, params, param_types)
        return list(self._rows)

    def execute_update(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        param_types: dict[str, Any] | None = None,
    ) -> int:
        """Records DML update execution."""
        _ = (params, param_types)
        self.updates.append(sql)
        return 1


class FakeSpannerDatabase:
    """Mock Cloud Spanner database supporting snapshots and RW transactions."""

    def __init__(
        self,
        snapshot_rows: list[tuple[Any, ...]],
        tx_rows: list[tuple[Any, ...]] | None = None,
    ) -> None:
        """Initializes fake Spanner database."""
        self.snapshot_rows = snapshot_rows
        self.tx_rows = tx_rows if tx_rows is not None else snapshot_rows
        self.last_tx: FakeSpannerTransaction | None = None
        self.ddl_updated = False

    def snapshot(self) -> FakeSpannerSnapshot:
        """Creates a fake read-only snapshot."""
        return FakeSpannerSnapshot(self.snapshot_rows)

    def run_in_transaction(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Runs a callable inside a fake read-write transaction."""
        self.last_tx = FakeSpannerTransaction(self.tx_rows)
        return func(self.last_tx, *args, **kwargs)


class FakeBigQueryClient:
    """Mock BigQuery client recording streamed lineage rows."""

    def __init__(self, fail_property_graph: bool = False) -> None:
        """Initializes fake BigQuery client."""
        self.inserted: dict[str, list[dict[str, Any]]] = {}
        self.fail_property_graph = fail_property_graph

    def insert_rows_json(
        self, table_id: str, rows: list[dict[str, Any]]
    ) -> list[Any]:
        """Records streamed JSON rows per table."""
        self.inserted.setdefault(table_id, []).extend(rows)
        return []

    def query(self, sql: str, job_config: Any = None) -> Any:
        """Simulates BigQuery DDL and query execution."""
        _ = job_config
        if (
            self.fail_property_graph
            and "CREATE OR REPLACE PROPERTY GRAPH" in sql
        ):
            raise ValueError("PROPERTY GRAPH requires Enterprise reservation")

        class _Job:
            def result(self, timeout: float | None = None) -> list[Any]:
                _ = timeout
                return []

        return _Job()


def _make_gql_row(
    user_id: int = 1001,
    email: str = "alice.chen@example.com",
    tier: str = "STANDARD",
    order_id: int = 90124,
    status: str = "Complete",
    age_days: int | None = 14,
    prior_refunds: int = 2,
    cond_id: str = "COND-REFUND-STD-100D-30D",
    max_refunds: int = 10,
) -> tuple[Any, ...]:
    """Constructs a 16-column OperationalContextGraph GQL result tuple."""
    return (
        user_id,
        email,
        tier,
        order_id,
        status,
        "Classic Merino Crewneck Sweater",
        "Chicago IL",
        89.50,
        age_days,
        prior_refunds,
        "POL-REFUND-STD-V1",
        "Tiered Standard and VIP Refund Policy",
        cond_id,
        max_refunds,
        30,
        "DENY_AUTONOMOUS_REFUND",
    )


class RefundWorkflowTest(unittest.TestCase):
    """Tests all 3 customer personas, 6 failure codes, and TOCTOU safety."""

    def setUp(self) -> None:
        """Resets in-memory caches before each test."""
        os.environ["DISABLE_VERTEX_LLM"] = "true"
        clear_catalog_cache()
        clear_memory_trace_store()
        clear_pending_confirmations()

    def test_activity1_customer_a_standard_approved(self) -> None:
        """Verifies Customer A (1001, STANDARD, 2 < 10 returns) is APPROVED."""
        self.assertIsInstance(refund_system_of_action.adk_workflow, AdkWorkflow)
        self.assertIsInstance(intent_agent.adk_agent, AdkAgent)
        self.assertIsInstance(response_agent.adk_agent, AdkAgent)
        db = FakeSpannerDatabase([_make_gql_row()])
        bq = FakeBigQueryClient()
        res = run_refund_workflow(
            user_id=1001,
            message="I would like to request a refund for order ORD-90124.",
            trace_id="trace-1111aaaa",
            spanner_db=db,
            bq_client=bq,
        )
        self.assertEqual(res["decision_status"], "APPROVED")
        self.assertIsNone(res["failure_code"])
        self.assertEqual(
            res["policy_eval"]["catalog_term_id"], "rolling-100d-refund-count"
        )
        self.assertEqual(
            res["policy_eval"]["condition_id"], "COND-REFUND-STD-100D-30D"
        )
        self.assertIsNotNone(db.last_tx)
        self.assertEqual(len(db.last_tx.updates), 2)

        traces = list_recent_traces()
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["trace_id"], "trace-1111aaaa")

    def test_activity2_customer_b_standard_denied_limit(self) -> None:
        """Verifies Customer B (2048, STANDARD, 12 >= 10 returns) is DENIED."""
        row = _make_gql_row(
            user_id=2048,
            email="jordan.taylor@example.com",
            tier="STANDARD",
            order_id=90588,
            age_days=10,
            prior_refunds=12,
            cond_id="COND-REFUND-STD-100D-30D",
            max_refunds=10,
        )
        db = FakeSpannerDatabase([row])
        bq = FakeBigQueryClient()
        res = run_refund_workflow(
            user_id=2048,
            message="Please refund my order ORD-90588.",
            trace_id="trace-2222bbbb",
            spanner_db=db,
            bq_client=bq,
        )
        self.assertEqual(res["decision_status"], "DENIED")
        self.assertEqual(res["failure_code"], "MAX_REFUNDS_EXCEEDED")
        self.assertEqual(
            res["action_outcome"]["action_type"], "BLOCK_SPANNER_MUTATION"
        )
        self.assertIsNone(db.last_tx)

    def test_activity3_customer_c_vip_approved_above_std_limit(self) -> None:
        """Verifies Customer C (3072, VIP, 12 < 20 returns) is APPROVED."""
        row = _make_gql_row(
            user_id=3072,
            email="claire.vance@example.com",
            tier="VIP",
            order_id=90910,
            age_days=7,
            prior_refunds=12,
            cond_id="COND-REFUND-VIP-100D-30D",
            max_refunds=20,
        )
        db = FakeSpannerDatabase([row])
        bq = FakeBigQueryClient()
        res = run_refund_workflow(
            user_id=3072,
            message="I would like to refund my order ORD-90910.",
            trace_id="trace-3333cccc",
            spanner_db=db,
            bq_client=bq,
        )
        self.assertEqual(res["decision_status"], "APPROVED")
        self.assertIsNone(res["failure_code"])
        self.assertEqual(res["policy_eval"]["customer_tier"], "VIP")
        self.assertEqual(
            res["policy_eval"]["condition_id"], "COND-REFUND-VIP-100D-30D"
        )
        self.assertEqual(
            res["policy_eval"]["catalog_term_id"], "customer-loyalty-tier"
        )
        self.assertEqual(res["policy_eval"]["max_refunds_100d"], 20)

    def test_failure_priorities_and_toctou_abort(self) -> None:
        """Tests missing order, unauthorized, expired, shipped, and TOCTOU."""
        db_empty = FakeSpannerDatabase([])
        res_missing = run_refund_workflow(
            user_id=1001,
            message="I want a refund please!",
            spanner_db=db_empty,
        )
        self.assertEqual(res_missing["failure_code"], "MISSING_ORDER_ID")

        res_unauth = run_refund_workflow(
            user_id=2048,
            message="Refund ORD-90124",
            spanner_db=db_empty,
        )
        self.assertEqual(
            res_unauth["failure_code"], "ORDER_NOT_FOUND_OR_UNAUTHORIZED"
        )

        db_expired = FakeSpannerDatabase(
            [_make_gql_row(order_id=90125, age_days=45)]
        )
        res_exp = run_refund_workflow(
            user_id=1001,
            message="Refund ORD-90125",
            spanner_db=db_expired,
        )
        self.assertEqual(res_exp["failure_code"], "RETURN_WINDOW_EXPIRED")
        self.assertEqual(
            res_exp["policy_eval"]["catalog_term_id"], "order-age-days"
        )

        db_shipped = FakeSpannerDatabase(
            [_make_gql_row(order_id=90126, status="Shipped", age_days=None)]
        )
        res_ship = run_refund_workflow(
            user_id=1001,
            message="Refund ORD-90126",
            spanner_db=db_shipped,
        )
        self.assertEqual(res_ship["failure_code"], "ORDER_NOT_DELIVERED")

        db_toctou = FakeSpannerDatabase(
            snapshot_rows=[_make_gql_row(order_id=90124, status="Complete")],
            tx_rows=[_make_gql_row(order_id=90124, status="Returned")],
        )
        res_toctou = run_refund_workflow(
            user_id=1001,
            message="Refund ORD-90124",
            spanner_db=db_toctou,
        )
        self.assertEqual(res_toctou["decision_status"], "DENIED")
        self.assertEqual(res_toctou["failure_code"], "ALREADY_RETURNED")
        self.assertEqual(
            res_toctou["policy_eval"]["evaluation_result"], "FAIL"
        )

    def test_bq_schema_fallback_and_catalog_aspect(self) -> None:
        """Verifies sql_fallback mode when PROPERTY GRAPH DDL is unsupported."""
        bq_client = FakeBigQueryClient(fail_property_graph=True)
        tables_ok, mode = ensure_bigquery_schema(bq_client=bq_client)
        self.assertTrue(tables_ok)
        self.assertEqual(mode, "sql_fallback")

        contract = fetch_knowledge_catalog_aspect()
        self.assertEqual(contract["tier_term_id"], "customer-loyalty-tier")
        self.assertEqual(contract["vip_tier"], "VIP")

        clear_catalog_cache()

        class _FakeTerm:
            def __init__(self, name: str) -> None:
                self.name = name

        class _FakeGlossary:
            name = (
                "projects/p/locations/global/glossaries/soa-business-glossary"
            )

        class _FakeDataplexClient:
            def get_glossary(self, name: str, timeout: float = 5.0) -> Any:
                _ = (name, timeout)
                return _FakeGlossary()

            def list_glossary_terms(
                self, parent: str, timeout: float = 5.0
            ) -> list[Any]:
                _ = (parent, timeout)
                return [
                    _FakeTerm(f"{parent}/terms/rolling-100d-refund-count"),
                    _FakeTerm(f"{parent}/terms/order-age-days"),
                    _FakeTerm(f"{parent}/terms/customer-loyalty-tier"),
                ]

        live_contract = fetch_knowledge_catalog_aspect(
            dataplex_client=_FakeDataplexClient()
        )
        self.assertEqual(
            live_contract["catalog_term_id"], "rolling-100d-refund-count"
        )
        self.assertEqual(
            live_contract["secondary_term_id"], "order-age-days"
        )
        self.assertEqual(
            live_contract["tier_term_id"], "customer-loyalty-tier"
        )
        clear_catalog_cache()

    def test_spanner_seed_and_reset_helpers(self) -> None:
        """Verifies idempotent Spanner seeding and demo order reset."""

        class _Batch:
            def __enter__(self) -> "_Batch":
                return self

            def __exit__(self, *args: Any) -> None:
                pass

            def insert_or_update(
                self, table: str, columns: list[str], values: list[Any]
            ) -> None:
                _ = (table, columns, values)

        class _SeedDB:
            """Mock database for Spanner hydration and reset tests."""

            def __init__(
                self, snapshot_rows: list[tuple[Any, ...]] | None = None
            ) -> None:
                self.tx_calls = 0
                self.snapshot_rows = snapshot_rows or []
                self.tables_written: list[str] = []

            def snapshot(self) -> FakeSpannerSnapshot:
                return FakeSpannerSnapshot(self.snapshot_rows)

            def update_ddl(self, ddl_statements: list[str]) -> Any:
                _ = ddl_statements

                class _Op:
                    def result(self, timeout: float = 0) -> None:
                        _ = timeout

                return _Op()

            def batch(self) -> Any:
                parent = self

                class _RecordingBatch(_Batch):
                    def insert_or_update(
                        self,
                        table: str,
                        columns: list[str],
                        values: list[Any],
                    ) -> None:
                        _ = (columns, values)
                        parent.tables_written.append(table)

                return _RecordingBatch()

            def run_in_transaction(self, fn: Any) -> Any:
                self.tx_calls += 1
                return fn(FakeSpannerTransaction([]))

        seed_db = _SeedDB()
        self.assertTrue(seed_spanner_if_empty(database=seed_db))
        self.assertIn("orders", seed_db.tables_written)

        fresh_db = _SeedDB(snapshot_rows=[(90124, 14)])
        self.assertFalse(seed_spanner_if_empty(database=fresh_db))
        self.assertEqual(fresh_db.tables_written, [])

        drifted_db = _SeedDB(snapshot_rows=[(90124, 22)])
        self.assertTrue(seed_spanner_if_empty(database=drifted_db))
        self.assertIn("orders", drifted_db.tables_written)

        reset_ids = reset_demo_orders(database=seed_db)
        self.assertEqual(reset_ids, [90124, 90588, 90910])

    def test_order_inference_and_clarification(self) -> None:
        """Verifies 'last order', product keyword, and clarify fallback."""
        order_rows = [
            (
                90126,
                "Shipped",
                "2026-10-17T00:00:00Z",
                None,
                None,
                90126,
                "Cashmere Ribbed Winter Beanie",
                58.0,
                "Shipped",
                None,
            ),
            (
                90124,
                "Complete",
                "2026-10-03T00:00:00Z",
                "2026-10-06T00:00:00Z",
                None,
                90124,
                "Alpine Gore-Tex Waterproof Shell Jacket",
                129.0,
                "Complete",
                None,
            ),
            (
                90125,
                "Complete",
                "2026-09-01T00:00:00Z",
                "2026-09-05T00:00:00Z",
                None,
                90125,
                "Polarized Aviator Titanium Sunglasses",
                165.0,
                "Complete",
                None,
            ),
        ]

        class _RoutingSnap:
            """Mock snapshot routing customer orders vs GQL queries."""

            def __enter__(self) -> "_RoutingSnap":
                return self

            def __exit__(self, *args: Any) -> None:
                pass

            def execute_sql(
                self, sql: str, **kwargs: Any
            ) -> list[tuple[Any, ...]]:
                _ = kwargs
                if "FROM orders AS o" in sql:
                    return list(order_rows)
                return [_make_gql_row(order_id=90124, status="Complete")]

        class _RoutingDB(FakeSpannerDatabase):
            """Mock database returning _RoutingSnap snapshots."""

            def snapshot(self) -> Any:
                return _RoutingSnap()

        db = _RoutingDB([_make_gql_row(order_id=90124, status="Complete")])
        res_last = run_refund_workflow(
            user_id=1001,
            message="Can I refund my last order?",
            spanner_db=db,
        )
        self.assertEqual(res_last["order_id"], 90124)
        self.assertEqual(res_last["resolution_mode"], "inferred")
        self.assertEqual(res_last["decision_status"], "APPROVED")
        self.assertIn("Inferred Order: ORD-90124", res_last["reply"])

        res_prod = run_refund_workflow(
            user_id=1001,
            message="Please refund my waterproof jacket.",
            spanner_db=db,
        )
        self.assertEqual(res_prod["order_id"], 90124)
        self.assertEqual(res_prod["resolution_mode"], "inferred")
        self.assertEqual(res_prod["decision_status"], "APPROVED")

        res_clarify = run_refund_workflow(
            user_id=1001,
            message="I want a refund please!",
            spanner_db=db,
        )
        self.assertIsNone(res_clarify["order_id"])
        self.assertEqual(res_clarify["resolution_mode"], "clarify")
        self.assertIsNone(res_clarify["unmatched_product"])
        self.assertEqual(res_clarify["failure_code"], "MISSING_ORDER_ID")
        self.assertEqual(len(res_clarify["candidate_orders"]), 3)
        self.assertIn(
            "Which order would you like to refund?", res_clarify["reply"]
        )
        self.assertIn("ORD-90124", res_clarify["reply"])

        res_unpurchased = run_refund_workflow(
            user_id=1001,
            message="I would like to refund Organic Supima Cotton Shirt order.",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertIsNone(res_unpurchased["order_id"])
        self.assertEqual(res_unpurchased["resolution_mode"], "clarify")
        self.assertEqual(
            res_unpurchased["unmatched_product"],
            "Organic Supima Cotton Shirt",
        )
        self.assertEqual(
            res_unpurchased["decision_status"], "PENDING_CONFIRMATION"
        )
        self.assertIn(
            "We could not find an order for 'Organic Supima Cotton Shirt'",
            res_unpurchased["reply"],
        )

        res_unpurchased_ko = run_refund_workflow(
            user_id=1001,
            message="셔츠 환불해주세요.",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertIsNone(res_unpurchased_ko["order_id"])
        self.assertEqual(
            res_unpurchased_ko["unmatched_product"],
            "Organic Supima Cotton Oxford Shirt",
        )
        self.assertIn(
            "구매 내역에서 'Organic Supima Cotton Oxford Shirt'",
            res_unpurchased_ko["reply"],
        )

        db_confirm = _RoutingDB(
            [_make_gql_row(order_id=90124, status="Complete")]
        )
        res_turn1 = run_refund_workflow(
            user_id=1001,
            message="Can I refund my last order?",
            spanner_db=db_confirm,
            require_confirmation=True,
        )
        self.assertEqual(res_turn1["order_id"], 90124)
        self.assertEqual(
            res_turn1["decision_status"], "PENDING_CONFIRMATION"
        )
        self.assertIsNone(db_confirm.last_tx)
        self.assertIsNotNone(res_turn1["pending_confirmation"])

        res_turn2 = run_refund_workflow(
            user_id=1001,
            message="Yes, please proceed with the refund.",
            spanner_db=db_confirm,
            require_confirmation=True,
        )
        self.assertEqual(res_turn2["order_id"], 90124)
        self.assertEqual(res_turn2["resolution_mode"], "confirmed")
        self.assertEqual(res_turn2["decision_status"], "APPROVED")
        self.assertIsNotNone(db_confirm.last_tx)
        self.assertEqual(len(db_confirm.last_tx.updates), 2)

        run_refund_workflow(
            user_id=1001,
            message="Refund ORD-90124",
            spanner_db=db_confirm,
            require_confirmation=True,
        )
        res_decline = run_refund_workflow(
            user_id=1001,
            message="No, wrong order.",
            spanner_db=db_confirm,
            require_confirmation=True,
        )
        self.assertIsNone(res_decline["order_id"])
        self.assertEqual(
            res_decline["decision_status"], "PENDING_CONFIRMATION"
        )
        self.assertEqual(res_decline["failure_code"], "MISSING_ORDER_ID")
        self.assertEqual(len(res_decline["candidate_orders"]), 3)

        res_no_refund = run_refund_workflow(
            user_id=1001,
            message="No I don't to refund",
            spanner_db=db_confirm,
            require_confirmation=True,
        )
        self.assertIsNone(res_no_refund["order_id"])
        self.assertEqual(res_no_refund["resolution_mode"], "cancelled")
        self.assertEqual(
            res_no_refund["decision_status"], "PENDING_CONFIRMATION"
        )
        self.assertIsNone(res_no_refund["failure_code"])
        self.assertIn(
            "no refund has been requested", res_no_refund["reply"]
        )

        fail_row = _make_gql_row(
            user_id=2048,
            email="jordan.taylor@example.com",
            tier="STANDARD",
            order_id=90588,
            age_days=10,
            prior_refunds=12,
            cond_id="COND-REFUND-STD-100D-30D",
            max_refunds=10,
        )
        db_fail_confirm = FakeSpannerDatabase([fail_row])
        res_fail_t1 = run_refund_workflow(
            user_id=2048,
            message="Refund ORD-90588",
            spanner_db=db_fail_confirm,
            require_confirmation=True,
        )
        self.assertEqual(res_fail_t1["order_id"], 90588)
        self.assertEqual(
            res_fail_t1["decision_status"], "PENDING_CONFIRMATION"
        )
        self.assertIsNotNone(res_fail_t1["pending_confirmation"])

        res_fail_t2 = run_refund_workflow(
            user_id=2048,
            message="Yes",
            spanner_db=db_fail_confirm,
            require_confirmation=True,
        )
        self.assertEqual(res_fail_t2["order_id"], 90588)
        self.assertEqual(res_fail_t2["resolution_mode"], "confirmed")
        self.assertEqual(res_fail_t2["decision_status"], "DENIED")
        self.assertEqual(
            res_fail_t2["failure_code"], "MAX_REFUNDS_EXCEEDED"
        )
        self.assertIsNone(db_fail_confirm.last_tx)

        res_list = run_refund_workflow(
            user_id=2048,
            message="Show me the list of last 3 orders",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertIsNone(res_list["order_id"])
        self.assertEqual(res_list["resolution_mode"], "list_orders")
        self.assertEqual(res_list["decision_status"], "ORDER_LIST")
        self.assertIsNone(res_list["failure_code"])
        self.assertEqual(len(res_list["candidate_orders"]), 3)
        self.assertIn("Here are your last 3 orders", res_list["reply"])

        res_oldest = run_refund_workflow(
            user_id=2048,
            message="What is oldest order from the list?",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertEqual(res_oldest["order_id"], 90125)
        self.assertEqual(res_oldest["resolution_mode"], "order_info")
        self.assertEqual(res_oldest["decision_status"], "ORDER_INFO")
        self.assertIn("ORD-90125", res_oldest["reply"])
        self.assertIn("Ordered: 2026-09-01", res_oldest["reply"])

        res_cheapest = run_refund_workflow(
            user_id=2048,
            message="What is the cheapest order from the list?",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertEqual(res_cheapest["order_id"], 90126)
        self.assertEqual(res_cheapest["resolution_mode"], "order_info")
        self.assertEqual(res_cheapest["decision_status"], "ORDER_INFO")
        self.assertIn("ORD-90126", res_cheapest["reply"])

        res_expensive = run_refund_workflow(
            user_id=2048,
            message="What is most expansive one",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertEqual(res_expensive["order_id"], 90125)
        self.assertEqual(res_expensive["resolution_mode"], "order_info")
        self.assertEqual(res_expensive["decision_status"], "ORDER_INFO")
        self.assertEqual(
            [c["order_id"] for c in res_expensive["candidate_orders"]],
            [90125],
        )

        res_refund_this = run_refund_workflow(
            user_id=2048,
            message="I want to refund this order",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertEqual(res_refund_this["order_id"], 90125)
        self.assertEqual(res_refund_this["resolution_mode"], "inferred")
        self.assertEqual(
            res_refund_this["decision_status"], "PENDING_CONFIRMATION"
        )
        self.assertIsNotNone(res_refund_this["pending_confirmation"])
        self.assertEqual(
            res_refund_this["pending_confirmation"]["order_id"], 90125
        )

        res_ko_exp = run_refund_workflow(
            user_id=2048,
            message="가장 비싼 주문은 무엇입니까?",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertEqual(res_ko_exp["order_id"], 90125)
        self.assertEqual(res_ko_exp["decision_status"], "ORDER_INFO")

        res_ko_followup = run_refund_workflow(
            user_id=2048,
            message="환불을 요청 드립니다.",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertEqual(res_ko_followup["order_id"], 90125)
        self.assertEqual(res_ko_followup["resolution_mode"], "inferred")
        self.assertEqual(
            res_ko_followup["decision_status"], "PENDING_CONFIRMATION"
        )
        self.assertIsNotNone(res_ko_followup["pending_confirmation"])
        self.assertEqual(
            res_ko_followup["pending_confirmation"]["order_id"], 90125
        )

        res_ko_prod = run_refund_workflow(
            user_id=2048,
            message="선글라스 환불해주세요.",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertEqual(res_ko_prod["order_id"], 90125)
        self.assertEqual(
            res_ko_prod["decision_status"], "PENDING_CONFIRMATION"
        )

        res_order_info = run_refund_workflow(
            user_id=2048,
            message="What is the status of ORD-90124?",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertEqual(res_order_info["order_id"], 90124)
        self.assertEqual(res_order_info["resolution_mode"], "order_info")
        self.assertEqual(res_order_info["decision_status"], "ORDER_INFO")
        self.assertIsNone(res_order_info["failure_code"])
        self.assertIsNone(res_order_info["pending_confirmation"])
        self.assertIn(
            "currently has status 'Complete'", res_order_info["reply"]
        )
        self.assertIn("Please refund ORD-90124", res_order_info["reply"])

        res_completed = run_refund_workflow(
            user_id=2048,
            message="What are my completed orders?",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertIsNone(res_completed["order_id"])
        self.assertEqual(
            [c["order_id"] for c in res_completed["candidate_orders"]],
            [90124, 90125],
        )

        sync_ctx = Context(
            {
                "user_id": 2048,
                "action_outcome": {"decision_status": "POLICY_INFO"},
                "candidate_orders": [
                    {
                        "order_id": 90126,
                        "product_name": "Cashmere Ribbed Winter Beanie",
                        "sale_price": 58.0,
                        "status": "Shipped",
                    },
                    {
                        "order_id": 90124,
                        "product_name": (
                            "Alpine Gore-Tex Waterproof Shell Jacket"
                        ),
                        "sale_price": 129.0,
                        "status": "Complete",
                    },
                    {
                        "order_id": 90125,
                        "product_name": (
                            "Polarized Aviator Titanium Sunglasses"
                        ),
                        "sale_price": 165.0,
                        "status": "Complete",
                    },
                ],
                "final_response": (
                    "Your recent completed orders include ORD-90124 and "
                    "ORD-90125. Both orders are in 'Complete' status."
                ),
            }
        )
        _sync_candidate_orders_with_response(sync_ctx)
        self.assertEqual(
            [c["order_id"] for c in sync_ctx.state["candidate_orders"]],
            [90124, 90125],
        )

        order_rows[:] = order_rows[:1]
        res_policy_info = run_refund_workflow(
            user_id=2048,
            message="What is your return policy?",
            spanner_db=db,
            require_confirmation=True,
        )
        self.assertIsNone(res_policy_info["order_id"])
        self.assertEqual(res_policy_info["resolution_mode"], "policy_info")
        self.assertEqual(res_policy_info["decision_status"], "POLICY_INFO")
        self.assertIsNone(res_policy_info["failure_code"])
        self.assertEqual(len(res_policy_info["candidate_orders"]), 1)
        self.assertIn("POL-REFUND-STD-V1", res_policy_info["reply"])

        with patch.dict(
            os.environ,
            {
                "DISABLE_VERTEX_LLM": "false",
                "GOOGLE_CLOUD_PROJECT": "test-project",
            },
        ), patch("app.agent.workflow.genai.Client") as mock_genai_cls:
            order_rows.extend(
                [
                    (
                        90124,
                        "Complete",
                        "2026-10-03T00:00:00Z",
                        "2026-10-06T00:00:00Z",
                        None,
                        90124,
                        "Alpine Gore-Tex Waterproof Shell Jacket",
                        129.0,
                        "Complete",
                        None,
                    ),
                    (
                        90125,
                        "Complete",
                        "2026-09-01T00:00:00Z",
                        "2026-09-05T00:00:00Z",
                        None,
                        90125,
                        "Polarized Aviator Titanium Sunglasses",
                        165.0,
                        "Complete",
                        None,
                    ),
                ]
            )
            mock_gen = mock_genai_cls.return_value.models.generate_content

            class _FakeResp:
                """Mock Gemini response payload."""

                def __init__(self, text: str) -> None:
                    self.text = text

            mock_gen.side_effect = [
                _FakeResp(
                    '{"intent": "ORDER_INFO", "order_id": 90125, '
                    '"list_limit": null, "status_filter": null, '
                    '"unmatched_product": null, '
                    '"refund_reason": "Most expensive order inquiry"}'
                ),
                _FakeResp("주문 ORD-90125 상세 안내입니다."),
                _FakeResp(
                    '{"intent": "REFUND_REQUEST", "order_id": 90125, '
                    '"list_limit": null, "status_filter": null, '
                    '"unmatched_product": null, '
                    '"refund_reason": "Customer requested sunglasses refund"}'
                ),
                _FakeResp("ORD-90125 환불을 진행할까요?"),
                _FakeResp(
                    '{"intent": "REFUND_REQUEST", "order_id": null, '
                    '"list_limit": null, "status_filter": null, '
                    '"unmatched_product": "Organic Supima Cotton Shirt", '
                    '"refund_reason": "Customer requested unpurchased shirt"}'
                ),
                _FakeResp(
                    "You have not purchased Organic Supima Cotton Shirt. "
                    "Your active orders are ORD-90126, ORD-90124, ORD-90125."
                ),
            ]
            bq_mock = FakeBigQueryClient()
            llm_t1 = run_refund_workflow(
                user_id=2048,
                message="가장 비싼 주문은 어떤 것인가요?",
                spanner_db=db,
                bq_client=bq_mock,
                require_confirmation=True,
            )
            self.assertEqual(llm_t1["order_id"], 90125)
            self.assertEqual(llm_t1["decision_status"], "ORDER_INFO")

            llm_t2 = run_refund_workflow(
                user_id=2048,
                message="환불을 요청 드립니다.",
                spanner_db=db,
                bq_client=bq_mock,
                require_confirmation=True,
            )
            self.assertEqual(llm_t2["order_id"], 90125)
            self.assertEqual(
                llm_t2["decision_status"], "PENDING_CONFIRMATION"
            )
            self.assertIsNotNone(llm_t2["pending_confirmation"])
            self.assertEqual(
                llm_t2["pending_confirmation"]["order_id"], 90125
            )
            self.assertIn("ORD-90125 환불을 진행할까요?", llm_t2["reply"])

            llm_t3 = run_refund_workflow(
                user_id=1001,
                message=(
                    "I would like to refund Organic Supima Cotton Shirt order."
                ),
                spanner_db=db,
                bq_client=bq_mock,
                require_confirmation=True,
            )
            self.assertIsNone(llm_t3["order_id"])
            self.assertEqual(
                llm_t3["unmatched_product"], "Organic Supima Cotton Shirt"
            )
            self.assertIn(
                "You have not purchased Organic Supima Cotton Shirt.",
                llm_t3["reply"],
            )

            mock_gen.side_effect = genai_errors.APIError(
                403, {"error": {"message": "Forbidden"}}
            )
            self.assertIsNone(
                _try_gemini_intent_extraction("I want a refund", [])
            )
            info_ctx = Context(
                {
                    "user_prompt": "What is my policy?",
                    "trace_id": "trace-9999ffff",
                    "action_outcome": {"decision_status": "POLICY_INFO"},
                }
            )
            self.assertIsNone(
                _try_gemini_response_generation(info_ctx, "Fallback text")
            )


if __name__ == "__main__":
    unittest.main()
