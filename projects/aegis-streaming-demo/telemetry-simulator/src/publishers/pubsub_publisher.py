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

"""Telemetry Publisher for Google Cloud Pub/Sub."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from publishers.base import BaseTelemetryPublisher

logger = logging.getLogger("aegis-telemetry-simulator")

try:
    import google.auth.exceptions
    from google.api_core.exceptions import GoogleAPICallError
    from google.cloud import pubsub_v1

    PUBSUB_AVAILABLE = True
    _PUBSUB_EXCEPTIONS: tuple[type[Exception], ...] = (
        GoogleAPICallError,
        google.auth.exceptions.GoogleAuthError,
        ValueError,
        TypeError,
        RuntimeError,
        OSError,
    )
except ImportError:
    PUBSUB_AVAILABLE = False
    _PUBSUB_EXCEPTIONS = (
        ValueError,
        TypeError,
        RuntimeError,
        OSError,
    )
    logger.warning(
        "google-cloud-pubsub is not installed. Pub/Sub publishing will run in "
        "simulated mode."
    )


class PubSubTelemetryPublisher(BaseTelemetryPublisher):
    """Handles high-throughput publishing to Google Cloud Pub/Sub."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        topic: Optional[str] = None,
    ):
        self.project_id = (
            project_id
            or os.getenv("GCP_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("PROJECT_ID", "")
        )
        self.topic = (
            topic
            or os.getenv("PUBSUB_TOPIC")
            or os.getenv("KAFKA_TOPIC")
            or "telemetry-raw"
        )
        self.ingestion_type = "pubsub"
        self.publisher = None
        self.topic_path = None
        self._init_publisher()

    def _init_publisher(self):
        if not PUBSUB_AVAILABLE or not self.project_id:
            logger.info(
                "Pub/Sub publisher operating in simulated mode (no project "
                "or client unavailable)."
            )
            self.publisher = None
            return

        try:
            batch_settings = pubsub_v1.types.BatchSettings(
                max_messages=100,
                max_bytes=1024 * 1024,
                max_latency=0.05,
            )
            self.publisher = pubsub_v1.PublisherClient(
                batch_settings=batch_settings
            )
            if "/" in self.topic:
                self.topic_path = self.topic
            else:
                self.topic_path = self.publisher.topic_path(
                    self.project_id, self.topic
                )
            logger.info(
                "Initialized Google Cloud Pub/Sub Publisher for topic: %s",
                self.topic_path,
            )
        except _PUBSUB_EXCEPTIONS as exc:
            logger.warning(
                "Could not initialize Pub/Sub PublisherClient: %s. "
                "Running in simulated mode.",
                exc,
            )
            self.publisher = None

    def publish_messages(self, messages: List[Dict[str, Any]]) -> int:
        """Publishes telemetry message dicts to the configured Pub/Sub topic."""
        if not messages:
            return 0

        published_count = 0
        for msg in messages:
            asset_id = msg.get("asset_id", "Asset-00")
            event_id = msg.get("event_id", "")
            is_anomaly = str(msg.get("is_anomaly", False))
            payload_bytes = json.dumps(msg).encode("utf-8")

            if self.publisher and self.topic_path:
                try:
                    self.publisher.publish(
                        self.topic_path,
                        data=payload_bytes,
                        asset_id=asset_id,
                        event_id=event_id,
                        is_anomaly=is_anomaly,
                    )
                    published_count += 1
                except _PUBSUB_EXCEPTIONS as exc:
                    logger.error(
                        "Failed publishing message to Pub/Sub for %s: %s",
                        asset_id,
                        exc,
                    )
            else:
                published_count += 1

        return published_count

    def flush(self) -> None:
        """Flushes buffered messages if publisher client supports it."""
        # pubsub_v1 PublisherClient automatically batches and flushes
        # based on batch_settings (max_latency=0.05).

    def close(self) -> None:
        """Closes publisher client."""
        if self.publisher and hasattr(self.publisher, "stop"):
            try:
                self.publisher.stop()
            except _PUBSUB_EXCEPTIONS as exc:
                logger.debug("Error stopping Pub/Sub publisher: %s", exc)
