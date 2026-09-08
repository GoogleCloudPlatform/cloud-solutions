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

"""Unit tests for pluggable pipeline controller clients."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("NO_GCE_CHECK", "true")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null")

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Local src/ directory must be added to sys.path before importing modules.
# pylint: disable=wrong-import-position
from pipeline_clients.continuous_query_client import (
    ContinuousQueryPipelineClient,
    _load_continuous_sql,
)
from pipeline_clients.dataflow_client import DataflowPipelineClient
from pipeline_clients.dataproc_client import DataprocPipelineClient
from pipeline_clients.factory import get_pipeline_client

# pylint: enable=wrong-import-position


class TestPipelineClients(unittest.TestCase):
    """Verifies factory instantiation and client behaviors."""

    def test_factory_default_dataproc(self):
        client = get_pipeline_client("dataproc")
        self.assertIsInstance(client, DataprocPipelineClient)
        self.assertEqual(client.engine_name, "dataproc")

    def test_factory_dataflow(self):
        client = get_pipeline_client("dataflow")
        self.assertIsInstance(client, DataflowPipelineClient)
        self.assertEqual(client.engine_name, "dataflow")

    def test_factory_bq_continuous(self):
        client = get_pipeline_client("bq_continuous")
        self.assertIsInstance(client, ContinuousQueryPipelineClient)
        self.assertEqual(client.engine_name, "bq_continuous")

    def test_dataproc_client_status(self):
        client = DataprocPipelineClient()
        status = client.get_status("test-project", "us-central1")
        self.assertIn("status", status)
        self.assertEqual(status["engine"], "dataproc")

    def test_dataflow_client_status(self):
        client = DataflowPipelineClient()
        status = client.get_status("test-project", "us-central1")
        self.assertIn("status", status)
        self.assertEqual(status["engine"], "dataflow")

    def test_dataflow_client_start_stop(self):
        client = DataflowPipelineClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "job": {
                "id": "job-12345",
                "name": "aegis-dataflow-streaming-test",
                "currentState": "JOB_STATE_STARTING",
            }
        }
        mock_http_client = MagicMock()
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.post.return_value = mock_resp
        mock_http_client.get.return_value = mock_resp

        with patch.object(
            client,
            "_get_auth_headers",
            return_value={"Authorization": "Bearer test"},
        ), patch("httpx.Client", return_value=mock_http_client):
            start_res = client.start_pipeline("test-project", "us-central1")
            self.assertEqual(start_res["status"], "PENDING")
            self.assertEqual(start_res["engine"], "dataflow")
            self.assertEqual(start_res["job_id"], "job-12345")

            stop_res = client.stop_pipeline("test-project", "us-central1")
            self.assertEqual(stop_res["status"], "STOPPED")
            self.assertEqual(stop_res["engine"], "dataflow")

    def test_cq_client_start_stop(self):
        sql = _load_continuous_sql()
        self.assertTrue(sql.startswith("SELECT"))
        self.assertIn("`{project_id}.{dataset_id}.telemetry_events`", sql)

        client = ContinuousQueryPipelineClient()
        start_res = client.start_pipeline("test-project", "us-central1")
        self.assertEqual(start_res["status"], "PENDING")
        self.assertEqual(start_res["engine"], "bq_continuous")

        refreshed = client.refresh_status_sync("test-project", "us-central1")
        self.assertEqual(refreshed["status"], "RUNNING")
        self.assertEqual(refreshed["engine"], "bq_continuous")

        stop_res = client.stop_pipeline("test-project", "us-central1")
        self.assertEqual(stop_res["status"], "STOPPED")
        self.assertEqual(stop_res["engine"], "bq_continuous")

        stopped_refreshed = client.refresh_status_sync(
            "test-project", "us-central1"
        )
        self.assertEqual(stopped_refreshed["status"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
