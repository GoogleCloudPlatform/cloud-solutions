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

"""Project Aegis - Telemetry Fleet Simulator Engine.

Manages in-memory fleet state for 15 industrial assets, natural sensor drift,
anomaly injection/normalization, and sliding-window 5-minute telemetry metrics.
Supports dynamic message generation rates (e.g. 15, 50, 100, 250, 500 msgs/sec).
"""

import asyncio
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from kafka_producer import ManagedKafkaProducer
from models import StreamStatusResponse

logger = logging.getLogger("aegis-telemetry-simulator")


class FleetSimulator:
    """Simulates industrial machinery telemetry across 15 assets."""

    def __init__(self, kafka_producer: Optional[ManagedKafkaProducer] = None):
        self.asset_ids: List[str] = [f"Asset-{i:02d}" for i in range(1, 16)]
        self.running: bool = False
        self.target_rate: int = int(os.getenv("TARGET_MSGS_PER_SEC", "100"))
        self.kafka_producer = kafka_producer or ManagedKafkaProducer()
        self.states: Dict[str, Dict[str, Any]] = {}
        self.message_timestamps: List[float] = []
        self._streaming_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        self._reset_all_assets_normalized()

    def _reset_all_assets_normalized(self):
        """Initializes or resets all 15 assets to healthy parameters."""
        now_str = datetime.now(timezone.utc).isoformat()
        for asset_id in self.asset_ids:
            self.states[asset_id] = {
                "asset_id": asset_id,
                "cpu_utilization": round(random.uniform(25.0, 45.0), 2),
                "temperature_c": round(random.uniform(45.0, 62.0), 2),
                "pressure_psi": round(random.uniform(32.0, 48.0), 2),
                "memory_utilization_pct": round(random.uniform(35.0, 55.0), 2),
                "status": "OK",
                "is_anomaly": False,
                "timestamp": now_str,
            }

    def _normalize_asset(self, asset_id: str) -> Dict[str, Any]:
        """Normalizes a single asset back to healthy baseline parameters."""
        now_str = datetime.now(timezone.utc).isoformat()
        self.states[asset_id].update(
            {
                "cpu_utilization": round(random.uniform(28.0, 38.0), 2),
                "temperature_c": round(random.uniform(48.0, 56.0), 2),
                "pressure_psi": round(random.uniform(32.0, 42.0), 2),
                "memory_utilization_pct": round(random.uniform(35.0, 48.0), 2),
                "status": "OK",
                "is_anomaly": False,
                "timestamp": now_str,
            }
        )
        return self.states[asset_id]

    async def start_stream(
        self, target_rate: Optional[int] = None
    ) -> Dict[str, Any]:
        """Starts simulating telemetry and streaming to Kafka."""
        async with self._lock:
            if target_rate and target_rate >= 1:
                self.target_rate = min(5000, target_rate)

            self._reset_all_assets_normalized()
            self.running = True

            if self._streaming_task is None or self._streaming_task.done():
                self._streaming_task = asyncio.create_task(
                    self._streaming_loop()
                )

            logger.info(
                "Telemetry streaming STARTED at %d msgs/sec.",
                self.target_rate,
            )
            msg = (
                f"Telemetry streaming started at {self.target_rate} msgs/sec. "
                "All 15 assets normalized to healthy baseline."
            )
            return {
                "status": "running",
                "running": True,
                "target_rate_msgs_per_sec": self.target_rate,
                "message": msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def stop_stream(self) -> Dict[str, Any]:
        """Stops simulating telemetry and streaming to Kafka."""
        async with self._lock:
            self.running = False
            if self._streaming_task and not self._streaming_task.done():
                self._streaming_task.cancel()
                try:
                    await self._streaming_task
                except asyncio.CancelledError:
                    pass
                self._streaming_task = None

            logger.info("Telemetry streaming STOPPED.")
            self.target_rate = int(os.getenv("TARGET_MSGS_PER_SEC", "100"))
            return {
                "status": "stopped",
                "running": False,
                "target_rate_msgs_per_sec": self.target_rate,
                "message": (
                    "Telemetry streaming stopped. Target rate reset to "
                    "default 100 msgs/sec."
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def create_anomaly(self) -> Tuple[str, Dict[str, Any]]:
        """Chooses one asset at random and creates an anomaly in its state."""
        if not self.running:
            raise ValueError(
                "Cannot create anomaly: telemetry stream is stopped. "
                "Please start stream first."
            )

        healthy_assets = [
            aid for aid, s in self.states.items() if not s["is_anomaly"]
        ]
        chosen_id = random.choice(
            healthy_assets if healthy_assets else self.asset_ids
        )

        cpu = round(random.uniform(94.5, 98.5), 1)
        temp = round(random.uniform(92.0, 96.5), 1)
        pressure = round(random.uniform(110.0, 125.0), 1)
        memory = round(random.uniform(85.0, 95.0), 1)
        now_str = datetime.now(timezone.utc).isoformat()

        self.states[chosen_id].update(
            {
                "cpu_utilization": cpu,
                "temperature_c": temp,
                "pressure_psi": pressure,
                "memory_utilization_pct": memory,
                "status": "CRITICAL",
                "is_anomaly": True,
                "timestamp": now_str,
            }
        )

        logger.info(
            "[Anomaly Injected] Asset %s set to CRITICAL (CPU: %f%%, "
            "Temp: %fC).",
            chosen_id,
            cpu,
            temp,
        )
        return chosen_id, self.states[chosen_id]

    def fix_anomaly(self, asset_id: str) -> Dict[str, Any]:
        """Normalizes an asset back to healthy baseline."""
        if asset_id not in self.states:
            raise KeyError(
                f"Unknown asset_id: '{asset_id}'. Must be Asset-01 to Asset-15."
            )

        normalized_state = self._normalize_asset(asset_id)
        logger.info(
            "[Anomaly Normalized] Asset %s normalized to OK baseline.",
            asset_id,
        )
        return normalized_state

    def get_status(self) -> StreamStatusResponse:
        """Calculates 5-minute rolling metrics."""
        now_ts = time.time()
        cutoff_5m = now_ts - 300.0

        self.message_timestamps = [
            ts for ts in self.message_timestamps if ts >= cutoff_5m
        ]
        total_5m = len(self.message_timestamps)

        rate_msgs_per_sec = round(total_5m / 300.0, 2) if total_5m > 0 else 0.0
        rate_formatted = (
            f"{rate_msgs_per_sec:.1f} msgs/sec in the last 5 minutes"
        )

        active_anomalies = [
            aid for aid, s in self.states.items() if s.get("is_anomaly", False)
        ]

        return StreamStatusResponse(
            status="running" if self.running else "stopped",
            running=self.running,
            target_rate_msgs_per_sec=self.target_rate,
            total_messages_last_5m=total_5m,
            rate_msgs_per_sec_5m=rate_msgs_per_sec,
            rate_formatted=rate_formatted,
            active_anomalies=active_anomalies,
            assets_count=len(self.asset_ids),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _update_drift(self):
        """Applies realistic natural sensor drift to all assets."""
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
            state["status"] = "WARNING" if (cpu > 75.0 or temp > 75.0) else "OK"

    async def _streaming_loop(self):
        """Continuous background generator publishing at target_rate."""
        logger.info(
            "Background streaming loop initiated at target_rate=%d msgs/sec.",
            self.target_rate,
        )

        while self.running:
            try:
                loop_start = time.time()
                self._update_drift()
                now_ts = time.time()
                now_str = datetime.now(timezone.utc).isoformat()

                num_assets = len(self.asset_ids)
                if self.target_rate <= num_assets:
                    sleep_interval = 1.0
                    multiplier = 1
                elif self.target_rate <= 150:
                    sleep_interval = max(
                        0.05, num_assets / float(self.target_rate)
                    )
                    multiplier = 1
                else:
                    sleep_interval = 0.10
                    multiplier = max(
                        1, round(self.target_rate / (num_assets * 10.0))
                    )

                batch_messages = []
                for asset_id in self.asset_ids:
                    st = self.states[asset_id]
                    for _ in range(multiplier):
                        rand_id = random.randint(100, 999)
                        evt_ts = int(now_ts * 1000)
                        evt_id = f"evt-{asset_id}-{evt_ts}-{rand_id}"
                        payload = {
                            "event_id": evt_id,
                            "asset_id": asset_id,
                            "timestamp": now_str,
                            "cpu_utilization": st["cpu_utilization"],
                            "temperature_c": st["temperature_c"],
                            "pressure_psi": st["pressure_psi"],
                            "memory_utilization_pct": st[
                                "memory_utilization_pct"
                            ],
                            "status": st["status"],
                            "is_anomaly": st["is_anomaly"],
                        }
                        batch_messages.append(payload)
                        self.message_timestamps.append(now_ts)

                self.kafka_producer.publish_messages(batch_messages)

                elapsed = time.time() - loop_start
                sleep_time = max(0.01, sleep_interval - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error in streaming loop iteration: %s", e)
                await asyncio.sleep(0.5)

        logger.info("Background telemetry streaming loop terminated.")
