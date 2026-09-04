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

"""
Unit tests for Telemetry Simulator Service endpoints and business logic.
"""

import pytest
from fastapi.testclient import TestClient
from main import app, fleet_simulator


@pytest.fixture(autouse=True)
def reset_simulator_state():
    """Ensure clean state before each test."""
    # pylint: disable=protected-access
    fleet_simulator.running = False
    if (
        fleet_simulator._streaming_task
        and not fleet_simulator._streaming_task.done()
    ):
        fleet_simulator._streaming_task.cancel()
    fleet_simulator._reset_all_assets_normalized()
    fleet_simulator.message_timestamps.clear()


client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "aegis-telemetry-simulator"


def test_initial_status_stopped():
    response = client.get("/api/stream-status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stopped"
    assert data["running"] is False
    assert data["total_messages_last_5m"] == 0
    assert data["rate_msgs_per_sec_5m"] == 0.0
    assert len(data["active_anomalies"]) == 0
    assert data["assets_count"] == 15


def test_create_anomaly_fails_when_stopped():
    response = client.post("/api/create-anomoly")
    assert response.status_code == 400
    data = response.json()
    assert "stream is stopped" in data["detail"].lower()


def test_fix_anomaly_fails_when_stopped():
    response = client.post("/api/fix-anomoly", json={"asset_id": "Asset-04"})
    assert response.status_code == 400
    data = response.json()
    assert "stream is stopped" in data["detail"].lower()


def test_start_and_stop_stream():
    # Start stream
    start_resp = client.post("/api/start-stream")
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["status"] == "running"
    assert start_data["running"] is True

    # Status should now be running
    status_resp = client.get("/api/stream-status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "running"
    assert status_resp.json()["running"] is True

    # Stop stream
    stop_resp = client.post("/api/stop-stream")
    assert stop_resp.status_code == 200
    stop_data = stop_resp.json()
    assert stop_data["status"] == "stopped"
    assert stop_data["running"] is False


def test_create_and_fix_anomaly_flow():
    # Start stream
    client.post("/api/start-stream")

    # Create anomaly (random asset chosen)
    anomaly_resp = client.post("/api/create-anomoly")
    assert anomaly_resp.status_code == 200
    anomaly_data = anomaly_resp.json()
    assert anomaly_data["status"] == "anomaly_created"

    # Status should reflect the active anomaly
    status_resp = client.get("/api/stream-status")
    active_anomalies = status_resp.json()["active_anomalies"]
    assert len(active_anomalies) >= 1
    chosen_id = active_anomalies[0]

    # Fix anomaly on the chosen asset
    fix_resp = client.post("/api/fix-anomoly", json={"asset_id": chosen_id})
    assert fix_resp.status_code == 200
    fix_data = fix_resp.json()
    assert fix_data["status"] == "normalized"
    assert fix_data["asset_id"] == chosen_id
    assert fix_data["asset"]["is_anomaly"] is False
    assert fix_data["asset"]["status"] == "OK"
    assert fix_data["asset"]["cpu_utilization"] < 50.0

    # Status should no longer list the fixed anomaly
    status_resp2 = client.get("/api/stream-status")
    assert chosen_id not in status_resp2.json()["active_anomalies"]


def test_fix_anomaly_invalid_asset():
    client.post("/api/start-stream")
    response = client.post(
        "/api/fix-anomoly", json={"asset_id": "NonExistentAsset"}
    )
    assert response.status_code == 404
    assert "unknown asset_id" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
