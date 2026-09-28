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

"""Dataproc Standard Spark cluster pipeline client for PySpark streaming."""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import google.auth.exceptions
from google.api_core.exceptions import GoogleAPICallError

# google-cloud-dataproc is an optional runtime dependency in local test
# environments without full Google Cloud SDKs installed.
try:
    from google.cloud import dataproc_v1

    DATAPROC_AVAILABLE = True
except ImportError:
    DATAPROC_AVAILABLE = False

from pipeline_clients.base import BasePipelineClient

logger = logging.getLogger("aegis-hud-backend")
if not DATAPROC_AVAILABLE:
    logger.warning("google-cloud-dataproc package not available.")

_DEFAULT_CLUSTER_NAME = "aegis-spark-cluster"

_RUNNING_JOB_STATES = frozenset(
    {
        "RUNNING",
        "DRIVER_MAIN_STARTED",
        "YARN_APPLICATION_RUNNING",
    }
)
_PENDING_JOB_STATES = frozenset(
    {
        "PENDING",
        "SETUP_DONE",
        "SUBSTATE_UNSPECIFIED",
    }
)
_ACTIVE_JOB_STATES = _RUNNING_JOB_STATES | _PENDING_JOB_STATES

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
    """Pipeline client for Dataproc Standard Spark Cluster."""

    def __init__(self) -> None:
        """Initializes the Dataproc job controller cache and client state."""
        self._job_client: Optional[Any] = None
        self._client_region: Optional[str] = None
        self._status_cache: Dict[str, Any] = {
            "status": "RUNNING",
            "batch_id": None,
            "job_id": None,
            "cluster_name": os.getenv(
                "DATAPROC_CLUSTER_NAME", _DEFAULT_CLUSTER_NAME
            ),
            "create_time": None,
            "engine": "dataproc",
        }
        self._cache_timestamp: float = 0.0
        self.cache_ttl_seconds: float = 10.0

    @property
    def engine_name(self) -> str:
        """Returns the pipeline engine identifier."""
        return "dataproc"

    def _get_cluster_name(self) -> str:
        """Returns the configured Dataproc Standard Spark cluster name."""
        return os.getenv("DATAPROC_CLUSTER_NAME", _DEFAULT_CLUSTER_NAME)

    def _get_client(self, region: str) -> Optional[Any]:
        """Returns a regional Dataproc JobControllerClient instance."""
        if (
            self._job_client is None or self._client_region != region
        ) and DATAPROC_AVAILABLE:
            try:
                self._job_client = dataproc_v1.JobControllerClient(
                    client_options={
                        "api_endpoint": f"{region}-dataproc.googleapis.com:443"
                    }
                )
                self._client_region = region
            except _DATAPROC_EXCEPTIONS as exc:
                logger.error(
                    "Error initializing Dataproc JobControllerClient: %s", exc
                )
                self._job_client = None
                self._client_region = None
        return self._job_client

    def _find_active_job_result(
        self, jobs: List[Any], cluster_name: str
    ) -> Optional[Dict[str, Any]]:
        """Returns status dictionary if an active job exists on the cluster."""
        for job in jobs:
            state_name = dataproc_v1.JobStatus.State(job.status.state).name
            if state_name in _ACTIVE_JOB_STATES:
                job_id = (
                    job.reference.job_id if job.reference else "aegis-etl-job"
                )
                create_time = (
                    str(job.status.state_start_time)
                    if job.status and job.status.state_start_time
                    else None
                )
                is_running = state_name in _RUNNING_JOB_STATES
                default_msg = (
                    f"Dataproc Standard Spark streaming active on warm "
                    f"vectorized Spark cluster ({cluster_name})."
                    if is_running
                    else (
                        f"Submitting PySpark streaming job to warm "
                        f"cluster {cluster_name} (~5-10s)..."
                    )
                )
                return {
                    "status": "RUNNING" if is_running else "PENDING",
                    "batch_id": job_id,
                    "job_id": job_id,
                    "cluster_name": cluster_name,
                    "create_time": create_time,
                    "state_name": state_name,
                    "engine": "dataproc",
                    "message": default_msg,
                    "error": None,
                }
        return None

    def _build_latest_job_result(
        self, jobs: List[Any], cluster_name: str
    ) -> Dict[str, Any]:
        """Builds status dictionary from the most recent job on the cluster."""
        sorted_jobs = sorted(
            jobs,
            key=lambda j: (
                j.status.state_start_time.timestamp()
                if j.status and j.status.state_start_time
                else 0
            ),
            reverse=True,
        )
        latest = sorted_jobs[0]
        latest_state = dataproc_v1.JobStatus.State(latest.status.state).name
        latest_id = (
            latest.reference.job_id if latest.reference else "aegis-etl-job"
        )
        create_time = (
            str(latest.status.state_start_time)
            if latest.status and latest.status.state_start_time
            else None
        )
        if latest_state in {"ERROR", "ATTEMPT_FAILURE"}:
            status = "FAILED"
            if latest.status.details:
                logger.warning(
                    "Dataproc job %s failed: %s",
                    latest_id,
                    latest.status.details,
                )
        elif latest_state in {
            "CANCELLED",
            "CANCEL_PENDING",
            "CANCEL_STARTED",
        }:
            status = "CANCELLED"
        else:
            status = "STOPPED"

        return {
            "status": status,
            "batch_id": latest_id,
            "job_id": latest_id,
            "cluster_name": cluster_name,
            "create_time": create_time,
            "state_name": latest_state,
            "engine": "dataproc",
            "message": (
                f"Dataproc streaming job on {cluster_name} is "
                f"{latest_state.lower()}."
                if status != "STOPPED"
                else (
                    f"Spark streaming job stopped (warm cluster "
                    f"{cluster_name} ready for instant restart)."
                )
            ),
            "error": (
                "Dataproc streaming job execution failed."
                if status == "FAILED"
                else None
            ),
        }

    def refresh_status_sync(
        self, project_id: str, region: str
    ) -> Dict[str, Any]:
        """Queries Dataproc jobs on the warm cluster and updates cache."""
        cluster_name = self._get_cluster_name()
        if not DATAPROC_AVAILABLE:
            self._status_cache = {
                "status": "STOPPED",
                "batch_id": None,
                "job_id": None,
                "cluster_name": cluster_name,
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
            jobs = list(
                client.list_jobs(
                    request={
                        "project_id": project_id,
                        "region": region,
                        "cluster_name": cluster_name,
                    },
                    timeout=8.0,
                )
            )

            active_result = self._find_active_job_result(jobs, cluster_name)
            if active_result is not None:
                self._status_cache = active_result
                self._cache_timestamp = time.time()
                return active_result

            if jobs:
                latest_result = self._build_latest_job_result(
                    jobs, cluster_name
                )
                self._status_cache = latest_result
                self._cache_timestamp = time.time()
                return latest_result

            result = {
                "status": "STOPPED",
                "batch_id": None,
                "job_id": None,
                "cluster_name": cluster_name,
                "create_time": None,
                "engine": "dataproc",
                "message": (
                    f"No active Spark jobs on warm cluster {cluster_name}."
                ),
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
        """Submits a PySpark streaming job to the warm Dataproc cluster."""
        self._cache_timestamp = 0.0
        cluster_name = self._get_cluster_name()
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
                    "message": "Could not create Dataproc JobControllerClient",
                }

            now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            job_id = f"aegis-etl-{now_str}"

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

            main_py = f"gs://{deps_bucket}/dependencies/aegis_etl.py"
            chk_loc = f"gs://{deps_bucket}/checkpoints/{job_id}"

            # All required Spark SQL Kafka and Google OAuth2 JARs are verified
            # with SHA-256 checksums and pre-installed in `/usr/lib/spark/jars`
            # on every cluster node via `data-ingestion/src/init_spark_deps.sh`.
            job = dataproc_v1.Job(
                reference=dataproc_v1.JobReference(
                    project_id=project_id,
                    job_id=job_id,
                ),
                placement=dataproc_v1.JobPlacement(
                    cluster_name=cluster_name,
                ),
                pyspark_job=dataproc_v1.PySparkJob(
                    main_python_file_uri=main_py,
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
                        "--shuffle-partitions=8",
                    ],
                    # Scale spark.sql.shuffle.partitions proportionally with
                    # Dataproc worker vCPUs (num_workers * vcpus_per_worker,
                    # e.g., 8 for 2x n2-standard-4 workers) to avoid 200-way
                    # Cloud Storage state-store checkpoint bottlenecks.
                    properties={
                        "spark.driver.extraClassPath": "/usr/lib/spark/jars/*",
                        "spark.executor.extraClassPath": (
                            "/usr/lib/spark/jars/*"
                        ),
                        "spark.dataproc.lineage.enabled": "true",
                        "spark.sql.shuffle.partitions": "8",
                        "spark.scheduler.mode": "FAIR",
                        "spark.sql.session.timeZone": "UTC",
                    },
                ),
            )

            client.submit_job(
                request={
                    "project_id": project_id,
                    "region": region,
                    "job": job,
                },
                timeout=15.0,
            )
            logger.info(
                "Submitted PySpark streaming job %s to warm cluster %s",
                job_id,
                cluster_name,
            )

            self._status_cache = {
                "status": "PENDING",
                "batch_id": job_id,
                "job_id": job_id,
                "cluster_name": cluster_name,
                "engine": "dataproc",
                "create_time": datetime.now(timezone.utc).isoformat(),
            }
            self._cache_timestamp = time.time()

            return {
                "status": "PENDING",
                "batch_id": job_id,
                "job_id": job_id,
                "cluster_name": cluster_name,
                "engine": "dataproc",
                "message": (
                    f"Spark streaming job ({job_id}) submitted to warm "
                    f"Dataproc Standard Spark cluster ({cluster_name})."
                ),
            }
        except _DATAPROC_EXCEPTIONS as exc:
            logger.error("Error starting Dataproc streaming job: %s", exc)
            return {
                "status": "FAILED",
                "engine": "dataproc",
                "message": "Failed to submit Spark streaming job to cluster.",
            }

    def stop_pipeline(self, project_id: str, region: str) -> Dict[str, Any]:
        """Cancels active PySpark streaming jobs on the warm cluster."""
        self._cache_timestamp = 0.0
        cluster_name = self._get_cluster_name()
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
                    "message": "Could not create Dataproc JobControllerClient",
                }

            jobs = list(
                client.list_jobs(
                    request={
                        "project_id": project_id,
                        "region": region,
                        "cluster_name": cluster_name,
                    },
                    timeout=10.0,
                )
            )
            stopped_count = 0
            for job in jobs:
                state_name = dataproc_v1.JobStatus.State(job.status.state).name
                if state_name in _ACTIVE_JOB_STATES and job.reference:
                    try:
                        client.cancel_job(
                            request={
                                "project_id": project_id,
                                "region": region,
                                "job_id": job.reference.job_id,
                            },
                            timeout=10.0,
                        )
                        stopped_count += 1
                    except _DATAPROC_EXCEPTIONS as exc:
                        logger.warning(
                            "Failed to cancel Dataproc job %s: %s",
                            job.reference.job_id,
                            exc,
                        )
            logger.info(
                "Cancelled %d active Dataproc streaming job(s) on %s.",
                stopped_count,
                cluster_name,
            )

            self._status_cache = {
                "status": "STOPPED",
                "batch_id": None,
                "job_id": None,
                "cluster_name": cluster_name,
                "engine": "dataproc",
                "create_time": datetime.now(timezone.utc).isoformat(),
            }
            self._cache_timestamp = time.time()

            return {
                "status": "STOPPED",
                "cluster_name": cluster_name,
                "engine": "dataproc",
                "message": (
                    f"Stopped {stopped_count} active Spark streaming job(s) on "
                    f"{cluster_name} (warm cluster remains ready)."
                ),
            }
        except _DATAPROC_EXCEPTIONS as exc:
            logger.error("Error stopping Dataproc streaming job: %s", exc)
            return {
                "status": "FAILED",
                "engine": "dataproc",
                "message": "Failed to stop Spark streaming job.",
            }
