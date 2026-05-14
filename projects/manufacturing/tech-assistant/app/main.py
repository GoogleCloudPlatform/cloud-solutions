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

"""FastAPI application demonstrating ADK Live API Toolkit with WebSocket."""

import asyncio
import base64
import io
import json
import logging
import os
import warnings
from pathlib import Path

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    Form,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.cloud import storage
from google.genai import types
from pypdf import PdfReader

# Load environment variables from .env file BEFORE importing agent
load_dotenv(Path(__file__).parent / ".env")

# Import agent after loading environment variables
# pylint: disable=wrong-import-position
# agent_type = os.getenv("DEMO_AGENT_TYPE", "google_search")
# if agent_type == "tech_assistant":
#     from tech_assistant_agent.agent import agent  # noqa: E402
# else:
#     from google_search_agent.agent import agent  # noqa: E402

from tech_assistant_agent.tech_assistant_agent import agent

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress Pydantic serialization warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Application name constant
APP_NAME = "bidi-demo"

# ========================================
# Phase 1: Application Initialization (once at startup)
# ========================================

app = FastAPI()

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Define your session service
session_service = InMemorySessionService()


def extract_text_from_pdf(pdf_data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_data))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error extracting text from PDF: %s", e)
        return f"Error extracting text from PDF: {e}"


# Load context from GCS if configured
def load_context_from_gcs():
    gcs_storage = os.getenv("GCS_STORAGE")
    if not gcs_storage:
        logger.info("GCS_STORAGE not set in .env")
        return None, ""

    if not gcs_storage.startswith("gs://"):
        logger.error("Invalid GCS_STORAGE URI. Must start with gs://")
        return None, ""

    try:
        uri_parts = gcs_storage[5:].split("/", 1)
        bucket_name = uri_parts[0]
        blob_prefix = uri_parts[1] if len(uri_parts) > 1 else ""

        client = storage.Client()
        bucket = client.bucket(bucket_name)

        # Read prompt.txt
        prompt_blob_name = os.path.join(blob_prefix, "prompt.txt").strip("/")
        prompt_blob = bucket.blob(prompt_blob_name)
        prompt_content = None
        if prompt_blob.exists():
            prompt_content = prompt_blob.download_as_text()
            logger.info("Loaded prompt from GCS: %s", prompt_blob_name)

        # Read other files
        files_content = ""
        blobs = bucket.list_blobs(prefix=blob_prefix)
        for blob in blobs:
            if blob.name == prompt_blob_name:
                continue

            logger.info("Processing file from GCS: %s", blob.name)
            filename = os.path.basename(blob.name)

            if blob.name.endswith(".pdf"):
                pdf_data = blob.download_as_bytes()
                text = extract_text_from_pdf(pdf_data)
                files_content += f"\n\n--- File: {filename} ---\n{text}"
            elif blob.name.endswith(".txt") or blob.name.endswith(".md"):
                text = blob.download_as_text()
                files_content += f"\n\n--- File: {filename} ---\n{text}"
            else:
                logger.warning("Unsupported file type in GCS: %s", blob.name)

        return prompt_content, files_content
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error reading context from GCS: %s", e)
        return None, ""


gcs_prompt, gcs_files = load_context_from_gcs()

# Combine into agent instruction
new_instruction = ""
if gcs_prompt:
    new_instruction += gcs_prompt
else:
    new_instruction += agent.instruction  # Keep default if no prompt.txt

if gcs_files:
    new_instruction += f"\n\nReference Documents:\n{gcs_files}"

if gcs_prompt or gcs_files:
    agent.instruction = new_instruction
    logger.info("Updated agent instruction with GCS context")

# Define your runner
runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)

# ========================================
# HTTP Endpoints
# ========================================


@app.get("/")
async def root():
    """Serve the index.html page."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/upload-context")
async def upload_context(
    prompt: str = Form(...),
    gcs_path: str = Form(...),
    files: list[UploadFile] = File([]),
):
    """Handle file uploads from the popup and save them to GCS."""
    logger.debug(
        "Received upload request: prompt=%s..., gcs_path=%s, files count=%d",
        prompt[:50],
        gcs_path,
        len(files),
    )

    if not gcs_path.startswith("gs://"):
        return {
            "status": "error",
            "message": "Invalid GCS path. Must start with gs://",
        }

    try:
        uri_parts = gcs_path[5:].split("/", 1)
        bucket_name = uri_parts[0]
        blob_prefix = uri_parts[1] if len(uri_parts) > 1 else ""

        client = storage.Client()
        bucket = client.bucket(bucket_name)

        # Save prompt.txt
        prompt_blob_name = os.path.join(blob_prefix, "prompt.txt").strip("/")
        blob = bucket.blob(prompt_blob_name)
        blob.upload_from_string(prompt)
        logger.info("Saved prompt to GCS: %s", prompt_blob_name)

        # Save additional files
        for file in files:
            if file.filename:
                file_blob_name = os.path.join(blob_prefix, file.filename).strip(
                    "/"
                )
                file_blob = bucket.blob(file_blob_name)
                file_blob.upload_from_file(file.file)
                logger.info("Saved file to GCS: %s", file_blob_name)

        return {"status": "success", "message": "Context saved to GCS"}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error saving context to GCS: %s", e)
        return {"status": "error", "message": str(e)}


@app.get("/get-context")
async def get_context():
    """Return the current prompt and GCS storage path."""
    gcs_storage = os.getenv("GCS_STORAGE", "")
    logger.info("[/get-context] GCS_STORAGE: %s", gcs_storage)
    prompt_content = ""
    files_list = []

    if gcs_storage.startswith("gs://"):
        try:
            uri_parts = gcs_storage[5:].split("/", 1)
            bucket_name = uri_parts[0]
            blob_prefix = uri_parts[1] if len(uri_parts) > 1 else ""

            client = storage.Client()
            bucket = client.bucket(bucket_name)

            prompt_blob_name = os.path.join(blob_prefix, "prompt.txt").strip(
                "/"
            )
            prompt_blob = bucket.blob(prompt_blob_name)

            logger.info("[/get-context] Checking blob: %s", prompt_blob_name)
            if prompt_blob.exists():
                prompt_content = prompt_blob.download_as_text()
                logger.info(
                    "[/get-context] Loaded prompt content: %s...",
                    prompt_content[:50],
                )
            else:
                logger.warning(
                    "[/get-context] Blob does not exist: %s", prompt_blob_name
                )

            # List other files
            blobs = bucket.list_blobs(prefix=blob_prefix)
            for blob in blobs:
                if blob.name == prompt_blob_name:
                    continue
                filename = os.path.basename(blob.name)
                if filename:
                    files_list.append(filename)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[/get-context] Error reading prompt: %s", e)

    return {
        "status": "success",
        "prompt": prompt_content,
        "gcs_path": gcs_storage,
        "files": files_list,
    }


# ========================================
# WebSocket Endpoint
# ========================================


@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
    proactivity: bool = False,
    affective_dialog: bool = False,
) -> None:
    """WebSocket endpoint for bidirectional streaming with ADK.

    Args:
        websocket: The WebSocket connection
        user_id: User identifier
        session_id: Session identifier
        proactivity: Enable proactive audio (native audio models only)
        affective_dialog: Enable affective dialog (native audio models only)
    """
    logger.debug(
        "WebSocket connection request: user_id=%s, session_id=%s, "
        "proactivity=%s, affective_dialog=%s",
        user_id,
        session_id,
        proactivity,
        affective_dialog,
    )
    await websocket.accept()
    logger.debug("WebSocket connection accepted")

    # ========================================
    # Phase 2: Session Initialization (once per streaming session)
    # ========================================

    # Automatically determine response modality based on model architecture
    # Native audio models (containing "native-audio" in name)
    # ONLY support AUDIO response modality.
    # Half-cascade models support both TEXT and AUDIO,
    # we default to TEXT for better performance.
    model_name = agent.model
    is_native_audio = "native-audio" in model_name.lower()

    if is_native_audio:
        # Native audio models require AUDIO response modality
        # with audio transcription
        response_modalities = ["AUDIO"]

        # Build RunConfig with optional proactivity and affective dialog
        # These features are only supported on native audio models
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=response_modalities,
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            session_resumption=types.SessionResumptionConfig(),
            proactivity=(
                types.ProactivityConfig(proactive_audio=True)
                if proactivity
                else None
            ),
            enable_affective_dialog=(
                affective_dialog if affective_dialog else None
            ),
        )
        logger.debug(
            "Native audio model detected: %s, "
            "using AUDIO response modality, "
            "proactivity=%s, affective_dialog=%s",
            model_name,
            proactivity,
            affective_dialog,
        )
    else:
        # Half-cascade models support TEXT response modality
        # for faster performance
        response_modalities = ["TEXT"]
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=response_modalities,
            input_audio_transcription=None,
            output_audio_transcription=None,
            session_resumption=types.SessionResumptionConfig(),
        )
        logger.debug(
            "Half-cascade model detected: %s, " "using TEXT response modality",
            model_name,
        )
        # Warn if user tried to enable native-audio-only features
        if proactivity or affective_dialog:
            logger.warning(
                "Proactivity and affective dialog are only supported on native "
                "audio models. Current model: %s. "
                "These settings will be ignored.",
                model_name,
            )
    logger.debug("RunConfig created: %s", run_config)

    # Get or create session (handles both new sessions and reconnections)
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    live_request_queue = LiveRequestQueue()

    # ========================================
    # Phase 3: Active Session (concurrent bidirectional communication)
    # ========================================

    async def upstream_task() -> None:
        """Receives messages from WebSocket and sends to LiveRequestQueue."""
        logger.debug("upstream_task started")
        while True:
            try:
                # Receive message from WebSocket (text or binary)
                message = await websocket.receive()
            except RuntimeError as e:
                if "disconnect message has been received" in str(e):
                    logger.debug("WebSocket disconnected in upstream task")
                    break
                raise e

            # Handle binary frames (audio data)
            if "bytes" in message:
                audio_data = message["bytes"]
                logger.debug(
                    "Received binary audio chunk: %d bytes", len(audio_data)
                )

                audio_blob = types.Blob(
                    mime_type="audio/pcm;rate=16000", data=audio_data
                )
                live_request_queue.send_realtime(audio_blob)

            # Handle text frames (JSON messages)
            elif "text" in message:
                text_data = message["text"]
                logger.debug("Received text message: %s...", text_data[:100])

                json_message = json.loads(text_data)

                # Extract text from JSON and send to LiveRequestQueue
                if json_message.get("type") == "text":
                    logger.debug(
                        "Sending text content: %s", json_message["text"]
                    )
                    content = types.Content(
                        parts=[types.Part(text=json_message["text"])]
                    )
                    live_request_queue.send_content(content)

                # Handle image data
                elif json_message.get("type") == "image":
                    logger.debug("Received image data")

                    # Decode base64 image data
                    image_data = base64.b64decode(json_message["data"])
                    mime_type = json_message.get("mimeType", "image/jpeg")

                    logger.debug(
                        "Sending image: %d bytes, type: %s",
                        len(image_data),
                        mime_type,
                    )

                    # Send image as blob
                    image_blob = types.Blob(
                        mime_type=mime_type, data=image_data
                    )
                    live_request_queue.send_realtime(image_blob)

    async def downstream_task() -> None:
        """Receives Events from run_live() and sends to WebSocket."""
        logger.debug("downstream_task started, calling runner.run_live()")
        logger.debug(
            "Starting run_live with user_id=%s, session_id=%s",
            user_id,
            session_id,
        )
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            event_json = event.model_dump_json(exclude_none=True, by_alias=True)
            logger.debug("[SERVER] Event: %s", event_json)
            await websocket.send_text(event_json)
        logger.debug("run_live() generator completed")

    # Run both tasks concurrently
    # Exceptions from either task will propagate and cancel the other task
    try:
        logger.debug(
            "Starting asyncio.gather for upstream and downstream tasks"
        )
        await asyncio.gather(upstream_task(), downstream_task())
        logger.debug("asyncio.gather completed normally")
    except WebSocketDisconnect:
        logger.debug("Client disconnected normally")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            "Unexpected error in streaming tasks: %s", e, exc_info=True
        )
    finally:
        # ========================================
        # Phase 4: Session Termination
        # ========================================

        # Always close the queue, even if exceptions occurred
        logger.debug("Closing live_request_queue")
        live_request_queue.close()
