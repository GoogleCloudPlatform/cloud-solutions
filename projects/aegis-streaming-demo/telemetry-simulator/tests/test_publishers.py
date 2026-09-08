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

"""Unit tests for pluggable telemetry publisher transports."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("NO_GCE_CHECK", "true")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null")

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Local src/ directory must be added to sys.path before importing modules.
# pylint: disable=wrong-import-position
from publishers.factory import get_publisher
from publishers.kafka_publisher import KafkaTelemetryPublisher
from publishers.pubsub_publisher import PubSubTelemetryPublisher
from simulator import FleetSimulator

# pylint: enable=wrong-import-position


class TestPublishers(unittest.TestCase):
    """Verifies factory instantiation and publisher behavior."""

    def test_factory_default_kafka(self):
        old_val = os.environ.pop("INGESTION_TYPE", None)
        try:
            pub = get_publisher()
            self.assertIsInstance(pub, KafkaTelemetryPublisher)
            self.assertEqual(pub.ingestion_type, "kafka")
        finally:
            if old_val:
                os.environ["INGESTION_TYPE"] = old_val

    def test_factory_pubsub(self):
        pub = get_publisher("pubsub")
        self.assertIsInstance(pub, PubSubTelemetryPublisher)
        self.assertEqual(pub.ingestion_type, "pubsub")

    def test_kafka_publisher_simulated_publish(self):
        pub = KafkaTelemetryPublisher()
        count = pub.publish_messages(
            [
                {
                    "asset_id": "Asset-01",
                    "cpu_utilization": 45.0,
                    "status": "OK",
                },
                {
                    "asset_id": "Asset-02",
                    "cpu_utilization": 50.0,
                    "status": "OK",
                },
            ]
        )
        self.assertEqual(count, 2)
        pub.flush()
        pub.close()

    def test_pubsub_publisher_simulated_publish(self):
        pub = PubSubTelemetryPublisher(
            project_id="test-project", topic="telemetry-raw"
        )
        count = pub.publish_messages(
            [
                {
                    "asset_id": "Asset-01",
                    "cpu_utilization": 45.0,
                    "status": "OK",
                },
            ]
        )
        self.assertEqual(count, 1)
        pub.flush()
        pub.close()

    def test_simulator_with_pubsub(self):
        pub = PubSubTelemetryPublisher()
        sim = FleetSimulator(publisher=pub)
        status = sim.get_status()
        self.assertEqual(status.ingestion_type, "pubsub")
        self.assertEqual(len(sim.asset_ids), 15)


if __name__ == "__main__":
    unittest.main()
