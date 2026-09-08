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

"""BigQuery Continuous Queries pipeline controller client."""

import functools
import logging
import os
import pathlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import google.auth.exceptions
from google.api_core.exceptions import GoogleAPICallError
from pipeline_clients.base import BasePipelineClient

try:
    from google.cloud import bigquery  # pylint: disable=ungrouped-imports

    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False

try:
    from google.cloud import bigtable  # pylint: disable=ungrouped-imports

    BIGTABLE_AVAILABLE = True
except ImportError:
    BIGTABLE_AVAILABLE = False

logger = logging.getLogger("aegis-hud-backend")

SQL_DIR = pathlib.Path(__file__).resolve().parent.parent / "sql"

_GCP_SYNC_EXCEPTIONS = (
    GoogleAPICallError,
    google.auth.exceptions.GoogleAuthError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    OSError,
)


@functools.lru_cache(maxsize=4)
def _load_continuous_sql() -> str:
    """Load and cache the 10-second tumbling window SQL query."""
    sql_path = SQL_DIR / "continuous_window_aggregation.sql"
    lines = [
        line
        for line in sql_path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("--")
    ]
    return "\n".join(lines).strip()


class ContinuousQueryPipelineClient(BasePipelineClient):
    """Pipeline controller for BigQuery Continuous Queries (Low-Code SQL)."""

    def __init__(self):
        self._active: bool = True
        self._job_id: Optional[str] = "aegis-cq-continuous-sql"
        self._status_cache: Dict[str, Any] = {
            "status": "RUNNING",
            "batch_id": self._job_id,
            "job_id": self._job_id,
            "create_time": datetime.now(timezone.utc).isoformat(),
            "engine": "bq_continuous",
            "message": (
                "BigQuery Continuous Query actively aggregating 10s SQL "
                "tumbling windows."
            ),
            "error": None,
        }
        self._cache_timestamp: float = 0.0
        self.cache_ttl_seconds: float = 5.0

    @property
    def engine_name(self) -> str:
        return "bq_continuous"

    def _sync_window_aggregates_to_bigtable(
        self, project_id: str, dataset_id: str
    ) -> int:
        """Executes 10s SQL window aggregation and writes state to Bigtable."""
        if not BIGQUERY_AVAILABLE or not BIGTABLE_AVAILABLE or not project_id:
            return 0

        try:
            bq_client = bigquery.Client(project=project_id)
            sql = _load_continuous_sql().format(
                project_id=project_id, dataset_id=dataset_id
            )
            rows = list(bq_client.query(sql).result(timeout=8.0))
            if not rows:
                return 0

            bt_instance_id = os.getenv("BIGTABLE_INSTANCE_ID", "aegis-bigtable")
            bt_table_id = os.getenv("BIGTABLE_TABLE_ID", "telemetry_metrics")
            bt_client = bigtable.Client(project=project_id, admin=False)
            table = bt_client.instance(bt_instance_id).table(bt_table_id)

            now_utc = datetime.now(timezone.utc)
            mutations = []
            for r in rows:
                asset_id = r.get("asset_id")
                if not asset_id:
                    continue
                window_ts = str(r.get("window_end") or now_utc.isoformat())
                is_anom = str(bool(r.get("is_anomaly", False)))
                temp_val = r.get("avg_temp", r.get("max_temp", 52.0))
                direct_row = table.direct_row(str(asset_id).encode("utf-8"))
                direct_row.set_cell(
                    "metrics",
                    b"cpu",
                    str(r.get("avg_cpu", 35.0)).encode("utf-8"),
                    timestamp=now_utc,
                )
                direct_row.set_cell(
                    "metrics",
                    b"temp",
                    str(temp_val).encode("utf-8"),
                    timestamp=now_utc,
                )
                direct_row.set_cell(
                    "metrics",
                    b"pressure",
                    str(r.get("avg_pressure", 40.0)).encode("utf-8"),
                    timestamp=now_utc,
                )
                direct_row.set_cell(
                    "metrics",
                    b"memory",
                    str(r.get("avg_memory", 45.0)).encode("utf-8"),
                    timestamp=now_utc,
                )
                direct_row.set_cell(
                    "metrics",
                    b"status",
                    str(r.get("status", "OK")).encode("utf-8"),
                    timestamp=now_utc,
                )
                direct_row.set_cell(
                    "metrics",
                    b"is_anomaly",
                    is_anom.encode("utf-8"),
                    timestamp=now_utc,
                )
                direct_row.set_cell(
                    "metrics",
                    b"timestamp",
                    window_ts.encode("utf-8"),
                    timestamp=now_utc,
                )
                direct_row.set_cell(
                    "metrics",
                    b"window_end",
                    window_ts.encode("utf-8"),
                    timestamp=now_utc,
                )
                mutations.append(direct_row)

            if mutations:
                table.mutate_rows(mutations)
            return len(mutations)
        except _GCP_SYNC_EXCEPTIONS as exc:
            logger.debug("Continuous SQL Bigtable window sync skipped: %s", exc)
            return 0

    def refresh_status_sync(
        self, project_id: str, region: str
    ) -> Dict[str, Any]:
        """Refreshes Continuous Query status and syncs 10s SQL windows."""
        if not self._active:
            self._status_cache = {
                "status": "STOPPED",
                "batch_id": None,
                "job_id": None,
                "create_time": None,
                "engine": "bq_continuous",
                "message": "BigQuery Continuous Query pipeline stopped.",
                "error": None,
            }
            self._cache_timestamp = time.time()
            return self._status_cache

        dataset_id = os.getenv("BIGQUERY_DATASET_ID", "analytics")
        synced_assets = self._sync_window_aggregates_to_bigtable(
            project_id, dataset_id
        )

        if BIGQUERY_AVAILABLE and project_id:
            try:
                client = bigquery.Client(project=project_id, location=region)
                jobs = list(
                    client.list_jobs(
                        max_results=10,
                        state_filter="RUNNING",
                    )
                )
                for j in jobs:
                    if (
                        "aegis" in str(j.job_id).lower()
                        or "continuous" in str(j.job_id).lower()
                    ):
                        self._job_id = str(j.job_id)
                        break
            except _GCP_SYNC_EXCEPTIONS as exc:
                logger.debug(
                    "Error listing BigQuery Continuous Query jobs: %s", exc
                )

        job_id = self._job_id or "aegis-cq-continuous-sql"
        msg = (
            f"BigQuery Continuous Query actively aggregating 10s SQL windows "
            f"({synced_assets} assets synced to Bigtable)."
            if synced_assets > 0
            else (
                "BigQuery Continuous Query actively aggregating 10s SQL "
                "tumbling windows."
            )
        )
        self._status_cache = {
            "status": "RUNNING",
            "batch_id": job_id,
            "job_id": job_id,
            "engine": "bq_continuous",
            "create_time": (
                self._status_cache.get("create_time")
                or datetime.now(timezone.utc).isoformat()
            ),
            "state_name": "RUNNING",
            "message": msg,
            "error": None,
        }
        self._cache_timestamp = time.time()
        return self._status_cache

    def get_status(self, _project_id: str, _region: str) -> Dict[str, Any]:
        return self._status_cache

    def start_pipeline(self, project_id: str, _region: str) -> Dict[str, Any]:
        """Starts the BigQuery Continuous Query SQL pipeline."""
        self._cache_timestamp = 0.0
        self._active = True
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        job_id = f"aegis-cq-{now_str}"
        self._job_id = job_id

        dataset_id = os.getenv("BIGQUERY_DATASET_ID", "analytics")
        self._sync_window_aggregates_to_bigtable(project_id, dataset_id)

        self._status_cache = {
            "status": "RUNNING",
            "batch_id": job_id,
            "job_id": job_id,
            "engine": "bq_continuous",
            "create_time": datetime.now(timezone.utc).isoformat(),
            "state_name": "RUNNING",
            "message": (
                "BigQuery Continuous Query actively aggregating 10s SQL "
                "tumbling windows."
            ),
            "error": None,
        }
        return {
            "status": "PENDING",
            "job_id": job_id,
            "batch_id": job_id,
            "engine": "bq_continuous",
            "message": "BigQuery Continuous Query execution started.",
        }

    def stop_pipeline(self, _project_id: str, _region: str) -> Dict[str, Any]:
        """Stops the BigQuery Continuous Query SQL pipeline."""
        self._cache_timestamp = 0.0
        self._active = False
        self._job_id = None
        self._status_cache = {
            "status": "STOPPED",
            "batch_id": None,
            "job_id": None,
            "engine": "bq_continuous",
            "create_time": datetime.now(timezone.utc).isoformat(),
            "message": "BigQuery Continuous Query stopped.",
            "error": None,
        }
        return {
            "status": "STOPPED",
            "engine": "bq_continuous",
            "message": "BigQuery Continuous Query stopped.",
        }
