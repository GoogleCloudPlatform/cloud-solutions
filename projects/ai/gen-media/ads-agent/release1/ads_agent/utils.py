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

# pylint: disable=C0114, C0301, W0612, W1203

import io
import logging

from google.cloud import storage
from PIL import Image, ImageOps

try:
    from .services import storage_service
except (ImportError, ValueError) as ex:
    from services import storage_service


def resize_images(uris: list[str], target_width: float, target_ratio: float):
    if not uris:
        return uris
    new_uris = []
    for uri in uris:
        blob = storage_service.StorageService().get_blob(uri)
        if not blob:
            raise ValueError(f"Blob not found for URI: {uri}")

        # Calculate original aspect ratio
        img_data = blob.download_as_bytes()
        with Image.open(io.BytesIO(img_data)) as img:
            orig_width, orig_height = img.size
            orig_ratio = orig_width / orig_height
            logging.info(f"Original aspect ratio for {uri}: {orig_ratio:.2f}")

        logging.info(f"Resizing {uri} to ratio {target_ratio}")
        resized_uri = resize_image(blob, target_width, target_ratio)
        new_uris.append(resized_uri)

    return new_uris


def resize_image(
    blob: storage.blob.Blob, target_width: float, aspect_ratio: float
) -> str:
    """
    Resizes an image from GCS and uploads the result back to GCS.
    Uses an in-memory buffer to avoid local disk storage.
    """
    # 1. Download blob bytes into memory and open with PIL
    img_data = blob.download_as_bytes()
    img = Image.open(io.BytesIO(img_data))

    # Capture original format (JPEG, PNG, etc.) to use during save
    original_format = img.format

    # 2. Process the image
    target_height = round(target_width / aspect_ratio)
    resized_img = ImageOps.fit(
        img, (target_width, target_height), Image.Resampling.LANCZOS
    )

    # 3. Save the resized image into an in-memory byte buffer
    # This replaces the need for a local file path
    byte_arr = io.BytesIO()
    resized_img.save(byte_arr, format=original_format)
    byte_arr.seek(0)  # Rewind the buffer to the beginning so we can read it

    # 4. Construct the new GCS path and upload
    path_parts = blob.name.rsplit(".", 1)
    base_name = path_parts[0]
    extension = path_parts[1] if len(path_parts) > 1 else "jpg"

    ratio_str = str(round(aspect_ratio, 2)).replace(".", "_")
    output_blob_name = f"{base_name}_resized.{extension}"

    # Create the new blob object and upload the buffer
    new_blob = blob.bucket.blob(output_blob_name)
    new_blob.upload_from_file(byte_arr, content_type=f"image/{extension.lower()}")

    # 5. Return the full GCS URL
    gcs_url = f"gs://{blob.bucket.name}/{output_blob_name}"

    return gcs_url
