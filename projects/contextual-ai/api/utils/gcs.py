# Copyright 2025 Google LLC
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

"""
GCS helper functions
"""

import json

from google.cloud import storage


def download_data_from_gcs(bucket_name: str, blob_name: str) -> str:
    """Downloads a file from the specified GCS bucket.

    Args:
        bucket_name: The name of the GCS bucket.
        blob_name: The name of the blob (object) to download.
        file_path: The local path to save the downloaded file.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    try:
        text = blob.download_as_string()
        print(f"File gs://{bucket_name}/{blob_name} downloaded")
        return json.loads(text)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error downloading gs://{bucket_name}/{blob_name}: {e}")


def upload_to_gcs(
    bucket_name: str, content: str, destination_blob_name: str
) -> None:
    """Uploads a file to the specified GCS bucket.

    Args:
        bucket_name: The name of the GCS bucket.
        file_path: The path to the file to upload.
        destination_blob_name: The name of the blob (object) in the bucket.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    try:
        blob.upload_from_string(data=content)
        print(f"File uploaded to gs://{bucket_name}/{destination_blob_name}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        msg = (
            f"Error uploading to "
            f"gs://{bucket_name}/{destination_blob_name}: {e}"
        )
        print(msg)


def download_from_gcs(bucket_name: str, blob_name: str) -> str:
    """Downloads a file from the specified GCS bucket.

    Args:
        bucket_name: The name of the GCS bucket.
        blob_name: The name of the blob (object) to download.
        file_path: The local path to save the downloaded file.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    try:
        text = blob.download_as_string()
        print(f"File gs://{bucket_name}/{blob_name} downloaded")
        return text
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error downloading gs://{bucket_name}/{blob_name}: {e}")
