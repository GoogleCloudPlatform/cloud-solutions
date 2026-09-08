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

"""Unit tests for state manager and router helpers."""

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("NO_GCE_CHECK", "true")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null")

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    # Probe whether FastAPI is installed before registering a test stub.
    import fastapi  # pylint: disable=unused-import
except ImportError:
    mock_fastapi = types.ModuleType("fastapi")

    class DummyAPIRouter:
        """Minimal router stub for offline unit testing."""

        def __init__(self, **_kwargs):
            pass

        def get(self, *_args, **_kwargs):
            return lambda fn: fn

        def post(self, *_args, **_kwargs):
            return lambda fn: fn

    class DummyHTTPException(Exception):
        """Minimal HTTPException stub for offline unit testing."""

        def __init__(self, status_code=500, detail=""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    mock_fastapi.APIRouter = DummyAPIRouter
    mock_fastapi.HTTPException = DummyHTTPException
    mock_fastapi.status = MagicMock(
        HTTP_400_BAD_REQUEST=400,
        HTTP_404_NOT_FOUND=404,
        HTTP_502_BAD_GATEWAY=502,
    )
    sys.modules["fastapi"] = mock_fastapi

# Local src/ directory and FastAPI stub must be set before importing modules.
# pylint: disable=wrong-import-position
from models import AgentMitigateRequest
from routers.agent import _normalize_mitigation_payload
from routers.analytics import generate_fallback_rows, get_predefined_queries
from state import TelemetryStateManager, normalize_utc_iso_timestamp

# pylint: enable=wrong-import-position


class TestStateAndRouters(unittest.TestCase):
    """Tests for TelemetryStateManager and HUD Backend router utilities."""

    def test_normalize_utc_iso_timestamp(self):
        res_z = normalize_utc_iso_timestamp("2026-09-21T10:15:30Z")
        self.assertTrue(res_z.endswith("Z"))
        self.assertIn("2026-09-21T10:15:30", res_z)

        res_empty = normalize_utc_iso_timestamp("")
        self.assertTrue(res_empty.endswith("Z"))

    def test_telemetry_state_manager_mitigation_cache(self):
        with patch.object(
            TelemetryStateManager, "_init_bigtable"
        ), patch.object(TelemetryStateManager, "_sync_initial_bigtable_state"):
            mgr = TelemetryStateManager()
            self.assertEqual(len(mgr.asset_ids), 15)
            payload = {"incident_id": "INC-TEST-01", "status": "MITIGATED"}
            mgr.store_mitigation("Asset-04", payload)
            self.assertEqual(mgr.get_mitigation("Asset-04"), payload)
            self.assertIn("Asset-04", mgr.get_all_mitigations())

    def test_predefined_queries_and_sql_loading(self):
        queries = get_predefined_queries("demo-proj", "analytics")
        self.assertEqual(len(queries), 3)
        query_ids = [q["query_id"] for q in queries]
        self.assertEqual(
            query_ids, ["fleet_stress", "thermal_spikes", "mitigation_roi"]
        )
        for q in queries:
            self.assertIn("SELECT", q["sql"])
            self.assertIn("demo-proj.analytics", q["sql"])

    def test_generate_fallback_rows(self):
        stress_rows = generate_fallback_rows("fleet_stress")
        self.assertEqual(len(stress_rows), 10)
        spike_rows = generate_fallback_rows("thermal_spikes")
        self.assertEqual(len(spike_rows), 12)
        roi_rows = generate_fallback_rows("mitigation_roi")
        self.assertEqual(len(roi_rows), 6)

    def test_normalize_mitigation_payload(self):
        req = AgentMitigateRequest(
            asset_id="Asset-04",
            cpu_utilization=95.5,
            temperature_c=92.0,
            event_type="THERMAL_OVERLOAD",
        )
        normalized = _normalize_mitigation_payload({}, req)
        self.assertEqual(normalized["asset_id"], "Asset-04")
        self.assertEqual(normalized["severity"], "CRITICAL")
        self.assertIn("tokenomics", normalized)
        self.assertIsInstance(normalized["mitigation_steps"], list)


if __name__ == "__main__":
    unittest.main()
