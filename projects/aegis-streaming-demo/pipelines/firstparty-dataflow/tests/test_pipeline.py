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
from unittest.mock import MagicMock

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
        """Mock window end boundary."""

        def to_utc_datetime(self) -> datetime:
            """Returns a fixed UTC datetime for window end."""
            return datetime(2026, 9, 8, 10, 0, 10, tzinfo=timezone.utc)

    def __init__(self) -> None:
        self.end = self.End()


class TestDataflowPipelineTransforms(unittest.TestCase):
    """Test suite verifying Apache Beam DoFns and transformation logic."""

    def setUp(self) -> None:
        self.parser = ParseTelemetryJsonDoFn()
        self.bq_formatter = FormatBigQueryRecordFn()
        self.aggregator = ComputeWindowAggregatesDoFn()
        self.bt_writer = WriteToBigtableDoFn(
            project_id="test-project",
            instance_id="aegis-bigtable",
            table_id="telemetry_metrics",
        )

    def test_parse_valid_json_string(self) -> None:
        """Verifies parsing a valid JSON string payload."""
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

    def test_parse_valid_json_bytes(self) -> None:
        """Verifies parsing a valid UTF-8 encoded JSON bytes payload."""
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

    def test_parse_invalid_json_skips_gracefully(self) -> None:
        """Verifies invalid JSON or missing asset_id payloads are skipped."""
        invalid_payloads = [
            "not-a-json",
            json.dumps({"no_asset_id": True}),
            b"{bad-bytes",
            12345,
        ]
        for payload in invalid_payloads:
            results = list(self.parser.process(payload))
            self.assertEqual(len(results), 0)

    def test_format_bigquery_record_nominal(self) -> None:
        """Verifies BigQuery record formatting for nominal telemetry."""
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

    def test_format_bigquery_record_critical_anomaly(self) -> None:
        """Verifies BigQuery record formatting flags CRITICAL anomalies."""
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

    def test_extract_asset_key(self) -> None:
        """Verifies extract_asset_key returns (asset_id, record) tuple."""
        item = {"asset_id": "Asset-05", "cpu_utilization": 22.0}
        key, val = extract_asset_key(item)
        self.assertEqual(key, "Asset-05")
        self.assertEqual(val, item)

    def test_window_aggregate_nominal(self) -> None:
        """Verifies 10s window aggregation for nominal OK records."""
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

    def test_window_aggregate_warning_and_empty(self) -> None:
        """Verifies WARNING threshold evaluation and empty window handling."""
        mock_window = MockWindow()
        empty_res = list(
            self.aggregator.process(("Asset-06", []), window_param=mock_window)
        )
        self.assertEqual(len(empty_res), 0)

        warning_records = [
            {
                "asset_id": "Asset-06",
                "cpu_utilization": 78.0,
                "temperature_c": 70.0,
                "pressure_psi": 50.0,
                "memory_utilization_pct": 60.0,
            }
        ]
        warn_res = list(
            self.aggregator.process(
                ("Asset-06", warning_records), window_param=mock_window
            )
        )
        self.assertEqual(len(warn_res), 1)
        self.assertEqual(warn_res[0]["status"], "WARNING")
        self.assertFalse(warn_res[0]["is_anomaly"])

    def test_window_aggregate_anomaly_trigger(self) -> None:
        """Verifies 10s window aggregation triggers CRITICAL anomaly status."""
        mock_window = MockWindow()
        records = [
            {
                "asset_id": "Asset-07",
                "cpu_utilization": 92.0,
                "temperature_c": 91.0,
                "pressure_psi": 142.0,
                "memory_utilization_pct": 90.0,
            },
            {
                "asset_id": "Asset-07",
                "cpu_utilization": 94.0,
                "temperature_c": 93.0,
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
        self.assertEqual(res["avg_temp"], 92.0)
        self.assertEqual(res["avg_pressure"], 144.0)
        self.assertEqual(res["status"], "CRITICAL")
        self.assertTrue(res["is_anomaly"])

    def test_bigtable_writer_offline_graceful(self) -> None:
        """Verifies WriteToBigtableDoFn passes elements through offline."""
        self.bt_writer.setup()
        self.bt_writer.start_bundle()
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
        self.bt_writer.finish_bundle()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["asset_id"], "Asset-08")

    def test_bigtable_writer_batches_rows_and_skips_stale_panes(self) -> None:
        """Verifies bundle batching and stale watermark pane suppression."""
        mock_table = MagicMock()
        mock_table.mutate_rows.return_value = []
        self.bt_writer.table = mock_table

        self.bt_writer.start_bundle()
        early_pane_1 = {
            "asset_id": "Asset-01",
            "avg_cpu": 30.0,
            "avg_temp": 50.0,
            "avg_pressure": 35.0,
            "avg_memory": 40.0,
            "status": "OK",
            "is_anomaly": False,
            "window_end": "2026-09-08T10:00:10Z",
            "ingestion_timestamp_ms": 1000,
            "record_count": 2,
        }
        early_pane_2 = {
            "asset_id": "Asset-01",
            "avg_cpu": 35.0,
            "avg_temp": 52.0,
            "avg_pressure": 36.0,
            "avg_memory": 42.0,
            "status": "OK",
            "is_anomaly": False,
            "window_end": "2026-09-08T10:00:10Z",
            "ingestion_timestamp_ms": 2000,
            "record_count": 4,
        }
        asset_2_pane = {
            "asset_id": "Asset-02",
            "avg_cpu": 40.0,
            "avg_temp": 55.0,
            "avg_pressure": 38.0,
            "avg_memory": 45.0,
            "status": "OK",
            "is_anomaly": False,
            "window_end": "2026-09-08T10:00:10Z",
            "ingestion_timestamp_ms": 2100,
            "record_count": 3,
        }
        list(self.bt_writer.process(early_pane_1))
        list(self.bt_writer.process(early_pane_2))
        list(self.bt_writer.process(asset_2_pane))
        self.bt_writer.finish_bundle()

        mock_table.mutate_rows.assert_called_once()
        mutated_rows = mock_table.mutate_rows.call_args[0][0]
        self.assertEqual(len(mutated_rows), 2)

        # Next bundle: newer window W2 for Asset-01 commits
        mock_table.mutate_rows.reset_mock()
        self.bt_writer.start_bundle()
        w2_pane = {
            "asset_id": "Asset-01",
            "avg_cpu": 36.0,
            "avg_temp": 53.0,
            "avg_pressure": 37.0,
            "avg_memory": 43.0,
            "status": "OK",
            "is_anomaly": False,
            "window_end": "2026-09-08T10:00:20Z",
            "ingestion_timestamp_ms": 11000,
            "record_count": 1,
        }
        list(self.bt_writer.process(w2_pane))
        self.bt_writer.finish_bundle()
        mock_table.mutate_rows.assert_called_once()

        # Subsequent bundle with delayed watermark pane for older window W1
        # must be skipped so it never overwrites W2
        mock_table.mutate_rows.reset_mock()
        self.bt_writer.start_bundle()
        stale_w1_watermark_pane = {
            "asset_id": "Asset-01",
            "avg_cpu": 35.0,
            "avg_temp": 52.0,
            "avg_pressure": 36.0,
            "avg_memory": 42.0,
            "status": "OK",
            "is_anomaly": False,
            "window_end": "2026-09-08T10:00:10Z",
            "ingestion_timestamp_ms": 9800,
            "record_count": 10,
        }
        list(self.bt_writer.process(stale_w1_watermark_pane))
        self.bt_writer.finish_bundle()
        mock_table.mutate_rows.assert_not_called()


if __name__ == "__main__":
    unittest.main()
