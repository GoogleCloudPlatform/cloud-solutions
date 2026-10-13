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

"""Unit tests for the certified Oracle EBS Workflow Client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from src.a2a.schemas import NotificationItem
from src.mcp.ebs_rest_client import EBSISGWorkflowRestClient
from src.workflow.client import EBSWorkflowClient


def test_list_notifications_all(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test retrieving all open workflow notifications."""
    items = mock_workflow_client.list_notifications()
    assert len(items) >= 4
    assert any(item.notification_id == 1001 for item in items)
    assert any(item.notification_id == 2001 for item in items)


def test_list_notifications_by_type(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test filtering notifications by message_type."""
    items = mock_workflow_client.list_notifications(message_type="POAPPR")
    assert all(item.message_type == "POAPPR" for item in items)
    assert any(item.notification_id == 2001 for item in items)


def test_get_notification_found(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test fetching an existing notification by ID."""
    item = mock_workflow_client.get_notification(1001)
    assert item.notification_id == 1001
    assert item.message_type == "APEXP"


def test_get_notification_not_found(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test explicit HTTP 404 raised when notification does not exist."""
    with pytest.raises(HTTPException) as exc_info:
        mock_workflow_client.get_notification(9999)
    assert exc_info.value.status_code == 404
    assert "9999 not found" in exc_info.value.detail


def test_get_notification_invalid_id(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test explicit HTTP 422 raised on non-positive notification ID."""
    with pytest.raises(HTTPException) as exc_info:
        mock_workflow_client.get_notification(-5)
    assert exc_info.value.status_code == 422


def test_get_notification_attributes(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test fetching attribute dictionary for an existing notification."""
    attrs = mock_workflow_client.get_notification_attributes(1001)
    assert attrs.get("HAS_RECEIPTS") == "N"
    assert attrs.get("EXP_REPORT_TOTAL") == 1500.0


def test_get_notification_detail(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test composite notification header and attributes detail object."""
    detail = mock_workflow_client.get_notification_detail(2001)
    assert detail.header.notification_id == 2001
    assert detail.attributes.get("VENDOR_STATUS") == "APPROVED"


def test_respond_via_plsql_certified(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test Path A PL/SQL execution with apps.wf_notification.respond."""
    res = mock_workflow_client.respond_via_plsql(
        nid=1001,
        action="APPROVE",
        comment="Approved by manager",
        responder="SYSADMIN",
    )
    assert res["status"] == "SUCCESS"
    assert res["execution_path"] == "PLSQL"
    assert res["notification_id"] == 1001


def test_respond_via_rest_certified(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test Path B certified ISG REST execution."""
    res = mock_workflow_client.respond_via_rest(
        nid=2001,
        action="REJECT",
        comment="Vendor unapproved",
        responder="MGR",
    )
    assert res["status"] == "SUCCESS"
    assert res["execution_path"] == "REST"
    assert res["action"] == "REJECT"


def test_respond_invalid_action(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test rejection of non-certified response action."""
    with pytest.raises(HTTPException) as exc_info:
        mock_workflow_client.respond(
            nid=1001, action="CANCEL", comment="Invalid"
        )
    assert exc_info.value.status_code == 422


def test_respond_invalid_path(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test rejection of unsupported integration path."""
    with pytest.raises(HTTPException) as exc_info:
        mock_workflow_client.respond(
            nid=1001, action="APPROVE", comment="Ok", path="UNSUPPORTED"
        )
    assert exc_info.value.status_code == 422


def test_respond_default_path_is_rest(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test default execution path for respond is REST (Primary)."""
    res = mock_workflow_client.respond(
        nid=1001, action="APPROVE", comment="Primary REST test"
    )
    assert res["status"] == "SUCCESS"
    assert res["execution_path"] == "REST"
    assert res["notification_id"] == 1001


def test_list_notifications_isg_rest_failover_to_plsql(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test transparent fallback to PL/SQL query on ISG REST error."""
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.ConnectError("ISG service unreachable")
    mock_workflow_client.set_http_client(mock_http)

    items = mock_workflow_client.list_notifications()
    assert len(items) >= 4
    assert any(item.notification_id == 1001 for item in items)


def test_get_notification_isg_rest_failover_to_plsql(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test transparent fallback to PL/SQL for get_notification on error."""
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.ConnectError("ISG service unreachable")
    mock_workflow_client.set_http_client(mock_http)

    item = mock_workflow_client.get_notification(1001)
    assert item.notification_id == 1001
    assert item.message_type == "APEXP"


def test_get_notification_attributes_isg_rest_failover_to_plsql(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test transparent fallback to PL/SQL for attributes on error."""
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.ConnectError("ISG service unreachable")
    mock_workflow_client.set_http_client(mock_http)

    attrs = mock_workflow_client.get_notification_attributes(1001)
    assert attrs.get("EXP_REPORT_TOTAL") == 1500.0


def test_respond_rest_failover_to_plsql(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test transparent fallback to PL/SQL API when ISG REST fails."""
    mock_http = MagicMock()
    mock_resp_get = MagicMock()
    mock_resp_get.status_code = 200
    mock_resp_get.json.return_value = {
        "notification_id": 1001,
        "message_type": "APEXP",
        "recipient_role": "JDOE",
        "status": "OPEN",
    }
    mock_http.get.return_value = mock_resp_get
    mock_http.post.side_effect = httpx.ConnectError("ISG gateway timed out")
    mock_workflow_client.set_http_client(mock_http)

    res = mock_workflow_client.respond(
        nid=1001,
        action="APPROVE",
        comment="Fallback to PLSQL test",
        path="REST",
    )
    assert res["status"] == "SUCCESS"
    assert res["execution_path"] == "PLSQL"
    assert res["notification_id"] == 1001


def test_ebs_isg_rest_client_endpoints() -> None:
    """Test EBSISGWorkflowRestClient sync and URL methods."""
    client = EBSISGWorkflowRestClient(base_url="http://127.0.0.1:8000")
    assert (
        client.get_endpoint_url()
        == "http://127.0.0.1:8000/webservices/rest/wf/respond"
    )

    with pytest.raises(HTTPException) as exc_info:
        client.get_notification_sync(0)
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        client.get_notification_attributes_sync(-1)
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        client.respond_to_notification_sync(
            nid=1001,
            action="INVALID",
            comment="test",
            user_name="USER",
        )
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        client.list_notifications_sync(limit=0)
    assert exc_info.value.status_code == 422


def test_respond_via_plsql_and_rest_closed_raises(
    mock_workflow_client: EBSWorkflowClient,
) -> None:
    """Test both PLSQL and REST paths reject already-CLOSED notifications."""
    closed_item = NotificationItem(
        notification_id=7119699,
        message_type="POAPPRV",
        message_name="EMAIL_PO_PDF",
        recipient_role="ADHOC245476943274117150PO",
        status="CLOSED",
        subject="Standard Purchase Order",
        amount=1200.0,
    )
    with patch.object(
        mock_workflow_client, "get_notification", return_value=closed_item
    ):
        for path_mode in ("REST", "PLSQL"):
            for act, verb in (("APPROVE", "approved"), ("REJECT", "rejected")):
                with pytest.raises(RuntimeError) as exc_info:
                    mock_workflow_client.respond(
                        nid=7119699,
                        action=act,
                        comment="Test closed guard",
                        path=path_mode,
                    )
                assert "already CLOSED" in str(exc_info.value)
                assert f"cannot be {verb}" in str(exc_info.value)


def test_list_notifications_isg_404_falls_back_and_respond_still_uses_rest(
    mock_workflow_client: EBSWorkflowClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ISG 404 on GET /notifications falls back and respond uses REST."""
    client = EBSWorkflowClient(engine=mock_workflow_client.engine)

    def _raise_404(**_kwargs: object) -> list[dict[str, object]]:
        raise HTTPException(
            status_code=404, detail="ISG 404 on collection GET"
        )

    monkeypatch.setattr(
        client.rest_client,
        "list_notifications_sync",
        _raise_404,
    )
    items = client.list_notifications(recipient="JDOE")
    assert len(items) >= 1

    rest_called = False

    def _mock_rest_respond(**_kwargs: object) -> dict[str, str]:
        nonlocal rest_called
        rest_called = True
        return {"status": "SUCCESS"}

    monkeypatch.setattr(
        client.rest_client,
        "respond_to_notification_sync",
        _mock_rest_respond,
    )
    monkeypatch.setattr(
        client,
        "get_notification",
        lambda nid: (
            mock_workflow_client.get_notification(nid)
            if not rest_called
            else mock_workflow_client.get_notification(nid).model_copy(
                update={"status": "CLOSED"}
            )
        ),
    )
    res = client.respond(
        nid=1001, action="APPROVE", comment="OK", path="REST"
    )
    assert rest_called is True
    assert res["execution_path"] == "REST"


def test_list_notifications_populates_risk_on_rest_and_plsql_paths(
    mock_workflow_client: EBSWorkflowClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify REST and PL/SQL populate risk for APEXP, POAPPR, and REQAPPR."""
    client = mock_workflow_client
    monkeypatch.setattr(client, "_isg_query_supported", False)
    plsql_items = {
        it.notification_id: it for it in client.list_notifications()
    }
    assert plsql_items[1001].message_type == "APEXP"
    assert plsql_items[1001].risk_level == "HIGH"
    assert plsql_items[1001].recommended_action == "ESCALATE"
    assert plsql_items[1002].message_type == "APEXP"
    assert plsql_items[1002].risk_level == "LOW"
    assert plsql_items[1002].recommended_action == "APPROVE"
    assert plsql_items[2001].message_type == "POAPPR"
    assert plsql_items[2001].risk_level == "MEDIUM"
    assert plsql_items[2001].recommended_action == "APPROVE"
    assert plsql_items[2002].message_type == "POAPPR"
    assert plsql_items[2002].risk_level == "CRITICAL"
    assert plsql_items[2002].recommended_action == "REJECT"
    assert plsql_items[3001].message_type == "REQAPPR"
    assert plsql_items[3001].risk_level == "LOW"
    assert plsql_items[3001].recommended_action == "APPROVE"

    monkeypatch.setattr(client, "_isg_query_supported", True)
    monkeypatch.setattr(
        client.rest_client,
        "list_notifications_sync",
        lambda **_kwargs: [
            {
                "notification_id": 1005,
                "message_type": "APEXP",
                "recipient_role": "OPERATIONS",
                "status": "OPEN",
                "subject": "Executive Travel Expense",
                "amount": 6500.0,
            },
            {
                "notification_id": 2002,
                "message_type": "POAPPRV",
                "recipient_role": "OPERATIONS",
                "status": "OPEN",
                "subject": "Vision Operations - Standard Purchase Order 6502",
                "amount": 440000.0,
            },
            {
                "notification_id": 3003,
                "message_type": "REQAPPR",
                "recipient_role": "OPERATIONS",
                "status": "OPEN",
                "subject": "Requisition for IT Equipment",
                "amount": 9600.0,
            },
        ],
    )
    rest_items = {
        it.notification_id: it
        for it in client.list_notifications(recipient="OPERATIONS")
    }
    for nid in (1005, 2002, 3003):
        assert rest_items[nid].risk_level == "HIGH"
        assert rest_items[nid].recommended_action == "ESCALATE"
