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

import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aegis-hud-backend")


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
    except Exception:  # pylint: disable=broad-exception-caught
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TelemetryStateManager:
    """Manages real-time state for 15 industrial assets backed by Bigtable."""

    def __init__(self):
        self.simulator_running: bool = False
        self.asset_ids: List[str] = [f"Asset-{i:02d}" for i in range(1, 16)]
        self.project_id: str = os.getenv(
            "GCP_PROJECT",
            os.getenv("GOOGLE_CLOUD_PROJECT", "aegis-streaming-1001"),
        )
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
            }

        self._sync_initial_bigtable_state()

    def store_mitigation(self, asset_id: str, data: Dict[str, Any]):
        self.latest_mitigations[asset_id] = data

    def get_mitigation(self, asset_id: str) -> Optional[Dict[str, Any]]:
        return self.latest_mitigations.get(asset_id)

    def get_all_mitigations(self) -> Dict[str, Any]:
        return self.latest_mitigations

    def _init_bigtable(self):
        try:
            # pylint: disable=import-outside-toplevel
            from google.cloud import bigtable

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
        except Exception as e:  # pylint: disable=broad-exception-caught
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
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "Failed to persist simulator state to Bigtable: %s", e
                )

    def sync_simulator_running_from_bigtable(self):
        """Syncs simulator running state from Bigtable."""
        if not self.bt_table:
            return
        try:
            row = self.bt_table.read_row("_simulator_control".encode("utf-8"))
            if row:
                cols = row.cells.get(self.column_family, {})
                cell_list = cols.get(b"running")
                if cell_list and len(cell_list) > 0:
                    val = cell_list[0].value.decode("utf-8")
                    self.simulator_running = val.lower() == "true"
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.debug("Bigtable simulator status sync exception: %s", e)

    def get_simulator_running(self) -> bool:
        """Return authoritative in-memory simulator running flag."""
        return self.simulator_running

    def _sync_initial_bigtable_state(self):
        """Read existing Bigtable state or write initial baseline rows."""
        if not self.bt_table:
            return

        try:
            rows = list(self.bt_table.read_rows())
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
        except Exception as e:  # pylint: disable=broad-exception-caught
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

        ts_normalized = normalize_utc_iso_timestamp(ts)

        is_stale = False
        data_age_seconds = 0.0
        try:
            clean_ts = ts_normalized.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            data_age_seconds = (datetime.now(timezone.utc) - dt).total_seconds()
            if data_age_seconds > 3600.0:
                is_stale = True
        except Exception:  # pylint: disable=broad-exception-caught
            is_stale = True

        is_anomaly = (
            str(is_anomaly_raw).lower() == "true"
            or status == "CRITICAL"
            or cpu > 90.0
            or temp > 90.0
        ) and not is_stale
        effective_status = "EXPIRED" if is_stale else status

        return {
            "cpu_utilization": cpu,
            "temperature_c": temp,
            "pressure_psi": pressure,
            "memory_utilization_pct": memory,
            "status": effective_status,
            "raw_status": status,
            "is_anomaly": is_anomaly,
            "is_stale": is_stale,
            "data_age_seconds": round(max(0.0, data_age_seconds), 1),
            "timestamp": ts_normalized,
        }

    def _persist_all_to_bigtable(self):
        """Write current states for all assets to Cloud Bigtable."""
        if not self.bt_table:
            return
        try:
            from google.cloud.bigtable.row import (  # pylint: disable=import-outside-toplevel
                DirectRow,
            )

            rows = []
            for asset_id, state in self.states.items():
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
                rows.append(row)

            errors = self.bt_table.mutate_rows(rows)
            if errors:
                for err in errors:
                    logger.error("Error seeding Bigtable row: %s", err)
            else:
                logger.info("Persisted %d rows to Bigtable.", len(rows))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to persist state to Bigtable: %s", e)

    def read_from_bigtable(self) -> List[Dict[str, Any]]:
        """Directly query Cloud Bigtable for all 15 asset states."""
        if not self.bt_table:
            return self.get_cached_snapshot()

        try:
            rows = list(self.bt_table.read_rows())
            if not rows:
                return self.get_cached_snapshot()

            snapshot = []
            found_ids = set()
            for row in rows:
                asset_id = row.row_key.decode("utf-8")
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
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error reading live rows from Bigtable: %s", e)
            return self.get_cached_snapshot()

    def get_cached_snapshot(self) -> List[Dict[str, Any]]:
        snapshot = []
        now_utc = datetime.now(timezone.utc)
        for asset_id in self.asset_ids:
            state = dict(self.states[asset_id])
            ts_str = state.get("timestamp", "")
            is_stale = False
            data_age_sec = 0.0
            try:
                clean_ts = ts_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                data_age_sec = (now_utc - dt).total_seconds()
                if data_age_sec > 3600.0:
                    is_stale = True
            except Exception:  # pylint: disable=broad-exception-caught
                is_stale = True

            state["is_stale"] = is_stale
            state["data_age_seconds"] = round(max(0.0, data_age_sec), 1)
            if is_stale:
                state["is_anomaly"] = False
                state["raw_status"] = state.get("status", "OK")
                state["status"] = "EXPIRED"

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
        self.states[asset_id].update(
            {
                "cpu_utilization": cpu,
                "temperature_c": temp,
                "pressure_psi": pressure,
                "memory_utilization_pct": 88.5,
                "status": "CRITICAL",
                "is_anomaly": True,
                "timestamp": now_str,
            }
        )

        if self.bt_table:
            try:
                from google.cloud.bigtable.row import (  # pylint: disable=import-outside-toplevel
                    DirectRow,
                )

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
                self.bt_table.mutate_rows([row])
                logger.info(
                    "[Simulator Signal] Injected anomaly into Bigtable for %s",
                    asset_id,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
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
        """Resets the asset's simulated physical metrics to normal baseline."""
        if asset_id not in self.states:
            raise KeyError(f"Unknown asset_id: {asset_id}")

        now_str = datetime.now(timezone.utc).isoformat()
        cpu = round(random.uniform(28.0, 38.0), 2)
        temp = round(random.uniform(48.0, 56.0), 2)
        pressure = round(random.uniform(32.0, 42.0), 2)
        memory = round(random.uniform(35.0, 48.0), 2)

        self.states[asset_id].update(
            {
                "cpu_utilization": cpu,
                "temperature_c": temp,
                "pressure_psi": pressure,
                "memory_utilization_pct": memory,
                "status": "OK",
                "is_anomaly": False,
                "timestamp": now_str,
            }
        )

        if self.bt_table:
            try:
                from google.cloud.bigtable.row import (  # pylint: disable=import-outside-toplevel
                    DirectRow,
                )

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
                row.set_cell(
                    self.column_family, b"memory", str(memory).encode("utf-8")
                )
                row.set_cell(self.column_family, b"status", b"OK")
                row.set_cell(self.column_family, b"is_anomaly", b"False")
                row.set_cell(
                    self.column_family, b"timestamp", now_str.encode("utf-8")
                )
                self.bt_table.mutate_rows([row])
                logger.info(
                    "[Simulator Relieve] Mutated Bigtable row for %s to "
                    "healthy baseline.",
                    asset_id,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Failed mutating Bigtable row for relieved anomaly: %s", e
                )

        simulator_url = os.getenv(
            "SIMULATOR_SERVICE_URL",
            "https://telemetry-simulator-yww5w7x2xa-uc.a.run.app",
        )
        try:
            import httpx  # pylint: disable=import-outside-toplevel

            with httpx.Client(timeout=3.0) as client:
                clean_url = simulator_url.rstrip("/")
                client.post(
                    f"{clean_url}/api/fix-anomoly",
                    json={"asset_id": asset_id},
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.debug(
                "Could not signal telemetry simulator during relieve: %s", e
            )

        logger.info(
            "[Simulator Relieve] Physical asset %s state reset.", asset_id
        )
        return {"asset_id": asset_id, **self.states[asset_id]}


class TelemetryStreamPublisher:
    """Publishes telemetry data batches to Kafka."""

    def __init__(self):
        self.project_id = os.getenv(
            "GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "")
        )
        self.kafka_brokers = os.getenv("KAFKA_BROKERS")
        self.kafka_topic = os.getenv("KAFKA_TOPIC", "telemetry-raw")

        self.kafka_messages_sent_timestamps = []
        self.kafka_producer = None
        if self.kafka_brokers:
            try:
                import base64  # pylint: disable=import-outside-toplevel

                import google.auth  # pylint: disable=import-outside-toplevel

                # pylint: disable=import-outside-toplevel
                from confluent_kafka import Producer as KafkaProducerClient
                from google.auth.transport.requests import (
                    Request as AuthRequest,  # pylint: disable=import-outside-toplevel
                )

                def oauth_cb(_config):
                    creds, _ = google.auth.default(
                        scopes=[
                            "https://www.googleapis.com/auth/cloud-platform"
                        ]
                    )
                    if not creds.valid:
                        creds.refresh(AuthRequest())
                    expiry_sec = (
                        creds.expiry.timestamp()
                        if creds.expiry
                        else (time.time() + 3600)
                    )
                    sa_email = (
                        getattr(creds, "service_account_email", None)
                        or getattr(creds, "account", None)
                        or os.environ.get("SERVICE_ACCOUNT")
                    )
                    if not sa_email:
                        raise RuntimeError(
                            "SERVICE_ACCOUNT env variable is not set."
                        )
                    header = {"alg": "GOOG_OAUTH2_TOKEN", "typ": "JWT"}
                    payload = {
                        "exp": int(expiry_sec),
                        "iss": "Google",
                        "iat": int(time.time()),
                        "sub": sa_email,
                    }

                    def b64url(d):
                        if isinstance(d, dict):
                            data = json.dumps(d).encode("utf-8")
                        else:
                            data = (
                                d.encode("utf-8") if isinstance(d, str) else d
                            )
                        return (
                            base64.urlsafe_b64encode(data)
                            .rstrip(b"=")
                            .decode("utf-8")
                        )

                    jwt_token = (
                        f"{b64url(header)}.{b64url(payload)}."
                        f"{b64url(creds.token)}"
                    )
                    logger.info(
                        "Refreshed Kafka OAuth JWT token for sub=%s",
                        sa_email,
                    )
                    return jwt_token, expiry_sec

                conf = {
                    "bootstrap.servers": self.kafka_brokers,
                    "security.protocol": "SASL_SSL",
                    "sasl.mechanisms": "OAUTHBEARER",
                    "oauth_cb": oauth_cb,
                }
                self.kafka_producer = KafkaProducerClient(conf)
                logger.info(
                    "Initialized Managed Kafka producer for brokers: %s",
                    self.kafka_brokers,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Could not initialize Kafka producer: %s", e)

    def publish_snapshot(self, snapshot: List[Dict[str, Any]]):
        """Publish a list of asset telemetry dictionaries to Kafka."""
        now_ts = time.time()
        cutoff = now_ts - 300
        for _ in snapshot:
            self.kafka_messages_sent_timestamps.append(now_ts)
        self.kafka_messages_sent_timestamps = [
            ts for ts in self.kafka_messages_sent_timestamps if ts >= cutoff
        ]

        for asset in snapshot:
            aid = asset["asset_id"]
            ats = asset["timestamp"]
            payload = {
                "event_id": f"evt-{aid}-{ats}",
                "asset_id": aid,
                "timestamp": ats,
                "cpu_utilization": asset["cpu_utilization"],
                "temperature_c": asset["temperature_c"],
                "pressure_psi": asset["pressure_psi"],
                "memory_utilization_pct": asset["memory_utilization_pct"],
                "status": asset["status"],
                "is_anomaly": asset.get("is_anomaly", False),
            }
            json_bytes = json.dumps(payload).encode("utf-8")
            asset_key = asset["asset_id"].encode("utf-8")

            if self.kafka_producer:
                try:

                    def delivery_report(err, _msg):
                        if err is not None:
                            logger.error("Kafka delivery failed: %s", err)

                    self.kafka_producer.produce(
                        self.kafka_topic,
                        key=asset_key,
                        value=json_bytes,
                        callback=delivery_report,
                    )
                    self.kafka_producer.poll(0)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error(
                        "Kafka produce error for %s: %s",
                        asset["asset_id"],
                        e,
                    )


state_manager = TelemetryStateManager()
stream_publisher = TelemetryStreamPublisher()
