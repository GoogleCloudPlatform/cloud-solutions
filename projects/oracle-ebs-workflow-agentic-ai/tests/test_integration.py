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

"""End-to-End Integration Tests for Oracle EBS Workflow Agent."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.a2a.a2a_server import app as gateway_app
from src.agents.workflow_agent import app as agent_app
from src.agents.workflow_agent import get_triage_service
from src.mcp.ebs_db_client import EBSDatabaseClient
from src.mcp.mcp_server import app as mcp_app
from src.workflow.client import EBSWorkflowClient
from src.workflow.service import WorkflowTriageService
from tests.conftest import MockDatabaseEngine


@pytest.fixture(name="agent_client")
def fixture_agent_client() -> TestClient:
    """Test client for core workflow agent wired with mock engine."""
    mock_db = MockDatabaseEngine()
    mock_http = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "SUCCESS"}
    mock_http.post.return_value = mock_response

    mock_client = EBSWorkflowClient(engine=mock_db, http_client=mock_http)
    mock_service = WorkflowTriageService(client=mock_client)

    agent_app.dependency_overrides[get_triage_service] = lambda: mock_service
    test_cli = TestClient(agent_app)
    return test_cli


@pytest.fixture(name="gateway_client")
def fixture_gateway_client() -> TestClient:
    """Test client for A2A Gateway microservice."""
    return TestClient(gateway_app)


# ==============================================================================
# Tier 1: Happy Paths
# ==============================================================================


def test_tier1_get_pending_worklist(agent_client: TestClient) -> None:
    """Tier 1 Happy Path: GET /worklist/pending returns active records."""
    mock_items = [
        {
            "notification_id": 10294,
            "message_type": "APEXP",
            "message_name": "EXPENSE_APPROVAL",
            "recipient_role": "JSMITH",
            "status": "OPEN",
            "subject": "Expense report for Q3 client visit",
            "begin_date": "2026-09-15 10:00:00",
            "due_date": "2026-09-22 10:00:00",
            "attributes": {
                "EXPENSE_AMOUNT": 1250.00,
                "JUSTIFICATION": "Client dinner",
            },
        }
    ]

    with patch.object(
        EBSDatabaseClient, "get_pending_notifications", return_value=mock_items
    ):
        response = agent_client.get(
            "/worklist/pending?recipient=JSMITH&limit=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["recipient"] == "JSMITH"
        assert data["items"][0]["notification_id"] == 10294
        assert data["items"][0]["amount"] == 1250.00


def test_tier1_post_worklist_respond_confirmed_plsql(
    agent_client: TestClient,
) -> None:
    """Tier 1 Happy Path: POST /worklist/respond executes certified PL/SQL."""
    payload = {
        "notification_ids": [1001],
        "action": "APPROVE",
        "comments": "Approved within travel limits",
        "responder": "JSMITH",
        "confirmed": True,
    }

    response = agent_client.post("/worklist/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["action"] == "APPROVE"
    assert len(data["processed_items"]) == 1
    assert data["processed_items"][0]["notification_id"] == 1001


def test_tier1_post_worklist_respond_unconfirmed_proposal(
    agent_client: TestClient,
) -> None:
    """Tier 1 Gate: POST /worklist/respond unconfirmed returns proposal."""
    payload = {
        "notification_ids": [1001],
        "action": "APPROVE",
        "comments": "Standard approval",
        "confirmed": False,
    }

    response = agent_client.post("/worklist/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CONFIRMATION_REQUIRED"
    assert data["requires_confirmation"] is True
    assert data["proposal"] is not None
    assert "confirm" in data["proposal"]["confirmation_prompt"].lower()


# ==============================================================================
# Tier 2: Validation Errors (HTTP 422)
# ==============================================================================


def test_tier2_missing_required_fields(agent_client: TestClient) -> None:
    """Tier 2 Validation: Missing required parameters yields HTTP 422."""
    response = agent_client.get("/worklist/pending")
    assert response.status_code == 422

    bad_payload = {"notification_ids": [1001]}
    post_res = agent_client.post("/worklist/respond", json=bad_payload)
    assert post_res.status_code == 422


def test_tier2_invalid_notification_type(agent_client: TestClient) -> None:
    """Tier 2 Validation: Invalid notification_type yields HTTP 422."""
    response = agent_client.get(
        "/worklist/pending?recipient=JSMITH&notification_type=INVALID_TYPE"
    )
    assert response.status_code == 422


def test_tier2_invalid_action_rejected(agent_client: TestClient) -> None:
    """Tier 2: Invalid actions like DELETE or DROP rejected with 422."""
    for bad_action in ("DELETE", "DROP"):
        res = agent_client.post(
            "/worklist/respond",
            json={
                "notification_ids": [1001],
                "action": bad_action,
                "confirmed": True,
            },
        )
        assert res.status_code == 422


# ==============================================================================
# Tier 3: Edge Cases & SQL Injection Prevention
# ==============================================================================


def test_tier3_non_existent_notification_id(agent_client: TestClient) -> None:
    """Tier 3 Edge Case: Non-existent notification ID raises HTTP 404."""
    response = agent_client.get("/notifications/99999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_tier3_sql_injection_escaped_in_bind_variables(
    agent_client: TestClient,
) -> None:
    """Tier 3: SQL injection strings safely handled via bind params."""
    sqli_recipient = "JSMITH' OR '1'='1"

    with patch.object(
        EBSDatabaseClient, "get_pending_notifications", return_value=[]
    ) as mock_get:
        response = agent_client.get(
            f"/worklist/pending?recipient={sqli_recipient}"
        )
        assert response.status_code == 200
        mock_get.assert_called_once_with(
            recipient=sqli_recipient,
            notification_type=None,
            max_amount=None,
            limit=50,
        )


# ==============================================================================
# MCP and Gateway Integration
# ==============================================================================


def test_mcp_tools_list() -> None:
    """Verify MCP tools list correctly."""
    client = TestClient(mcp_app)
    response = client.post("/tools/list")
    assert response.status_code == 200
    tool_names = [t["name"] for t in response.json()["tools"]]
    assert "ebs_list_pending_notifications" in tool_names
    assert "ebs_verify_policy" in tool_names
    assert "ebs_triage_workflow" in tool_names


def test_conversational_chat_flow(gateway_client: TestClient) -> None:
    """Verify conversational chat proxy returns formatted Markdown reply."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "total_count": 1,
        "recipient": "JSMITH",
        "items": [
            {
                "notification_id": 10294,
                "message_type": "APEXP",
                "subject": "Client travel expense",
                "amount": 1250.00,
            }
        ],
    }

    with (
        patch("src.a2a.proxy.get_ai_client") as mock_ai_client,
        patch("src.a2a.proxy.generate_content_with_models") as mock_generate,
        patch("src.a2a.formatter.get_ai_client") as mock_fmt_client,
        patch("src.a2a.formatter.generate_content_with_models") as mock_fmt_gen,
        patch("src.a2a.proxy.forward_request", return_value=mock_resp),
    ):
        mock_ai_client.return_value = MagicMock()
        mock_fmt_client.return_value = MagicMock()
        mock_generate.return_value = MagicMock(
            text='{"action": "triage", "recipient": "JSMITH"}'
        )
        mock_fmt_gen.return_value = MagicMock(
            text=(
                "### Pending Worklist\n"
                "- Notification **10294**: Client travel expense ($1,250.00)"
            )
        )
        response = gateway_client.post(
            "/chat",
            json={
                "message": "Triage my pending worklist",
                "recipient": "JSMITH",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "10294" in data["reply"]
