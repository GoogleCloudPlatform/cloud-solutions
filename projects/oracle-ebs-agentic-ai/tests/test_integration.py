# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Integration test suite for Oracle EBS Agentic AI components."""

import json
import os
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.genai import types
from src.a2a.a2a_server import app as a2a_app
from src.a2a.proxy import ActionPlan, _generate_content_with_fallback
from src.agents.financial_agent import app as financial_app
from src.agents.financial_agent import register_with_a2a as register_financial
from src.agents.inventory_agent import app as inventory_app
from src.agents.inventory_agent import register_with_a2a as register_inventory
from src.agents.supplier_agent import app as supplier_app
from src.agents.supplier_agent import register_with_a2a as register_supplier
from src.gemini_cli_extensions.oracle import ExecutionEngine
from src.mcp.ebs_db_client import EBSDatabaseClient
from src.mcp.mcp_server import _resolve_organization_info
from src.mcp.mcp_server import app as mcp_app
from src.oracle.skills import NLToSQLEngine

os.environ.setdefault("ORACLE_MOCK_DB", "true")


def make_mock_ai_client(content: Dict[str, Any]) -> MagicMock:
    """Creates a mock Gemini AI client returning structured JSON."""
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = json.dumps(content)
    mock_client.models.generate_content.return_value = mock_res
    return mock_client


def test_ebs_database_client_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Database Client parameters and Apps Context setup."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.delenv("ORACLE_HOST", raising=False)
    client = EBSDatabaseClient(
        host="127.0.0.1",
        port=1521,
        service_name="ebsdb",
        user="apps",
        password="apps",
    )
    assert client.host == "127.0.0.1"
    assert client.port == 1521
    assert client.service_name == "ebsdb"
    assert client.user == "apps"
    assert client.dsn == "127.0.0.1:1521/ebsdb"

    # Verify Apps Context initialization with default environment fallbacks
    success = client.initialize_apps_context()
    assert success is True
    assert client.is_context_initialized() is True

    # Verify Apps Context initialization with explicit parameters
    explicit_success = client.initialize_apps_context(
        user_id=1001, resp_id=50123, resp_appl_id=401
    )
    assert explicit_success is True


def test_ebs_database_client_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test initialize_apps_context() with FND environment variables."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.delenv("ORACLE_HOST", raising=False)
    monkeypatch.setenv("FND_USER_ID", "1099")
    monkeypatch.setenv("FND_RESP_ID", "50100")
    monkeypatch.setenv("FND_RESP_APPL_ID", "200")

    client = EBSDatabaseClient()
    success = client.initialize_apps_context()
    assert success is True
    assert client.is_context_initialized() is True


def test_a2a_discovery_server() -> None:
    """Verify A2A server registration, catalog listing, and lookup."""
    client = TestClient(a2a_app)

    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    card = {
        "name": "inventory_agent",
        "description": "Agent responsible for stock level checks",
        "endpoint_url": "http://127.0.0.1:8001",
        "version": "1.0.0",
        "capabilities": ["inventory_check", "stock_threshold"],
        "endpoints": {"check-stock": "/check-stock"},
        "metadata": {"database": "ebsdb"},
    }
    reg_res = client.post("/register", json=card)
    assert reg_res.status_code == 201
    assert reg_res.json()["name"] == "inventory_agent"

    list_res = client.get("/agents")
    assert list_res.status_code == 200
    names = [agent["name"] for agent in list_res.json()]
    assert "inventory_agent" in names

    get_res = client.get("/agents/inventory_agent")
    assert get_res.status_code == 200
    assert get_res.json()["endpoint_url"] == "http://127.0.0.1:8001"


def test_a2a_delete_and_not_found() -> None:
    """Tests DELETE /agents/{name} returning 204 and GET returning 404."""
    client = TestClient(a2a_app)

    card = {
        "name": "agent_to_delete",
        "description": "Agent to be deleted",
        "endpoint_url": "http://127.0.0.1:8099",
    }
    reg_res = client.post("/register", json=card)
    assert reg_res.status_code == 201

    del_res = client.delete("/agents/agent_to_delete")
    assert del_res.status_code == 204

    get_res = client.get("/agents/agent_to_delete")
    assert get_res.status_code == 404


def test_a2a_agent_card_endpoints() -> None:
    """Verify standard A2A Agent Card endpoints (/agent.json, etc.)."""
    client = TestClient(a2a_app)

    endpoints = [
        "/agent.json",
        "/.well-known/agent.json",
        "/a2a/agent.json",
        "/agent-card.json",
    ]
    for path in endpoints:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Oracle EBS Autonomous Assistant"
        assert data["version"] == "1.0.0"
        assert data["protocolVersion"] == "0.3.0"
        assert "defaultInputModes" in data
        assert "defaultOutputModes" in data
        assert "skills" in data
        assert isinstance(data["capabilities"], dict)
        assert isinstance(data["skills"], list)
        assert len(data["skills"]) >= 3
        for skill in data["skills"]:
            assert "id" in skill
            assert "name" in skill
            assert "description" in skill
            assert "tags" in skill
            assert "examples" in skill


def _get_mock_post_res(target_url: str, json_data: Dict[str, Any]) -> Any:
    """Helper to generate mock HTTP response objects for proxy tests."""
    mock_res = MagicMock()
    mock_res.status_code = 200
    if "check-stock" in target_url:
        mock_res.json.return_value = {
            "item_code": json_data.get("item_code", "AS54888"),
            "organization_id": json_data.get("organization_id", 204),
            "on_hand_quantity": 6.0,
            "status": "CRITICAL_LOW_STOCK",
        }
    elif "invoice-status" in target_url:
        mock_res.json.return_value = {
            "invoice_number": json_data.get("invoice_number", "INV-2024-001"),
            "total_found": 1,
            "status": "PAID",
        }
    elif "calculate-dso" in target_url:
        mock_res.json.return_value = {"dso_days": 42.5, "status": "HEALTHY"}
    elif "negotiate" in target_url:
        mock_res.json.return_value = {
            "po_number": json_data.get("po_number", "PO-100"),
            "supplier_name": "Office Depot",
            "accepted": True,
        }
    elif "supplier-items" in target_url:
        mock_res.json.return_value = {
            "supplier_id": json_data.get("supplier_id", 515),
            "supplier_name": "Acme Industrial Supplies",
            "total_items": 1,
            "items": [
                {
                    "inventory_item_id": 1001,
                    "item_code": "AS54888",
                    "description": "Desktop PC Platinum Edition",
                    "unit_price": 45.0,
                    "organization_id": 204,
                    "po_number": "PO-1001",
                }
            ],
            "status": "SUCCESS",
            "notes": "Found 1 item for supplier 515.",
        }
    return mock_res


def test_a2a_post_message_dispatcher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify gateway HTTP proxy routing for stock check, invoice, DSO."""
    client = TestClient(a2a_app)

    async def _mock_post(*args: Any, **kwargs: Any) -> Any:
        target_url = (
            str(args[1])
            if len(args) > 1
            else str(args[0] if args else kwargs.get("url", ""))
        )
        return _get_mock_post_res(target_url, kwargs.get("json") or {})

    monkeypatch.setattr("httpx.AsyncClient.post", _mock_post)

    # 1. Stock check proxy
    res = client.post(
        "/check-stock", json={"item_code": "AS54888", "organization_id": 204}
    )
    assert res.status_code == 200
    assert res.json()["item_code"] == "AS54888"

    # 2. Invoice status proxy
    res = client.post("/invoice-status", json={"invoice_num": "INV-2024-001"})
    assert res.status_code == 200
    assert res.json()["invoice_number"] == "INV-2024-001"

    # 3. DSO calculation proxy
    res = client.post("/calculate-dso", json={"period_days": 90})
    assert res.status_code == 200
    assert res.json()["dso_days"] == 42.5

    # 4. Supplier Negotiation proxy
    res = client.post(
        "/negotiate", json={"item_code": "AS54888", "quantity": 500}
    )
    assert res.status_code == 200
    assert res.json()["accepted"] is True

    # 5. A2A Conversational Message Dispatcher (POST / and POST /message)
    with patch("src.a2a.proxy._generate_content_with_fallback") as mock_gen:
        mock_stock_res = MagicMock()
        mock_stock_res.text = json.dumps(
            {
                "action": "check_stock",
                "item_code": "AS54888",
                "organization_id": 204,
            }
        )
        mock_inv_res = MagicMock()
        mock_inv_res.text = json.dumps(
            {"action": "invoice_status", "invoice_num": "INV-2024-001"}
        )

        def _side_effect(*args: Any, **kwargs: Any) -> Any:
            user_prompt = str(
                kwargs.get("contents", args[1] if len(args) > 1 else "")
            ).lower()
            if "invoice" in user_prompt:
                return (mock_inv_res, None)
            if "stock" in user_prompt or "as54888" in user_prompt:
                return (mock_stock_res, None)
            return (None, None)

        mock_gen.side_effect = _side_effect

        res_msg = client.post(
            "/message", json={"text": "check stock for AS54888"}
        )
        assert res_msg.status_code == 200
        assert "result" in res_msg.json()
        assert res_msg.json()["result"]["data"]["item_code"] == "AS54888"

        res_root = client.post(
            "/", json={"text": "invoice status for INV-2024-001"}
        )
        assert res_root.status_code == 200
        assert "result" in res_root.json()
        assert (
            res_root.json()["result"]["data"]["invoice_number"]
            == "INV-2024-001"
        )

        # 6. A2A v0.3.0 nested message structure and multi-verb testing
        nested_payload = {
            "message": {
                "role": "user",
                "parts": [{"text": "check stock for AS54888"}],
            }
        }
        res_nested = client.post("/a2a/v1/message", json=nested_payload)
        assert res_nested.status_code == 200
        assert "result" in res_nested.json()
        assert res_nested.json()["result"]["data"]["item_code"] == "AS54888"

        res_tasks = client.post("/tasks", json={"text": "Hi"})
        assert res_tasks.status_code == 200
        assert "result" in res_tasks.json()
        assert res_tasks.json()["result"]["status"] == {"state": "completed"}
        assert res_tasks.json()["status"] == "SUCCESS"
        assert "text" in res_tasks.json()
        assert "supplier 515" in res_tasks.json()["text"]
        actions = res_tasks.json()["result"]["data"]["supported_actions"]
        assert "supplier_items" in actions

    res_agent_post = client.post("/agent.json")
    assert res_agent_post.status_code == 200
    assert res_agent_post.json()["name"] == "Oracle EBS Autonomous Assistant"

    # 7. Worker exception 200 OK error payload transformation
    with patch("httpx.AsyncClient.post") as mock_err_post:
        mock_err_res = MagicMock()
        mock_err_res.status_code = 500
        mock_err_res.text = "Internal Worker Failure"
        mock_err_post.return_value = mock_err_res

        res_err = client.post(
            "/check-stock",
            json={"item_code": "AS54888", "organization_id": 204},
        )
        assert res_err.status_code == 200
        assert res_err.json()["status"] == "ERROR"
        assert "Worker service returned error" in res_err.json()["text"]


def test_model_fallback_chain() -> None:
    """Verify primary model falls back to secondary or returns error."""
    mock_client = MagicMock()

    # Case 1: Primary succeeds
    mock_resp = MagicMock()
    mock_resp.text = "Primary Success"
    mock_client.models.generate_content.return_value = mock_resp

    res, err = _generate_content_with_fallback(
        mock_client, "test prompt", types.GenerateContentConfig()
    )
    assert res is not None
    assert res.text == "Primary Success"
    assert err is None

    # Case 2: Primary fails, Fallback succeeds
    mock_fallback_resp = MagicMock()
    mock_fallback_resp.text = "Fallback Success"
    mock_client.models.generate_content.side_effect = [
        Exception("3.5 not found"),
        mock_fallback_resp,
    ]

    res, err = _generate_content_with_fallback(
        mock_client, "test prompt", types.GenerateContentConfig()
    )
    assert res is not None
    assert res.text == "Fallback Success"
    assert err is None

    # Case 3: Both fail
    mock_client.models.generate_content.side_effect = Exception(
        "Model not available"
    )
    res, err = _generate_content_with_fallback(
        mock_client, "test prompt", types.GenerateContentConfig()
    )
    assert res is None
    assert err is not None
    assert "Gemini Flash models are not available" in err


def test_worker_agents_a2a_registration_helpers() -> None:
    """Tests calling register_with_a2a() helper function on workers."""
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        assert register_inventory() is True
        assert register_financial() is True
        assert register_supplier() is True


def test_inventory_agent_check_stock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify inventory agent stock checking endpoint."""
    client = TestClient(inventory_app)

    assert client.get("/health").status_code == 200

    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        lambda self, q, p=None: [
            {
                "INVENTORY_ITEM_ID": 1001,
                "ITEM_CODE": "AS54888",
                "SEGMENT1": "AS54888",
                "DESCRIPTION": "Hard Disk Drive 500GB",
                "ORGANIZATION_ID": 204,
                "TOTAL_ON_HAND": 45.0,
                "TRANSACTION_QUANTITY": 45.0,
                "PRIMARY_TRANSACTION_QUANTITY": 45.0,
            }
        ],
    )

    payload = {
        "item_id": "AS54888",
        "organization_id": 204,
        "min_threshold": 10.0,
    }
    response = client.post("/check-stock", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == "AS54888"
    assert data["organization_id"] == 204
    assert "on_hand_quantity" in data
    assert "below_threshold" in data
    assert "status" in data


def test_financial_agent_invoice_status_and_dso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify financial agent invoice status and DSO metrics calculation."""
    client = TestClient(financial_app)

    assert client.get("/health").status_code == 200

    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        lambda self, q, p=None: [
            {
                "INVOICE_NUM": "INV-2026-9901",
                "VENDOR_ID": 105,
                "INVOICE_AMOUNT": 5000.0,
            }
        ],
    )

    # AP Invoice status check
    payload = {
        "invoice_number": "INV-2026-9901",
        "vendor_id": 105,
    }
    response = client.post("/invoice-status", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["total_found"] >= 1
    assert len(data["invoices"]) >= 1

    # DSO Calculation check
    dso_payload = {
        "period_days": 90,
        "total_accounts_receivable": 450000.0,
        "total_credit_sales": 1000000.0,
    }
    dso_response = client.post("/calculate-dso", json=dso_payload)
    assert dso_response.status_code == 200
    dso_data = dso_response.json()
    assert dso_data["dso_days"] == 40.5
    assert dso_data["evaluation"] == "OPTIMAL"


def test_financial_agent_dso_edge_cases() -> None:
    """Tests /calculate-dso MODERATE and HIGH_RISK evaluation tiers."""
    client = TestClient(financial_app)

    # 1. total_credit_sales <= 0 returns HTTP 400
    bad_payload = {
        "period_days": 90,
        "total_accounts_receivable": 50000.0,
        "total_credit_sales": 0.0,
    }
    bad_res = client.post("/calculate-dso", json=bad_payload)
    assert bad_res.status_code == 400

    # 2. MODERATE tier (e.g. 50 days)
    mod_payload = {
        "period_days": 90,
        "total_accounts_receivable": 50000.0,
        "total_credit_sales": 90000.0,
    }
    mod_res = client.post("/calculate-dso", json=mod_payload)
    assert mod_res.status_code == 200
    mod_data = mod_res.json()
    assert mod_data["dso_days"] == 50.0
    assert mod_data["evaluation"] == "MODERATE"

    # 3. HIGH_RISK tier (e.g. 70 days)
    high_payload = {
        "period_days": 90,
        "total_accounts_receivable": 70000.0,
        "total_credit_sales": 90000.0,
    }
    high_res = client.post("/calculate-dso", json=high_payload)
    assert high_res.status_code == 200
    high_data = high_res.json()
    assert high_data["dso_days"] == 70.0
    assert high_data["evaluation"] == "HIGH_RISK"


def test_financial_agent_invoice_status_missing_params() -> None:
    """Tests /invoice-status returning HTTP 422 when no params provided."""
    client = TestClient(financial_app)
    response = client.post("/invoice-status", json={})
    assert response.status_code == 422
    assert "At least one query parameter" in response.json()["detail"]


def test_financial_agent_analyze_financials_agentic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify financial agent agentic /analyze-financials endpoint."""
    mock_content = {
        "summary": "Financial analysis for INV-2024-001",
        "invoices": [],
        "days_sales_outstanding": 37.5,
        "cash_flow_health": "OPTIMAL",
        "recommended_actions": ["Review payment schedule"],
    }
    monkeypatch.setattr(
        "src.agents.financial_agent.get_ai_client",
        lambda: make_mock_ai_client(mock_content),
    )
    client = TestClient(financial_app)
    response = client.post(
        "/analyze-financials",
        json={
            "query": "Inspect invoice status for INV-2024-001 and calculate DSO"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "invoices" in data
    assert "cash_flow_health" in data


def test_inventory_agent_analyze_inventory_agentic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify inventory agent agentic /analyze-inventory endpoint."""
    mock_content = {
        "summary": "Inventory check for AS54888 in organization 204",
        "item_id": "AS54888",
        "organization_id": 204,
        "on_hand_quantity": 45.0,
        "min_threshold": 10.0,
        "below_threshold": False,
        "stock_status": "SUFFICIENT_STOCK",
        "recommended_actions": [
            "Check stock for item AS54888 in Organization 204"
        ],
        "details": {"source": "mock_ai"},
    }
    monkeypatch.setattr(
        "src.agents.inventory_agent.get_ai_client",
        lambda: make_mock_ai_client(mock_content),
    )
    client = TestClient(inventory_app)
    response = client.post(
        "/analyze-inventory",
        json={
            "query": "Check stock level for item AS54888 in organization 204"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "on_hand_quantity" in data
    assert "stock_status" in data


def test_supplier_agent_analyze_suppliers_agentic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify supplier agent agentic /analyze-suppliers endpoint."""
    mock_content = {
        "summary": "Supplier negotiation evaluated successfully",
        "supplier_id": 301,
        "supplier_name": "Acme Industrial Supplies",
        "negotiation_accepted": True,
        "proposed_unit_price": 12.00,
        "counter_unit_price": 12.24,
        "recommended_actions": ["Issue purchase order"],
        "metadata": {},
    }
    monkeypatch.setattr(
        "src.agents.supplier_agent.get_ai_client",
        lambda: make_mock_ai_client(mock_content),
    )
    client = TestClient(supplier_app)
    response = client.post(
        "/analyze-suppliers",
        json={"query": "Negotiate pricing for item AS54888 with supplier 301"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "supplier_id" in data
    assert "negotiation_accepted" in data


def test_supplier_agent_negotiate_and_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify supplier agent negotiation and vendor catalog REST API."""
    client = TestClient(supplier_app)

    assert client.get("/health").status_code == 200

    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        lambda self, q, p=None: [
            {
                "SUPPLIER_ID": 301,
                "SUPPLIER_NAME": "Acme Industrial Supplies",
                "UNIT_PRICE": 45.0,
                "ITEM_CODE": "AS54888",
            }
        ],
    )

    # Test vendor catalog REST lookup
    cat_payload = {
        "item_id": "AS54888",
        "required_quantity": 50.0,
    }
    cat_response = client.post("/vendor-catalog", json=cat_payload)
    assert cat_response.status_code == 200
    cat_data = cat_response.json()
    assert cat_data["total_vendors_found"] >= 1
    assert cat_data["best_quote"]["unit_price"] > 0

    # Test negotiation endpoint
    neg_payload = {
        "supplier_id": 301,
        "item_id": "AS54888",
        "target_quantity": 150.0,
        "target_unit_price": 45.00,
        "proposed_payment_terms": "Net 30",
    }
    neg_response = client.post("/negotiate", json=neg_payload)
    assert neg_response.status_code == 200
    neg_data = neg_response.json()
    assert neg_data["accepted"] is True
    assert neg_data["supplier_id"] == 301


def test_supplier_agent_catalog_unlisted_sku() -> None:
    """Tests /vendor-catalog for unlisted SKUs returning zero vendors."""
    client = TestClient(supplier_app)
    cat_payload = {
        "item_id": "UNKNOWN_SKU_9999",
        "required_quantity": 20.0,
    }
    response = client.post("/vendor-catalog", json=cat_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == "UNKNOWN_SKU_9999"
    assert data["total_vendors_found"] == 0
    assert data["best_quote"] is None
    assert len(data["all_quotes"]) == 0


def test_supplier_agent_negotiate_low_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests /negotiate for low-volume orders (target_quantity < 100)."""
    client = TestClient(supplier_app)

    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        lambda self, q, p=None: [
            {
                "SUPPLIER_ID": 301,
                "SUPPLIER_NAME": "Acme Industrial Supplies",
                "UNIT_PRICE": 50.0,
                "ITEM_CODE": "AS54888",
            }
        ],
    )

    neg_payload = {
        "supplier_id": 301,
        "item_id": "AS54888",
        "target_quantity": 50.0,
        "target_unit_price": 50.00,
        "proposed_payment_terms": "Net 30",
    }
    response = client.post("/negotiate", json=neg_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] is False
    assert data["counter_unit_price"] == 55.00


def test_financial_agent_dso_period_days_validation() -> None:
    """Verify /calculate-dso returns HTTP 400 when period_days <= 0."""
    client = TestClient(financial_app)
    bad_payload_zero = {
        "period_days": 0,
        "total_accounts_receivable": 50000.0,
        "total_credit_sales": 100000.0,
    }
    res_zero = client.post("/calculate-dso", json=bad_payload_zero)
    assert res_zero.status_code == 400
    assert "period_days must be greater than zero" in res_zero.json()["detail"]

    bad_payload_neg = {
        "period_days": -30,
        "total_accounts_receivable": 50000.0,
        "total_credit_sales": 100000.0,
    }
    res_neg = client.post("/calculate-dso", json=bad_payload_neg)
    assert res_neg.status_code == 400
    assert "period_days must be greater than zero" in res_neg.json()["detail"]


def test_supplier_agent_negotiate_invalid_inputs() -> None:
    """Verify /negotiate returns HTTP 400 when target_quantity <= 0."""
    client = TestClient(supplier_app)

    bad_qty = {
        "supplier_id": 301,
        "item_id": "AS54888",
        "target_quantity": 0,
        "target_unit_price": 50.0,
    }
    res_qty = client.post("/negotiate", json=bad_qty)
    assert res_qty.status_code == 400

    bad_price = {
        "supplier_id": 301,
        "item_id": "AS54888",
        "target_quantity": 100,
        "target_unit_price": 0,
    }
    res_price = client.post("/negotiate", json=bad_price)
    assert res_price.status_code == 400


def test_zero_integer_id_default_fallbacks() -> None:
    """Verify integer 0 for organization_id, vendor_id, invoice_id returns
    404."""
    inv_client = TestClient(inventory_app)
    fin_client = TestClient(financial_app)

    # Check organization_id = 0 in inventory agent returns 404
    # (not found in org 0)
    inv_res = inv_client.post(
        "/check-stock", json={"item_id": "AS54888", "organization_id": 0}
    )
    assert inv_res.status_code == 404

    # Check non-existent vendor_id = 0 and invoice_id = 0 in financial
    # agent returns 404
    fin_res = fin_client.post(
        "/invoice-status", json={"vendor_id": 0, "invoice_id": 0}
    )
    assert fin_res.status_code == 404


def test_terraform_vpc_sc_and_iam_configuration() -> None:
    """Verify terraform/main.tf contains required terraform resources."""
    tf_main_path = os.path.join(
        os.path.dirname(__file__), "..", "terraform", "main.tf"
    )
    with open(tf_main_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "google_secret_manager_secret_iam_member" in content
    assert "roles/secretmanager.secretAccessor" in content


def test_environment_tier_mock_database_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ENVIRONMENT tier validation."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    dev_client = EBSDatabaseClient()
    assert dev_client.is_dev_mode is True

    monkeypatch.setattr(
        dev_client.execution_engine,
        "execute",
        lambda *a, **kw: [{"INVOICE_NUM": "INV-101"}],
    )
    res_dev = dev_client.execute_query("SELECT * FROM apps.ap_invoices_all")
    assert len(res_dev) > 0

    monkeypatch.setenv("ENVIRONMENT", "prod")
    # Verify ValueError is raised when production DB configuration is missing
    with pytest.raises(
        ValueError, match="Missing required Oracle DB configuration"
    ):
        EBSDatabaseClient()

    # Set required production DB environment variables
    monkeypatch.setenv("ORACLE_HOST", "10.0.0.50")
    monkeypatch.setenv("ORACLE_PORT", "1521")
    monkeypatch.setenv("ORACLE_SERVICE_NAME", "PROD_EBS")
    monkeypatch.setenv("ORACLE_USER", "apps")
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")

    prod_client = EBSDatabaseClient()
    assert prod_client.is_dev_mode is False
    monkeypatch.setattr(
        prod_client.execution_engine,
        "execute",
        lambda *a, **kw: [],
    )

    res_prod = prod_client.execute_nl_query(
        "Fetch invoices", context={"tables": ["AP_INVOICES_ALL"]}
    )
    assert len(res_prod) == 0

    monkeypatch.delenv("ORACLE_HOST", raising=False)
    monkeypatch.delenv("ORACLE_PORT", raising=False)
    monkeypatch.delenv("ORACLE_SERVICE_NAME", raising=False)
    monkeypatch.delenv("ORACLE_USER", raising=False)
    monkeypatch.delenv("ORACLE_PASSWORD", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "dev")


def test_oracle_skills_and_gemini_extension_engine() -> None:
    """Verify Gemini CLI Extension and Oracle Skills engine translation."""
    ext_engine = ExecutionEngine(
        dsn="127.0.0.1:1521/ebsdb", user="apps", password="apps"
    )

    # 1. Test LLM NL2SQL generator integration
    def mock_llm(_prompt: str, _ctx: Optional[Dict[str, Any]]) -> str:
        return (
            "SELECT INVOICE_ID, INVOICE_NUM FROM AP_INVOICES_ALL WHERE"
            " VENDOR_ID = 501"
        )

    llm_skills_engine = NLToSQLEngine(
        execution_engine=ext_engine, llm_generator=mock_llm
    )
    llm_sql = llm_skills_engine.translate_prompt(
        "Fetch invoices for vendor 501"
    )
    assert llm_sql == (
        "SELECT INVOICE_ID, INVOICE_NUM FROM AP_INVOICES_ALL WHERE VENDOR_ID ="
        " 501"
    )

    # 2. Test rule-based translation fallback
    skills_engine = NLToSQLEngine(execution_engine=ext_engine)

    sql_inv = skills_engine.translate_prompt(
        "Show me AP invoices", context={"tables": ["AP_INVOICES_ALL"]}
    )
    assert "AP_INVOICES_ALL" in sql_inv

    sql_stock = skills_engine.translate_prompt(
        "Check stock levels",
        context={"tables": ["MTL_ONHAND_QUANTITIES_DETAIL"]},
    )
    assert "MTL_ONHAND_QUANTITIES_DETAIL" in sql_stock


def test_custom_invoice_and_item_extraction_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify proxy routes handle custom invoice formats and item requests."""
    client = TestClient(a2a_app)

    async def _mock_post(*args: Any, **kwargs: Any) -> Any:
        target_url = (
            str(args[1])
            if len(args) > 1
            else str(args[0] if args else kwargs.get("url", ""))
        )
        json_data = kwargs.get("json") or {}
        mock_res = MagicMock()
        mock_res.status_code = 200
        if "invoice-status" in target_url:
            mock_res.json.return_value = {
                "invoice_number": json_data.get("invoice_num")
                or json_data.get("invoice_number"),
                "status": "PAID",
            }
        elif "check-stock" in target_url:
            mock_res.json.return_value = {
                "item_code": json_data.get("item_code"),
                "organization_id": json_data.get("organization_id"),
                "on_hand_quantity": 45.0,
            }
        return mock_res

    monkeypatch.setattr("httpx.AsyncClient.post", _mock_post)

    res_ers = client.post(
        "/invoice-status", json={"invoice_num": "ERS-9163-109073"}
    )
    assert res_ers.status_code == 200
    assert res_ers.json()["invoice_number"] == "ERS-9163-109073"

    res_item = client.post(
        "/check-stock", json={"item_code": "45", "organization_id": 207}
    )
    assert res_item.status_code == 200
    assert res_item.json()["item_code"] == "45"


def test_mcp_server_consolidated_tool_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify consolidated MCP tool server endpoints and handlers."""
    mcp_client = TestClient(mcp_app)

    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        lambda self, q, p=None: [
            {
                "INVOICE_NUM": "INV-2024-001",
                "VENDOR_ID": 105,
                "SUPPLIER_NAME": "Acme Industrial Supplies",
                "UNIT_PRICE": 12.50,
            }
        ],
    )

    # Health check
    health_res = mcp_client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"
    assert health_res.json()["service"] == "oracle_ebs_mcp_server"

    # Check stock tool
    stock_res = mcp_client.post(
        "/check-stock",
        json={"item_code": "AS54888", "organization_id": 204},
    )
    assert stock_res.status_code == 200
    stock_json = stock_res.json()
    assert stock_json["item_code"] == "AS54888"
    assert stock_json["organization_id"] == 204
    assert stock_json["on_hand_quantity"] >= 0.0

    # Invoice status tool
    inv_res = mcp_client.post(
        "/invoice-status",
        json={"invoice_num": "INV-2024-001"},
    )
    assert inv_res.status_code == 200
    inv_json = inv_res.json()
    assert inv_json["status"] == "SUCCESS"
    assert inv_json["total_found"] >= 1

    # Calculate DSO tool
    dso_res = mcp_client.post(
        "/calculate-dso",
        json={"period_days": 90},
    )
    assert dso_res.status_code == 200
    dso_json = dso_res.json()
    assert dso_json["period_days"] == 90
    assert dso_json["dso_days"] >= 0.0
    assert dso_json["evaluation"] in (
        "OPTIMAL",
        "EVALUATE_CREDIT_TERMS",
        "CRITICAL_DSO_HIGH",
    )

    # Negotiate tool
    neg_res = mcp_client.post(
        "/negotiate",
        json={"item_code": "AS54888", "quantity": 100},
    )
    assert neg_res.status_code == 200
    neg_json = neg_res.json()
    assert neg_json["item_code"] == "AS54888"
    assert neg_json["quantity"] == 100
    assert neg_json["status"] == "QUOTE_ACCEPTED"


def test_domain_worker_agent_list_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify domain-specific list endpoints on worker agents."""
    inv_client = TestClient(inventory_app)
    sup_client = TestClient(supplier_app)
    fin_client = TestClient(financial_app)

    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        lambda self, q, p=None: [
            {
                "ORGANIZATION_ID": 204,
                "ORGANIZATION_CODE": "V1",
                "ORGANIZATION_NAME": "Vision Operations",
                "VENDOR_ID": 301,
                "VENDOR_NAME": "Acme Industrial Supplies",
            }
        ],
    )

    # Inventory Agent: /organizations & /items
    orgs_res = inv_client.post("/organizations", json={"limit": 5})
    assert orgs_res.status_code == 200
    assert orgs_res.json()["status"] == "SUCCESS"
    assert len(orgs_res.json()["organizations"]) >= 1

    items_res = inv_client.post(
        "/items", json={"organization_id": 204, "limit": 5}
    )
    assert items_res.status_code == 200
    assert items_res.json()["status"] == "SUCCESS"

    # Supplier Agent: /suppliers
    sups_res = sup_client.post("/suppliers", json={"limit": 5})
    assert sups_res.status_code == 200
    assert sups_res.json()["status"] == "SUCCESS"
    assert len(sups_res.json()["suppliers"]) >= 1

    # Financial Agent: /recent-invoices & /receivables
    invs_res = fin_client.post("/recent-invoices", json={"limit": 5})
    assert invs_res.status_code == 200
    assert invs_res.json()["status"] == "SUCCESS"

    rec_res = fin_client.post("/receivables", json={"period_days": 90})
    assert rec_res.status_code == 200
    assert rec_res.json()["status"] == "SUCCESS"
    assert rec_res.json()["dso_days"] >= 0.0


def test_database_error_response_sanitization(monkeypatch: Any) -> None:
    """Verify unhandled database exceptions return sanitized 500 responses."""

    def _mock_raise_db_err(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "ORA-00942: table or view does not exist at 10.115.0.30"
        )

    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        _mock_raise_db_err,
    )
    inv_client = TestClient(inventory_app, raise_server_exceptions=False)

    res = inv_client.post(
        "/check-stock",
        json={"item_code": "AS54888", "organization_id": 204},
    )
    assert res.status_code == 500
    detail = res.json().get("detail", "")
    assert detail == "Database operation failed"
    assert "ORA-00942" not in detail
    assert "10.115.0.30" not in detail


def test_non_existent_entity_resolution_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify offline AI client raises HTTP 500 for unassisted analysis."""
    monkeypatch.setattr(
        "src.agents.inventory_agent.get_ai_client", lambda: None
    )
    monkeypatch.setattr("src.agents.supplier_agent.get_ai_client", lambda: None)
    inv_client = TestClient(inventory_app)
    res_inv = inv_client.post(
        "/analyze-inventory",
        json={"query": "Give me the list of items from organization Acme"},
    )
    assert res_inv.status_code == 500

    sup_client = TestClient(supplier_app)
    res_sup = sup_client.post(
        "/analyze-suppliers",
        json={"query": "Negotiate contract for supplier NonExistentCorp"},
    )
    assert res_sup.status_code == 500


def test_a2a_raw_json_agent_card_rejection() -> None:
    """Verify posting invalid payload types to proxy is rejected with 422."""
    a2a_client = TestClient(a2a_app)
    res = a2a_client.post(
        "/check-stock", json={"organization_id": "invalid_integer_string"}
    )
    assert res.status_code == 422


def test_dynamic_db_org_resolution_without_static_maps(
    monkeypatch: Any,
) -> None:
    """Verify org resolution queries org_organization_definitions."""

    def _mock_execute_query(_self: Any, _sql: str, params: Any = None) -> Any:
        p = params or {}
        tok = str(p.get("tok") or p.get("org_code") or _sql or "").upper()
        if "PR4" in tok or "1384" in tok:
            return [
                {
                    "ORGANIZATION_ID": 1384,
                    "ORGANIZATION_CODE": "PR4",
                    "ORGANIZATION_NAME": "PR4 Operating Org",
                }
            ]
        if "V1" in tok or "204" in tok:
            return [
                {
                    "ORGANIZATION_ID": 204,
                    "ORGANIZATION_CODE": "V1",
                    "ORGANIZATION_NAME": "Vision Operations",
                }
            ]
        if "M1" in tok or "207" in tok:
            return [
                {
                    "ORGANIZATION_ID": 207,
                    "ORGANIZATION_CODE": "M1",
                    "ORGANIZATION_NAME": "Seattle Manufacturing",
                }
            ]
        return []

    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        _mock_execute_query,
    )

    # Verify _resolve_organization_info resolves via DB query results
    oid_pr4, code_pr4, name_pr4 = _resolve_organization_info("PR4")
    assert oid_pr4 == 1384
    assert code_pr4 == "PR4"
    assert name_pr4 == "PR4 Operating Org"

    oid_v1, code_v1, _ = _resolve_organization_info("V1")
    assert oid_v1 == 204
    assert code_v1 == "V1"

    # Verify /items in inventory_agent resolves organization_code="PR4"
    inv_client = TestClient(inventory_app)
    items_res = inv_client.post(
        "/items", json={"organization_code": "PR4", "limit": 10}
    )
    assert items_res.status_code == 200
    res_data = items_res.json()
    assert res_data["status"] == "SUCCESS"
    assert res_data["organization_id"] == 1384


def test_pagination_boundary_and_zero_credit_sales_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify limit > 100 and zero credit sales return 422."""
    client = TestClient(a2a_app)
    fin_client = TestClient(financial_app)

    # 1. Limit > 100 bound validation (HTTP 422)
    res_large_limit = client.post("/items", json={"limit": 500})
    assert res_large_limit.status_code == 422

    # 2. Zero credit sales during DSO calculation (HTTP 422)
    monkeypatch.setattr(
        "src.mcp.ebs_db_client.EBSDatabaseClient.execute_query",
        lambda self, q, p=None: [
            {"TOTAL_RECEIVABLES": 10000.0, "TOTAL_CREDIT_SALES": 0.0}
        ],
    )
    res_zero_sales = fin_client.post("/calculate-dso", json={"period_days": 90})
    assert res_zero_sales.status_code == 422
    err_detail = res_zero_sales.json()["detail"]
    assert (
        "Missing required financial metrics" in err_detail
        or "Zero" in err_detail
    )


def test_supplier_items_endpoint_and_a2a_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify /supplier-items endpoint and A2A cognitive dispatching."""
    sup_client = TestClient(supplier_app)
    a2a_client = TestClient(a2a_app)

    async def _mock_post(*args: Any, **kwargs: Any) -> Any:
        target_url = (
            str(args[1])
            if len(args) > 1
            else str(args[0] if args else kwargs.get("url", ""))
        )
        return _get_mock_post_res(target_url, kwargs.get("json") or {})

    monkeypatch.setattr("httpx.AsyncClient.post", _mock_post)

    # 1. Direct query to supplier_agent /supplier-items
    res = sup_client.post(
        "/supplier-items", json={"supplier_id": 515, "limit": 10}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["supplier_id"] == 515
    assert len(data["items"]) >= 1
    assert data["items"][0]["item_code"] == "AS54888"

    # 2. Non-existent supplier returns NOT_FOUND status
    res_none = sup_client.post("/supplier-items", json={"supplier_id": 9999})
    assert res_none.status_code == 200
    none_data = res_none.json()
    assert none_data["status"] == "NOT_FOUND"
    assert none_data["total_items"] == 0
    assert none_data["items"] == []

    # 3. Validation: limit <= 0 returns HTTP 400 or HTTP 422
    res_bad = sup_client.post("/supplier-items", json={"limit": 0})
    assert res_bad.status_code in (400, 422)

    # 4. A2A Cognitive Dispatching: "Give me the items for supplier 515"
    with patch("src.a2a.proxy._generate_content_with_fallback") as mock_gen:
        mock_dispatch_res = MagicMock()
        mock_dispatch_res.text = json.dumps(
            {"action": "supplier_items", "supplier_id": 515}
        )
        mock_gen.return_value = (mock_dispatch_res, None)

        a2a_msg_res = a2a_client.post(
            "/message", json={"text": "Give me the items for supplier 515"}
        )
        assert a2a_msg_res.status_code == 200
        a2a_data = a2a_msg_res.json()
        assert "result" in a2a_data
        assert a2a_data["jsonrpc"] == "2.0"
        result_text = a2a_data["result"]["text"]
        assert "AS54888" in result_text or "515" in result_text


def test_a2a_dispatcher_limit_clamping_and_error_sanitization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ActionPlan limit clamping and resilient error handling."""
    # 1. Test ActionPlan.clamp_limit behavior
    plan_high = ActionPlan.model_validate(
        {"action": "organizations", "limit": 300}
    )
    assert plan_high.limit == 100

    plan_negative = ActionPlan.model_validate(
        {"action": "organizations", "limit": -10}
    )
    assert plan_negative.limit == 1

    plan_none = ActionPlan.model_validate({"action": "organizations"})
    assert plan_none.limit == 50

    # 2. Test A2A dispatcher with out-of-bounds limit from LLM
    a2a_client = TestClient(a2a_app)

    async def _mock_post(*_args: Any, **_kwargs: Any) -> Any:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "status": "SUCCESS",
            "total_found": 1,
            "organizations": [
                {
                    "organization_id": 204,
                    "organization_code": "V1",
                    "organization_name": "Vision Operations",
                }
            ],
        }
        return mock_res

    monkeypatch.setattr("httpx.AsyncClient.post", _mock_post)

    with patch("src.a2a.proxy._generate_content_with_fallback") as mock_gen:
        mock_dispatch_res = MagicMock()
        mock_dispatch_res.text = json.dumps(
            {"action": "organizations", "limit": 300}
        )
        mock_gen.return_value = (mock_dispatch_res, None)

        res = a2a_client.post(
            "/", json={"text": "List operating organizations"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        assert data["status"] == "SUCCESS"


def test_items_by_organization_code_a2a_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify listing items using organization code via A2A dispatcher."""
    plan = ActionPlan.model_validate(
        {"action": "items", "organization_code": "AD1"}
    )
    assert plan.organization_code == "AD1"

    a2a_client = TestClient(a2a_app)
    received_payload: Dict[str, Any] = {}

    async def _mock_post(*_args: Any, **kwargs: Any) -> Any:
        nonlocal received_payload
        if kwargs.get("json"):
            received_payload = kwargs["json"]
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "status": "SUCCESS",
            "organization_id": 498,
            "organization_code": "AD1",
            "total_found": 1,
            "items": [
                {
                    "inventory_item_id": 100,
                    "item_code": "AD100",
                    "description": "AD1 Test Item",
                    "organization_id": 498,
                    "total_on_hand": 5.0,
                }
            ],
        }
        return mock_res

    monkeypatch.setattr("httpx.AsyncClient.post", _mock_post)

    with patch("src.a2a.proxy._generate_content_with_fallback") as mock_gen:
        mock_dispatch_res = MagicMock()
        mock_dispatch_res.text = json.dumps(
            {"action": "items", "organization_code": "AD1"}
        )
        mock_synth_res = MagicMock()
        mock_synth_res.text = "Items for AD1: AD100 Test Item"
        mock_gen.side_effect = [
            (mock_dispatch_res, None),
            (mock_synth_res, None),
        ]

        res = a2a_client.post(
            "/message",
            json={"text": "List items for Organization code AD1"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["jsonrpc"] == "2.0"
        assert received_payload.get("organization_code") == "AD1"
        assert "AD100" in data["result"]["text"]
