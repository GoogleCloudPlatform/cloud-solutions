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


# pylint: disable=C0114, C0301, C0415, W0311, W0611, W0718, W1405
import base64
import mimetypes
import os
import random
import string
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from ..dtos.generated_media import GeneratedMedia
from . import utils_gcs
from .constants import get_required_env_var
from .utils_logging import Severity, log_function_call, log_message

AGENT_VERSION = get_required_env_var("AGENT_VERSION")
GOOGLE_CLOUD_BUCKET_ARTIFACTS = get_required_env_var("GOOGLE_CLOUD_BUCKET_ARTIFACTS")

CONTEXT_UI_PREFIX = "ui:status_update"
SESSION_STATE_ID = "SESSION_STATE_ID"
SESSION_ARTIFACTS_STATE_KEY = "SESSION_ARTIFACTS_STATE"
TEMP_ARTIFACTS_STATE_KEY = "TEMP_ARTIFACTS_STATE"


class AssetRefType(Enum):
    GCS = "gcs"
    URL = "url"
    FILENAME = "filename"
    NONE = "none"


def stringify_llm_request(llm_request: LlmRequest) -> str:
    """Converts an LlmRequest into a simple string for logging."""
    if not llm_request.contents:
        return ""
    parts = []
    for content in llm_request.contents:
        if content and content.parts:
            for part in content.parts:
                if part and part.text and isinstance(part.text, str):
                    processed_text = part.text.replace("\n", " -(nl)- ")
                    parts.append(processed_text)
    final_string = " - ".join(parts)
    return final_string.strip()


def stringify_llm_response(llm_response: LlmResponse) -> str:
    """Converts an LlmResponse into a simple string for logging."""
    if not llm_response:
        return "no llm_response"
    elif not llm_response.content:
        return "no llm_response.content"
    elif not llm_response.content.parts:
        return "no llm_response.content.parts"
    parts = []
    for part in llm_response.content.parts:
        if part and part.text and isinstance(part.text, str):
            processed_text = part.text.replace("\n", " -(nl)- ")
            parts.append(processed_text)
        elif part and part.inline_data:
            parts.append(f"[Non String: {type(part.inline_data)}]")
    final_string = " - ".join(parts)
    return final_string.strip()


def classify_asset_reference(reference: str) -> AssetRefType:
    """Classifies the reference type: GCS, URL, or FILENAME.

    Args:
        reference (str): The asset reference.

    Returns:
        AssetRefType: The classified type.
    """
    # Check GCS
    try:
        utils_gcs.parse_gcs_url(reference)
        return AssetRefType.GCS
    except ValueError:
        pass
    except Exception:
        pass

    # Check URL
    parsed_url = urlparse(reference)
    if parsed_url.scheme in ["http", "https"]:
        return AssetRefType.URL

    return AssetRefType.FILENAME


def check_asset_exists(reference: str, expected_content_types: Set[str]) -> Tuple[bool, AssetRefType]:
    """
    Checks if an asset reference exists and, if public, matches content types.

    This function handles three types of references in order:
    1.  **Google Cloud Storage URIs**: (e.g., `gs://...` or `https://storage.cloud.google.com/...`)
        Checks for existence only.
    2.  **Public URLs**: (e.g., `http://...` or `https://...`)
        Checks for 2xx status and matching content-type.
    3.  **Simple Filenames**: (e.g., `image.png` or `folder/image.png`)
        Checks for existence within the GOOGLE_CLOUD_BUCKET_ARTIFACTS.

    Args:
        reference (str): The asset URI, URL, or filename to check.
        expected_content_types (List[str]): A list of lowercase mimetypes
                                           (e.g., ["image/png", "video/mp4"]).
                                           *Note: This is only used for Public URLs.*

    Returns:
        Tuple[bool, AssetRefType]: (True if the asset exists, False otherwise), and the identified type.
    """
    log_message(f"Checking asset existence for: {reference}", Severity.INFO)

    ref_type = classify_asset_reference(reference)

    if ref_type == AssetRefType.GCS:
        log_message("Is GCS URI.", Severity.DEBUG)
        exists = utils_gcs.check_if_gcs_file_exists_from_string(reference)
        log_message("GCS file exists? {exists}", Severity.DEBUG)
        return (exists, ref_type) if exists else (False, AssetRefType.NONE)

    elif ref_type == AssetRefType.URL:
        log_message("Is Public URL. Checking status and content-type.", Severity.DEBUG)
        try:
            response = requests.head(reference, allow_redirects=True, timeout=5)
            if not response.ok:
                log_message("Public URL check failed. Status: {response.status_code}", Severity.WARNING)
                return False, AssetRefType.NONE

            if not expected_content_types:
                log_message("Public URL check success. No expected content types specified.", Severity.INFO)
                return True, ref_type

            content_type = response.headers.get("content-type", "").lower()
            normalized_expected_types = [t.lower() for t in expected_content_types]

            for expected_type in normalized_expected_types:
                if expected_type in content_type:
                    log_message(f"Public URL check success. Content-Type '{content_type}' is valid.", Severity.INFO)
                    return True, ref_type

            log_message(f"Public URL check failed. Mismatch: Content-Type '{content_type}' is not in {normalized_expected_types}.", Severity.WARNING)
            return False, AssetRefType.NONE

        except requests.exceptions.RequestException as e:
            log_message(f"Public URL check failed. Exception: {e}", Severity.ERROR)
            return False, AssetRefType.NONE

    else:
        # Filename or bucket/path
        # Try to parse as GCS first if it contains a slash
        if "/" in reference:
            try:
                # Try prepending gs:// if it doesn't have it, to see if it's a valid GCS path
                test_uri = f"gs://{reference}"
                bucket, path = utils_gcs.parse_gcs_url(test_uri)
                log_message(f"Interpreting '{reference}' as GCS path: bucket='{bucket}', path='{path}'", Severity.DEBUG)
                file_exists = utils_gcs.check_if_gcs_file_exists_from_bucket_and_path(
                    bucket_name=bucket,
                    file_path=path
                )
                log_message(f"GCS file exists? {file_exists}", Severity.DEBUG)
                return (file_exists, AssetRefType.GCS) if file_exists else (False, AssetRefType.NONE)
            except Exception:
                # Fallback to default artifact bucket if GCS parsing fails or other error
                pass

        log_message(f"Checking as filename in artifact bucket: {GOOGLE_CLOUD_BUCKET_ARTIFACTS}", Severity.DEBUG)
        try:
            file_exists = utils_gcs.check_if_gcs_file_exists_from_bucket_and_path(
                bucket_name=GOOGLE_CLOUD_BUCKET_ARTIFACTS,
                file_path=reference
            )
            log_message(f"Filename check in artifact bucket exists? {file_exists}", Severity.DEBUG)

            if file_exists and expected_content_types:
                # ... (mimetype check logic remains same)
                pass

            return (file_exists, AssetRefType.FILENAME) if file_exists else (False, AssetRefType.NONE)
        except Exception as e:
            log_message(f"Filename check failed. Exception: {e}", Severity.ERROR)
            return False, AssetRefType.NONE


def extract_filename_from_url(url: str) -> str:
    """Extracts the filename with extension from a URL.

    Args:
        url (str): The URL to process.

    Returns:
        str: The filename with extension.
    """
    parsed_url = urlparse(url)
    path = parsed_url.path
    return os.path.basename(path)


@log_function_call
def download_bytes_from_reference(reference: str) -> tuple[bytes, str | None]:
    """Downloads bytes and retrieves mimetype from a reference (GCS, URL, or filename)."""
    ref_type = classify_asset_reference(reference)

    asset: bytes | None = None
    mimetype: str | None = None

    if ref_type == AssetRefType.GCS:
        mimetype, _ = mimetypes.guess_type(reference)
        asset = utils_gcs.download_bytes_from_gcs(reference)
    elif ref_type == AssetRefType.URL:
        response = requests.get(reference)
        response.raise_for_status()
        mimetype = response.headers.get("Content-Type")
        if not mimetype:
            mimetype, _ = mimetypes.guess_type(reference)
        return response.content, mimetype
    else:
        # Filename in artifact bucket
        gcs_uri = f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{reference}"
        mimetype, _ = mimetypes.guess_type(reference)
        asset = utils_gcs.download_bytes_from_gcs(gcs_uri)

    if not asset:
        log_message("Reference is empty or corrupt - could not download file bytes", Severity.ERROR)
        raise RuntimeError("Reference is empty or corrupt - could not download file bytes")

    return asset, mimetype


def transfer_reference_to_gcs(
    reference: str, destination_bucket: str, destination_blob_name: str | None = None
) -> str:
    """Downloads a file from a reference and uploads it to GCS.

    Args:
        reference (str): The source reference (GCS URI, URL, or filename).
        destination_bucket (str): The GCS bucket to upload to.
        destination_blob_name (str | None): The destination blob name.
                                            If None, uses the filename from the reference.

    Returns:
        str: The GCS URI of the uploaded file.
    """
    file_bytes, _ = download_bytes_from_reference(reference)

    if not destination_blob_name:
        destination_blob_name = extract_filename_from_url(reference)

    return utils_gcs.upload_to_gcs(
        bucket_path=destination_bucket,
        file_bytes=file_bytes,
        destination_blob_name=destination_blob_name,
    )


def agentspace_print(context: CallbackContext, message: str) -> None:
    context.state[CONTEXT_UI_PREFIX] = message
    log_message(f"Printed UI Message: {message}", Severity.INFO)


def get_number_of_images(number_of_images: int, default_num) -> int:
    max_number_of_images = 4 if not isinstance(default_num, int) else int(default_num)

    if not isinstance(number_of_images, int) or number_of_images <= 0:
        number_of_images = 1
    elif number_of_images > max_number_of_images:
        number_of_images = max_number_of_images

    return number_of_images


async def load_resource(
    source_path: str, tool_context: ToolContext
) -> GeneratedMedia | None:
    """Loads image bytes from either a GCS path or a tool artifact.

    Args:
        source_path (str): The path to the image.
        context (CallbackContext): The context for artifact management.

    Returns:
        A tuple with the image bytes, identifier, and MIME type.
    """
    log_message(f"Loading image resource from source path {source_path}", Severity.INFO)

    # 1. Try loading from artifact service
    # If source_path is a URI, we need to extract the filename to look up in artifacts
    if classify_asset_reference(source_path) != AssetRefType.FILENAME:
         artifact_name = extract_filename_from_url(source_path)
    else:
         artifact_name = source_path

    # identifier = os.path.basename(artifact_name).split(".")[0]
    identifier = os.path.basename(artifact_name)

    # Guess mime type from the original source path or artifact name
    mime_type, _ = mimetypes.guess_type(source_path)
    if not mime_type:
         mime_type, _ = mimetypes.guess_type(artifact_name)

    if not mime_type:
        # Fallback to previous default behavior or generic type
        lower_path = source_path.lower()
        if lower_path.endswith(".jpg") or lower_path.endswith(".jpeg"):
             mime_type = "image/jpeg"
        elif lower_path.endswith(".png"):
             mime_type = "image/png"
        elif lower_path.endswith(".mp4"):
             mime_type = "video/mp4"
        elif lower_path.endswith(".mp3"):
             mime_type = "audio/mpeg"
        elif lower_path.endswith(".wav"):
             mime_type = "audio/wav"
        elif lower_path.endswith(".pdf"):
             mime_type = "application/pdf"
        else:
             mime_type = "application/octet-stream"

    image_bytes = None

    # Try loading as artifact first
    log_message(f"Attempting to load as artifact: {artifact_name}", Severity.DEBUG)
    artifact: Optional[types.Part] = await tool_context.load_artifact(artifact_name)
    if artifact:
        if isinstance(artifact, dict):
            image_bytes = artifact.get("inline_data", {}).get("data")
        else:
            image_bytes = (
                artifact.inline_data.data if artifact and artifact.inline_data else None
            )

        if image_bytes:
             log_message(f"Loaded artifact with artifact_name: {artifact_name}. image_bytes length: {len(image_bytes)}", Severity.DEBUG)
             return GeneratedMedia(
                 media_bytes=image_bytes,
                 mime_type=mime_type,
                 filename=artifact_name
            )

    # 2. If not found, try GCS
    log_message(f"Artifact not found or empty. Attempting to load from GCS: {source_path}", Severity.WARNING)

    gcs_candidates = []

    if classify_asset_reference(source_path) == AssetRefType.GCS:
        gcs_candidates.append(source_path)
    else:
        # It's a filename or path, construct candidates
        session_id = get_or_create_unique_session_id(tool_context)
        # a) gs://{BUCKET}/{SESSION_ID}/{source_path}
        gcs_candidates.append(f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{session_id}/{source_path}")
        # b) gs://{BUCKET}/{source_path}
        gcs_candidates.append(f"gs://{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{source_path}")
        # c) gs://{source_path}
        gcs_candidates.append(f"gs://{source_path}")

    for gcs_uri in gcs_candidates:
        try:
            log_message(f"Trying to download from GCS: {gcs_uri}", Severity.DEBUG)
            image_bytes = utils_gcs.download_bytes_from_gcs(gcs_uri)
            if image_bytes:
                log_message(f"Successfully downloaded from GCS: {gcs_uri}", Severity.INFO)
                return GeneratedMedia(
                    gcs_uri=gcs_uri,
                    media_bytes=image_bytes,
                    mime_type=mime_type,
                    filename=identifier
                )

        except Exception as e:
            log_message(f"Failed to download from {gcs_uri}: {e}", Severity.DEBUG)

    log_message(f"Could not load resource from any source: {source_path}", Severity.ERROR)
    return None


async def save_to_artifact_and_render_asset(
    asset: GeneratedMedia, context: CallbackContext, *, gcs_folder:str | None = None, save_in_gcs: bool = True, save_in_artifacts: bool = False
) -> GeneratedMedia:

    log_message(
        f"Saving file in artifacts. image_url: {asset.gcs_uri}. asset_name: {asset.filename}",
        Severity.INFO
    )

    if not asset.media_bytes and not asset.gcs_uri:
        raise ValueError("GeneratedMedia object needs to either have `media_bytes` or `gcs_uri` set")

    # TODO: change this code to also allow for download from URL (not GCS)
    file = asset.media_bytes or utils_gcs.download_bytes_from_gcs(str(asset.gcs_uri))

    if not file:
        raise RuntimeError(f"Cannot save file to artifacts. No bytes to upload: gcs_uri: {asset.gcs_uri}. asset_name: {asset.filename}. mimetype: {asset.mime_type}")

    asset.media_bytes = file

    if save_in_artifacts:
        await context.save_artifact(
            filename=asset.filename,
            artifact=types.Part.from_bytes(
                data=file,
                mime_type=asset.mime_type,
            ),
        )

        log_message(f"Saved file in artifacts. URL: {asset.gcs_uri}. File size: {len(file)}. asset_name: {asset.filename}", Severity.INFO)

    if save_in_gcs:
        bucket_path = f"{GOOGLE_CLOUD_BUCKET_ARTIFACTS}/{gcs_folder}" if gcs_folder else GOOGLE_CLOUD_BUCKET_ARTIFACTS
        gcs_uri = utils_gcs.upload_to_gcs(
            bucket_path=bucket_path,
            destination_blob_name=asset.filename,
            file_bytes=file
        )

        asset.gcs_uri = utils_gcs.normalize_to_authenticated_url(gcs_uri)
        log_message(f"Saved file in GCS. URL: {asset.gcs_uri}. File size: {len(file)}. asset_name: {asset.filename}", Severity.INFO)

    store_inline_artifact_metadata(context, asset)

    return asset


def store_inline_artifact_metadata(context: CallbackContext, asset: GeneratedMedia, add_to_temp: bool = False):
    """Saves the asset metadata to the session state for inline retrieval.

    Args:
        tool_context: The tool context containing the session state.
        asset: The generated media asset to save.
    """
    try:
        new_artifact_entry = {
            "id": asset.filename,
            "asset": asset.to_obj_sans_bytes(),
            "last_modified": datetime.now().isoformat()
        }

         # Retrieve existing artifacts.
        session_artifacts = context.state.get(SESSION_ARTIFACTS_STATE_KEY, {})
        if not isinstance(session_artifacts, dict):
            # Fallback if it was somehow initialized different than a dict
            session_artifacts = {}

        # Update or add the artifact entry
        session_artifacts[asset.filename] = new_artifact_entry

        # Save back to state
        context.state[SESSION_ARTIFACTS_STATE_KEY] = session_artifacts

        if add_to_temp:
            temp_artifacts = context.state.get(f"{context.state.TEMP_PREFIX}{TEMP_ARTIFACTS_STATE_KEY}", {})
            if not isinstance(temp_artifacts, dict):
                temp_artifacts = {}
            temp_artifacts[asset.filename] = new_artifact_entry
            context.state[f"{context.state.TEMP_PREFIX}{TEMP_ARTIFACTS_STATE_KEY}"] = temp_artifacts

        log_message(f"Saved inline artifact metadata for: {asset.filename}", Severity.INFO)
    except Exception as e:
        log_message(f"WARNING: Failed to save inline artifact metadata: {e}", Severity.WARNING)


def get_and_clear_temp_inline_artifacts(context: CallbackContext) -> dict:
    temp_artifacts = context.state.get(f"{context.state.TEMP_PREFIX}{TEMP_ARTIFACTS_STATE_KEY}", {})
    if not isinstance(temp_artifacts, dict):
        # Fallback if it was somehow initialized different than a dict
        temp_artifacts = {}

    context.state[f"{context.state.TEMP_PREFIX}{TEMP_ARTIFACTS_STATE_KEY}"] = {}
    return temp_artifacts


def get_or_create_unique_session_id(callback_context: CallbackContext):
    session_id = get_unique_session_id(callback_context) or callback_context.session.id
    if not session_id:
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        session_id = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random_suffix}"

    callback_context.state[SESSION_STATE_ID] = session_id
    return session_id


def get_unique_session_id(context: ReadonlyContext):
    return context.state.get(SESSION_STATE_ID)


def to_dict_recursive(obj: Any) -> Any:
    """Recursively converts an object and its nested objects into a dictionary."""
    if not hasattr(obj, "__dict__"):
        return obj
    result = {}
    for key, value in obj.__dict__.items():
        if key.startswith("_"):
            continue
        element = to_dict_recursive(value)
        result[key] = element
    return result


_genai_client = None
_genai_client_global = None


def get_genai_client(use_global: bool = False):
    """Get or create the GenAI client.

    Args:
        use_global: If True, use 'global' location for gemini-3 models
    """
    global _genai_client, _genai_client_global
    from google import genai

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if use_global:
        if _genai_client_global is None:
            _genai_client_global = genai.Client(
                vertexai=True,
                project=project_id,
                location="global",
            )
        return _genai_client_global
    else:
        if _genai_client is None:
            _genai_client = genai.Client(
                vertexai=True,
                project=project_id,
                location=location,
            )
        return _genai_client
