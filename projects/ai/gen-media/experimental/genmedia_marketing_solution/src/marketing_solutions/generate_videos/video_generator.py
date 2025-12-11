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
GenMedia Marketing Solution Module - Video.
"""

import base64
import json
import logging
import mimetypes
import os
import random
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

import google.auth
import google.auth.transport.requests
import requests
import vertexai
from dotenv import load_dotenv
from google.cloud import storage
from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class VideoGenerator:
    """
    Agent responsible for generating videos using Vertex AI Video Generation API
    and performing post-processing tasks like combining, adding audio,
    and adding text.

    This class is responsible for:
    - Generating video clips from text prompts or images using the Veo model.
    - Generating background music using the Lyria model.
    - Combining multiple video clips into a single video.
    - Adding audio tracks (music) to videos.
    - Managing the entire video creation workflow, including handling
      long-running operations,interacting with Google Cloud Storage for
      media assets, and processing video files locally.
    """

    NUM_RPC_RETRY = 3
    RPC_RETRY_BACKOFF_SECONDS = 8
    VIDEO_GEN_SEED = 2025
    DEFAULT_ASPECT_RATIO = "16:9"  # Landscape as default
    DEFAULT_PROMPT_STYLE = (
        "A hyperrealistic, {videoStyle} close-up shot of the bakery product. "
        "**The product is perfectly centered and stationary in the frame. "
        "Absolutely no alterations to product, background, or existing scene "
        "elements. Only the camera's perspective shifts.** The camera slowly "
        "and smoothly orbits in a complete 360-degree circle **AROUND THE "
        "PRODUCT'S AXIS**, showcasing it from all angles while **maintaining "
        "a consistent, tight framing on the product**. Emphasize the intricate "
        "details, textures, and the play of light and shadow on the product. "
        "The background is a **warm, inviting bakery environment, softly "
        "blurred (bokeh)**. We get hints of a wooden counter, perhaps a "
        "dusting of flour, and the gentle glow of the bakery's interior, all "
        "complementing the product without distracting from it. Do not add "
        "any other objects, text, or visual elements"
    )

    def __init__(self):
        """
        Initializes the VideoGenerator, setting up clients and configurations.

        Raises:
            ValueError: If any required environment variables are missing.
            Exception: If Vertex AI or GCS initialization fails.
        """
        self.logger = logging.getLogger(__name__)
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION")
        self.veo_model_id = os.getenv("VEO_MODEL_ID")
        self.bucket_name = os.getenv("GCS_BUCKET_NAME")
        self.api_endpoint = os.getenv("VEO_API_ENDPOINT")
        self.lyria_model_id = os.getenv("LYRIA_MODEL_ID")

        self.storage_client: Optional[storage.Client] = None

        if not all(
            [
                self.project_id,
                self.location,
                self.veo_model_id,
                self.api_endpoint,
                self.bucket_name,
                self.lyria_model_id,
            ]
        ):
            self.logger.error(
                "Missing one or more essential environment variables for "
                "VideoGenerator. Please check PROJECT_ID, LOCATION, "
                "VEO_MODEL_ID, VEO_API_ENDPOINT, "
                "GCS_BUCKET_NAME,LYRIA_MODEL_ID."
            )
            raise ValueError("Missing essential environment variables.")

        try:
            vertexai.init(project=self.project_id, location=self.location)
            self.storage_client = storage.Client()
            self.logger.info("VideoGenerator initialized successfully.")
        except Exception:# pylint: disable=broad-exception-caught
            self.logger.exception(
                "Vertex AI, GCS, or Text-to-Speech initialization failed."
            )
            self.storage_client = None
            self.texttospeech_client = None

    def _get_api_endpoint(self) -> str:
        """Constructs the API endpoint URL."""
        return (
            f"https://{self.api_endpoint}/v1/projects/{self.project_id}/"
            f"locations/{self.location}/publishers/google/models/"
            f"{self.veo_model_id}:predictLongRunning"
        )

    def _get_query_endpoint(self) -> str:
        """Constructs the query endpoint URL for long-running operations."""
        return (
            f"https://{self.api_endpoint}/v1/projects/{self.project_id}/"
            f"locations/{self.location}/publishers/google/models/"
            f"{self.veo_model_id}:fetchPredictOperation"
        )

    def _run_shell_command(
        self, command: str, num_retries: int, backoff_seconds: int
    ) -> Dict[str, Any]:
        """
        Executes a shell command with retries.

        Args:
            command: The shell command string to execute.
            num_retries: Number of times to retry the command on failure.
            backoff_seconds: Time to wait between retries.

        Returns:
            A dictionary containing success status and output/operation_id.
        """
        for i in range(num_retries):
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.logger.debug("Shell command output: %s", result.stdout)
                return {"success": True, "output": result.stdout}
            except subprocess.CalledProcessError as e:
                self.logger.warning(
                    "Shell command failed (attempt %d/%d): %s",
                    i + 1,
                    num_retries,
                    e.stderr,
                )
                if i == num_retries - 1:
                    return {"success": False, "output": e.stderr}
                time.sleep(backoff_seconds)
            except Exception as e:# pylint: disable=broad-exception-caught
                self.logger.exception(
                    "Unexpected error running shell command (attempt %d/%d).",
                    i + 1,
                    num_retries,
                )
                if i == num_retries - 1:
                    return {"success": False, "output": str(e)}
                time.sleep(backoff_seconds)
        return {"success": False, "output": "Unknown error after retries."}

    def run_video_gen_shell(self, command: str) -> Dict[str, Any]:
        """
        Runs the video generation shell command and extracts operation ID.
        """
        response = self._run_shell_command(
            command, self.NUM_RPC_RETRY, self.RPC_RETRY_BACKOFF_SECONDS
        )
        if response["success"]:
            try:
                operation_id = json.loads(response["output"])["name"].split(
                    "operations/"
                )[1]
                return {"operation_id": operation_id}
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.error(
                    "Failed to parse operation ID from video gen response: "
                    "%s. Raw output: %s",
                    e,
                    response["output"],
                )
                return {
                    "success": False,
                    "output": f"Failed to parse operation ID: {e}",
                }
        return response

    def run_op_query_shell(self, command: str) -> Dict[str, Any]:
        """
        Runs the operation query shell command and extracts status/response.
        """
        response = self._run_shell_command(
            command, self.NUM_RPC_RETRY, self.RPC_RETRY_BACKOFF_SECONDS
        )
        if response["success"]:
            try:
                status = json.loads(response["output"])
                operation_id = status["name"].split("operations/")[1]
                if "done" in status and status["done"]:
                    if "error" in status:
                        self.logger.error(
                            "Operation %s completed with error: %s",
                            operation_id,
                            status["error"],
                        )
                        return {"success": False, "output": status["error"]}
                    else:
                        self.logger.info(
                            "Operation %s completed successfully.", operation_id
                        )
                        return {"success": True, "output": status["response"]}
                else:
                    self.logger.info(
                        "Operation %s still in progress.", operation_id
                    )
                    return {"success": True, "output": operation_id}
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.error(
                    "Failed to parse operation status from query response: "
                    "%s. Raw output: %s",
                    e,
                    response["output"],
                )
                return {
                    "success": False,
                    "output": f"Failed to parse status: {e}",
                }
        return response

    def compose_videogen_request(
        self,
        prompt: str,
        image_data: Optional[str],
        mime_type: Optional[str],
        video_uri: Optional[str],
        gcs_uri: str,
        seed: int,
        aspect_ratio: str,
        num_videos: int,
    ) -> Dict[str, Any]:
        """
        Composes the request payload for video generation.
        """
        instance = {"prompt": prompt}
        if image_data:
            instance["image"] = {
                "bytesBase64Encoded": image_data,
                "mimeType": mime_type,
            }
        if video_uri:
            instance["video"] = {"gcsUri": video_uri}
        request = {
            "instances": [instance],
            "parameters": {
                "storageUri": gcs_uri,
                "sampleCount": num_videos,
                "seed": seed,
                "aspectRatio": aspect_ratio,
            },
        }
        return request

    def generate_bearer_access_token(self) -> str:
        """
        Generates a Google Cloud bearer access token.
        """
        try:
            creds, _ = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)
            return creds.token
        except Exception: # pylint: disable=broad-exception-caught
            self.logger.exception("Failed to generate bearer access token.")
            raise

    def generate_video(
        self,
        prompt: str,
        image_data: Optional[str],
        mime_type: Optional[str],
        video_uri: Optional[str],
        gcs_uri: str,
        seed: int,
        aspect_ratio: str,
        num_videos: int,
    ) -> Dict[str, Any]:
        """
        Initiates the video generation process.

        Args:
            prompt: The text prompt for the video generation.
            image_data: Base64-encoded image data, if any.
            mime_type: The MIME type of the image data.
            video_uri: The GCS URI of a video to use as input.
            gcs_uri: The GCS URI where the output video will be stored.
            seed: The random seed for the generation.
            aspect_ratio: The aspect ratio of the output video.
            num_videos: The number of videos to generate.

        Returns:
            A dictionary containing the 'operation_id.
        """
        request_payload_dict = self.compose_videogen_request(
            prompt,
            image_data,
            mime_type,
            video_uri,
            gcs_uri,
            seed,
            aspect_ratio,
            num_videos,
        )

        token = self.generate_bearer_access_token()
        tmp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                suffix=".json",
                dir="/tmp",
                encoding="utf-8",
            ) as tmp_req_file_obj:
                tmp_file_path = tmp_req_file_obj.name
                json.dump(request_payload_dict, tmp_req_file_obj)

            command = f"""curl \
                {self._get_api_endpoint()} \
                -H "Authorization: Bearer {token}" \
                -H "Content-Type: application/json" \
                -X POST \
                -d @{tmp_file_path}"""
            return self.run_video_gen_shell(command)
        except Exception as e:# pylint: disable=broad-exception-caught
            self.logger.exception(
                "Error preparing or executing video generation curl command."
            )
            return {"success": False, "output": str(e)}
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    def compose_query_request(self, op_id: str) -> Dict[str, Any]:
        """
        Composes the request payload for querying the status of
        a long-running operation.

        Args:
            op_id: The ID of the long-running operation.

        Returns:
            A dictionary representing the request payload.
        """
        return {
            "operationName": (
                f"projects/{self.project_id}/locations/{self.location}/"
                f"publishers/google/models/{self.veo_model_id}/operations/"
                f"{op_id}"
            )
        }

    def query_op_status(self, op_id: str) -> Any:
        """
        Queries the status of a long-running video generation operation.
        """
        request_payload_dict = self.compose_query_request(op_id)
        token = self.generate_bearer_access_token()
        tmp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                suffix=".json",
                dir="/tmp",
                encoding="utf-8",
            ) as tmp_query_file_obj:
                tmp_file_path = tmp_query_file_obj.name
                json.dump(request_payload_dict, tmp_query_file_obj)

            command = f"""curl \
                {self._get_query_endpoint()} \
                -H "Authorization: Bearer {token}" \
                -H "Content-Type: application/json" \
                -X POST \
                -d @{tmp_file_path}"""
            result = self.run_op_query_shell(command)
            if result["success"]:
                return result["output"]
            else:
                self.logger.error(
                    "Query operation status failed for op_id %s: %s",
                    op_id,
                    result["output"],
                )
                return {"error": result["output"]}
        except Exception as e:# pylint: disable=broad-exception-caught
            self.logger.exception(
                "Error preparing or executing operation query curl command "
                "for op_id %s.",
                op_id,
            )
            return {"error": str(e)}
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    def generate_video_uri(
        self,
        prompt_customized: Optional[str],
        image: str,
        video_style: str,
        video_dur: float,
        num_videos: int = 1,
        angles: Optional[List[str]] = None,
    ) -> Optional[List[str]]:
        """
        Generates one or more videos from an image and a prompt,
        and returns a list of GCS URIs.

        Args:
            prompt_customized: A custom prompt for the video generation.
            image: The path to a local image file or the GCS URI of an image.
            video_style: The style of the video to be generated
                        (e.g., 'cinematic', 'realistic').
            video_dur: The desired duration of each video in seconds.
            num_videos: The number of videos to generate (1-3).
            angles: A list of camera angles to use for the videos.

        Returns:
            A list of GCS URIs of the generated and trimmed videos.

        """
        if not 1 <= num_videos <= 3:
            self.logger.error("Number of videos must be between 1 and 3.")
            return None

        self.logger.info(
            "Initiating generation of %s video(s) for image: %s",
            num_videos,
            image,
        )
        video_uris = []
        for i in range(num_videos):
            angle_prompt = ""
            if angles:
                angle_prompt = angles[i % len(angles)]

            base_prompt = (
                prompt_customized
                if prompt_customized
                else self.DEFAULT_PROMPT_STYLE.format(videoStyle=video_style)
            )

            prompt = f"{base_prompt} {angle_prompt}"
            seed = random.randint(0, 2**32 - 1)  # Use a random seed
            aspect_ratio = self.DEFAULT_ASPECT_RATIO
            unique_id = uuid.uuid4().hex
            output_gcs_prefix = (
                f"gs://{self.bucket_name}/demo-agent-media/demo_video/"
                f"{unique_id}/"
            )

            self.logger.info(
                "Requesting video output to GCS prefix: %s for image: %s",
                output_gcs_prefix,
                image,
            )
            video_gcs = ""
            image_data = None
            mime_type = None

            # Image processing logic (same as before)
            if image.startswith("gs://"):
                if not self.storage_client:
                    self.logger.error(
                        "Storage client not initialized. Cannot download GCS"
                        "image."
                    )
                    return None
                try:
                    bucket_name = image.split("/")[2]
                    blob_name = "/".join(image.split("/")[3:])
                    bucket = self.storage_client.bucket(bucket_name)
                    blob = bucket.blob(blob_name)
                    image_bytes = blob.download_as_bytes()
                    mime_type = (
                        blob.content_type if blob.content_type else "image/jpeg"
                    )
                    image_data = base64.b64encode(image_bytes).decode("utf-8")
                    self.logger.info(
                        "Successfully downloaded and encoded GCS image: %s",
                        image,
                    )
                except Exception:# pylint: disable=broad-exception-caught
                    self.logger.exception(
                        "Error downloading or encoding GCS image '%s'.", image
                    )
                    return None
            elif os.path.exists(image):
                self.logger.info("Reading image from local path: %s", image)
                try:
                    with open(image, "rb") as f:
                        image_bytes = f.read()
                    image_data = base64.b64encode(image_bytes).decode("utf-8")
                    mime_type, _ = mimetypes.guess_type(image)
                    if mime_type is None:
                        mime_type = "image/jpeg"
                    self.logger.info(
                        "Successfully read and encoded local image: %s", image
                    )
                except Exception:# pylint: disable=broad-exception-caught
                    self.logger.exception(
                        "Error reading or encoding local image '%s'.", image
                    )
                    return None
            else:
                self.logger.warning(
                    "Image path does not exist and is not a GCS URI: %s. "
                    "Assuming it's base64 encoded image data directly.",
                    image,
                )
                image_data = image
                mime_type = "image/jpeg"

            op_id_result = self.generate_video(
                prompt,
                image_data,
                mime_type,
                video_gcs,
                output_gcs_prefix,
                seed,
                aspect_ratio,
                1,
            )  # Generate one video at a time

            if not op_id_result.get("operation_id"):
                self.logger.error(
                    "Failed to initiate video generation for %s. Output: %s",
                    image,
                    op_id_result.get("output", "N/A"),
                )
                return None

            original_op_id = op_id_result["operation_id"]
            self.logger.info(
                "Video generation operation initiated for %s. "
                "Original Operation ID: %s",
                image,
                original_op_id,
            )

            current_op_id_being_polled = original_op_id
            query_res = self.query_op_status(current_op_id_being_polled)

            while isinstance(query_res, str):
                if query_res != current_op_id_being_polled:
                    self.logger.info(
                        "Operation ID changed during polling. Original: %s, "
                        "Previously polled: %s, New current: %s. "
                        "Continuing to poll %s.",
                        original_op_id,
                        current_op_id_being_polled,
                        query_res,
                        query_res,
                    )
                current_op_id_being_polled = query_res

                self.logger.info(
                    "Operation %s still in progress. Waiting %s seconds...",
                    current_op_id_being_polled,
                    self.RPC_RETRY_BACKOFF_SECONDS,
                )
                time.sleep(self.RPC_RETRY_BACKOFF_SECONDS)
                query_res = self.query_op_status(current_op_id_being_polled)

                if (
                    query_res
                    and isinstance(query_res, dict)
                    and query_res.get("error")
                ):
                    self.logger.error(
                        "Error while polling operation %s "
                        "(Original task op_id: %s): %s",
                        current_op_id_being_polled,
                        original_op_id,
                        query_res["error"],
                    )
                    return None

            if (
                not isinstance(query_res, dict)
                or query_res.get("error")
                or "videos" not in query_res
                or not query_res["videos"]
            ):
                self.logger.error(
                    "Video generation failed or returned invalid data for "
                    "op_id %s. Response: %s",
                    original_op_id,
                    query_res,
                )
                return None

            gcs_uri = query_res["videos"][0]["gcsUri"]
            self.logger.info("Received generated video URI: %s", gcs_uri)

            # Video processing and trimming logic
            local_original_path = None
            local_trimmed_path = None
            try:
                base_blob_path = gcs_uri.replace(
                    f"gs://{self.bucket_name}/", ""
                )
                base_name_from_gcs = os.path.basename(base_blob_path)

                local_original_path = os.path.join(
                    tempfile.gettempdir(), f"{unique_id}_{base_name_from_gcs}"
                )
                local_trimmed_filename_stem = (
                    f"{unique_id}_{os.path.splitext(base_name_from_gcs)[0]}"
                    "_trimmed"
                )
                local_trimmed_path = os.path.join(
                    tempfile.gettempdir(), f"{local_trimmed_filename_stem}.mp4"
                )

                blob = self.storage_client.bucket(self.bucket_name).blob(
                    base_blob_path
                )
                self.logger.info(
                    "Downloading %s to %s", gcs_uri, local_original_path
                )
                blob.download_to_filename(local_original_path)

                with VideoFileClip(local_original_path) as video_clip:
                    trimmed_video = video_clip.subclipped(
                        0, min(video_clip.duration, video_dur)
                    )
                    self.logger.info(
                        "Trimming video to %s seconds. Saving to %s",
                        trimmed_video.duration,
                        local_trimmed_path,
                    )
                    trimmed_video.write_videofile(
                        local_trimmed_path,
                        codec="libx264",
                        audio_codec="aac",
                        fps=video_clip.fps,
                    )

                trimmed_blob_name = base_blob_path.replace(
                    ".mp4", "_trimmed.mp4"
                )
                blob_trimmed = self.storage_client.bucket(
                    self.bucket_name
                ).blob(trimmed_blob_name)
                self.logger.info(
                    "Uploading trimmed video from %s to GCS: %s",
                    local_trimmed_path,
                    trimmed_blob_name,
                )
                blob_trimmed.upload_from_filename(local_trimmed_path)

                trimmed_gcs_uri = f"gs://{self.bucket_name}/{trimmed_blob_name}"
                self.logger.info(
                    "Trimmed video uploaded to: %s", trimmed_gcs_uri
                )
                video_uris.append(trimmed_gcs_uri)
            except Exception:# pylint: disable=broad-exception-caught
                self.logger.exception(
                    "Error processing generated video from GCS URI %s.",
                    gcs_uri,
                )
                return None
            finally:
                if local_original_path and os.path.exists(local_original_path):
                    os.unlink(local_original_path)
                if local_trimmed_path and os.path.exists(local_trimmed_path):
                    os.unlink(local_trimmed_path)

        return video_uris

    def combine_videos(
        self, local_video_paths: List[str], output_path: str
    ) -> Optional[str]:
        """
        Combines multiple local video files into a single video.

        Args:
            local_video_paths: A list of file paths to local video clips.
            output_path: The desired path for the combined output video.

        Returns:
            The path to the combined video file if successful, None otherwise.
        """
        video_clips: List[VideoFileClip] = []
        try:
            for path in local_video_paths:
                if not os.path.exists(path):
                    self.logger.error(
                        "Video file not found locally for combining: %s", path
                    )
                    continue
                video_clips.append(VideoFileClip(path))

            if not video_clips:
                self.logger.error("No valid video clips found to combine.")
                return None

            final_video = concatenate_videoclips(video_clips)
            self.logger.info("Combining videos to %s...", output_path)
            final_video.write_videofile(
                output_path, codec="libx264", audio_codec="aac"
            )
            self.logger.info("Combined video saved to: %s", output_path)
            return output_path
        except Exception:# pylint: disable=broad-exception-caught
            self.logger.exception("Error combining videos to %s.", output_path)
            return None
        finally:
            for clip in video_clips:
                clip.close()

    def generate_music(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        sample_count: int = 1,  # Default 1
        seed: Optional[int] = None,
    ) -> Optional[str]:
        """
        Generates music using Google's Lyria model.

        Args:
            prompt: The text prompt for the music generation.
            negative_prompt: A negative prompt to guide the music generation.
            duration_seconds: The desired duration of the music in seconds.
            sample_count: The number of music samples to generate.
            seed: The random seed for the generation.

        Returns:
            The path to the temporary music file, or None if an error occurs.
        """
        api_endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/"
            f"publishers/google/models/{self.lyria_model_id}:predict"
        )

        safe_prompts = [
            "A calm and relaxing ambient background music.",
            "An upbeat and positive electronic background music.",
        ]

        prompts_to_try = [prompt] + safe_prompts

        for i, current_prompt in enumerate(prompts_to_try):
            instance_payload: Dict[str, Any] = {"prompt": prompt}
            if negative_prompt:
                instance_payload["negative_prompt"] = negative_prompt

            if duration_seconds:
                # Lyria API expects duration_seconds
                instance_payload["output_spec"] = {
                    "duration_seconds": duration_seconds
                }

            if seed is not None:
                instance_payload["seed"] = seed

            instance_payload["sample_count"] = sample_count

            request_data = {"instances": [instance_payload], "parameters": {}}

            self.logger.info(
                "Sending music generation request to %s with payload: %s",
                api_endpoint,
                json.dumps(request_data, indent=2),
            )
            token = self.generate_bearer_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                api_endpoint, headers=headers, json=request_data
            )
            response_json = response.json()

            if "error" in response_json and "recitation" in response_json[
                "error"
            ].get("message", ""):
                self.logger.warning(
                    "Music generation failed with recitation check on prompt: "
                    "'%s'. Retrying with a more generic prompt (%d/%d).",
                    current_prompt,
                    i + 1,
                    len(prompts_to_try),
                )
                continue

            if not response_json:
                self.logger.error(
                    "Failed to get response from music generation API."
                )
                return None

            if (
                "predictions" not in response_json
                or not isinstance(response_json["predictions"], list)
                or not response_json["predictions"]
            ):
                self.logger.error(
                    "No 'predictions' found in music API response or "
                    "predictions list is empty. Response: %s",
                    response_json,
                )
                return None

            try:
                prediction = response_json["predictions"][0]
                if "bytesBase64Encoded" not in prediction:
                    self.logger.error(
                        "'bytesBase64Encoded' not found in prediction. "
                        "Prediction: %s",
                        prediction,
                    )
                    return None

                bytes_b64 = prediction["bytesBase64Encoded"]
                decoded_audio_data = base64.b64decode(bytes_b64)

                with tempfile.NamedTemporaryFile(
                    suffix=".mp3", delete=False
                ) as temp_music_file:
                    temp_music_file.write(decoded_audio_data)
                    self.logger.info(
                        "Generated music saved to: %s", temp_music_file.name
                    )
                    return temp_music_file.name

            except (IndexError, KeyError) as e:
                self.logger.error(
                    "Error parsing music API response (IndexError or KeyError: "
                    "%s). Response: %s",
                    e,
                    response_json,
                )
                return None
            except Exception:# pylint: disable=broad-exception-caught
                self.logger.exception(
                    "Error processing music API response or saving file."
                )
                return None

        self.logger.error(
            "Music generation failed after all retries. The music generation"
            " was blocked by recitation checks. Please try different prompts."
        )
        return None

    def add_audio_to_video(
        self, video_path: str, audio_path: str, final_output_path: str
    ) -> Optional[str]:
        """
        Adds an audio track to a video clip.

        Args:
            video_path: Path to the input video file.
            audio_path: Path to the input audio file.
            final_output_path: Path for the output video file with audio.

        Returns:
            The path to the final video file if successful, None otherwise.
        """
        if not os.path.exists(video_path):
            self.logger.error("Video file not found: %s", video_path)
            return None
        if not os.path.exists(audio_path):
            self.logger.error("Audio file not found: %s", audio_path)
            return None

        video_clip: Optional[VideoFileClip] = None
        audio_clip: Optional[AudioFileClip] = None
        try:
            video_clip = VideoFileClip(video_path)
            audio_clip = AudioFileClip(audio_path)

            self.logger.info(
                "Video duration: %s, Audio duration: %s",
                video_clip.duration,
                audio_clip.duration,
            )

            if audio_clip.duration > video_clip.duration:
                self.logger.info(
                    "Audio duration (%ss) is longer than video duration "
                    "(%ss). Trimming audio.",
                    audio_clip.duration,
                    video_clip.duration,
                )
                audio_clip = audio_clip.subclipped(0, video_clip.duration)
            elif audio_clip.duration < video_clip.duration:
                self.logger.info(
                    "Audio duration (%ss) is shorter than video duration "
                    "(%ss). Audio will end before video.",
                    audio_clip.duration,
                    video_clip.duration,
                )

            final_clip = video_clip.with_audio(audio_clip)

            self.logger.info(
                "Writing final video with audio to: %s", final_output_path
            )
            final_clip.write_videofile(
                final_output_path, codec="libx264", audio_codec="aac"
            )
            self.logger.info("Video with audio saved to: %s", final_output_path)
            return final_output_path
        except Exception as e:# pylint: disable=broad-exception-caught
            self.logger.exception("Error adding audio to video: %s", e)
            return None
        finally:
            if video_clip:
                video_clip.close()
            if audio_clip:
                audio_clip.close()
