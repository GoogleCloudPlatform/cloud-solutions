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

"""Unit tests for the Project Aegis 1st-Party Cloud Dataflow Pipeline."""

import json
import os
import sys
import unittest
from datetime import datetime, timezone

os.environ.setdefault("NO_GCE_CHECK", "true")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null")

# Add pipeline src directory to sys.path
pipeline_src = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src")
)
if pipeline_src not in sys.path:
    sys.path.insert(0, pipeline_src)

# Local src/ directory must be added to sys.path before importing modules.
# pylint: disable-next=wrong-import-position
from pipeline import (
    ComputeWindowAggregatesDoFn,
    FormatBigQueryRecordFn,
    ParseTelemetryJsonDoFn,
    WriteToBigtableDoFn,
    extract_asset_key,
)


class MockWindow:
    """Mock Beam window for testing window parameter extraction."""

    class End:
        def to_utc_datetime(self):
            return datetime(2026, 9, 8, 10, 0, 10, tzinfo=timezone.utc)

    def __init__(self):
        self.end = self.End()


class TestDataflowPipelineTransforms(unittest.TestCase):
    """Test suite verifying Apache Beam DoFns and transformation logic."""

    def setUp(self):
        self.parser = ParseTelemetryJsonDoFn()
        self.bq_formatter = FormatBigQueryRecordFn()
        self.aggregator = ComputeWindowAggregatesDoFn()
        self.bt_writer = WriteToBigtableDoFn(
            project_id="test-project",
            instance_id="aegis-bigtable",
            table_id="telemetry_metrics",
        )

    def test_parse_valid_json_string(self):
        raw_msg = json.dumps(
            {
                "asset_id": "Asset-01",
                "timestamp": "2026-09-08T10:00:00Z",
                "cpu_utilization": 42.5,
                "temperature_c": 55.0,
                "pressure_psi": 99.0,
                "memory_utilization_pct": 50.0,
                "status": "OK",
            }
        )
        results = list(self.parser.process(raw_msg))
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["asset_id"], "Asset-01")
        self.assertEqual(res["cpu_utilization"], 42.5)
        self.assertEqual(res["temperature_c"], 55.0)
        self.assertEqual(res["status"], "OK")

    def test_parse_valid_json_bytes(self):
        raw_msg = json.dumps(
            {
                "asset_id": "Asset-02",
                "timestamp": "2026-09-08T10:00:00.000Z",
                "cpu_utilization": 95.0,
                "temperature_c": 88.0,
                "pressure_psi": 145.0,
                "memory_utilization_pct": 85.0,
                "status": "CRITICAL",
            }
        ).encode("utf-8")
        results = list(self.parser.process(raw_msg))
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["asset_id"], "Asset-02")
        self.assertEqual(res["cpu_utilization"], 95.0)

    def test_parse_invalid_json_skips_gracefully(self):
        invalid_payloads = [
            "not-a-json",
            json.dumps({"no_asset_id": True}),
            b"{bad-bytes",
            12345,
        ]
        for payload in invalid_payloads:
            results = list(self.parser.process(payload))
            self.assertEqual(len(results), 0)

    def test_format_bigquery_record_nominal(self):
        record = {
            "asset_id": "Asset-03",
            "timestamp": "2026-09-08T10:00:00Z",
            "cpu_utilization": 30.0,
            "temperature_c": 45.0,
            "pressure_psi": 100.0,
            "memory_utilization_pct": 40.0,
            "status": "OK",
        }
        results = list(self.bq_formatter.process(record))
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertFalse(res["is_anomaly"])
        self.assertEqual(res["status"], "OK")

    def test_format_bigquery_record_critical_anomaly(self):
        record = {
            "asset_id": "Asset-04",
            "timestamp": "2026-09-08T10:00:00Z",
            "cpu_utilization": 96.5,
            "temperature_c": 92.0,
            "pressure_psi": 155.0,
            "memory_utilization_pct": 88.0,
            "status": "CRITICAL",
        }
        results = list(self.bq_formatter.process(record))
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertTrue(res["is_anomaly"])
        self.assertEqual(res["status"], "CRITICAL")

    def test_extract_asset_key(self):
        item = {"asset_id": "Asset-05", "cpu_utilization": 22.0}
        key, val = extract_asset_key(item)
        self.assertEqual(key, "Asset-05")
        self.assertEqual(val, item)

    def test_window_aggregate_nominal(self):
        mock_window = MockWindow()
        records = [
            {
                "asset_id": "Asset-06",
                "cpu_utilization": 20.0,
                "temperature_c": 50.0,
                "pressure_psi": 30.0,
                "memory_utilization_pct": 40.0,
            },
            {
                "asset_id": "Asset-06",
                "cpu_utilization": 40.0,
                "temperature_c": 60.0,
                "pressure_psi": 40.0,
                "memory_utilization_pct": 60.0,
            },
        ]
        results = list(
            self.aggregator.process(
                ("Asset-06", records), window_param=mock_window
            )
        )
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["asset_id"], "Asset-06")
        self.assertEqual(res["avg_cpu"], 30.0)
        self.assertEqual(res["avg_temp"], 55.0)
        self.assertEqual(res["avg_pressure"], 35.0)
        self.assertEqual(res["avg_memory"], 50.0)
        self.assertEqual(res["status"], "OK")
        self.assertFalse(res["is_anomaly"])
        self.assertEqual(res["record_count"], 2)

    def test_window_aggregate_anomaly_trigger(self):
        mock_window = MockWindow()
        records = [
            {
                "asset_id": "Asset-07",
                "cpu_utilization": 92.0,
                "temperature_c": 88.0,
                "pressure_psi": 142.0,
                "memory_utilization_pct": 90.0,
            },
            {
                "asset_id": "Asset-07",
                "cpu_utilization": 94.0,
                "temperature_c": 90.0,
                "pressure_psi": 146.0,
                "memory_utilization_pct": 92.0,
            },
        ]
        results = list(
            self.aggregator.process(
                ("Asset-07", records), window_param=mock_window
            )
        )
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["asset_id"], "Asset-07")
        self.assertEqual(res["avg_cpu"], 93.0)
        self.assertEqual(res["avg_temp"], 89.0)
        self.assertEqual(res["avg_pressure"], 144.0)
        self.assertEqual(res["status"], "CRITICAL")
        self.assertTrue(res["is_anomaly"])

    def test_bigtable_writer_offline_graceful(self):
        self.bt_writer.setup()
        element = {
            "asset_id": "Asset-08",
            "avg_cpu": 32.5,
            "avg_temp": 52.0,
            "avg_pressure": 35.0,
            "avg_memory": 44.0,
            "status": "OK",
            "is_anomaly": False,
            "window_end": "2026-09-08T10:00:10Z",
        }
        # Offline mode without live Bigtable instance passes through cleanly
        results = list(self.bt_writer.process(element))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["asset_id"], "Asset-08")


if __name__ == "__main__":
    unittest.main()
