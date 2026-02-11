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

# GCS Utilities for Saving Outputs
# Centralized save functions for all modules
"""GCS utilities for saving outputs from all modules."""

import uuid
from datetime import datetime
from typing import Any, Dict

from google.api_core import exceptions as gcs_exceptions


def save_to_gcs(
    storage_client,
    bucket_name: str,
    blob_path: str,
    data: bytes,
    metadata: Dict[str, Any] = None,
    content_type: str = "image/png",
) -> str:
    """Save data to GCS and return the public URL.

    Args:
        storage_client: GCS storage client
        bucket_name: Name of the GCS bucket
        blob_path: Path in the bucket where to save
        data: Binary data to save
        metadata: Optional metadata to attach
        content_type: MIME type of the content
            (default: image/png)

    Returns:
        str: GCS URI of the saved file
    """
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        # Upload data with correct content type
        blob.upload_from_string(
            data, content_type=content_type
        )

        # Add metadata if provided
        if metadata:
            blob.metadata = metadata
            blob.patch()

        return f"gs://{bucket_name}/{blob_path}"

    except gcs_exceptions.GoogleAPICallError as e:
        print(f"Error saving to GCS: {str(e)}")
        return None


def generate_unique_path(
    base_path: str,
    prefix: str = "",
    extension: str = "png",
) -> str:
    """Generate a unique file path with timestamp.

    Args:
        base_path: Base directory path
            (e.g., "outputs/model_creation/")
        prefix: Optional prefix for the filename
        extension: File extension (default: png)

    Returns:
        str: Unique file path
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]

    if prefix:
        filename = (
            f"{prefix}_{timestamp}_{unique_id}"
            f".{extension}"
        )
    else:
        filename = (
            f"{timestamp}_{unique_id}.{extension}"
        )

    return f"{base_path}{filename}"


# Define standard paths for each module
GCS_PATHS = {
    "model_creation": {
        "base": "outputs/model_creation/",
        "generated": "outputs/model_creation/generated/",
        "custom": "outputs/model_creation/custom/",
    },
    "single_vto": {
        "base": "outputs/single_vto/",
        "results": "outputs/single_vto/results/",
        "variations": "outputs/single_vto/variations/",
    },
    "multi_tryon": {
        "base": "outputs/multi_tryon/",
        "batch": "outputs/multi_tryon/batch/",
        "videos": "outputs/multi_tryon/videos/",
    },
    "beauty_demo": {
        "base": "outputs/beauty_demo/",
        "makeup": "outputs/beauty_demo/makeup/",
        "variations": (
            "outputs/beauty_demo/variations/"
        ),
    },
    "complete_workflow": {
        "base": "outputs/complete_workflow/",
        "vto": "outputs/complete_workflow/vto/",
        "beauty": "outputs/complete_workflow/beauty/",
        "videos": "outputs/complete_workflow/videos/",
        "face_closeup": (
            "outputs/complete_workflow/face_closeup/"
        ),
    },
}


def save_model_to_gcs(
    storage_client,
    bucket_name: str,
    model_data: bytes,
    model_type: str = "generated",
    metadata: Dict = None,
) -> str:
    """Save generated model to GCS."""
    path_key = (
        "custom" if model_type == "custom"
        else "generated"
    )
    blob_path = generate_unique_path(
        GCS_PATHS["model_creation"][path_key],
        prefix="model",
    )
    return save_to_gcs(
        storage_client, bucket_name,
        blob_path, model_data, metadata,
    )


def save_vto_result_to_gcs(
    storage_client,
    bucket_name: str,
    result_data: bytes,
    is_variation: bool = False,
    metadata: Dict = None,
) -> str:
    """Save VTO result to GCS."""
    path_key = (
        "variations" if is_variation else "results"
    )
    blob_path = generate_unique_path(
        GCS_PATHS["single_vto"][path_key],
        prefix="vto",
    )
    return save_to_gcs(
        storage_client, bucket_name,
        blob_path, result_data, metadata,
    )


def save_batch_vto_to_gcs(
    storage_client,
    bucket_name: str,
    result_data: bytes,
    model_name: str,
    product_name: str,
    metadata: Dict = None,
) -> str:
    """Save batch VTO result to GCS."""
    prefix = (
        f"{model_name}_{product_name}"
        .replace(" ", "_")
        .replace("/", "_")[:50]
    )
    blob_path = generate_unique_path(
        GCS_PATHS["multi_tryon"]["batch"],
        prefix=prefix,
    )
    return save_to_gcs(
        storage_client, bucket_name,
        blob_path, result_data, metadata,
    )


def save_beauty_result_to_gcs(
    storage_client,
    bucket_name: str,
    result_data: bytes,
    is_variation: bool = False,
    metadata: Dict = None,
) -> str:
    """Save beauty result to GCS."""
    path_key = (
        "variations" if is_variation else "makeup"
    )
    blob_path = generate_unique_path(
        GCS_PATHS["beauty_demo"][path_key],
        prefix="beauty",
    )
    return save_to_gcs(
        storage_client, bucket_name,
        blob_path, result_data, metadata,
    )


def save_complete_workflow_to_gcs(
    storage_client,
    bucket_name: str,
    result_data: bytes,
    stage: str,
    metadata: Dict = None,
) -> str:
    """Save complete workflow result to GCS."""
    # stage can be: vto, beauty, videos, face_closeup
    if stage not in GCS_PATHS["complete_workflow"]:
        stage = "base"

    prefix_map = {
        "vto": "vto_result",
        "beauty": "beauty_result",
        "videos": "video",
        "face_closeup": "face",
    }

    prefix = prefix_map.get(stage, "result")
    extension = (
        "mp4" if stage == "videos" else "png"
    )

    blob_path = generate_unique_path(
        GCS_PATHS["complete_workflow"][stage],
        prefix=prefix,
        extension=extension,
    )

    return save_to_gcs(
        storage_client, bucket_name,
        blob_path, result_data, metadata,
    )


def save_video_to_gcs(
    storage_client,
    bucket_name: str,
    video_data: bytes,
    module: str = "multi_tryon",
    metadata: Dict = None,
) -> str:
    """Save video to GCS."""
    if module == "complete_workflow":
        base_path = (
            GCS_PATHS["complete_workflow"]["videos"]
        )
    else:
        base_path = (
            GCS_PATHS["multi_tryon"]["videos"]
        )

    blob_path = generate_unique_path(
        base_path,
        prefix="runway_video",
        extension="mp4",
    )
    return save_to_gcs(
        storage_client, bucket_name,
        blob_path, video_data, metadata,
        content_type="video/mp4",
    )
