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

"""Cloud Dataflow pipeline controller client for Apache Beam streaming."""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from pipeline_clients.base import BasePipelineClient

logger = logging.getLogger("aegis-hud-backend")

try:
    import google.auth
    import google.auth.exceptions
    from google.api_core.exceptions import GoogleAPICallError
    from google.auth.transport.requests import Request as AuthRequest

    GOOGLE_AUTH_AVAILABLE = True
    _AUTH_EXCEPTIONS: tuple[type[Exception], ...] = (
        google.auth.exceptions.GoogleAuthError,
        GoogleAPICallError,
        ValueError,
        OSError,
    )
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False
    _AUTH_EXCEPTIONS = (ValueError, OSError)

_DATAFLOW_API_EXCEPTIONS = (
    httpx.HTTPError,
    ValueError,
    KeyError,
    TypeError,
    OSError,
)


class DataflowPipelineClient(BasePipelineClient):
    """Pipeline controller for Google Cloud Dataflow (Apache Beam)."""

    def __init__(self) -> None:
        self._status_cache: Dict[str, Any] = {
            "status": "STOPPED",
            "batch_id": None,
            "job_id": None,
            "create_time": None,
            "engine": "dataflow",
            "message": "Cloud Dataflow pipeline stopped.",
            "error": None,
        }
        self._cache_timestamp: float = 0.0
        self.cache_ttl_seconds: float = 12.0

    @property
    def engine_name(self) -> str:
        """Returns the engine identifier ('dataflow')."""
        return "dataflow"

    def _get_auth_headers(self) -> Dict[str, str]:
        """Fetches Google Cloud OAuth2 bearer headers for Dataflow API calls."""
        if not GOOGLE_AUTH_AVAILABLE:
            return {}
        try:
            creds, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            if not creds.valid:
                creds.refresh(AuthRequest())
            return {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            }
        except _AUTH_EXCEPTIONS as exc:
            logger.debug(
                "Failed getting Google Cloud auth token for Dataflow: %s", exc
            )
            return {}

    def refresh_status_sync(
        self, project_id: str, region: str
    ) -> Dict[str, Any]:
        """Queries Dataflow API for active streaming jobs."""
        if not GOOGLE_AUTH_AVAILABLE or not project_id:
            self._status_cache = {
                "status": "STOPPED",
                "batch_id": None,
                "job_id": None,
                "create_time": None,
                "engine": "dataflow",
                "message": (
                    "Dataflow client operating in simulated/offline mode."
                ),
                "error": None,
            }
            self._cache_timestamp = time.time()
            return self._status_cache

        headers = self._get_auth_headers()
        if not headers:
            return self._status_cache

        url = (
            f"https://dataflow.googleapis.com/v1b3/projects/{project_id}/"
            f"locations/{region}/jobs"
        )

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs: List[Dict[str, Any]] = data.get("jobs", [])
                    aegis_jobs = [
                        j
                        for j in jobs
                        if "aegis" in j.get("name", "").lower()
                        or "streaming" in j.get("name", "").lower()
                    ]

                    for job in aegis_jobs:
                        job_state = job.get("currentState", "")
                        job_name = job.get("name", "")
                        job_id = job.get("id", "")
                        if job_state in [
                            "JOB_STATE_RUNNING",
                            "JOB_STATE_STARTING",
                            "JOB_STATE_PENDING",
                            "JOB_STATE_QUEUED",
                        ]:
                            is_running = job_state == "JOB_STATE_RUNNING"
                            active_msg = (
                                "Cloud Dataflow Apache Beam streaming "
                                "active."
                            )
                            pending_msg = (
                                "Provisioning Cloud Dataflow worker VMs..."
                            )
                            result = {
                                "status": (
                                    "RUNNING" if is_running else "PENDING"
                                ),
                                "batch_id": job_id,
                                "job_id": job_id,
                                "job_name": job_name,
                                "engine": "dataflow",
                                "create_time": job.get("createTime"),
                                "state_name": job_state,
                                "message": (
                                    active_msg if is_running else pending_msg
                                ),
                                "error": None,
                            }
                            self._status_cache = result
                            self._cache_timestamp = time.time()
                            return result

                    # If no active job found, inspect latest Aegis job
                    if aegis_jobs:
                        latest_job = aegis_jobs[0]
                        latest_state = latest_job.get("currentState", "STOPPED")
                        latest_name = latest_job.get("name")
                        status = (
                            "FAILED" if "FAIL" in latest_state else "STOPPED"
                        )
                        result = {
                            "status": status,
                            "batch_id": latest_job.get("id"),
                            "job_id": latest_job.get("id"),
                            "job_name": latest_name,
                            "engine": "dataflow",
                            "create_time": latest_job.get("createTime"),
                            "state_name": latest_state,
                            "message": (
                                f"Cloud Dataflow job {latest_name} is "
                                f"{latest_state.lower()}."
                            ),
                            "error": None,
                        }
                        self._status_cache = result
                        self._cache_timestamp = time.time()
                        return result

            self._status_cache = {
                "status": "STOPPED",
                "batch_id": None,
                "job_id": None,
                "create_time": None,
                "engine": "dataflow",
                "message": "No active Cloud Dataflow jobs found.",
                "error": None,
            }
            self._cache_timestamp = time.time()
            return self._status_cache
        except _DATAFLOW_API_EXCEPTIONS as exc:
            logger.warning("Error querying Dataflow API: %s", exc)
            self._cache_timestamp = time.time()
            return self._status_cache

    def get_status(self, _project_id: str, _region: str) -> Dict[str, Any]:
        """Returns cached Dataflow pipeline status."""
        return self._status_cache

    def _cancel_active_aegis_jobs(
        self,
        client: httpx.Client,
        project_id: str,
        region: str,
        headers: Dict[str, str],
    ) -> int:
        """Cancels any running or pending Aegis Dataflow jobs."""
        stopped_count = 0
        list_url = (
            f"https://dataflow.googleapis.com/v1b3/projects/{project_id}/"
            f"locations/{region}/jobs"
        )
        try:
            resp = client.get(list_url, headers=headers)
            if resp.status_code != 200:
                return 0
            jobs: List[Dict[str, Any]] = resp.json().get("jobs", [])
            for job in jobs:
                job_state = job.get("currentState", "")
                job_name = job.get("name", "")
                job_id = job.get("id", "")
                if (
                    "aegis" in job_name.lower()
                    or "streaming" in job_name.lower()
                ) and job_state in [
                    "JOB_STATE_RUNNING",
                    "JOB_STATE_STARTING",
                    "JOB_STATE_PENDING",
                    "JOB_STATE_QUEUED",
                ]:
                    job_url = f"{list_url}/{job_id}"
                    client.put(
                        job_url,
                        headers=headers,
                        json={"requestedState": "JOB_STATE_CANCELLED"},
                    )
                    stopped_count += 1
        except _DATAFLOW_API_EXCEPTIONS as exc:
            logger.warning("Error cancelling active Dataflow jobs: %s", exc)
        return stopped_count

    def _seek_subscription_to_now(
        self,
        client: httpx.Client,
        subscription_path: str,
        headers: Dict[str, str],
    ) -> None:
        """Seeks the Pub/Sub subscription to current UTC time."""
        seek_url = f"https://pubsub.googleapis.com/v1/{subscription_path}:seek"
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            client.post(seek_url, headers=headers, json={"time": now_iso})
        except _DATAFLOW_API_EXCEPTIONS as exc:
            logger.debug(
                "Non-fatal error seeking subscription %s: %s",
                subscription_path,
                exc,
            )

    def start_pipeline(self, project_id: str, region: str) -> Dict[str, Any]:
        """Starts the Dataflow streaming pipeline using Flex Template launch."""
        self._cache_timestamp = 0.0
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        job_name = f"aegis-dataflow-streaming-{now_str}"

        headers = self._get_auth_headers()
        if not headers or not project_id:
            return {
                "status": "FAILED",
                "engine": "dataflow",
                "message": (
                    "Dataflow client missing authentication or project_id."
                ),
            }

        staging_bucket = (
            os.getenv("STAGING_BUCKET")
            or os.getenv("DEPS_BUCKET")
            or f"{project_id}-dataflow-staging"
        )
        pubsub_sub = os.getenv(
            "PUBSUB_SUBSCRIPTION", "telemetry-raw-dataflow-sub"
        )
        if "/" not in pubsub_sub:
            pubsub_sub = f"projects/{project_id}/subscriptions/{pubsub_sub}"

        machine_type = os.getenv("DATAFLOW_MACHINE_TYPE", "n2-standard-2")
        bigtable_inst = os.getenv("BIGTABLE_INSTANCE_ID", "aegis-bigtable")
        bigquery_ds = os.getenv("BIGQUERY_DATASET_ID", "analytics")
        service_account_email = os.getenv(
            "SERVICE_ACCOUNT",
            f"aegis-sa@{project_id}.iam.gserviceaccount.com",
        )
        subnetwork_uri = os.getenv(
            "SUBNETWORK_URI",
            f"projects/{project_id}/regions/{region}/subnetworks/aegis-subnet",
        )
        if subnetwork_uri.startswith("projects/"):
            subnetwork_full_url = (
                f"https://www.googleapis.com/compute/v1/{subnetwork_uri}"
            )
        else:
            subnetwork_full_url = subnetwork_uri

        url = (
            f"https://dataflow.googleapis.com/v1b3/projects/{project_id}/"
            f"locations/{region}/flexTemplates:launch"
        )
        payload = {
            "launchParameter": {
                "jobName": job_name,
                "containerSpecGcsPath": (
                    f"gs://{staging_bucket}/templates/"
                    "aegis_dataflow_template.json"
                ),
                "parameters": {
                    "input_subscription": pubsub_sub,
                    "bigtable_project": project_id,
                    "bigtable_instance": bigtable_inst,
                    "bigtable_table": "telemetry_metrics",
                    "bigquery_table": (
                        f"{project_id}:{bigquery_ds}.telemetry_events"
                    ),
                    "window_seconds": "10",
                    "trigger_interval_seconds": "1",
                },
                "environment": {
                    "tempLocation": f"gs://{staging_bucket}/temp",
                    "stagingLocation": f"gs://{staging_bucket}/staging",
                    "serviceAccountEmail": service_account_email,
                    "subnetwork": subnetwork_full_url,
                    "ipConfiguration": "WORKER_IP_PRIVATE",
                    "machineType": machine_type,
                    "enableStreamingEngine": True,
                    "maxWorkers": 5,
                    "numWorkers": 1,
                },
            }
        }

        try:
            with httpx.Client(timeout=25.0) as client:
                self._cancel_active_aegis_jobs(
                    client, project_id, region, headers
                )
                self._seek_subscription_to_now(client, pubsub_sub, headers)
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    job = data.get("job", {})
                    job_id = job.get("id", job_name)
                    self._status_cache = {
                        "status": "PENDING",
                        "batch_id": job_id,
                        "job_id": job_id,
                        "job_name": job.get("name", job_name),
                        "engine": "dataflow",
                        "create_time": (
                            job.get("createTime")
                            or datetime.now(timezone.utc).isoformat()
                        ),
                        "state_name": "JOB_STATE_STARTING",
                        "message": (
                            "Cloud Dataflow Apache Beam streaming pipeline "
                            "submitted."
                        ),
                        "error": None,
                    }
                    self._cache_timestamp = time.time()
                    logger.info(
                        "Submitted Cloud Dataflow Flex Template job %s "
                        "(ID: %s)",
                        job_name,
                        job_id,
                    )
                    return {
                        "status": "PENDING",
                        "job_id": job_id,
                        "engine": "dataflow",
                        "message": (
                            "Cloud Dataflow Apache Beam streaming pipeline "
                            "submitted."
                        ),
                    }

                error_detail = resp.text
                logger.error(
                    "Failed launching Dataflow Flex Template (%s): %s",
                    resp.status_code,
                    error_detail,
                )
                return {
                    "status": "FAILED",
                    "engine": "dataflow",
                    "message": "Failed to launch Cloud Dataflow job.",
                }
        except _DATAFLOW_API_EXCEPTIONS as exc:
            logger.error("Error launching Dataflow pipeline: %s", exc)
            return {
                "status": "FAILED",
                "engine": "dataflow",
                "message": "Failed to start Cloud Dataflow pipeline.",
            }

    def stop_pipeline(self, project_id: str, region: str) -> Dict[str, Any]:
        """Cancels or drains running Dataflow streaming jobs."""
        self._cache_timestamp = 0.0
        headers = self._get_auth_headers()
        stopped_count = 0

        if headers and project_id:
            try:
                with httpx.Client(timeout=10.0) as client:
                    stopped_count = self._cancel_active_aegis_jobs(
                        client, project_id, region, headers
                    )
            except _DATAFLOW_API_EXCEPTIONS as exc:
                logger.warning("Error cancelling Dataflow jobs: %s", exc)

        self._status_cache = {
            "status": "STOPPED",
            "batch_id": None,
            "job_id": None,
            "engine": "dataflow",
            "create_time": datetime.now(timezone.utc).isoformat(),
            "message": "Cloud Dataflow streaming pipeline stopped.",
            "error": None,
        }
        return {
            "status": "STOPPED",
            "engine": "dataflow",
            "message": f"Stopped {stopped_count} active Cloud Dataflow job(s).",
        }
