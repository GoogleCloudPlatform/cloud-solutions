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

"""End-to-end API tests for the Workflow Agent Worker microservice."""

from fastapi.testclient import TestClient
from src.agents.workflow_agent import register_with_a2a


def test_agent_health(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_notifications_endpoint(client: TestClient) -> None:
    """Test notifications listing API."""
    response = client.get("/notifications?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["count"] >= 4


def test_get_notification_detail_endpoint(client: TestClient) -> None:
    """Test notification detail lookup API."""
    response = client.get("/notifications/1001")
    assert response.status_code == 200
    data = response.json()
    assert data["header"]["notification_id"] == 1001
    assert data["attributes"]["HAS_RECEIPTS"] == "N"


def test_get_notification_not_found(client: TestClient) -> None:
    """Verify explicit HTTP 404 when notification does not exist."""
    response = client.get("/notifications/9999")
    assert response.status_code == 404
    assert "9999 not found" in response.json()["detail"]


def test_get_notification_invalid_id(client: TestClient) -> None:
    """Verify explicit HTTP 422 on negative notification ID."""
    response = client.get("/notifications/-10")
    assert response.status_code == 422


def test_verify_policy_endpoint(client: TestClient) -> None:
    """Test batch policy evaluation endpoint."""
    payload = {"notification_ids": [1001, 2001]}
    response = client.post("/verify-policy", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_evaluated"] == 2
    assert data["high_risk_count"] == 1


def test_verify_policy_non_existent_nid(client: TestClient) -> None:
    """Verify explicit HTTP 404 when notification does not exist."""
    payload = {"notification_ids": [99999]}
    response = client.post("/verify-policy", json=payload)
    assert response.status_code == 404
    assert "99999 not found" in response.json()["detail"]


def test_respond_worklist_invalid_action(client: TestClient) -> None:
    """Verify explicit HTTP 422 on invalid action parameter."""
    payload = {
        "action": "INVALID_ACTION",
        "notification_ids": [1001],
    }
    response = client.post("/worklist/respond", json=payload)
    assert response.status_code == 422


def test_triage_endpoint(client: TestClient) -> None:
    """Test comprehensive triage endpoint."""
    response = client.get("/triage")
    assert response.status_code == 200
    data = response.json()
    assert data["total_pending"] >= 4
    assert "markdown_table" in data
    assert "| NID |" in data["markdown_table"]


def test_approve_confirmation_gate(client: TestClient) -> None:
    """Test approve endpoint halts at confirmation gate when unconfirmed."""
    payload = {
        "action": "APPROVE",
        "notification_ids": [1001],
        "confirmed": False,
    }
    response = client.post("/approve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CONFIRMATION_REQUIRED"
    assert data["required_confirmation_flag"] is True

    # Now provide confirmation
    payload["confirmed"] = True
    res_confirmed = client.post("/approve", json=payload)
    assert res_confirmed.status_code == 200
    data_conf = res_confirmed.json()
    assert data_conf["status"] == "COMPLETED"
    assert data_conf["results"][0]["status"] == "SUCCESS"


def test_reject_confirmation_gate(client: TestClient) -> None:
    """Test reject endpoint halts at confirmation gate when unconfirmed."""
    payload = {
        "action": "REJECT",
        "notification_ids": [2002],
        "confirmed": False,
    }
    response = client.post("/reject", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CONFIRMATION_REQUIRED"

    payload["confirmed"] = True
    res_confirmed = client.post("/reject", json=payload)
    assert res_confirmed.status_code == 200
    assert res_confirmed.json()["status"] == "COMPLETED"


def test_direct_respond_endpoint(client: TestClient) -> None:
    """Test direct response API."""
    payload = {
        "nid": 1001,
        "action": "APPROVE",
        "comment": "Direct respond test",
        "path": "PLSQL",
    }
    response = client.post("/respond", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"


def test_register_with_a2a_skip() -> None:
    """Test auto-registration skips gracefully when server is offline."""
    success = register_with_a2a("http://127.0.0.1:54321")
    assert success is False
