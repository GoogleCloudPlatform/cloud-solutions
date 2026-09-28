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

"""Unit tests for Telemetry Simulator Service endpoints and business logic."""

import os
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("NO_GCE_CHECK", "true")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null")

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Local src/ directory must be added to sys.path before importing modules.
# pylint: disable-next=wrong-import-position
from main import app, fleet_simulator


class TestSimulatorService(unittest.TestCase):
    """Test suite for Telemetry Simulator endpoints."""

    # Resetting internal simulator task and state attributes between unit tests.
    # pylint: disable=protected-access
    def setUp(self) -> None:
        """Ensure clean state before each test."""
        fleet_simulator.running = False
        if (
            fleet_simulator._streaming_task
            and not fleet_simulator._streaming_task.done()
        ):
            fleet_simulator._streaming_task.cancel()
        fleet_simulator._reset_all_assets_normalized()
        fleet_simulator.message_timestamps.clear()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        """Stop background streaming task after each test."""
        fleet_simulator.running = False
        if (
            fleet_simulator._streaming_task
            and not fleet_simulator._streaming_task.done()
        ):
            fleet_simulator._streaming_task.cancel()

    # pylint: enable=protected-access

    def test_health_check(self) -> None:
        """Verifies /health returns 200 healthy response."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "aegis-telemetry-simulator")

    def test_initial_status_stopped(self) -> None:
        """Verifies initial stream status is stopped with 15 assets."""
        response = self.client.get("/api/stream-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "stopped")
        self.assertFalse(data["running"])
        self.assertEqual(data["total_messages_last_5m"], 0)
        self.assertEqual(data["rate_msgs_per_sec_5m"], 0.0)
        self.assertEqual(len(data["active_anomalies"]), 0)
        self.assertEqual(data["assets_count"], 15)

    def test_create_anomaly_fails_when_stopped(self) -> None:
        """Verifies /api/create-anomoly returns 400 when stream is stopped."""
        response = self.client.post("/api/create-anomoly")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("stream is stopped", data["detail"].lower())

    def test_fix_anomaly_empty_asset(self) -> None:
        """Verifies /api/fix-anomoly returns 400 when asset_id is empty."""
        response = self.client.post("/api/fix-anomoly", json={"asset_id": ""})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("asset_id must be provided", data["detail"].lower())

    def test_start_and_stop_stream(self) -> None:
        """Verifies starting and stopping the telemetry stream."""
        # Start stream
        start_resp = self.client.post("/api/start-stream")
        self.assertEqual(start_resp.status_code, 200)
        start_data = start_resp.json()
        self.assertEqual(start_data["status"], "running")
        self.assertTrue(start_data["running"])

        # Status should now be running
        status_resp = self.client.get("/api/stream-status")
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.json()["status"], "running")
        self.assertTrue(status_resp.json()["running"])

        # Stop stream
        stop_resp = self.client.post("/api/stop-stream")
        self.assertEqual(stop_resp.status_code, 200)
        stop_data = stop_resp.json()
        self.assertEqual(stop_data["status"], "stopped")
        self.assertFalse(stop_data["running"])

    def test_create_and_fix_anomaly_flow(self) -> None:
        """Verifies end-to-end anomaly creation and remediation flow."""
        # Start stream
        self.client.post("/api/start-stream")

        # Create anomaly (random asset chosen)
        anomaly_resp = self.client.post("/api/create-anomoly")
        self.assertEqual(anomaly_resp.status_code, 200)
        anomaly_data = anomaly_resp.json()
        self.assertEqual(anomaly_data["status"], "anomaly_created")

        # Status should reflect the active anomaly
        status_resp = self.client.get("/api/stream-status")
        active_anomalies = status_resp.json()["active_anomalies"]
        self.assertGreaterEqual(len(active_anomalies), 1)
        chosen_id = active_anomalies[0]

        # Fix anomaly on the chosen asset
        fix_resp = self.client.post(
            "/api/fix-anomoly", json={"asset_id": chosen_id}
        )
        self.assertEqual(fix_resp.status_code, 200)
        fix_data = fix_resp.json()
        self.assertEqual(fix_data["status"], "normalized")
        self.assertEqual(fix_data["asset_id"], chosen_id)
        self.assertFalse(fix_data["asset"]["is_anomaly"])
        self.assertEqual(fix_data["asset"]["status"], "OK")
        self.assertLess(fix_data["asset"]["cpu_utilization"], 50.0)

        # Status should no longer list the fixed anomaly
        status_resp2 = self.client.get("/api/stream-status")
        self.assertNotIn(chosen_id, status_resp2.json()["active_anomalies"])

    def test_fix_anomaly_invalid_asset(self) -> None:
        """Verifies /api/fix-anomoly returns 404 for unknown asset_id."""
        self.client.post("/api/start-stream")
        response = self.client.post(
            "/api/fix-anomoly", json={"asset_id": "NonExistentAsset"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
