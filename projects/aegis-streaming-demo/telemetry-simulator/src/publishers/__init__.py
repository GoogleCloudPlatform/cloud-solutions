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

"""Telemetry Publisher Package.

Exports pluggable telemetry publishers for Kafka and Google Cloud Pub/Sub.
"""

from publishers.base import BaseTelemetryPublisher
from publishers.factory import get_publisher
from publishers.kafka_publisher import KafkaTelemetryPublisher
from publishers.pubsub_publisher import PubSubTelemetryPublisher

__all__ = [
    "BaseTelemetryPublisher",
    "KafkaTelemetryPublisher",
    "PubSubTelemetryPublisher",
    "get_publisher",
]
