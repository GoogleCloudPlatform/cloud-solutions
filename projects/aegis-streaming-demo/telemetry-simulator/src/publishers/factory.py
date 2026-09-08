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

"""Factory for instantiating the configured telemetry publisher transport."""

import logging
import os
from typing import Optional

from publishers.base import BaseTelemetryPublisher
from publishers.kafka_publisher import KafkaTelemetryPublisher
from publishers.pubsub_publisher import PubSubTelemetryPublisher

logger = logging.getLogger("aegis-telemetry-simulator")


def get_publisher(
    ingestion_type: Optional[str] = None,
) -> BaseTelemetryPublisher:
    """Returns the appropriate BaseTelemetryPublisher implementation.

    Checks parameter, then INGESTION_TYPE env var (default: 'kafka').
    """
    transport = (
        (ingestion_type or os.getenv("INGESTION_TYPE", "kafka")).strip().lower()
    )

    if transport in ["pubsub", "pub_sub", "cloud_pubsub"]:
        logger.info("Using PubSubTelemetryPublisher (transport=%s)", transport)
        return PubSubTelemetryPublisher()

    logger.info("Using KafkaTelemetryPublisher (transport=%s)", transport)
    return KafkaTelemetryPublisher()
