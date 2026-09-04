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

"""Project Aegis - Telemetry Simulator Kafka Producer.

Authenticated Apache Kafka producer for Google Cloud Managed Kafka.
"""

import base64
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("aegis-telemetry-simulator")

try:
    from confluent_kafka import Producer as KafkaProducerClient

    CONFLUENT_KAFKA_AVAILABLE = True
except ImportError:
    CONFLUENT_KAFKA_AVAILABLE = False
    logger.warning(
        "confluent_kafka is not installed. Kafka publishing will run in "
        "simulated mode."
    )


class ManagedKafkaProducer:
    """Handles authenticated Kafka publishing to Google Cloud Managed Kafka."""

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        topic: Optional[str] = None,
        service_account_email: Optional[str] = None,
    ):
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BROKERS", ""
        )
        self.topic = topic or os.getenv("KAFKA_TOPIC", "telemetry-raw")
        self.service_account_email = service_account_email or os.getenv(
            "SERVICE_ACCOUNT", ""
        )
        self.producer = None
        self._init_producer()

    def _get_oauth_token(self) -> Tuple[str, float]:
        """Generate OAuth2 JWT token required by Google Cloud Managed Kafka."""
        # pylint: disable=import-outside-toplevel
        import google.auth
        from google.auth.transport.requests import Request as AuthRequest

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        if not creds.valid:
            creds.refresh(AuthRequest())

        expiry_sec = (
            creds.expiry.timestamp() if creds.expiry else (time.time() + 3600)
        )
        sa_email = (
            self.service_account_email
            or getattr(creds, "service_account_email", None)
            or getattr(creds, "account", None)
        )
        if not sa_email:
            sa_email = "aegis-sa@aegis-streaming-1001.iam.gserviceaccount.com"

        header = {"alg": "GOOG_OAUTH2_TOKEN", "typ": "JWT"}
        payload = {
            "exp": int(expiry_sec),
            "iss": "Google",
            "iat": int(time.time()),
            "sub": sa_email,
        }

        def b64url(d: Any) -> str:
            if isinstance(d, dict):
                data = json.dumps(d).encode("utf-8")
            else:
                data = d.encode("utf-8") if isinstance(d, str) else d
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

        jwt_token = f"{b64url(header)}.{b64url(payload)}.{b64url(creds.token)}"
        logger.debug(
            "Refreshed Kafka OAuth JWT token for sub=%s (expires at %f)",
            sa_email,
            expiry_sec,
        )
        return jwt_token, expiry_sec

    def _init_producer(self):
        if not CONFLUENT_KAFKA_AVAILABLE or not self.bootstrap_servers:
            logger.info(
                "Kafka producer operating in simulated mode (no brokers or "
                "client unavailable)."
            )
            self.producer = None
            return

        try:

            def oauth_callback(_config: Any) -> Tuple[str, float]:
                return self._get_oauth_token()

            conf = {
                "bootstrap.servers": self.bootstrap_servers,
                "security.protocol": "SASL_SSL",
                "sasl.mechanisms": "OAUTHBEARER",
                "oauth_cb": oauth_callback,
                "client.id": "aegis-telemetry-simulator",
                "queue.buffering.max.messages": 100000,
                "queue.buffering.max.kbytes": 10240,
                "batch.num.messages": 100,
            }
            self.producer = KafkaProducerClient(conf)
            logger.info(
                "Initialized Managed Kafka Producer for brokers: %s | "
                "Topic: %s",
                self.bootstrap_servers,
                self.topic,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Could not initialize KafkaProducerClient: %s. "
                "Running in simulated mode.",
                exc,
            )
            self.producer = None

    def publish_messages(self, messages: List[Dict[str, Any]]) -> int:
        """Publishes telemetry message dicts to the configured Kafka topic."""
        if not messages:
            return 0

        published_count = 0
        for msg in messages:
            asset_id = msg.get("asset_id", "Asset-00")
            key = asset_id.encode("utf-8")
            value = json.dumps(msg).encode("utf-8")

            if self.producer:
                try:

                    def delivery_callback(err, _kmsg, target_id=asset_id):
                        if err:
                            logger.error(
                                "Kafka message delivery failed for %s: %s",
                                target_id,
                                err,
                            )

                    self.producer.produce(
                        self.topic,
                        key=key,
                        value=value,
                        callback=delivery_callback,
                    )
                    published_count += 1
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error(
                        "Failed producing message for %s: %s",
                        asset_id,
                        e,
                    )
            else:
                published_count += 1

        if self.producer:
            self.producer.poll(0)

        return published_count

    def flush(self, timeout: float = 2.0):
        if self.producer:
            self.producer.flush(timeout=timeout)
