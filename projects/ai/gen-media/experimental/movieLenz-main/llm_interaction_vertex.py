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

"""A module for interacting with Gemini models via the Vertex AI SDK.

Example usage:
    python llm_interaction_vertex.py

This module provides a GeminiVertexCaller class for interacting with Google's
Gemini models through the Vertex AI API.
"""

import os
import time
from typing import Any, List, Sequence, Union

from absl import app
from google import genai
from google.api_core import exceptions
from google.genai import types

DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_LOCATION = "global"


class GeminiVertexCaller:
    """A class to interact with Gemini models via the Vertex AI SDK."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        project: str | None = None,
        location: str = DEFAULT_LOCATION,
        # Allow passing credentials directly for more flexibility/testing
    ):
        """Initializes the GeminiVertexCaller."""
        self._client = genai.Client(
            vertexai=True, project=project, location=location
        )
        self._model = model_name
        # Basic generation config, can be customized further
        self._generation_config = types.GenerateContentConfig(
            candidate_count=1,
            temperature=0.5,
            top_p=1,
            max_output_tokens=8192,
        )

    def _generate_content(
        self,
        contents: List[Union[str, types.Part]],
        generation_config: types.GenerateContentConfig | None = None,
    ) -> str:
        """Helper method to call the generate_content API and extract text."""
        config_to_use = generation_config or self._generation_config
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # The genai library expects a list of Parts within a single
                # Content object for simple multi-part prompts
                # (text, image, video).
                responses = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config_to_use,
                )
                return responses.candidates[0].content.parts[0].text
            except exceptions.ResourceExhausted as e:
                if attempt < max_retries - 1:
                    print(
                        f"Resource exhausted (429). Retrying in 60 seconds... "
                        f"(Attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(60)
                else:
                    print("Max retries reached. Raising the final exception.")
                    raise e
            except exceptions.GoogleAPIError as e:  # Catch other API errors
                # Handle potential API errors
                print(f"Error calling Vertex AI API: {e}")
                raise e
        return ""

    def call_with_list(
        self, inputs: List[Any], response_mime_type: str | None = None
    ) -> str:
        """Calls Gemini with a list of inputs (text, or (bytes, mime_type)
        tuples).

        Args:
          inputs: A list containing text strings or tuples of
            (bytes, mime_type) for image/video data.

        Returns:
          The generated text content from Gemini as a string.

        Raises:
          TypeError: If an unsupported type is found in the input list, or
            if raw bytes are passed instead of (bytes, mime_type) tuples.
        """
        parts = []
        for item in inputs:
            if isinstance(item, str):
                parts.append(types.Part.from_text(text=item))
            elif (
                isinstance(item, tuple)
                and len(item) == 2
                and isinstance(item[0], bytes)
                and isinstance(item[1], str)
            ):
                # Expecting (bytes, mime_type) tuple
                mime_type = item[1]
                data = item[0]
                # Basic validation for common image/video types, but optional
                if not mime_type or "/" not in mime_type:
                    raise ValueError(f"Invalid MIME type provided: {mime_type}")
                parts.append(
                    types.Part.from_bytes(mime_type=mime_type, data=data)
                )
            elif isinstance(item, bytes):
                # Explicitly disallow raw bytes without a MIME type
                raise TypeError(
                    "Raw bytes found in input list. Please provide bytes as a "
                    "(bytes, mime_type) tuple."
                )
            else:
                raise TypeError(
                    f"Unsupported type in input list: {type(item)}. "
                    "Expected str or (bytes, mime_type) tuple."
                )
        current_config = self._generation_config
        if response_mime_type:
            config_kwargs = self._generation_config.__dict__
            config_kwargs["response_mime_type"] = response_mime_type
            current_config = types.GenerateContentConfig(**config_kwargs)
        return self._generate_content(parts, generation_config=current_config)

    def call_with_text(
        self, prompt: str, response_mime_type: str | None = None
    ) -> str:
        """Calls Gemini with a text-only prompt.

        Args:
          prompt: The text prompt to send to Gemini.
          response_mime_type: Optional. The desired MIME type for the response.

        Returns:
          The generated text content from Gemini as a string.
        """
        current_config = self._generation_config
        if response_mime_type:
            config_kwargs = self._generation_config.__dict__
            config_kwargs["response_mime_type"] = response_mime_type
            current_config = types.GenerateContentConfig(**config_kwargs)
        return self._generate_content(
            [types.Part.from_text(text=prompt)],
            generation_config=current_config,
        )

    def call_with_text_and_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mimetype: str = "image/png",
        response_mime_type: str | None = None,
    ) -> str:
        """Calls Gemini with a text prompt and an image.

        Args:
          prompt: The text prompt to send to Gemini.
          image_bytes: The image bytes to send to Gemini.
          mimetype: The MIME type of the image (e.g., "image/jpeg",
            "image/png").
          response_mime_type: Optional. The desired MIME type for the
            response.

        Returns:
          The generated text content from Gemini as a string.
        """
        parts = [
            types.Part.from_bytes(mime_type=mimetype, data=image_bytes),
            types.Part.from_text(text=prompt),
        ]
        current_config = self._generation_config
        if response_mime_type:
            config_kwargs = self._generation_config.__dict__
            config_kwargs["response_mime_type"] = response_mime_type
            current_config = types.GenerateContentConfig(**config_kwargs)
        return self._generate_content(parts, generation_config=current_config)

    def call_with_text_and_video(
        self,
        prompt: str,
        video_bytes: bytes,
        mimetype: str = "video/mp4",
        response_mime_type: str | None = None,
    ) -> str:
        """Calls Gemini with a text prompt and a video.

        Args:
          prompt: The text prompt to send to Gemini.
          video_bytes: The video bytes to send to Gemini.
          mimetype: The MIME type of the video (e.g., "video/mp4",
            "video/mpeg").
          response_mime_type: Optional. The desired MIME type for the
            response.

        Returns:
          The generated text content from Gemini as a string.
        """
        parts = [
            types.Part.from_bytes(mime_type=mimetype, data=video_bytes),
            types.Part.from_text(text=prompt),
        ]
        current_config = self._generation_config
        if response_mime_type:
            config_kwargs = self._generation_config.__dict__
            config_kwargs["response_mime_type"] = response_mime_type
            current_config = types.GenerateContentConfig(**config_kwargs)
        return self._generate_content(parts, generation_config=current_config)


def main(argv: Sequence[str]) -> None:
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments.")

    # Example Usage
    # Make sure Application Default Credentials (ADC) are set up correctly:
    # gcloud auth application-default login
    #
    # Set your project using environment variable:
    # export GOOGLE_CLOUD_PROJECT=your-project-id
    # export GOOGLE_CLOUD_LOCATION=us-central1  # optional, defaults to
    # us-central1
    try:
        # Get project and location from environment variables with fallbacks
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT environment variable must be set. "
                "Run: export GOOGLE_CLOUD_PROJECT=your-project-id"
            )
        location_id = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

        # if _ROBOT_ACCOUNT_EMAIL.value:
        #   print(
        #       f"Using robot account: {_ROBOT_ACCOUNT_EMAIL.value} with "
        #       f"scopes: {_ROBOT_SCOPES.value}"
        #   )
        #   caller = GeminiVertexCaller(
        #       project=project_id,
        #       location=location_id,
        #       robot_account_email=_ROBOT_ACCOUNT_EMAIL.value,
        #       scopes=_ROBOT_SCOPES.value,
        #   )
        # else:
        print("Using Application Default Credentials (ADC).")
        # You might need to specify project and location if not inferred
        # correctly by ADC or if you want to override them.
        caller = GeminiVertexCaller(project=project_id, location=location_id)

        # Text example
        print("--- Text Example ---")
        response_text = caller.call_with_text("What is the capital of France?")
        print(
            f"Prompt: What is the capital of France?\n"
            f"Response: {response_text}\n"
        )

        # Text and Image example (requires a sample image)
        # print("--- Text+Image Example ---")
        # try:
        #   with open("path/to/your/image.png", "rb") as f:
        #     image_data = f.read()
        #   response_image = caller.call_with_text_and_image(
        #       "Describe this image.", image_data, mimetype="image/png"
        #   )
        #   print(f"Prompt: Describe this image.\nResponse: {response_image}\n")
        # except FileNotFoundError:
        #   print("Skipping image example: Image file not found.")
        # except Exception as e:
        #    print(f"Image example failed: {e}")

        # List example (mixed text and potentially image/video bytes)
        print("--- List Example ---")
        # Example with just text items in the list
        list_response = caller.call_with_list(
            ["Explain the concept of AI.", "Give a short example."],
            response_mime_type="application/json",
        )
        print(
            "Prompt: ['Explain the concept of AI.', "
            f"'Give a short example.']\n"
            f"Response: {list_response}\n"
        )

    except exceptions.GoogleAPIError as e:
        print(f"An error occurred: {e}")
        print(
            "Please ensure you have authenticated with GCP "
            "(gcloud auth application-default login)"
        )
        print("and that the Vertex AI API is enabled for your project.")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    app.run(main)
