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

"""Dataproc Serverless pipeline controller client for PySpark streaming."""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

import google.auth.exceptions
from google.api_core.exceptions import GoogleAPICallError
from pipeline_clients.base import BasePipelineClient

try:
    from google.cloud import dataproc_v1  # pylint: disable=ungrouped-imports

    DATAPROC_AVAILABLE = True
except ImportError:
    DATAPROC_AVAILABLE = False

logger = logging.getLogger("aegis-hud-backend")
if not DATAPROC_AVAILABLE:
    logger.warning("google-cloud-dataproc package not available.")

_DATAPROC_EXCEPTIONS = (
    GoogleAPICallError,
    google.auth.exceptions.GoogleAuthError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    OSError,
)


class DataprocPipelineClient(BasePipelineClient):
    """Pipeline controller for Dataproc Serverless PySpark (Velox C++)."""

    def __init__(self):
        self._batch_client = None
        self._status_cache: Dict[str, Any] = {
            "status": "RUNNING",
            "batch_id": None,
            "create_time": None,
            "engine": "dataproc",
        }
        self._cache_timestamp: float = 0.0
        self.cache_ttl_seconds: float = 12.0

    @property
    def engine_name(self) -> str:
        return "dataproc"

    def _get_client(self, region: str):
        if self._batch_client is None and DATAPROC_AVAILABLE:
            try:
                self._batch_client = dataproc_v1.BatchControllerClient(
                    client_options={
                        "api_endpoint": f"{region}-dataproc.googleapis.com:443"
                    }
                )
            except _DATAPROC_EXCEPTIONS as exc:
                logger.error(
                    "Error initializing Dataproc BatchControllerClient: %s", exc
                )
                self._batch_client = None
        return self._batch_client

    def refresh_status_sync(
        self, project_id: str, region: str
    ) -> Dict[str, Any]:
        """Queries Dataproc directly and updates in-memory status cache."""
        if not DATAPROC_AVAILABLE:
            self._status_cache = {
                "status": "STOPPED",
                "batch_id": None,
                "create_time": None,
                "engine": "dataproc",
                "error": "Dataproc SDK unavailable",
            }
            self._cache_timestamp = time.time()
            return self._status_cache

        client = self._get_client(region)
        if not client:
            return self._status_cache

        try:
            parent = f"projects/{project_id}/locations/{region}"
            batches = list(
                client.list_batches(request={"parent": parent}, timeout=8.0)
            )

            for b in batches:
                state_name = dataproc_v1.Batch.State(b.state).name
                if state_name in ["RUNNING", "PENDING", "ACTIVE"]:
                    default_msg = (
                        "Dataproc Serverless PySpark streaming active "
                        "(Velox C++ Engine)."
                        if state_name in ["RUNNING", "ACTIVE"]
                        else "Allocating Spark compute nodes (~60-90s)..."
                    )
                    result = {
                        "status": (
                            "RUNNING"
                            if state_name in ["RUNNING", "ACTIVE"]
                            else "PENDING"
                        ),
                        "batch_id": b.name.split("/")[-1],
                        "create_time": str(b.create_time),
                        "state_name": state_name,
                        "engine": "dataproc",
                        "message": default_msg,
                        "error": None,
                    }
                    self._status_cache = result
                    self._cache_timestamp = time.time()
                    return result

            if batches:
                sorted_batches = sorted(
                    batches,
                    key=lambda b: (
                        b.create_time.timestamp() if b.create_time else 0
                    ),
                    reverse=True,
                )
                latest = sorted_batches[0]
                latest_state = dataproc_v1.Batch.State(latest.state).name
                if latest_state == "FAILED":
                    status = "FAILED"
                    if latest.state_message:
                        logger.warning(
                            "Dataproc batch %s failed: %s",
                            latest.name,
                            latest.state_message,
                        )
                elif latest_state == "CANCELLED":
                    status = "CANCELLED"
                else:
                    status = "STOPPED"
                result = {
                    "status": status,
                    "batch_id": latest.name.split("/")[-1],
                    "create_time": str(latest.create_time),
                    "state_name": latest_state,
                    "engine": "dataproc",
                    "message": (
                        f"Dataproc batch is {latest_state.lower()}."
                        if status != "STOPPED"
                        else "Dataproc pipeline is stopped."
                    ),
                    "error": (
                        "Dataproc batch execution failed."
                        if status == "FAILED"
                        else None
                    ),
                }
                self._status_cache = result
                self._cache_timestamp = time.time()
                return result

            result = {
                "status": "STOPPED",
                "batch_id": None,
                "create_time": None,
                "engine": "dataproc",
                "message": "No Dataproc batches found.",
                "error": None,
            }
            self._status_cache = result
            self._cache_timestamp = time.time()
            return result
        except _DATAPROC_EXCEPTIONS as exc:
            logger.warning("Error refreshing Dataproc pipeline status: %s", exc)
            self._cache_timestamp = time.time()
            return self._status_cache

    def get_status(self, _project_id: str, _region: str) -> Dict[str, Any]:
        """Returns cached Dataproc status instantly (<0.01ms)."""
        return self._status_cache

    def start_pipeline(self, project_id: str, region: str) -> Dict[str, Any]:
        """Submits a new Dataproc Serverless PySpark streaming batch job."""
        self._cache_timestamp = 0.0
        if not DATAPROC_AVAILABLE:
            return {
                "status": "FAILED",
                "engine": "dataproc",
                "message": "Dataproc SDK unavailable",
            }
        try:
            client = self._get_client(region)
            if not client:
                return {
                    "status": "FAILED",
                    "engine": "dataproc",
                    "message": "Could not create Dataproc client",
                }

            parent = f"projects/{project_id}/locations/{region}"
            now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            batch_id = f"aegis-etl-{now_str}"

            deps_bucket = os.getenv(
                "DEPS_BUCKET", f"{project_id}-dataproc-deps"
            )
            kafka_brokers = os.getenv(
                "KAFKA_BROKERS",
                (
                    f"bootstrap.aegis-kafka-cluster.{region}.managedkafka."
                    f"{project_id}.cloud.goog:9092"
                ),
            )
            kafka_topic = os.getenv("KAFKA_TOPIC", "telemetry-raw")
            bigtable_inst = os.getenv("BIGTABLE_INSTANCE_ID", "aegis-bigtable")
            bigquery_ds = os.getenv("BIGQUERY_DATASET_ID", "analytics")
            service_account_email = os.getenv(
                "SERVICE_ACCOUNT",
                f"aegis-sa@{project_id}.iam.gserviceaccount.com",
            )
            subnetwork_uri = os.getenv(
                "SUBNETWORK_URI",
                (
                    f"projects/{project_id}/regions/{region}/"
                    "subnetworks/aegis-subnet"
                ),
            )

            exec_config_kwargs = {}
            if service_account_email:
                exec_config_kwargs["service_account"] = service_account_email
            if subnetwork_uri:
                exec_config_kwargs["subnetwork_uri"] = subnetwork_uri

            main_py = f"gs://{deps_bucket}/dependencies/aegis_etl.py"
            reqs_py = f"gs://{deps_bucket}/dependencies/requirements.txt"
            chk_loc = f"gs://{deps_bucket}/checkpoints/{batch_id}"

            kafka_pkg = (
                "org.apache.spark:spark-sql-kafka-0-10_2.13:3.5.0,"
                "com.google.cloud.hosted.kafka:"
                "managed-kafka-auth-login-handler:1.0.5"
            )
            batch = dataproc_v1.Batch(
                pyspark_batch=dataproc_v1.PySparkBatch(
                    main_python_file_uri=main_py,
                    python_file_uris=[reqs_py],
                    args=[
                        f"--project-id={project_id}",
                        "--source-type=kafka",
                        f"--kafka-bootstrap-servers={kafka_brokers}",
                        f"--kafka-topic={kafka_topic}",
                        f"--bigtable-instance={bigtable_inst}",
                        "--bigtable-table=telemetry_metrics",
                        f"--bigquery-dataset={bigquery_ds}",
                        "--bigquery-table=telemetry_events",
                        f"--checkpoint-location={chk_loc}",
                    ],
                ),
                runtime_config=dataproc_v1.RuntimeConfig(
                    version="2.2",
                    properties={
                        "spark.jars.packages": kafka_pkg,
                        "spark.jars.repositories": (
                            "https://packages.confluent.io/maven/"
                        ),
                        "spark.dataproc.lineage.enabled": "true",
                        "spark.extraListeners": (
                            "io.openlineage.spark.agent."
                            "OpenLineageSparkListener"
                        ),
                        "spark.spark.vectorized.enabled": "true",
                        "spark.sql.execution.vectorized.enabled": "true",
                        "spark.sql.session.timeZone": "UTC",
                    },
                ),
                environment_config=dataproc_v1.EnvironmentConfig(
                    execution_config=dataproc_v1.ExecutionConfig(
                        **exec_config_kwargs
                    )
                ),
            )

            client.create_batch(
                request={
                    "parent": parent,
                    "batch": batch,
                    "batch_id": batch_id,
                },
                timeout=15.0,
            )
            logger.info("Submitted new Dataproc batch job: %s", batch_id)

            self._status_cache = {
                "status": "PENDING",
                "batch_id": batch_id,
                "engine": "dataproc",
                "create_time": datetime.now(timezone.utc).isoformat(),
            }
            self._cache_timestamp = time.time()

            return {
                "status": "PENDING",
                "batch_id": batch_id,
                "engine": "dataproc",
                "message": (
                    "Managed Spark streaming pipeline submitted successfully."
                ),
            }
        except _DATAPROC_EXCEPTIONS as exc:
            logger.error("Error starting Dataproc pipeline: %s", exc)
            return {
                "status": "FAILED",
                "engine": "dataproc",
                "message": "Failed to start Managed Spark pipeline.",
            }

    def stop_pipeline(self, project_id: str, region: str) -> Dict[str, Any]:
        """Deletes active Dataproc Serverless batch streaming jobs."""
        self._cache_timestamp = 0.0
        if not DATAPROC_AVAILABLE:
            return {
                "status": "FAILED",
                "engine": "dataproc",
                "message": "Dataproc SDK unavailable",
            }
        try:
            client = self._get_client(region)
            if not client:
                return {
                    "status": "FAILED",
                    "engine": "dataproc",
                    "message": "Could not create Dataproc client",
                }

            parent = f"projects/{project_id}/locations/{region}"
            batches = list(
                client.list_batches(
                    request={"parent": parent, "order_by": "create_time desc"},
                    timeout=10.0,
                )
            )
            stopped_count = 0
            for b in batches:
                state_name = dataproc_v1.Batch.State(b.state).name
                if state_name in ["RUNNING", "PENDING", "ACTIVE"]:
                    try:
                        client.delete_batch(name=b.name, timeout=10.0)
                        stopped_count += 1
                    except _DATAPROC_EXCEPTIONS as exc:
                        logger.warning(
                            "Failed to delete batch %s: %s", b.name, exc
                        )
            logger.info(
                "Stopped %d active Dataproc pipeline(s).", stopped_count
            )

            self._status_cache = {
                "status": "STOPPED",
                "batch_id": None,
                "engine": "dataproc",
                "create_time": datetime.now(timezone.utc).isoformat(),
            }
            self._cache_timestamp = time.time()

            return {
                "status": "STOPPED",
                "engine": "dataproc",
                "message": (
                    f"Stopped {stopped_count} active Managed Spark pipeline(s)."
                ),
            }
        except _DATAPROC_EXCEPTIONS as exc:
            logger.error("Error stopping Dataproc pipeline: %s", exc)
            return {
                "status": "FAILED",
                "engine": "dataproc",
                "message": "Failed to stop Managed Spark pipeline.",
            }
