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

"""Telemetry state manager and Bigtable synchronization cache."""

import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import google.auth.exceptions
from google.api_core.exceptions import GoogleAPICallError

try:
    from google.cloud import bigtable
    from google.cloud.bigtable.row import DirectRow
    from google.cloud.bigtable.row_filters import CellsColumnLimitFilter

    BIGTABLE_AVAILABLE = True
except ImportError:
    bigtable = None  # type: ignore
    DirectRow = None  # type: ignore
    CellsColumnLimitFilter = None  # type: ignore
    BIGTABLE_AVAILABLE = False

try:
    from pipeline_clients import get_pipeline_client
except ImportError:
    get_pipeline_client = None  # type: ignore

logger = logging.getLogger("aegis-hud-backend")

_BIGTABLE_EXCEPTIONS = (
    GoogleAPICallError,
    google.auth.exceptions.GoogleAuthError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    OSError,
)


STALE_THRESHOLD_SECONDS = 3600.0
CRITICAL_THRESHOLD = 90.0
WARNING_THRESHOLD = 75.0


def normalize_utc_iso_timestamp(ts_val: Any) -> str:
    """Normalizes timestamp into strict ISO 8601 UTC string ending in 'Z'."""
    if not ts_val:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        s = str(ts_val).strip()
        if not s:
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        s = s.replace(" ", "T")
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s[:-1] + "+00:00")
        elif "+" in s or ("-" in s[10:] and len(s) > 19):
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _evaluate_staleness_and_status(
    state_dict: dict[str, Any], now_epoch: float
) -> None:
    """Evaluates timestamp staleness and updates status and anomaly flags."""
    ts_str = str(state_dict.get("timestamp", ""))
    is_stale = False
    data_age_sec = 0.0
    try:
        clean_ts = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        data_age_sec = now_epoch - dt.timestamp()
        if data_age_sec > STALE_THRESHOLD_SECONDS:
            is_stale = True
    except (ValueError, TypeError):
        is_stale = True

    cur_status = str(state_dict.get("status", "OK")).upper()
    if cur_status != "EXPIRED":
        state_dict["raw_status"] = state_dict.get("raw_status", cur_status)

    state_dict["is_stale"] = is_stale
    state_dict["data_age_seconds"] = round(max(0.0, data_age_sec), 1)
    if is_stale:
        state_dict["is_anomaly"] = False
        state_dict["status"] = "EXPIRED"
        return

    cpu = float(state_dict.get("cpu_utilization", 0.0))
    temp = float(state_dict.get("temperature_c", 0.0))
    raw_anom = state_dict.get("is_anomaly", False)
    is_anom = (
        raw_anom.lower() == "true"
        if isinstance(raw_anom, str)
        else bool(raw_anom)
    )
    if (
        is_anom
        or cur_status == "CRITICAL"
        or cpu > CRITICAL_THRESHOLD
        or temp > CRITICAL_THRESHOLD
    ):
        state_dict["status"] = "CRITICAL"
        state_dict["is_anomaly"] = True
    elif (
        cur_status == "WARNING"
        or cpu > WARNING_THRESHOLD
        or temp > WARNING_THRESHOLD
    ):
        state_dict["status"] = "WARNING"
        state_dict["is_anomaly"] = False
    else:
        state_dict["status"] = "OK"
        state_dict["is_anomaly"] = False


class TelemetryStateManager:
    """Manages real-time state for 15 industrial assets backed by Bigtable."""

    def __init__(self):
        self.simulator_running: bool = False
        self.asset_ids: List[str] = [f"Asset-{i:02d}" for i in range(1, 16)]
        self.project_id: str = (
            os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""
        ).strip()
        self.bigtable_instance_id: str = os.getenv(
            "BIGTABLE_INSTANCE_ID", "aegis-bigtable"
        )
        self.bigtable_table_id: str = os.getenv(
            "BIGTABLE_TABLE_ID", "telemetry_metrics"
        )
        self.column_family: str = "metrics"

        self.bt_client = None
        self.bt_table = None
        self._init_bigtable()

        self.latest_mitigations: Dict[str, Any] = {}

        self.states: Dict[str, Dict[str, Any]] = {}
        for asset_id in self.asset_ids:
            self.states[asset_id] = {
                "cpu_utilization": round(random.uniform(25.0, 45.0), 2),
                "temperature_c": round(random.uniform(45.0, 62.0), 2),
                "pressure_psi": round(random.uniform(32.0, 48.0), 2),
                "memory_utilization_pct": round(random.uniform(35.0, 55.0), 2),
                "status": "OK",
                "is_anomaly": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ingestion_timestamp_ms": None,
                "db_insert_timestamp_ms": None,
                "pipeline_latency_ms": None,
            }

        self._sync_initial_bigtable_state()

    def store_mitigation(self, asset_id: str, data: Dict[str, Any]):
        """Store the latest AI agent mitigation payload for an asset."""
        self.latest_mitigations[asset_id] = data

    def get_mitigation(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Return the latest stored mitigation payload for an asset, if any."""
        return self.latest_mitigations.get(asset_id)

    def get_all_mitigations(self) -> Dict[str, Any]:
        """Return all stored asset mitigation payloads."""
        return self.latest_mitigations

    def _init_bigtable(self):
        # Note for reviewers: In offline CI/local unit tests
        # (`NO_GCE_CHECK="true"` or when `project_id` is unset), live Bigtable
        # client initialization is skipped and unit tests inject a mocked
        # `bt_table`.
        if (
            not BIGTABLE_AVAILABLE
            or bigtable is None
            or not self.project_id
            or os.getenv("NO_GCE_CHECK") == "true"
        ):
            self.bt_client = None
            self.bt_table = None
            return
        try:
            self.bt_client = bigtable.Client(
                project=self.project_id, admin=False
            )
            instance = self.bt_client.instance(self.bigtable_instance_id)
            self.bt_table = instance.table(self.bigtable_table_id)
            logger.info(
                "Initialized Bigtable client for '%s.%s.%s'",
                self.project_id,
                self.bigtable_instance_id,
                self.bigtable_table_id,
            )
        except _BIGTABLE_EXCEPTIONS as e:
            logger.warning("Could not initialize Bigtable client: %s", e)
            self.bt_client = None
            self.bt_table = None

    def set_simulator_running(self, running: bool):
        """Update simulator running flag and persist to Bigtable control row."""
        self.simulator_running = bool(running)
        logger.info(
            "Telemetry simulator state updated: running=%s",
            self.simulator_running,
        )
        if self.bt_table:
            try:
                row = self.bt_table.direct_row(
                    "_simulator_control".encode("utf-8")
                )
                row.set_cell(
                    self.column_family,
                    "running".encode("utf-8"),
                    str(self.simulator_running).encode("utf-8"),
                    timestamp=datetime.now(timezone.utc),
                )
                row.commit()
            except _BIGTABLE_EXCEPTIONS as e:
                logger.warning(
                    "Failed to persist simulator state to Bigtable: %s", e
                )

    def _latest_cell_filter(self) -> Any:
        """Return a Bigtable row filter limiting reads to the latest version."""
        if CellsColumnLimitFilter is not None:
            return CellsColumnLimitFilter(1)
        return None

    def sync_simulator_running_from_bigtable(self):
        """Syncs simulator running state from Bigtable."""
        if not self.bt_table:
            return
        try:
            row = self.bt_table.read_row(
                "_simulator_control".encode("utf-8"),
                filter_=self._latest_cell_filter(),
            )
            if row:
                cols = row.cells.get(self.column_family, {})
                cell_list = cols.get(b"running")
                if cell_list and len(cell_list) > 0:
                    val = cell_list[0].value.decode("utf-8")
                    self.simulator_running = val.lower() == "true"
        except _BIGTABLE_EXCEPTIONS as e:
            logger.debug("Bigtable simulator status sync exception: %s", e)

    def get_simulator_running(self) -> bool:
        """Return authoritative in-memory simulator running flag."""
        return self.simulator_running

    def _sync_initial_bigtable_state(self):
        """Read existing Bigtable state or write initial baseline rows."""
        if not self.bt_table:
            return

        try:
            rows = list(
                self.bt_table.read_rows(filter_=self._latest_cell_filter())
            )
            if rows:
                logger.info(
                    "Synchronized %d asset rows from Cloud Bigtable.", len(rows)
                )
                for row in rows:
                    asset_id = row.row_key.decode("utf-8")
                    if asset_id in self.asset_ids:
                        self.states[asset_id] = self._parse_bigtable_row(row)
            else:
                logger.info(
                    "Bigtable table empty. Seeding initial baseline rows..."
                )
                self._persist_all_to_bigtable()
        except _BIGTABLE_EXCEPTIONS as e:
            logger.warning("Failed initial Bigtable sync: %s", e)

    def _parse_bigtable_row(self, row) -> Dict[str, Any]:
        cols = row.cells.get(self.column_family, {})

        def get_val(key: str, default: Any):
            cell_list = cols.get(key.encode("utf-8"))
            if cell_list and len(cell_list) > 0:
                return cell_list[0].value.decode("utf-8")
            return default

        cpu_raw = get_val("cpu", "30.0")
        temp_raw = get_val("temp", "50.0")
        press_raw = get_val("pressure", "35.0")
        mem_raw = get_val("memory", "40.0")
        status = get_val("status", "OK")
        is_anomaly_raw = get_val("is_anomaly", "False")
        ts = get_val("timestamp", datetime.now(timezone.utc).isoformat())
        ingestion_ms_raw = get_val("ingestion_timestamp_ms", None)
        db_insert_ms_raw = get_val("db_insert_timestamp_ms", None)

        try:
            cpu = round(float(cpu_raw), 2)
        except ValueError:
            cpu = 30.0
        try:
            temp = round(float(temp_raw), 2)
        except ValueError:
            temp = 50.0
        try:
            pressure = round(float(press_raw), 2)
        except ValueError:
            pressure = 35.0
        try:
            memory = round(float(mem_raw), 2)
        except ValueError:
            memory = 40.0

        ingestion_timestamp_ms: Optional[int] = None
        if ingestion_ms_raw is not None:
            try:
                val = int(float(ingestion_ms_raw))
                if val > 0:
                    ingestion_timestamp_ms = val
            except (ValueError, TypeError):
                ingestion_timestamp_ms = None

        db_insert_timestamp_ms: Optional[int] = None
        if db_insert_ms_raw is not None:
            try:
                val = int(float(db_insert_ms_raw))
                if val > 0:
                    db_insert_timestamp_ms = val
            except (ValueError, TypeError):
                db_insert_timestamp_ms = None

        pipeline_latency_ms: Optional[int] = None
        if (
            ingestion_timestamp_ms is not None
            and db_insert_timestamp_ms is not None
        ):
            pipeline_latency_ms = max(
                0, db_insert_timestamp_ms - ingestion_timestamp_ms
            )

        ts_normalized = normalize_utc_iso_timestamp(ts)
        state_dict: Dict[str, Any] = {
            "cpu_utilization": cpu,
            "temperature_c": temp,
            "pressure_psi": pressure,
            "memory_utilization_pct": memory,
            "status": status,
            "raw_status": status,
            "is_anomaly": str(is_anomaly_raw).lower() == "true",
            "timestamp": ts_normalized,
            "ingestion_timestamp_ms": ingestion_timestamp_ms,
            "db_insert_timestamp_ms": db_insert_timestamp_ms,
            "pipeline_latency_ms": pipeline_latency_ms,
        }
        _evaluate_staleness_and_status(state_dict, time.time())
        return state_dict

    def _persist_all_to_bigtable(self):
        """Write current states for all assets to Cloud Bigtable."""
        if not self.bt_table or DirectRow is None:
            return
        try:
            now_ms = int(time.time() * 1000)
            rows = []
            for asset_id, state in self.states.items():
                ing_ms = state.get("ingestion_timestamp_ms") or now_ms
                db_ms = state.get("db_insert_timestamp_ms") or now_ms
                state["ingestion_timestamp_ms"] = ing_ms
                state["db_insert_timestamp_ms"] = db_ms
                row = DirectRow(row_key=asset_id.encode("utf-8"))
                row.set_cell(
                    self.column_family,
                    b"cpu",
                    str(state["cpu_utilization"]).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"temp",
                    str(state["temperature_c"]).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"pressure",
                    str(state["pressure_psi"]).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"memory",
                    str(state["memory_utilization_pct"]).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"status",
                    str(state["status"]).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"is_anomaly",
                    str(state["is_anomaly"]).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"timestamp",
                    str(state["timestamp"]).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"ingestion_timestamp_ms",
                    str(ing_ms).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"db_insert_timestamp_ms",
                    str(db_ms).encode("utf-8"),
                )
                rows.append(row)

            statuses = self.bt_table.mutate_rows(rows)
            failed_errors = [
                err for err in (statuses or []) if getattr(err, "code", 0) != 0
            ]
            if failed_errors:
                for err in failed_errors:
                    logger.error("Error seeding Bigtable row: %s", err)
            else:
                logger.info("Persisted %d rows to Bigtable.", len(rows))
        except _BIGTABLE_EXCEPTIONS as e:
            logger.error("Failed to persist state to Bigtable: %s", e)

    def _maybe_sync_continuous_query(self) -> None:
        """Sync BigQuery Continuous Query windows if active and due."""
        engine = os.getenv("PIPELINE_ENGINE", "").lower()
        if engine not in (
            "bq_continuous",
            "continuous_query",
            "bigquery_continuous",
        ):
            return
        now_ts = time.time()
        if now_ts - getattr(self, "_last_cq_sync", 0.0) < 3.0:
            return
        self._last_cq_sync = now_ts
        if get_pipeline_client is None:
            return
        try:
            client = get_pipeline_client()
            client.refresh_status_sync(
                self.project_id,
                os.getenv("GCP_REGION", "us-central1"),
            )
        except _BIGTABLE_EXCEPTIONS as e:
            logger.debug(
                "Non-critical Continuous Query sync exception: %s",
                e,
            )

    def read_from_bigtable(self) -> List[Dict[str, Any]]:
        """Directly query Cloud Bigtable for all 15 asset states."""
        if not self.bt_table:
            return self.get_cached_snapshot()

        self._maybe_sync_continuous_query()

        try:
            rows = list(
                self.bt_table.read_rows(filter_=self._latest_cell_filter())
            )
            if not rows:
                return self.get_cached_snapshot()

            snapshot = []
            found_ids = set()
            for row in rows:
                asset_id = row.row_key.decode("utf-8")
                if asset_id not in self.asset_ids:
                    continue
                parsed = self._parse_bigtable_row(row)
                self.states[asset_id] = parsed
                found_ids.add(asset_id)
                snapshot.append({"asset_id": asset_id, **parsed})

            for asset_id in self.asset_ids:
                if asset_id not in found_ids:
                    snapshot.append(
                        {"asset_id": asset_id, **self.states[asset_id]}
                    )

            snapshot.sort(key=lambda a: a["asset_id"])
            return snapshot
        except _BIGTABLE_EXCEPTIONS as e:
            logger.error("Error reading live rows from Bigtable: %s", e)
            return self.get_cached_snapshot()

    def get_cached_snapshot(self) -> List[Dict[str, Any]]:
        """Return the sorted in-memory telemetry snapshot."""
        snapshot = []
        now_epoch = time.time()
        for asset_id in self.asset_ids:
            state = dict(self.states[asset_id])
            _evaluate_staleness_and_status(state, now_epoch)
            snapshot.append({"asset_id": asset_id, **state})
        snapshot.sort(key=lambda a: a["asset_id"])
        return snapshot

    def get_snapshot(self) -> List[Dict[str, Any]]:
        """Primary snapshot entry point: returns cached snapshot instantly."""
        return self.get_cached_snapshot()

    def update_drift(self):
        """Simulate natural sensor drift across assets."""
        if not self.simulator_running:
            return

        now_str = datetime.now(timezone.utc).isoformat()
        for state in self.states.values():
            state["timestamp"] = now_str

            if state["is_anomaly"]:
                state["cpu_utilization"] = round(
                    max(
                        91.0,
                        min(
                            99.5,
                            state["cpu_utilization"]
                            + random.uniform(-0.5, 0.5),
                        ),
                    ),
                    2,
                )
                state["temperature_c"] = round(
                    max(
                        90.0,
                        min(
                            105.0,
                            state["temperature_c"] + random.uniform(-0.3, 0.6),
                        ),
                    ),
                    2,
                )
                state["status"] = "CRITICAL"
                continue

            cpu_drift = random.uniform(-2.0, 2.0)
            temp_drift = random.uniform(-1.0, 1.0)
            pressure_drift = random.uniform(-1.5, 1.5)
            memory_drift = random.uniform(-1.0, 1.0)

            cpu = round(
                max(15.0, min(80.0, state["cpu_utilization"] + cpu_drift)), 2
            )
            temp = round(
                max(35.0, min(82.0, state["temperature_c"] + temp_drift)), 2
            )
            pressure = round(
                max(20.0, min(65.0, state["pressure_psi"] + pressure_drift)), 2
            )
            memory = round(
                max(
                    20.0,
                    min(80.0, state["memory_utilization_pct"] + memory_drift),
                ),
                2,
            )

            state["cpu_utilization"] = cpu
            state["temperature_c"] = temp
            state["pressure_psi"] = pressure
            state["memory_utilization_pct"] = memory

            if cpu > 75.0 or temp > 75.0:
                state["status"] = "WARNING"
            else:
                state["status"] = "OK"

    def inject_anomaly(
        self,
        asset_id: str,
        cpu: float = 96.5,
        temp: float = 94.8,
        pressure: float = 115.0,
    ) -> Dict[str, Any]:
        """Simulates physical sensor malfunction/thermal runaway."""
        if asset_id not in self.states:
            raise KeyError(f"Unknown asset_id: {asset_id}")

        now_str = datetime.now(timezone.utc).isoformat()
        now_ms = int(time.time() * 1000)
        self.states[asset_id].update(
            {
                "cpu_utilization": cpu,
                "temperature_c": temp,
                "pressure_psi": pressure,
                "memory_utilization_pct": 88.5,
                "status": "CRITICAL",
                "is_anomaly": True,
                "timestamp": now_str,
                "ingestion_timestamp_ms": now_ms,
                "db_insert_timestamp_ms": now_ms,
                "pipeline_latency_ms": 0,
            }
        )

        if self.bt_table and DirectRow is not None:
            try:
                row = DirectRow(row_key=asset_id.encode("utf-8"))
                row.set_cell(
                    self.column_family, b"cpu", str(cpu).encode("utf-8")
                )
                row.set_cell(
                    self.column_family, b"temp", str(temp).encode("utf-8")
                )
                row.set_cell(
                    self.column_family,
                    b"pressure",
                    str(pressure).encode("utf-8"),
                )
                row.set_cell(self.column_family, b"memory", b"88.5")
                row.set_cell(self.column_family, b"status", b"CRITICAL")
                row.set_cell(self.column_family, b"is_anomaly", b"True")
                row.set_cell(
                    self.column_family, b"timestamp", now_str.encode("utf-8")
                )
                row.set_cell(
                    self.column_family,
                    b"ingestion_timestamp_ms",
                    str(now_ms).encode("utf-8"),
                )
                row.set_cell(
                    self.column_family,
                    b"db_insert_timestamp_ms",
                    str(now_ms).encode("utf-8"),
                )
                self.bt_table.mutate_rows([row])
                logger.info(
                    "[Simulator Signal] Injected anomaly into Bigtable for %s",
                    asset_id,
                )
            except _BIGTABLE_EXCEPTIONS as e:
                logger.error("Failed mutating Bigtable row for anomaly: %s", e)

        logger.info(
            "[Simulator Signal] Physical asset %s anomaly -> CPU: %f%%, "
            "Temp: %fC",
            asset_id,
            cpu,
            temp,
        )
        return {"asset_id": asset_id, **self.states[asset_id]}

    def relieve_anomaly(self, asset_id: str) -> Dict[str, Any]:
        """Deprecated: State is restored exclusively by AI Agent actuator."""
        logger.info(
            "[State] relieve_anomaly called for %s (no-op; agent actuator "
            "drives simulation state).",
            asset_id,
        )
        if asset_id in self.states:
            return {"asset_id": asset_id, **self.states[asset_id]}
        raise KeyError(f"Unknown asset_id: {asset_id}")


state_manager = TelemetryStateManager()
