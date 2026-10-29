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

"""Unit tests for FastAPI endpoints, read-only guards, and sql_fallback."""

import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from app.agent.bq_lineage import (
    clear_memory_trace_store,
    execute_readonly_bigquery,
    set_bq_graph_mode,
)
from app.agent.spanner_client import validate_readonly_spanner_query
from app.agent.workflow import clear_pending_confirmations
from app.main import app
from app.tests.test_workflow import FakeSpannerDatabase, _make_gql_row
from fastapi.testclient import TestClient


class FastAPIEndpointsTest(unittest.TestCase):
    """Tests all HTML and JSON routes on the unified FastAPI server."""

    def setUp(self) -> None:
        """Initializes TestClient and resets trace memory."""
        os.environ["DISABLE_VERTEX_LLM"] = "true"
        clear_memory_trace_store()
        clear_pending_confirmations()
        self.client = TestClient(app)

    @patch("app.main.seed_spanner_if_empty", return_value=True)
    @patch(
        "app.main.ensure_bigquery_schema",
        return_value=(True, "sql_fallback"),
    )
    def test_health_and_ui_routes(
        self, _mock_bq: Any, _mock_seed: Any
    ) -> None:
        """Verifies /api/health, /shop, and /console return HTTP 200."""
        health_resp = self.client.get("/api/health")
        self.assertEqual(health_resp.status_code, 200)
        body = health_resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["spanner_seeded"])
        self.assertTrue(body["bq_tables_ready"])

        shop_resp = self.client.get("/shop")
        self.assertEqual(shop_resp.status_code, 200)
        self.assertIn("TheLook Shopping Mall", shop_resp.text)
        self.assertIn('id="lang-toggle-btn"', shop_resp.text)
        self.assertIn('id="reset-demo-btn"', shop_resp.text)
        self.assertIn('id="reset-progress-modal"', shop_resp.text)
        self.assertIn('id="reset-confirm-btn"', shop_resp.text)
        self.assertIn('id="reset-cancel-btn"', shop_resp.text)
        self.assertIn('id="clear-chat-btn"', shop_resp.text)
        self.assertIn('id="chat-persona-label"', shop_resp.text)
        self.assertNotIn('id="theme-toggle-btn"', shop_resp.text)
        self.assertIn("bg-slate-50", shop_resp.text)
        self.assertIn(
            "no-cache", shop_resp.headers.get("Cache-Control", "")
        )

        console_resp = self.client.get("/console")
        self.assertEqual(console_resp.status_code, 200)
        self.assertIn("Data Engineer Investigation Console", console_resp.text)
        self.assertIn('id="lang-toggle-btn"', console_resp.text)
        self.assertIn('id="reset-demo-btn"', console_resp.text)
        self.assertIn('id="reset-progress-modal"', console_resp.text)
        self.assertIn('id="reset-confirm-btn"', console_resp.text)
        self.assertIn('id="reset-cancel-btn"', console_resp.text)
        self.assertNotIn('id="refresh-traces-btn"', console_resp.text)
        self.assertNotIn('id="theme-toggle-btn"', console_resp.text)
        self.assertIn("bg-slate-50", console_resp.text)
        self.assertIn(
            "no-cache", console_resp.headers.get("Cache-Control", "")
        )

        shop_js_resp = self.client.get("/static/shop.js")
        self.assertEqual(shop_js_resp.status_code, 200)
        self.assertIn("soa_chat_history_by_user", shop_js_resp.text)
        self.assertIn("soa_pending_order_by_user", shop_js_resp.text)
        self.assertIn("soa_active_user_id", shop_js_resp.text)
        self.assertIn("loadPersistedChatState", shop_js_resp.text)
        self.assertIn("savePersistedChatState", shop_js_resp.text)
        self.assertIn("clearPersistedChatState", shop_js_resp.text)

        console_js_resp = self.client.get("/static/console.js")
        self.assertEqual(console_js_resp.status_code, 200)
        self.assertIn("soa_chat_history_by_user", console_js_resp.text)
        self.assertIn("soa_pending_order_by_user", console_js_resp.text)
        self.assertIn("soa_active_user_id", console_js_resp.text)

    @patch("app.main.fetch_storefront_products")
    @patch("app.main.fetch_persona_customers")
    @patch("app.main.fetch_customer_orders")
    def test_storefront_and_persona_endpoints(
        self,
        mock_orders: Any,
        mock_customers: Any,
        mock_products: Any,
    ) -> None:
        """Verifies /api/products, /api/customers, and /api/customers/orders."""
        mock_products.return_value = [
            {
                "id": 501,
                "name": "Classic Merino Crewneck Sweater",
                "brand": "Calvin Klein",
                "category": "Sweaters",
                "department": "Women",
                "retail_price": 89.5,
                "distribution_center_name": "Chicago IL",
                "policy_id": "POL-REFUND-STD-V1",
            }
        ]
        mock_customers.return_value = [
            {
                "user_id": 1001,
                "first_name": "Alice",
                "last_name": "Chen",
                "email": "alice.chen@example.com",
                "customer_tier": "STANDARD",
                "prior_refund_count_100d": 2,
                "max_refunds_100d": 10,
            },
            {
                "user_id": 3072,
                "first_name": "Claire",
                "last_name": "Vance",
                "email": "claire.vance@example.com",
                "customer_tier": "VIP",
                "prior_refund_count_100d": 12,
                "max_refunds_100d": 20,
            },
        ]
        mock_orders.return_value = [
            {
                "order_id": 90124,
                "status": "Complete",
                "created_at": "2026-10-01T00:00:00Z",
                "delivered_at": "2026-10-06T00:00:00Z",
                "returned_at": None,
                "items": [],
            }
        ]

        self.assertEqual(self.client.get("/api/products").status_code, 200)
        cust_resp = self.client.get("/api/customers")
        self.assertEqual(cust_resp.status_code, 200)
        self.assertEqual(len(cust_resp.json()["customers"]), 2)

        ord_resp = self.client.get("/api/customers/1001/orders")
        self.assertEqual(ord_resp.status_code, 200)
        self.assertEqual(ord_resp.json()["orders"][0]["order_id"], 90124)

    def test_chat_refund_and_trace_graph_endpoints(self) -> None:
        """Verifies POST /api/chat/refund and GET /api/traces/{id}/graph."""
        fake_db = FakeSpannerDatabase([_make_gql_row()])
        with patch(
            "app.agent.spanner_client.get_spanner_database",
            return_value=fake_db,
        ):
            chat_turn1 = self.client.post(
                "/api/chat/refund",
                json={
                    "user_id": 1001,
                    "message": "주문 ORD-90124 환불 요청합니다.",
                },
            )
            self.assertEqual(chat_turn1.status_code, 200)
            payload1 = chat_turn1.json()
            self.assertEqual(
                payload1["decision_status"], "PENDING_CONFIRMATION"
            )
            self.assertIsNone(fake_db.last_tx)
            clear_pending_confirmations()

            chat_resp = self.client.post(
                "/api/chat/refund",
                json={
                    "user_id": 1001,
                    "message": "네, 확인했습니다. 환불 진행해주세요.",
                    "pending_order_id": payload1["order_id"],
                },
            )
            self.assertEqual(chat_resp.status_code, 200)
            payload = chat_resp.json()
            self.assertEqual(payload["decision_status"], "APPROVED")
            self.assertIsNotNone(fake_db.last_tx)
            trace_id = payload["trace_id"]

            graph_resp = self.client.get(f"/api/traces/{trace_id}/graph")
            self.assertEqual(graph_resp.status_code, 200)
            graph_data = graph_resp.json()
            layers = {n["data"]["layer"] for n in graph_data["nodes"]}
            self.assertEqual(layers, {"bq", "r2g", "u2g"})

            stream_resp = self.client.post(
                "/api/chat/refund/stream",
                json={
                    "user_id": 1001,
                    "message": "주문 ORD-90124 환불 요청합니다.",
                },
            )
            self.assertEqual(stream_resp.status_code, 200)
            stream_events = [
                json.loads(line)
                for line in stream_resp.text.strip().splitlines()
                if line.strip()
            ]
            step_nodes = {
                ev["node_name"]
                for ev in stream_events
                if ev.get("type") == "step"
            }
            self.assertEqual(
                step_nodes,
                {
                    "IntentAgent",
                    "resolve_catalog_contract",
                    "evaluate_spanner_policy",
                    "route_and_commit_action",
                    "ResponseAgent",
                },
            )
            self.assertEqual(stream_events[-1]["type"], "result")
            self.assertEqual(
                stream_events[-1]["data"]["decision_status"],
                "PENDING_CONFIRMATION",
            )

            with patch(
                "app.main.reset_demo_orders",
                return_value=[90124, 90588, 90910],
            ):
                reset_resp = self.client.post("/api/demo/reset")
                self.assertEqual(reset_resp.status_code, 200)
                reset_body = reset_resp.json()
                self.assertEqual(reset_body["status"], "reset")
                self.assertEqual(
                    reset_body["reset_order_ids"], [90124, 90588, 90910]
                )
                self.assertIn(
                    "agent_sessions", reset_body["bq_tables_cleared"]
                )
                traces_after = self.client.get("/api/traces").json()["traces"]
                self.assertEqual(traces_after, [])

        bad_trace = self.client.get("/api/traces/invalid_trace_id/graph")
        self.assertEqual(bad_trace.status_code, 400)

        with patch(
            "app.main.run_refund_workflow",
            side_effect=KeyError("unexpected error"),
        ):
            err_resp = self.client.post(
                "/api/chat/refund",
                json={"user_id": 1001, "message": "Refund ORD-90124"},
            )
            self.assertEqual(err_resp.status_code, 500)
            self.assertEqual(
                err_resp.json()["detail"],
                "Unable to process refund workflow request.",
            )

    def test_governance_and_readonly_query_guards(self) -> None:
        """Verifies /api/governance and Spanner/BigQuery read-only guards."""
        gov_resp = self.client.get("/api/governance")
        self.assertEqual(gov_resp.status_code, 200)
        gov_data = gov_resp.json()
        self.assertIn("catalog_contract", gov_data)
        self.assertEqual(
            gov_data["catalog_contract"]["tier_term_id"],
            "customer-loyalty-tier",
        )

        with self.assertRaises(ValueError):
            validate_readonly_spanner_query("DELETE FROM orders WHERE true")

        commented_gql = validate_readonly_spanner_query(
            "-- Purpose: Explain how Spanner GQL works without UPDATE\n"
            "GRAPH OperationalContextGraph\n"
            "MATCH (u:users {id: 1001}) RETURN u.id AS user_id"
        )
        self.assertTrue(commented_gql.startswith("-- Purpose:"))

        sp_mutate = self.client.post(
            "/api/query/spanner",
            json={"query": "UPDATE orders SET status = 'Returned' WHERE true"},
        )
        self.assertEqual(sp_mutate.status_code, 400)

        bq_mutate = self.client.post(
            "/api/query/bigquery",
            json={"query": "DROP TABLE soa_action_lineage.agent_sessions"},
        )
        self.assertEqual(bq_mutate.status_code, 400)

    def test_bigquery_sql_fallback_template_dispatch(self) -> None:
        """Verifies GRAPH_TABLE queries map to parameterized SQL in fallback."""
        set_bq_graph_mode("sql_fallback")
        executed_queries: list[str] = []

        class _FakeResult:
            schema = []

            def __iter__(self) -> Any:
                return iter(
                    [
                        {
                            "trace_id": "trace-a1b2c3d4",
                            "decision_status": "APPROVED",
                        }
                    ]
                )

        class _FakeJob:
            def result(self, timeout: float | None = None) -> _FakeResult:
                _ = timeout
                return _FakeResult()

        class _MockBQ:
            def query(self, sql: str, job_config: Any = None) -> _FakeJob:
                _ = job_config
                executed_queries.append(sql)
                return _FakeJob()

        mock_bq = _MockBQ()
        gql_approval = (
            "-- Purpose: Audit ActionLineageGraph without CREATE/UPDATE\n"
            "SELECT * FROM GRAPH_TABLE(soa_action_lineage.ActionLineageGraph "
            "MATCH (s:AgentSession {trace_id: 'trace-a1b2c3d4'}) "
            "RETURN s.trace_id AS trace_id)"
        )
        res1 = execute_readonly_bigquery(gql_approval, bq_client=mock_bq)
        self.assertEqual(res1["execution_mode"], "sql_fallback")
        self.assertIn("WHERE s.trace_id = @trace_id", executed_queries[-1])

        gql_denial = (
            "SELECT rejection_reason FROM GRAPH_TABLE("
            "soa_action_lineage.ActionLineageGraph "
            "MATCH (s:AgentSession) "
            "-[:evaluated_policy]->(pe:PolicyEvaluation "
            "{evaluation_result: 'FAIL'}) "
            "WHERE s.trace_id = 'trace-e5f6a7b8' "
            "RETURN s.trace_id AS trace_id)"
        )
        res2 = execute_readonly_bigquery(gql_denial, bq_client=mock_bq)
        self.assertEqual(res2["execution_mode"], "sql_fallback")
        self.assertIn("pe.evaluation_result = 'FAIL'", executed_queries[-1])
        self.assertIn("WHERE s.trace_id = @trace_id", executed_queries[-1])

        gql_all_denials = (
            "SELECT rejection_reason FROM GRAPH_TABLE("
            "soa_action_lineage.ActionLineageGraph "
            "MATCH (s:AgentSession) "
            "-[:evaluated_policy]->(pe:PolicyEvaluation "
            "{evaluation_result: 'FAIL'}) "
            "-- WHERE s.trace_id = 'trace-e5f6a7b8'\n"
            "RETURN s.trace_id AS trace_id)"
        )
        res3 = execute_readonly_bigquery(gql_all_denials, bq_client=mock_bq)
        self.assertEqual(res3["execution_mode"], "sql_fallback")
        self.assertIn("pe.evaluation_result = 'FAIL'", executed_queries[-1])
        self.assertNotIn("WHERE s.trace_id = @trace_id", executed_queries[-1])
        self.assertIn(
            "ORDER BY s.started_at DESC LIMIT 50",
            executed_queries[-1],
        )


if __name__ == "__main__":
    unittest.main()
