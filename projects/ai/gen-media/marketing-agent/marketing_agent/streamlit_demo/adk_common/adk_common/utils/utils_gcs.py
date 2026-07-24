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

import io
import mimetypes
from typing import Any
from urllib.parse import unquote, urlparse, urlunparse

from adk_common.utils.utils_logging import Severity, log_message
from google.api_core import exceptions
from google.api_core.client_info import ClientInfo
from google.api_core.exceptions import NotFound
from google.cloud import storage

from ..dtos.generated_media import GeneratedMedia
from .constants import get_required_env_var

AGENT_VERSION = get_required_env_var("AGENT_VERSION")
GOOGLE_CLOUD_PROJECT = get_required_env_var("GOOGLE_CLOUD_PROJECT")
USER_AGENT = f"cde/agentspace-tahoe-demo/{AGENT_VERSION}"

GCS_AUTHENTICATED_DOMAIN = "https://storage.cloud.google.com/"
GCS_AUTHENTICATED_DOMAIN_SANS_PROTOCOL = "storage.cloud.google.com"
GCS_PUBLIC_DOMAIN = "https://storage.googleapis.com/"
GCS_PUBLIC_DOMAIN_SANS_PROTOCOL = "storage.googleapis.com"

DEPLOYMENT_BUCKET_SOFT_DELETE_DAYS = 7


def create_bucket_from_spec(
    bucket_name: str, bucket_location: str, project: str
) -> storage.Bucket:
    """
    Creates a GCS bucket with specific settings

    Handles the case where the bucket already exists.
    """
    client = storage.Client(project=project)

    try:
        # 1. Define the bucket "resource" with all its settings
        # This object acts as a "blueprint" for creation.
        bucket_resource = client.bucket(bucket_name)
        bucket_resource.location = bucket_location

        # Set Storage Class (Standard is default, but good to be explicit)
        bucket_resource.storage_class = "STANDARD"

        # Set Access Control to "Uniform"
        bucket_resource.iam_configuration.uniform_bucket_level_access_enabled = True

        # Set Object Versioning to "Off" (default)
        bucket_resource.versioning_enabled = False

        # Set the 7-day Soft Delete Policy
        if DEPLOYMENT_BUCKET_SOFT_DELETE_DAYS > 0:
            # Calculate retention in seconds
            retention_seconds = DEPLOYMENT_BUCKET_SOFT_DELETE_DAYS * 24 * 60 * 60
            bucket_resource.soft_delete_policy.retention_duration_seconds = (
                retention_seconds
            )

        # 2. Try to create the bucket using the resource object
        print(f"Attempting to create bucket '{bucket_name}' in {bucket_location}...")
        bucket = client.create_bucket(bucket_resource)

        log_message(f"Bucket '{bucket_name}' created successfully with:", Severity.INFO)
        log_message(f"Location: {bucket.location}", Severity.INFO)
        log_message(
            f"Soft Delete: {bucket.soft_delete_policy.retention_duration_seconds} seconds",
            Severity.INFO,
        )

    except exceptions.Conflict:
        # The 409 Conflict exception means the bucket already exists.
        log_message(f"Bucket '{bucket_name}' already exists. Fetching.", Severity.INFO)
        bucket = client.get_bucket(bucket_name)

    except Exception as e:
        log_message(f"An unexpected error occurred: {e}", Severity.ERROR)
        raise e

    return bucket


def upload_to_gcs(
    bucket_path: str, file_bytes: bytes, destination_blob_name: str
) -> str:
    """Uploads a file to Google Cloud Storage

    Args:
        bucket_path (str): Name of the GCS bucket/path (no tailing `/`).
        file_bytes (bytes): The file bytes to upload.
        destination_blob_name (str): Name of the object in the GCS bucket (can be /folder/file.png).

    Returns:
        str: URI to resource in GCS.
    """

    log_message("Started Uploading to GCS", Severity.INFO)

    gs_uri = normalize_to_gs_bucket_uri(bucket_path)
    bucket_name, path = parse_gcs_url(gs_uri)

    if path.endswith("/"):
        path = path[:-1]

    if path:
        destination_blob_path = f"{path}/{destination_blob_name}"
    else:
        destination_blob_path = destination_blob_name

    storage_client = storage.Client(
        project=GOOGLE_CLOUD_PROJECT, client_info=ClientInfo(user_agent=USER_AGENT)
    )

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_path)

    blob.upload_from_file(io.BytesIO(file_bytes))

    log_message(
        f"File uploaded to gs://{bucket_name}/{destination_blob_path}", Severity.INFO
    )

    return f"gs://{bucket_name}/{destination_blob_path}"


def download_bytes_from_gcs(uri: str) -> bytes | None:
    """Downloads a file from Google Cloud Storage and returns its content as bytes.

    Args:
        uri (str): The GCS URI of the object (e.g., "gs://bucket_name/path/to/file").

    Returns:
        bytes: The raw content of the file.
    """

    try:
        gs_uri = normalize_to_gs_bucket_uri(uri)
        bucket_name, path = parse_gcs_url(gs_uri)

        storage_client = storage.Client(
            project=GOOGLE_CLOUD_PROJECT, client_info=ClientInfo(user_agent=USER_AGENT)
        )
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(path)

        # This is the most direct way to get the file's content as bytes
        file_bytes = blob.download_as_bytes()

        log_message(
            f"File gs://{bucket_name}/{path} downloaded as bytes.", Severity.INFO
        )
        return file_bytes
    except exceptions.NotFound as e:
        log_message("File not found in GCS.", Severity.WARNING)
        return None


def parse_gcs_url(uri: str) -> tuple[str, str]:
    """
    Parses a GCS URI to extract the bucket name and the file path.

    Args:
        uri: A string representing the GCS URI (e.g., "gs://bucket_name/path/to/file").

    Returns:
        A tuple containing:
        (a) The bucket name (str).
        (b) The full path to the file within the bucket (str).

        Raises Exception if the URL is not from a GCS bucket.
    """

    try:
        parts = urlparse(uri)
        if parts.scheme == "gs":
            bucket_name = parts.netloc
            file_path = parts.path.lstrip("/")
            return bucket_name, file_path
        elif (
            GCS_AUTHENTICATED_DOMAIN_SANS_PROTOCOL in parts.netloc
            or GCS_PUBLIC_DOMAIN_SANS_PROTOCOL in parts.netloc
        ):
            # The path will be /bucket-name/path/to/file
            path_parts = parts.path.lstrip("/").split("/", 1)
            if len(path_parts) >= 1 and path_parts[0]:
                bucket_name = path_parts[0]
                file_path = path_parts[1] if len(path_parts) > 1 else ""
                return bucket_name, file_path
    except Exception as e:
        log_message(f"Error parsing GCS URI: {e}", Severity.ERROR)
        raise e

    log_message(f"URI is not from a GCS bucket. URI: {uri}", Severity.INFO)
    raise RuntimeWarning(f"URI is not from a GCS bucket. URI: {uri}")


def check_if_gcs_file_exists_from_bucket_and_path(
    bucket_name: str, file_path: str
) -> bool:
    """Checks if a file exists in a GCS bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        return blob.exists()
    except Exception as e:
        log_message(f"Error checking GCS file: {e}", Severity.ERROR)
        return False


def check_if_gcs_file_exists_from_string(
    reference: str, optional_bucket: str | None = None
) -> bool:
    file_exists = False

    try:
        bucket, path = parse_gcs_url(reference)
        # If parse_gcs_url succeeds, it's a GCS URL.
        log_message(f"Is GCS URI. Bucket: '{bucket}', Path: '{path}'", Severity.DEBUG)
        file_exists = check_if_gcs_file_exists_from_bucket_and_path(bucket, path)
        log_message(f"GCS file exists? {file_exists}", Severity.DEBUG)
    except ValueError:
        # It's not a GCS URI, so we return False.
        log_message(f"Not a GCS URI, proceeding...", Severity.DEBUG)
        pass
    except Exception as e:
        # Catch any other unexpected errors during GCS parsing
        log_message(
            f"GCS parsing failed unexpectedly. Exception: {e}", Severity.WARNING
        )
        pass

    if not file_exists and optional_bucket:
        return check_if_gcs_file_exists_from_bucket_and_path(optional_bucket, reference)

    return file_exists


def get_gcs_uri_from_bucket_name(bucket_name) -> str:
    """Returns a GCS URI for a given bucket name.

    Args:
        bucket_name (str): The name of the GCS bucket.

    Returns:
        str: The GCS URI (e.g., 'gs://project_id/bucket_name').
    """

    uri = f"gs://{bucket_name}"
    return uri


def normalize_to_gs_bucket_uri(path: str) -> str:
    """Normalizes a GCS path, URL, or bucket/object path to a GCS object URI.

    Args:
        path: The input string representing the GCS location.

    Returns:
        The normalized GCS object URI in the format 'gs://<bucket-name>/<path-to-file>'.
    """
    if path.startswith("gs://"):
        # It's already in the correct format, but we should unquote the path
        # to handle any percent-encoded characters from sources like signed URLs.
        parsed = urlparse(path)
        return urlunparse(("gs", parsed.netloc, unquote(parsed.path), "", "", ""))

    elif path.startswith("http://") or path.startswith("https://"):
        parsed_url = urlparse(path)

        # GCS HTTP paths are typically /<bucket>/<object>
        # Split the path into components
        path_parts = parsed_url.path.strip("/").split("/", 1)
        if len(path_parts) < 2:
            raise ValueError(f"Invalid GCS HTTP URL format: {path}")

        bucket_name = path_parts[0]
        object_path = path_parts[1]

        # Decode the object path to restore spaces
        decoded_path = unquote(object_path)

        return f"gs://{bucket_name}/{decoded_path}"

    else:
        # Assume it's a bucket/object path
        path_parts = path.strip("/").split("/", 1)
        if len(path_parts) < 2:
            # Handle cases like "my-bucket" which should be converted to "gs://my-bucket"
            bucket_name = path_parts[0] if path_parts else ""
            return f"gs://{bucket_name}"

        bucket_name = path_parts[0]
        object_path = path_parts[1]

        # No URL decoding needed for this path style
        return f"gs://{bucket_name}/{object_path}"


def normalize_to_authenticated_url(path: str) -> str:
    """Normalizes a GCS path or public URL to a full authenticated URL.

    This function takes a string representing a GCS object and returns a
    full 'storage.cloud.google.com' URL for it. It can handle:
    1. A GCS URI (e.g., 'gs://my-bucket/folder/file.txt')
    2. A public GCS HTTP URL (e.g., 'https://storage.googleapis.com/my-bucket/folder/file.txt')
    3. A path that includes the bucket and object (e.g., 'my-bucket/folder/file.txt')

    Args:
        path: The input string representing the GCS object location.

    Returns:
        The full authenticated URL in the format
        'https://storage.cloud.google.com/<bucket-name>/<path-to-file>'.
    """
    uri = normalize_to_gs_bucket_uri(path)
    return uri.replace("gs://", GCS_AUTHENTICATED_DOMAIN)


def get_text_files_from_gcs_bucket(
    bucket_name: str, prefix: str | None = None
) -> list[str]:
    """
    Retrieves and parses all specified text files from a GCS bucket.

    Args:
        bucket_name: The name of the GCS bucket (e.g., "my-data-bucket").
        prefix: (Optional) The "folder" path to search within the bucket
                (e.g., "reports/october/"). If None, searches the
                entire bucket.

    Returns:
        A list of strings, where each string is the text
        content of a file.
    """

    # This automatically finds your `gcloud auth` credentials
    try:
        storage_client = storage.Client()
        # You can also pass a project ID if needed:
        # storage_client = storage.Client(project="my-project-id")

        # Check if the bucket exists
        bucket = storage_client.get_bucket(bucket_name)

    except NotFound:
        log_message(f"Error: Bucket '{bucket_name}' not found.", Severity.ERROR)
        log_message(
            "Please check the bucket name and your permissions.", Severity.ERROR
        )
        return []
    except Exception as e:
        log_message(
            f"An error occurred during authentication or client setup: {e}",
            Severity.ERROR,
        )
        log_message(
            "Have you run 'gcloud auth application-default login'?", Severity.ERROR
        )
        return []

    document_texts = []

    # 1. List all files (blobs) in the bucket, filtered by the prefix
    # This list is recursive by default (includes "subfolders")
    search_path = prefix or ""
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)

    log_message(
        f"Searching for .txt files in: gs://{bucket_name}/{search_path}...",
        Severity.INFO,
    )

    # 2. Loop through files, filter, and read
    for blob in blobs:

        # --- KEY ASSUMPTION: Only processing .txt files ---
        # Change ".txt" to ".csv", ".json", or remove the 'if'
        # to attempt to read all files.
        if blob.name.endswith(".txt") or blob.name.endswith(".md"):
            log_message(f"  - Processing: {blob.name}", Severity.INFO)
            try:
                # 3. Download the file's content as a string
                # This is the GCS equivalent of "parsing"
                text_content = blob.download_as_text()
                document_texts.append(text_content)

            except UnicodeDecodeError:
                log_message(
                    f"    Skipping (not a valid UTF-8 file): {blob.name}",
                    Severity.WARNING,
                )
            except Exception as e:
                log_message(f"    Error processing {blob.name}: {e}", Severity.ERROR)

        elif blob.name.endswith("/"):
            # This is a "folder" placeholder, skip it
            pass
        else:
            log_message(
                f"  - Skipping (not a .txt or .md file): {blob.name}", Severity.DEBUG
            )

    log_message("\nProcessing complete.", Severity.INFO)
    return document_texts


def download_text_from_gcs(uri: str) -> str:
    """Downloads a file from Google Cloud Storage and returns its content as bytes.

    Args:
        uri (str): The GCS URI of the object (e.g., "gs://bucket_name/path/to/file").

    Returns:
        bytes: The raw content of the file.
    """
    gs_uri = normalize_to_gs_bucket_uri(uri)
    bucket_name, path = parse_gcs_url(gs_uri)

    storage_client = storage.Client(
        project=GOOGLE_CLOUD_PROJECT, client_info=ClientInfo(user_agent=USER_AGENT)
    )
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(path)

    # This is the most direct way to get the file's content as bytes
    file_text = blob.download_as_text()

    log_message(f"File gs://{bucket_name}/{path} downloaded as bytes.", Severity.INFO)
    return file_text


def get_files_metadata_from_gcs_bucket(
    bucket_name: str, prefix: str | None = None
) -> list[dict[str, Any]]:
    """
    Retrieves metadata for all files in a specific bucket and folder.

    Args:
        bucket_name: The name of the GCS bucket.
        prefix: (Optional) The folder path to search within.

    Returns:
        A list of dictionaries with keys:
        - filename (str): The blob name.
        - uri (str): The gs:// URI.
        - mime_type (str): The content type.
        - last_modified (datetime): The last modification time.
    """
    try:
        storage_client = storage.Client()
        # Verify bucket exists
        storage_client.get_bucket(bucket_name)

    except NotFound:
        log_message(f"Error: Bucket '{bucket_name}' not found.", Severity.ERROR)
        return []
    except Exception as e:
        log_message(f"Error initializing GCS client or bucket: {e}", Severity.ERROR)
        return []

    metadata_list = []

    # list_blobs is recursive by default if delimiter is not set
    log_message(f"Listing files in gs://{bucket_name}/{prefix or ''}...", Severity.INFO)
    try:
        blobs = storage_client.list_blobs(bucket_name, prefix=prefix)

        for blob in blobs:
            if blob.name.endswith("/"):
                continue

            uri = f"gs://{bucket_name}/{blob.name}"

            # Fallback for generic mime types
            mime_type = blob.content_type
            if not mime_type or mime_type == "application/octet-stream":
                # Guess based on extension
                guessed_type, _ = mimetypes.guess_type(blob.name)
                if guessed_type:
                    mime_type = guessed_type

            generated_media = GeneratedMedia(
                filename=blob.name,
                gcs_uri=normalize_to_authenticated_url(uri),
                mime_type=mime_type,
            )

            metadata = {
                "id": blob.name,
                "asset": generated_media.to_obj_sans_bytes(),
                "last_modified": blob.updated.isoformat() if blob.updated else None,
            }

            metadata_list.append(metadata)

        log_message(f"Found {len(metadata_list)} files.", Severity.INFO)
        return metadata_list

    except Exception as e:
        log_message(f"Error listing blobs: {e}", Severity.ERROR)
        return []


def normalize_bucket_uri(url: str):
    """Normalizes GCS URLs to gs:// format."""
    if not url:
        return None
    if url.startswith("gs://"):
        return url

    parsed = urlparse(url)
    path = unquote(parsed.path)

    if (
        parsed.netloc.endswith(".storage.googleapis.com")
        and parsed.netloc != "storage.googleapis.com"
    ):
        bucket = parsed.netloc.replace(".storage.googleapis.com", "")
        obj = path.lstrip("/")
        return f"gs://{bucket}/{obj}"

    if parsed.netloc in ["storage.googleapis.com", "storage.cloud.google.com"]:
        clean_path = path.lstrip("/")
        if "/" in clean_path:
            bucket, obj = clean_path.split("/", 1)
            return f"gs://{bucket}/{obj}"

    return None


def download_blob_to_bytes(bucket_name: str, source_blob_name: str) -> bytes:
    """Downloads a blob from the bucket to bytes."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob_data = blob.download_as_bytes()
    return blob_data


def generate_min_image(source_blob_name: str):
    """Generates a thumbnail (minified) version of a GCS image if it doesn't exist."""
    import io as _io
    from PIL import Image

    storage_client = storage.Client()
    image_path = source_blob_name.strip()
    bucket_name = (
        image_path.replace("gs://", "")
        .replace("https://storage.cloud.google.com/", "")
        .split("/")[0]
    )
    source_blob_name = image_path.replace(f"gs://{bucket_name}/", "").replace(
        f"https://storage.cloud.google.com/{bucket_name}/", ""
    )
    bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(source_blob_name)
    if not blob.exists():
        return None

    min_blob_name = source_blob_name.replace(".png", "_min.png").replace(
        ".jpg", "_min.jpg"
    )
    min_blob = bucket.blob(min_blob_name)

    if not min_blob.exists():
        image_bytes = blob.download_as_bytes()
        original_img = Image.open(_io.BytesIO(image_bytes))
        target_height = 200
        aspect_ratio = original_img.width / original_img.height
        target_width = int(target_height * aspect_ratio)
        thumbnail_img = original_img.resize(
            (target_width, target_height), Image.Resampling.LANCZOS
        )
        min_img_byte_arr = _io.BytesIO()
        fmt = original_img.format if original_img.format else "PNG"
        thumbnail_img.save(min_img_byte_arr, format=fmt)
        min_img_bytes = min_img_byte_arr.getvalue()
        min_blob.upload_from_string(
            min_img_bytes, content_type=blob.content_type or "image/png"
        )

    return min_blob_name
