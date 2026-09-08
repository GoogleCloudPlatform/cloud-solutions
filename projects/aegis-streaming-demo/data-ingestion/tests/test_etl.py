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

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Local src/ directory must be added to sys.path before importing ETL modules.
# pylint: disable-next=wrong-import-position
from aegis_etl import TELEMETRY_SCHEMA, parse_args  # noqa: E402


class TestTelemetrySchema(unittest.TestCase):
    """Test suite for PySpark telemetry schema definitions."""

    def test_telemetry_schema_field_names(self):
        """Test that schema defines all expected telemetry fields."""
        expected_fields = [
            "asset_id",
            "timestamp",
            "cpu_utilization",
            "temperature_c",
            "pressure_psi",
            "memory_utilization_pct",
            "status",
        ]
        field_names = [field.name for field in TELEMETRY_SCHEMA.fields]
        self.assertEqual(field_names, expected_fields)

    def test_telemetry_schema_types(self):
        """Test that field types match expected PySpark types."""
        type_map = {
            field.name: field.dataType.typeName()
            for field in TELEMETRY_SCHEMA.fields
        }
        self.assertEqual(type_map["asset_id"], "string")
        self.assertEqual(type_map["timestamp"], "string")
        self.assertEqual(type_map["cpu_utilization"], "double")
        self.assertEqual(type_map["temperature_c"], "double")
        self.assertEqual(type_map["pressure_psi"], "double")
        self.assertEqual(type_map["memory_utilization_pct"], "double")
        self.assertEqual(type_map["status"], "string")


class TestEtlArgParsing(unittest.TestCase):
    """Test suite for PySpark ETL CLI argument parser."""

    def test_default_argument_values(self):
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

    def test_custom_arguments(self):
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


if __name__ == "__main__":
    unittest.main()
