# Copyright 2026 Google LLC
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


# pylint: disable=C0301, C0415, W0718, W1203
"""Service that interacts with the Google Cloud Storage API."""

import logging
import os

from google.api_core.client_info import ClientInfo
from google.cloud import storage


class StorageService:
    """Service that interacts with the Google Cloud Storage API."""

    def __init__(self):
        """Initializes the StorageService."""

        # Create Storage client
        self.storage_client = storage.Client(
            project=os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("PROJECT_ID")),
            client_info=ClientInfo(user_agent="CampaignTraffickingAgent"),
        )

    def get_blob(self, uri: str) -> storage.blob.Blob | None:
        """Returns a GCS blob object from its full URI.

        Args:
            uri: The full URI of the GCS blob
            (e.g., "gs://my-bucket/path/to/file").

        Returns:
            The GCS blob object or None if not found.
        """
        try:
            uri_clean = uri
            if uri_clean.startswith("gs://"):
                uri_clean = uri_clean[5:]
            elif uri_clean.startswith("https://storage.cloud.google.com/"):
                uri_clean = uri_clean[len("https://storage.cloud.google.com/"):]
            elif uri_clean.startswith("https://storage.googleapis.com/"):
                uri_clean = uri_clean[len("https://storage.googleapis.com/"):]

            bucket_name, path = uri_clean.split("/", 1)
            logging.info(f"[StorageService] get_blob: uri={uri}")
            logging.info(f"[StorageService] get_blob: bucket={bucket_name}, path={path}")
            logging.info(f"[StorageService] get_blob: project={self.storage_client.project}")

            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(path)

            exists = blob.exists()
            logging.info(f"[StorageService] get_blob: exists={exists}")

            if exists:
                return blob

            # Try listing to debug
            prefix = path.rsplit("/", 1)[0] + "/" if "/" in path else ""
            logging.info(f"[StorageService] listing blobs with prefix={prefix}")
            found_blobs = list(bucket.list_blobs(prefix=prefix, max_results=5))
            for fb in found_blobs:
                logging.info(f"[StorageService]   found: {fb.name}")

            return None
        except Exception as e:
            logging.error(f"[StorageService] get_blob ERROR for {uri}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
