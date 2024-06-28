# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Publish to Pub/Sub random JSON messages.

This script will write random JSON mesages to a Pub/Sub topic at a specified
interval. It is used for demonstration purposes.
"""

import argparse
import datetime
import json
import time

from faker import Faker
from google.cloud import pubsub_v1


def publish(project_id, topic_id, sleep):
    """Publish mesages to Pub/Sub topic at the sleep interval."""

    pub = pubsub_v1.PublisherClient()
    topic = pub.topic_path(project_id, topic_id)
    fake = Faker()

    while True:
        pub.publish(
            topic,
            bytes(
                json.dumps(
                    {
                        "ts": datetime.datetime.now().isoformat(),
                        "message": fake.sentence(),
                    }
                ),
                "utf-8",
            ),
        ).result()
        time.sleep(sleep)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="publish_to_pubsub",
        description="Write random JSON messages to PubSub",
    )
    parser.add_argument(
        "project_id", type=str, help="Project ID for publishing"
    )
    parser.add_argument("topic_id", type=str, help="Topic ID for publishing")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.1,
        help="Delay between message publishing",
    )

    args = parser.parse_args()

    publish(args.project_id, args.topic_id, args.sleep)
