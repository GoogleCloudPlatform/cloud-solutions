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

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("NO_GCE_CHECK", "true")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null")

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Local src/ directory must be added to sys.path before importing modules.
# pylint: disable=wrong-import-position
import state
from fastapi import HTTPException
from models import AgentApproveRequest, AgentMitigateRequest
from pipeline_clients.continuous_query_client import (
    ContinuousQueryPipelineClient,
    _load_continuous_sql,
)
from pipeline_clients.dataflow_client import DataflowPipelineClient
from pipeline_clients.dataproc_client import DataprocPipelineClient
from pipeline_clients.factory import get_pipeline_client
from routers import agent as agent_router
from routers import pipeline as pipeline_router

# pylint: enable=wrong-import-position


class TestPipelineClients(unittest.TestCase):
    """Verifies factory instantiation and client behaviors."""

    def test_factory_default_dataproc(self) -> None:
        """Verifies factory returns DataprocPipelineClient for 'dataproc'."""
        client = get_pipeline_client("dataproc")
        self.assertIsInstance(client, DataprocPipelineClient)
        self.assertEqual(client.engine_name, "dataproc")

    def test_factory_dataflow(self) -> None:
        """Verifies factory returns DataflowPipelineClient for 'dataflow'."""
        client = get_pipeline_client("dataflow")
        self.assertIsInstance(client, DataflowPipelineClient)
        self.assertEqual(client.engine_name, "dataflow")

    def test_factory_bq_continuous(self) -> None:
        """Verifies factory returns ContinuousQueryPipelineClient."""
        client = get_pipeline_client("bq_continuous")
        self.assertIsInstance(client, ContinuousQueryPipelineClient)
        self.assertEqual(client.engine_name, "bq_continuous")

    def test_dataproc_client_status(self) -> None:
        """Verifies default warm cluster status cache structure."""
        client = DataprocPipelineClient()
        status = client.get_status("test-project", "us-central1")
        self.assertIn("status", status)
        self.assertEqual(status["engine"], "dataproc")
        self.assertEqual(status["cluster_name"], "aegis-spark-cluster")

    def test_dataproc_client_start_stop(self) -> None:
        """Verifies submitting and cancelling a job on the warm cluster."""
        client = DataprocPipelineClient()
        mock_job_client = MagicMock()
        mock_job = MagicMock()
        mock_job.reference.job_id = "aegis-etl-20260924-093000"
        mock_job.status.state = "RUNNING"
        mock_job.status.state_start_time = None
        mock_job_client.list_jobs.return_value = [mock_job]

        mock_dp_module = MagicMock()
        mock_state_enum = MagicMock()
        mock_state_enum.name = "RUNNING"
        mock_dp_module.JobStatus.State.return_value = mock_state_enum

        with patch.object(
            client, "_get_client", return_value=mock_job_client
        ), patch(
            "pipeline_clients.dataproc_client.DATAPROC_AVAILABLE", True
        ), patch(
            "pipeline_clients.dataproc_client.dataproc_v1",
            mock_dp_module,
            create=True,
        ):
            start_res = client.start_pipeline("test-project", "us-central1")
            self.assertEqual(start_res["status"], "PENDING")
            self.assertEqual(start_res["engine"], "dataproc")
            self.assertEqual(start_res["cluster_name"], "aegis-spark-cluster")
            mock_job_client.submit_job.assert_called_once()

            refreshed = client.refresh_status_sync(
                "test-project", "us-central1"
            )
            self.assertEqual(refreshed["status"], "RUNNING")
            self.assertEqual(refreshed["job_id"], "aegis-etl-20260924-093000")

            stop_res = client.stop_pipeline("test-project", "us-central1")
            self.assertEqual(stop_res["status"], "STOPPED")
            self.assertEqual(stop_res["engine"], "dataproc")
            mock_job_client.cancel_job.assert_called_once()

    def test_dataproc_client_error_and_empty_states(self) -> None:
        """Verifies FAILED on job ERROR and STOPPED on empty job list."""
        client = DataprocPipelineClient()
        mock_job_client = MagicMock()
        mock_failed_job = MagicMock()
        mock_failed_job.reference.job_id = "aegis-etl-failed"
        mock_failed_job.status.state = "ERROR"
        mock_failed_job.status.details = "Container exited with non-zero code"
        mock_failed_job.status.state_start_time = None

        mock_dp_module = MagicMock()
        mock_state_enum = MagicMock()
        mock_state_enum.name = "ERROR"
        mock_dp_module.JobStatus.State.return_value = mock_state_enum

        with patch.object(
            client, "_get_client", return_value=mock_job_client
        ), patch(
            "pipeline_clients.dataproc_client.DATAPROC_AVAILABLE", True
        ), patch(
            "pipeline_clients.dataproc_client.dataproc_v1",
            mock_dp_module,
            create=True,
        ):
            mock_job_client.list_jobs.return_value = [mock_failed_job]
            failed_res = client.refresh_status_sync(
                "test-project", "us-central1"
            )
            self.assertEqual(failed_res["status"], "FAILED")
            self.assertEqual(failed_res["job_id"], "aegis-etl-failed")

            mock_job_client.list_jobs.return_value = []
            empty_res = client.refresh_status_sync(
                "test-project", "us-central1"
            )
            self.assertEqual(empty_res["status"], "STOPPED")
            self.assertIsNone(empty_res["job_id"])

    def test_dataflow_client_status(self) -> None:
        """Verifies DataflowPipelineClient default status structure."""
        client = DataflowPipelineClient()
        status = client.get_status("test-project", "us-central1")
        self.assertIn("status", status)
        self.assertEqual(status["engine"], "dataflow")

    def test_dataflow_client_start_stop(self) -> None:
        """Verifies Dataflow Flex Template launch, cancellation, and stop."""
        client = DataflowPipelineClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "jobs": [
                {
                    "id": "old-job-1",
                    "name": "aegis-dataflow-streaming-old",
                    "currentState": "JOB_STATE_RUNNING",
                }
            ],
            "job": {
                "id": "job-12345",
                "name": "aegis-dataflow-streaming-test",
                "currentState": "JOB_STATE_STARTING",
            },
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

            # Verify existing active job was cancelled before launching new job
            mock_http_client.put.assert_called_once()
            # Verify Flex Template launch uses named sub & n2-standard-2
            launch_call = mock_http_client.post.call_args_list[-1]
            launch_json = launch_call.kwargs["json"]["launchParameter"]
            expected_sub = (
                "projects/test-project/subscriptions/"
                "telemetry-raw-dataflow-sub"
            )
            self.assertEqual(
                launch_json["parameters"]["input_subscription"],
                expected_sub,
            )
            self.assertEqual(
                launch_json["parameters"]["trigger_interval_seconds"], "1"
            )
            self.assertEqual(
                launch_json["environment"]["machineType"], "n2-standard-2"
            )
            self.assertEqual(
                launch_json["environment"]["ipConfiguration"],
                "WORKER_IP_PRIVATE",
            )
            self.assertTrue(launch_json["environment"]["enableStreamingEngine"])

            stop_res = client.stop_pipeline("test-project", "us-central1")
            self.assertEqual(stop_res["status"], "STOPPED")
            self.assertEqual(stop_res["engine"], "dataflow")

    def test_cq_client_start_stop(self) -> None:
        """Verifies ContinuousQueryPipelineClient lifecycle transitions."""
        sql = _load_continuous_sql()
        self.assertTrue(sql.startswith("SELECT"))
        self.assertIn("`{project_id}.{dataset_id}.telemetry_events`", sql)

        client = ContinuousQueryPipelineClient()
        with patch.object(client, "_worker_loop"), patch.object(
            client, "_sync_window_aggregates_to_bigtable", return_value=0
        ):
            start_res = client.start_pipeline("test-project", "us-central1")
            self.assertEqual(start_res["status"], "PENDING")
            self.assertEqual(start_res["engine"], "bq_continuous")

            refreshed = client.refresh_status_sync(
                "test-project", "us-central1"
            )
            self.assertEqual(refreshed["status"], "RUNNING")
            self.assertEqual(refreshed["engine"], "bq_continuous")

            stop_res = client.stop_pipeline("test-project", "us-central1")
            self.assertEqual(stop_res["status"], "STOPPED")
            self.assertEqual(stop_res["engine"], "bq_continuous")

            stopped_refreshed = client.refresh_status_sync(
                "test-project", "us-central1"
            )
            self.assertEqual(stopped_refreshed["status"], "STOPPED")

    def test_state_manager_uses_latest_cell_filter(self) -> None:
        """Verifies Bigtable reads pass CellsColumnLimitFilter(1)."""
        filter_cls = state.CellsColumnLimitFilter or MagicMock(
            side_effect=lambda limit: MagicMock(limit=limit)
        )
        with patch.object(state, "CellsColumnLimitFilter", filter_cls):
            manager = state.TelemetryStateManager()
            mock_table = MagicMock()
            mock_table.read_rows.return_value = []
            mock_table.read_row.return_value = None
            manager.bt_table = mock_table

            manager.read_from_bigtable()
            mock_table.read_rows.assert_called_once()
            _, kwargs = mock_table.read_rows.call_args
            self.assertIn("filter_", kwargs)
            self.assertIsNotNone(kwargs["filter_"])

            manager.sync_simulator_running_from_bigtable()
            mock_table.read_row.assert_called_once()
            _, row_kwargs = mock_table.read_row.call_args
            self.assertIn("filter_", row_kwargs)
            self.assertIsNotNone(row_kwargs["filter_"])

    def test_pipeline_router_endpoints(self) -> None:
        """Verifies /api/pipeline/status, /start, and /stop router endpoints."""
        mock_client = MagicMock()
        mock_client.get_status.return_value = {
            "status": "RUNNING",
            "engine": "dataproc",
        }
        mock_client.start_pipeline.return_value = {
            "status": "PENDING",
            "engine": "dataproc",
        }
        mock_client.stop_pipeline.return_value = {
            "status": "STOPPED",
            "engine": "dataproc",
        }

        with patch(
            "routers.pipeline.get_pipeline_client", return_value=mock_client
        ):
            status_res = asyncio.run(pipeline_router.pipeline_status())
            self.assertEqual(status_res["status"], "RUNNING")

            start_res = asyncio.run(pipeline_router.start_pipeline())
            self.assertEqual(start_res["status"], "PENDING")

            stop_res = asyncio.run(pipeline_router.stop_pipeline())
            self.assertEqual(stop_res["status"], "STOPPED")

    def test_agent_router_recommendation_and_retrieval(self) -> None:
        """Verifies /api/agent/recommendation and recommendation getters."""
        req = AgentMitigateRequest(
            asset_id="Asset-04",
            cpu_utilization=96.2,
            temperature_c=94.5,
            event_type="CRITICAL_THERMAL_OVERLOAD",
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "incident_id": "INC-20260928-TEST01",
            "severity": "CRITICAL",
            "root_cause_summary": "Thermal overload on Asset-04",
        }
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value = mock_async_client
        mock_async_client.post.return_value = mock_resp

        with patch(
            "routers.agent.get_gcp_id_token", AsyncMock(return_value="tok")
        ), patch("httpx.AsyncClient", return_value=mock_async_client):
            rec = asyncio.run(agent_router.proxy_agent_recommendation(req))
            self.assertEqual(rec["incident_id"], "INC-20260928-TEST01")
            self.assertEqual(rec["asset_id"], "Asset-04")
            self.assertIn("tokenomics", rec)

        all_recs = agent_router.get_all_recommendations()
        self.assertIn("Asset-04", all_recs["recommendations"])

        single_rec = agent_router.get_asset_recommendation("Asset-04")
        self.assertEqual(single_rec["incident_id"], "INC-20260928-TEST01")

        with self.assertRaises(HTTPException) as ctx:
            agent_router.get_asset_recommendation("Asset-99")
        self.assertEqual(ctx.exception.status_code, 404)

        mock_resp_err = MagicMock()
        mock_resp_err.status_code = 500
        mock_resp_err.text = "Internal Server Error"
        mock_async_client.post.return_value = mock_resp_err
        with patch(
            "routers.agent.get_gcp_id_token", AsyncMock(return_value="tok")
        ), patch("httpx.AsyncClient", return_value=mock_async_client):
            with self.assertRaises(HTTPException) as err_ctx:
                asyncio.run(agent_router.proxy_agent_recommendation(req))
            self.assertEqual(err_ctx.exception.status_code, 502)

    def test_agent_router_approve_and_execute_mitigation(self) -> None:
        """Verifies /api/agent/approve HTTP execution and timeline steps."""
        approve_req = AgentApproveRequest(
            asset_id="Asset-04",
            incident_id="INC-20260928-TEST01",
            approved_by="Plant Operator",
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "bigquery_logged": True,
            "action_taken": "Throttled and cooled Asset-04.",
            "actuator_response": {"status": "remediated"},
        }
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value = mock_async_client
        mock_async_client.post.return_value = mock_resp

        with patch(
            "routers.agent.get_gcp_id_token", AsyncMock(return_value="tok")
        ), patch("httpx.AsyncClient", return_value=mock_async_client):
            res = asyncio.run(
                agent_router.approve_and_execute_mitigation(approve_req)
            )
            self.assertTrue(res["success"])
            self.assertEqual(res["execution_mode"], "AGENT_SERVICE_HTTP")
            self.assertEqual(res["asset_id"], "Asset-04")
            self.assertEqual(len(res["steps"]), 6)

    def test_agent_router_geap_reasoning_engine_forwards_all_fields(
        self,
    ) -> None:
        """Verifies GEAP ReasoningEngine.query receives all request fields."""
        req = AgentMitigateRequest(
            asset_id="Asset-04",
            cpu_utilization=96.2,
            temperature_c=94.5,
            pressure_psi=162.0,
            memory_utilization_pct=89.5,
            status="CRITICAL",
            event_type="THERMAL_OVERLOAD",
            additional_context="Bearing vibration elevated",
        )
        mock_engine = MagicMock()
        mock_engine.query.return_value = {
            "incident_id": "INC-GEAP-01",
            "severity": "CRITICAL",
            "root_cause_summary": "Bearing thermal overload on Asset-04",
        }
        mock_re_mod = MagicMock()
        mock_re_mod.ReasoningEngine.return_value = mock_engine
        mock_vertexai = MagicMock()

        with patch.dict(
            os.environ,
            {
                "AGENT_SERVICE_URL": (
                    "projects/test-proj/locations/us-central1/"
                    "reasoningEngines/999"
                )
            },
            clear=False,
        ), patch("routers.agent.vertexai", mock_vertexai, create=True), patch(
            "routers.agent.reasoning_engines", mock_re_mod, create=True
        ):
            res = asyncio.run(agent_router.proxy_agent_recommendation(req))
            self.assertEqual(res["incident_id"], "INC-GEAP-01")
            mock_engine.query.assert_called_once_with(
                asset_id="Asset-04",
                cpu_utilization=96.2,
                temperature_c=94.5,
                pressure_psi=162.0,
                memory_utilization_pct=89.5,
                status="CRITICAL",
                event_type="THERMAL_OVERLOAD",
                additional_context="Bearing vibration elevated",
            )


if __name__ == "__main__":
    unittest.main()
