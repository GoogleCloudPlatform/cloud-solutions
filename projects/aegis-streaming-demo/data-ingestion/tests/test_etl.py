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

"""Unit tests for Dataproc Serverless PySpark ETL pipeline."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("NO_GCE_CHECK", "true")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null")

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Local src/ directory must be added to sys.path before importing ETL modules.
# pylint: disable-next=wrong-import-position
from aegis_etl import (  # noqa: E402
    _BT_TABLES,
    TELEMETRY_SCHEMA,
    _notify_agent_of_critical_anomalies,
    parse_args,
    write_batch_to_bigtable,
)


class _FakeSparkRow:
    """Mock pyspark.sql.Row supporting __getitem__ and asDict() without get."""

    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key: str):
        return self._data[key]

    def asDict(self) -> dict:  # pylint: disable=invalid-name
        """Convert row to dictionary like pyspark.sql.Row.asDict()."""
        return dict(self._data)


class TestWriteBatchToBigtable(unittest.TestCase):
    """Test suite for Bigtable foreachBatch sink with Spark Row objects."""

    def setUp(self) -> None:
        _BT_TABLES.clear()

    @patch.dict(
        "os.environ",
        {"AGENT_SERVICE_URL": "", "AGENT_ENDPOINT_URL": ""},
        clear=False,
    )
    @patch("aegis_etl.HAVE_BIGTABLE", True)
    @patch("aegis_etl.DirectRow")
    @patch("aegis_etl.bigtable")
    def test_write_batch_to_bigtable_handles_spark_rows_without_get(
        self, mock_bt_module, mock_direct_row
    ) -> None:
        """Test write_batch_to_bigtable converts Rows and sets timestamps."""
        older_row = _FakeSparkRow(
            {
                "asset_id": "Asset-01",
                "avg_cpu": 35.0,
                "avg_temp": 50.0,
                "avg_pressure": 40.0,
                "avg_memory": 45.0,
                "status": "OK",
                "is_anomaly": "false",
                "ingestion_timestamp_ms": 1700000000000,
                "window_end": "2026-09-24T12:00:00Z",
            }
        )
        fake_row = _FakeSparkRow(
            {
                "asset_id": "Asset-01",
                "avg_cpu": 97.5,
                "avg_temp": 95.0,
                "avg_pressure": 160.0,
                "avg_memory": 88.0,
                "status": "CRITICAL",
                "is_anomaly": "true",
                "ingestion_timestamp_ms": 1700000010500,
                "window_end": "2026-09-24T12:00:10Z",
            }
        )
        mock_batch_df = unittest.mock.MagicMock()
        mock_batch_df.collect.return_value = [fake_row, older_row]

        write_batch_to_bigtable(
            batch_df=mock_batch_df,
            batch_id=1,
            project_id="test-project",
            instance_id="test-bt",
            table_id="telemetry_metrics",
            column_family="metrics",
        )

        mock_bt_module.Client.assert_called_once_with(
            project="test-project", admin=False
        )
        mock_direct_row.assert_called_once_with(row_key=b"Asset-01")
        mock_row_obj = mock_direct_row.return_value
        cell_calls = {
            call.args[1]: call.args[2]
            for call in mock_row_obj.set_cell.call_args_list
        }
        self.assertEqual(cell_calls[b"status"], b"CRITICAL")
        self.assertEqual(
            cell_calls[b"ingestion_timestamp_ms"], b"1700000010500"
        )
        self.assertIn(b"db_insert_timestamp_ms", cell_calls)
        self.assertTrue(int(cell_calls[b"db_insert_timestamp_ms"].decode()) > 0)
        mock_instance = mock_bt_module.Client.return_value.instance.return_value
        mock_table = mock_instance.table.return_value
        mock_table.mutate_rows.assert_called_once()
        mutated_rows = mock_table.mutate_rows.call_args[0][0]
        self.assertEqual(len(mutated_rows), 1)

    @patch("urllib.request.urlopen")
    def test_notify_agent_skips_reasoning_engine_and_sends_http(
        self, mock_urlopen
    ) -> None:
        """Test _notify_agent_of_critical_anomalies with GEAP and HTTP URLs."""
        records = [
            {
                "asset_id": "Asset-04",
                "avg_cpu": 96.5,
                "avg_temp": 94.0,
                "avg_pressure": 150.0,
                "avg_memory": 85.0,
                "status": "CRITICAL",
                "is_anomaly": "true",
            }
        ]
        with patch.dict(
            "os.environ",
            {
                "AGENT_SERVICE_URL": (
                    "projects/test/locations/us-central1/reasoningEngines/123"
                )
            },
            clear=False,
        ):
            _notify_agent_of_critical_anomalies(records)
            mock_urlopen.assert_not_called()

        with patch.dict(
            "os.environ",
            {"AGENT_SERVICE_URL": "http://localhost:8000"},
            clear=False,
        ):
            _notify_agent_of_critical_anomalies(records)
            mock_urlopen.assert_called_once()
            req_obj = mock_urlopen.call_args.args[0]
            self.assertEqual(
                req_obj.full_url,
                "http://localhost:8000/api/agent/recommendation",
            )


class TestTelemetrySchema(unittest.TestCase):
    """Test suite for PySpark telemetry schema definitions."""

    def test_telemetry_schema_field_names(self) -> None:
        """Test that schema defines all expected telemetry fields."""
        expected_fields = [
            "asset_id",
            "timestamp",
            "ingestion_timestamp_ms",
            "cpu_utilization",
            "temperature_c",
            "pressure_psi",
            "memory_utilization_pct",
            "status",
        ]
        field_names = [field.name for field in TELEMETRY_SCHEMA.fields]
        self.assertEqual(field_names, expected_fields)

    def test_telemetry_schema_types(self) -> None:
        """Test that field types match expected PySpark types."""
        type_map = {
            field.name: field.dataType.typeName()
            for field in TELEMETRY_SCHEMA.fields
        }
        self.assertEqual(type_map["asset_id"], "string")
        self.assertEqual(type_map["timestamp"], "string")
        self.assertEqual(type_map["ingestion_timestamp_ms"], "long")
        self.assertEqual(type_map["cpu_utilization"], "double")
        self.assertEqual(type_map["temperature_c"], "double")
        self.assertEqual(type_map["pressure_psi"], "double")
        self.assertEqual(type_map["memory_utilization_pct"], "double")
        self.assertEqual(type_map["status"], "string")


class TestEtlArgParsing(unittest.TestCase):
    """Test suite for PySpark ETL CLI argument parser."""

    def test_default_argument_values(self) -> None:
        """Test default argument values when none are provided."""
        with patch.object(sys, "argv", ["aegis_etl.py"]):
            args = parse_args()
            self.assertEqual(args.source_type, "kafka")
            self.assertEqual(args.kafka_topic, "telemetry-raw")
            self.assertEqual(args.bigquery_dataset, "analytics")
            self.assertEqual(args.bigquery_table, "telemetry_events")
            self.assertEqual(args.bigtable_table, "telemetry_metrics")
            self.assertEqual(args.bigtable_column_family, "metrics")
            self.assertEqual(args.window_duration, "10 seconds")
            self.assertEqual(args.shuffle_partitions, 8)

    def test_custom_arguments(self) -> None:
        """Test parsing custom command-line arguments."""
        custom_argv = [
            "aegis_etl.py",
            "--project-id",
            "my-custom-project",
            "--source-type",
            "kafka",
            "--kafka-bootstrap-servers",
            "custom-bootstrap:9092",
            "--kafka-topic",
            "custom-topic",
            "--bigquery-dataset",
            "custom_dataset",
            "--bigquery-table",
            "custom_table",
            "--bigtable-instance",
            "custom-bt",
            "--window-duration",
            "30 seconds",
            "--shuffle-partitions",
            "16",
        ]
        with patch.object(sys, "argv", custom_argv):
            args = parse_args()
            self.assertEqual(args.project_id, "my-custom-project")
            self.assertEqual(
                args.kafka_bootstrap_servers, "custom-bootstrap:9092"
            )
            self.assertEqual(args.kafka_topic, "custom-topic")
            self.assertEqual(args.bigquery_dataset, "custom_dataset")
            self.assertEqual(args.bigquery_table, "custom_table")
            self.assertEqual(args.bigtable_instance, "custom-bt")
            self.assertEqual(args.window_duration, "30 seconds")
            self.assertEqual(args.shuffle_partitions, 16)


if __name__ == "__main__":
    unittest.main()
