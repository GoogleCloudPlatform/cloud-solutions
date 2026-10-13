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

"""Shared pytest fixtures and test doubles for Oracle EBS Workflow testing."""

import json
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from src.a2a.a2a_server import app as a2a_app
from src.agents.workflow_agent import app as agent_app
from src.agents.workflow_agent import get_triage_service
from src.gemini_cli_extensions.oracle import ExecutionEngine
from src.mcp.mcp_server import app as mcp_app
from src.mcp.mcp_server import get_service as get_mcp_service
from src.workflow.client import EBSWorkflowClient
from src.workflow.service import WorkflowTriageService

TEST_NOTIFICATIONS = {
    1001: {
        "header": {
            "notification_id": 1001,
            "message_type": "APEXP",
            "message_name": "EXP_APPR_MSG",
            "recipient_role": "JDOE",
            "status": "OPEN",
            "subject": "Expense Report EXP-2024-001 for $1,500.00",
            "priority": 50,
            "begin_date": "2026-09-10T08:00:00",
            "due_date": "2026-09-20T17:00:00",
            "amount": 1500.0,
        },
        "attributes": {
            "EXP_REPORT_TOTAL": 1500.0,
            "HAS_RECEIPTS": "N",
            "WEEKEND_SPEND": "N",
        },
    },
    1002: {
        "header": {
            "notification_id": 1002,
            "message_type": "APEXP",
            "message_name": "EXP_APPR_MSG",
            "recipient_role": "JDOE",
            "status": "OPEN",
            "subject": "Expense Report EXP-2024-002 for $250.00",
            "priority": 50,
            "begin_date": "2026-09-11T09:00:00",
            "due_date": "2026-09-21T17:00:00",
            "amount": 250.0,
        },
        "attributes": {
            "EXP_REPORT_TOTAL": 250.0,
            "HAS_RECEIPTS": "Y",
            "WEEKEND_SPEND": "N",
        },
    },
    2001: {
        "header": {
            "notification_id": 2001,
            "message_type": "POAPPR",
            "message_name": "PO_APPR_MSG",
            "recipient_role": "JDOE",
            "status": "OPEN",
            "subject": "Purchase Order PO-5001 for $45,000.00",
            "priority": 40,
            "begin_date": "2026-09-12T10:00:00",
            "due_date": "2026-09-22T17:00:00",
            "amount": 45000.0,
        },
        "attributes": {
            "PO_AMOUNT": 45000.0,
            "VENDOR_STATUS": "APPROVED",
            "AFTER_THE_FACT": "N",
        },
    },
    2002: {
        "header": {
            "notification_id": 2002,
            "message_type": "POAPPR",
            "message_name": "PO_APPR_MSG",
            "recipient_role": "JDOE",
            "status": "OPEN",
            "subject": "Purchase Order PO-5002 for $120,000.00",
            "priority": 20,
            "begin_date": "2026-09-12T11:00:00",
            "due_date": "2026-09-22T17:00:00",
            "amount": 120000.0,
        },
        "attributes": {
            "PO_AMOUNT": 120000.0,
            "VENDOR_STATUS": "PROBATIONARY",
            "AFTER_THE_FACT": "Y",
        },
    },
    3001: {
        "header": {
            "notification_id": 3001,
            "message_type": "REQAPPR",
            "message_name": "REQ_APPR_MSG",
            "recipient_role": "JDOE",
            "status": "OPEN",
            "subject": "Requisition REQ-8001 for $4,500.00",
            "priority": 50,
            "begin_date": "2026-09-13T12:00:00",
            "due_date": "2026-09-23T17:00:00",
            "amount": 4500.0,
        },
        "attributes": {
            "REQ_AMOUNT": 4500.0,
            "SPLIT_REQUISITION": "N",
            "JUSTIFICATION": "Quarterly office IT supplies and hardware.",
        },
    },
}


class MockDatabaseEngine(ExecutionEngine):
    """In-memory test double simulating Oracle EBS PL/SQL API calls."""

    def __init__(self) -> None:
        super().__init__(dsn="test:1521/test", user="apps", password="pwd")
        self.mutations_executed: list[dict[str, Any]] = []

    def execute_plsql(
        self, plsql_block: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Simulate certified PL/SQL API calls against mock notifications."""
        binds = params or {}
        block_upper = plsql_block.upper()

        if "GET_OPEN_WORKLIST" in block_upper:
            results = []
            for item in TEST_NOTIFICATIONS.values():
                hdr = dict(item["header"])
                hdr["attributes"] = dict(item.get("attributes", {}))
                msg_type = binds.get("message_type")
                if msg_type and hdr["message_type"] != str(msg_type).upper():
                    continue
                recipient = binds.get("recipient")
                if (
                    recipient
                    and hdr["recipient_role"] != str(recipient).upper()
                ):
                    continue
                results.append(hdr)
            return {"status": "SUCCESS", "out_json": json.dumps(results)}

        if "GET_NOTIFICATION_INFO" in block_upper:
            nid = int(binds.get("nid", 0))
            if nid in TEST_NOTIFICATIONS:
                return {
                    "status": "SUCCESS",
                    "out_json": json.dumps(TEST_NOTIFICATIONS[nid]["header"]),
                }
            return {"status": "SUCCESS", "out_json": None}

        if "GET_NOTIFICATION_ATTRS" in block_upper:
            nid = int(binds.get("nid", 0))
            if nid in TEST_NOTIFICATIONS:
                attrs = TEST_NOTIFICATIONS[nid]["attributes"]
                rows = [
                    {
                        "name": k,
                        "text_value": str(v) if isinstance(v, str) else None,
                        "number_value": (
                            float(v) if isinstance(v, (int, float)) else None
                        ),
                        "date_value": None,
                    }
                    for k, v in attrs.items()
                ]
                return {"status": "SUCCESS", "out_json": json.dumps(rows)}
            return {"status": "SUCCESS", "out_json": "[]"}

        self.mutations_executed.append({"block": plsql_block, "params": binds})
        return {
            "status": "SUCCESS",
            "message": "Mock PL/SQL executed successfully",
        }


@pytest.fixture(name="mock_db_engine")
def fixture_mock_db_engine() -> MockDatabaseEngine:
    """Fixture providing simulated Oracle database engine."""
    return MockDatabaseEngine()


def create_mock_isg_http_client() -> MagicMock:
    """Create a mock HTTP client simulating Oracle ISG REST endpoints."""
    mock_http = MagicMock()

    def mock_get(
        url: str,
        params: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> MagicMock:
        resp = MagicMock()
        url_str = str(url)
        if url_str.endswith("/attributes"):
            parts = url_str.rstrip("/").split("/")
            nid = int(parts[-2])
            if nid in TEST_NOTIFICATIONS:
                resp.status_code = 200
                resp.json.return_value = dict(
                    TEST_NOTIFICATIONS[nid]["attributes"]
                )
                resp.text = json.dumps(TEST_NOTIFICATIONS[nid]["attributes"])
                return resp
            resp.status_code = 404
            resp.json.return_value = {
                "detail": f"Workflow notification {nid} not found"
            }
            resp.text = f"Workflow notification {nid} not found"
            return resp

        if "/notifications/" in url_str:
            parts = url_str.rstrip("/").split("/")
            nid = int(parts[-1])
            if nid in TEST_NOTIFICATIONS:
                resp.status_code = 200
                resp.json.return_value = dict(TEST_NOTIFICATIONS[nid]["header"])
                resp.text = json.dumps(TEST_NOTIFICATIONS[nid]["header"])
                return resp
            resp.status_code = 404
            resp.json.return_value = {
                "detail": f"Workflow notification {nid} not found"
            }
            resp.text = f"Workflow notification {nid} not found"
            return resp

        if url_str.endswith("/notifications"):
            p = params or {}
            items = []
            for n in TEST_NOTIFICATIONS.values():
                hdr = dict(n["header"])
                hdr["attributes"] = dict(n.get("attributes", {}))
                if (
                    p.get("message_type")
                    and hdr["message_type"] != str(p["message_type"]).upper()
                ):
                    continue
                if (
                    p.get("recipient")
                    and hdr["recipient_role"] != str(p["recipient"]).upper()
                ):
                    continue
                items.append(hdr)
            resp.status_code = 200
            resp.json.return_value = items
            resp.text = json.dumps(items)
            return resp

        resp.status_code = 200
        resp.json.return_value = []
        resp.text = "[]"
        return resp

    def mock_post(_url: str, **kwargs: Any) -> MagicMock:
        resp = MagicMock()
        body = kwargs.get("json") or {}
        raw_nid = (
            body.get("notification_id")
            or body.get("RESPOND_Input", {})
            .get("InputParameters", {})
            .get("NID")
            or body.get("SETATTRTEXT_Input", {})
            .get("InputParameters", {})
            .get("NID")
            or 0
        )
        nid = int(raw_nid)
        if nid and nid not in TEST_NOTIFICATIONS:
            resp.status_code = 404
            resp.json.return_value = {
                "detail": f"Workflow notification {nid} not found"
            }
            resp.text = f"Workflow notification {nid} not found"
            return resp
        resp.status_code = 200
        resp.json.return_value = {
            "status": "SUCCESS",
            "execution_path": "REST",
            "notification_id": nid,
            "message": "Response recorded via ISG REST",
        }
        resp.text = json.dumps({"status": "SUCCESS"})
        return resp

    mock_http.get.side_effect = mock_get
    mock_http.post.side_effect = mock_post
    return mock_http


@pytest.fixture(name="mock_workflow_client")
def fixture_mock_workflow_client(
    mock_db_engine: MockDatabaseEngine,
) -> EBSWorkflowClient:
    """Fixture providing workflow client wired to mock database."""
    mock_http = create_mock_isg_http_client()
    return EBSWorkflowClient(engine=mock_db_engine, http_client=mock_http)


@pytest.fixture(name="mock_workflow_service")
def fixture_mock_workflow_service(
    mock_workflow_client: EBSWorkflowClient,
) -> WorkflowTriageService:
    """Fixture providing workflow triage service with mock client."""
    return WorkflowTriageService(client=mock_workflow_client)


@pytest.fixture(name="client")
def fixture_client(
    mock_workflow_service: WorkflowTriageService,
) -> Generator[TestClient, None, None]:
    """FastAPI test client for Workflow Agent worker service."""
    agent_app.dependency_overrides[get_triage_service] = (
        lambda: mock_workflow_service
    )
    with TestClient(agent_app) as test_cli:
        yield test_cli
    agent_app.dependency_overrides.clear()


@pytest.fixture(name="a2a_client")
def fixture_a2a_client() -> Generator[TestClient, None, None]:
    """FastAPI test client for A2A Gateway server."""
    with TestClient(a2a_app) as test_cli:
        yield test_cli


@pytest.fixture(name="mcp_client")
def fixture_mcp_client(
    mock_workflow_service: WorkflowTriageService,
) -> Generator[TestClient, None, None]:
    """FastAPI test client for MCP server."""
    mcp_app.dependency_overrides[get_mcp_service] = (
        lambda: mock_workflow_service
    )
    with TestClient(mcp_app) as test_cli:
        yield test_cli
    mcp_app.dependency_overrides.clear()
