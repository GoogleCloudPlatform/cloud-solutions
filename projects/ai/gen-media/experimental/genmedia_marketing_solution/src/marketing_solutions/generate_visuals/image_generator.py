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
GenMedia Marketing Solution Module - Image.
"""

import asyncio
import logging
import os
import uuid

import google.genai as genai
import vertexai
from dotenv import load_dotenv
from google.cloud import storage
from google.genai import types
from vertexai.preview.vision_models import Image, ImageGenerationModel

# --- Configuration and Initialization ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ImageGenerator:
    """
    Generates images using either the Nano Banana or Imagen 4,
    determined by the IMAGE_MODEL_NAME environment variable.
    All generated images are saved to Google Cloud Storage (GCS).
    """

    def __init__(self):
        """
        Initializes the ImageGenerator.

        This method sets up the necessary clients and configurations for
        image generation.
        It requires the following environment variables to be set:
        - GOOGLE_CLOUD_PROJECT: The Google Cloud project ID.
        - GOOGLE_CLOUD_LOCATION: The Google Cloud location
          (e.g., 'us-central1').
        - GCS_BUCKET_NAME: The name of the Google Cloud Storage bucket for
          storing media assets.
        - IMAGE_GEMINI_MODEL: The image generation model to use
          ('imagen-4.0-generate-001' or 'gemini-2.5-flash-image').

        Clients for GenAI, GCS, and Imagen are initialized lazily.
        """
        self.logger = logging.getLogger("ImageGenerator")
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION")
        self.bucket_name = os.getenv("GCS_BUCKET_NAME")
        self.default_model_name = os.getenv("IMAGE_GEMINI_MODEL")

        self.IMAGEN_4_MODEL = "imagen-4.0-generate-001"
        self.GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"

        # Initialize clients lazily
        self._genai_client = None
        self._storage_client = None
        self._imagen_model = None

        if not all(
            [
                self.project_id,
                self.location,
                self.bucket_name,
                self.default_model_name,
            ]
        ):
            self.logger.error(
                "Missing required environment variables (PROJECT, LOCATION,"
                "BUCKET_NAME, IMAGE_MODEL_NAME)."
            )
            raise EnvironmentError(
                "One or more required environment variables are missing."
            )

        if self.default_model_name not in [
            self.IMAGEN_4_MODEL,
            self.GEMINI_IMAGE_MODEL,
        ]:
            if self.default_model_name == "gemini-2.5-flash-image":
                self.logger.warning(
                    "Model name '%s' mapped to required name '%s'.",
                    self.default_model_name,
                    self.GEMINI_IMAGE_MODEL,
                )
                self.default_model_name = self.GEMINI_IMAGE_MODEL
            else:
                raise ValueError(
                    f"Unknown model name '{self.default_model_name}'. Must be"
                    f" '{self.IMAGEN_4_MODEL}' or '{self.GEMINI_IMAGE_MODEL}'."
                )

        vertexai.init(project=self.project_id, location=self.location)

    # --- Client/Model ---
    def _get_genai_client(self):
        """Initializes and returns the GenAI client for Gemini models."""
        if self._genai_client is None:
            self.logger.info("Initializing GenAI client for Vertex AI.")
            self._genai_client = genai.Client(
                vertexai=True, project=self.project_id, location=self.location
            )
        return self._genai_client

    def _get_storage_client(self):
        """Initializes and returns the GCS client for uploads."""
        if self._storage_client is None:
            self.logger.info("Initializing GCS client.")
            self._storage_client = storage.Client()
        return self._storage_client

    def _get_imagen_model(self, model_name: str):
        """Initializes and returns the Vertex AI Imagen model."""
        if (
            self._imagen_model is None
            or self._imagen_model.model_name != model_name
        ):
            self.logger.info("Initializing Imagen Model: %s", model_name)
            self._imagen_model = ImageGenerationModel.from_pretrained(
                model_name
            )
        return self._imagen_model

    def _save_local_image(self, path: str, image_bytes: bytes):
        """Helper to save image bytes to a local file."""
        with open(path, "wb") as f:
            f.write(image_bytes)

    # --- Utility Methods ---
    def generate_image_prompt(self, product_info, custom_scene=None):
        """
        Generates a refined, photorealistic image prompt.

        Args:
            product_info: A dictionary containing information about the product.
            custom_scene: Optional string to override the default scene.

        Returns:
            A string containing the generated prompt.
        """
        product_name = product_info.get("name", "Pumpkin Cream Scone")
        product_category = product_info.get("category", "bakery")
        default_scene = (
            "on a rustic wooden table, artfully arranged on a **large white"
            " ceramic platter**. Beside the platter is a single crafted white"
            " ceramic mug filled with a **hot, steaming latte** (with latte"
            " art). The entire cafe interior is visible and in focus in the"
            " background."
        )
        scene = custom_scene if custom_scene else default_scene
        prompt = (
            f"High-resolution product photography of {product_name}, a "
            f"{product_category} item.\n"
            "A close-up shot showing **4-6 freshly-baked, golden-brown "
            f"{product_name}**.\n"
            f"**The products are in {scene}.**\n"
            "A wisp of steam should be rising from the hot latte.\n"
            "The image must be photorealistic, with a sharp focus on both the "
            f"crumb texture of the {product_name} and the details of the "
            "background.\n"
            "Use bright, natural lighting."
        )
        return prompt

    async def upload_bytes_to_gcs(
        self, image_bytes: bytes, prefix: str, mime_type: str = "image/png"
    ):
        """Uploads raw image bytes to GCS and returns the URI."""
        storage_client = self._get_storage_client()
        bucket = storage_client.bucket(self.bucket_name)
        ext = mime_type.split("/")[-1]
        unique_id = uuid.uuid4().hex
        image_filename = f"generated_images/{prefix}_{unique_id}.{ext}"
        blob = bucket.blob(image_filename)

        await asyncio.to_thread(
            blob.upload_from_string,
            image_bytes,
            content_type=mime_type,
            timeout=60,
        )

        gcs_uri = f"gs://{self.bucket_name}/{image_filename}"

        # Save image to local output/images directory
        local_output_dir = "output/images"
        os.makedirs(local_output_dir, exist_ok=True)

        # Extract base filename from GCS path
        local_filename = os.path.basename(image_filename)
        local_file_path = os.path.join(local_output_dir, local_filename)

        await asyncio.to_thread(
            lambda: self._save_local_image(local_file_path, image_bytes)
        )
        self.logger.info("Image also saved locally to: %s", local_file_path)

        return gcs_uri

    async def generate_and_save_image(
        self, product_info, custom_scene: str = None
    ):
        """Routes to the correct model based on the determined
        self.default_model_name.
        """
        prompt = self.generate_image_prompt(product_info, custom_scene)

        if self.default_model_name == self.GEMINI_IMAGE_MODEL:
            self.logger.info("Model selected: %s.", self.GEMINI_IMAGE_MODEL)
            return await self._generate_with_genai_client(prompt)

        elif self.default_model_name == self.IMAGEN_4_MODEL:
            self.logger.info("Model selected: %s.", self.IMAGEN_4_MODEL)
            return await self._generate_with_imagen_model(
                prompt, self.IMAGEN_4_MODEL
            )

        else:
            raise ValueError(
                "Internal error: Invalid model name"
                f" '{self.default_model_name}'."
            )

    # --- Gemini Generation Implementation---
    async def _generate_with_genai_client(self, prompt: str):
        """
        Generates an image using the Gemini model and uploads it to GCS.

        Args:
            prompt: The prompt to use for image generation.

        Returns:
            A list containing the GCS URI of the generated image.
        """
        client = self._get_genai_client()

        contents = [
            types.Content(
                role="user", parts=[types.Part.from_text(text=prompt)]
            )
        ]

        # Configuration for Gemini
        generation_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            response_modalities=["IMAGE"],
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_NONE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="BLOCK_NONE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"
                ),
            ],
            image_config=types.ImageConfig(
                aspect_ratio="4:3",
            ),
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=self.GEMINI_IMAGE_MODEL,
            contents=contents,
            config=generation_config,
        )

        if not (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
            and response.candidates[0].content.parts[0].inline_data
            and response.candidates[0].content.parts[0].inline_data.data
        ):
            raise RuntimeError("Gemini model did not return valid image data.")

        image_bytes = response.candidates[0].content.parts[0].inline_data.data

        gcs_uri = await self.upload_bytes_to_gcs(
            image_bytes, "gemini", "image/png"
        )
        self.logger.info(
            "Gemini visual generated and saved to GCS. URI: %s", gcs_uri
        )
        return [gcs_uri]

    # --- Imagen Generation Implementation ---
    async def _generate_with_imagen_model(self, prompt: str, model_name: str):
        """
        Generates an image using the Imagen model and uploads it to GCS.

        Args:
            prompt: The prompt to use for image generation.
            model_name: The name of the Imagen model to use.

        Returns:
            A list of GCS URIs of the generated images.
        """
        model = self._get_imagen_model(model_name)

        # Configuration for Imagen
        images = await asyncio.to_thread(
            model.generate_images,
            prompt=prompt,
            number_of_images=1,  # number of images to generate, default 1
            aspect_ratio="4:3",
            safety_filter_level="block_few",
            person_generation="allow_adult",
        )

        image_urls = []
        for i, generated_image in enumerate(images):
            try:
                if isinstance(generated_image, Image):
                    image_bytes = generated_image.image_bytes
                    gcs_uri = await self.upload_bytes_to_gcs(
                        image_bytes, "imagen", "image/jpeg"
                    )
                    image_urls.append(gcs_uri)
                    self.logger.info(
                        "Imagen image %d saved to GCS. URI: %s", i + 1, gcs_uri
                    )
                else:
                    self.logger.error(
                        "Generated image %d is not a valid Vertex AI Image"
                        " object.",
                        i + 1,
                    )
            except (ValueError, RuntimeError) as e:
                self.logger.error(
                    "Error processing Imagen image: %s", e, exc_info=True
                )
        return image_urls

