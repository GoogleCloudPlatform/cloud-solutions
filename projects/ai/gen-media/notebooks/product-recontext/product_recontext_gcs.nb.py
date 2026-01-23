# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown] id="sUQs1-3UNlYq"
# """
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
# """

# %% [markdown]
# # Product Image Recontextualization with Google Cloud Storage
#
# <table align="left">
#   <td style="text-align: center">
#     <a href="https://colab.research.google.com/github/GoogleCloudPlatform/cloud-solutions/blob/main/projects/ai/gen-media/notebooks/product-recontext/product_recontext_gcs.ipynb">
#       <img width="32px" src="https://www.gstatic.com/pantheon/images/bigquery/welcome_page/colab-logo.svg" alt="Google Colaboratory logo"><br> Open in Colab
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://console.cloud.google.com/vertex-ai/colab/import/https:%2F%2Fraw.githubusercontent.com%2FGoogleCloudPlatform%2Fcloud-solutions%2Fmain%2Fprojects%2Fai%2Fgen-media%2Fnotebooks%2Fproduct-recontext%2Fproduct_recontext_gcs.ipynb">
#       <img width="32px" src="https://lh3.googleusercontent.com/JmcxdQi-qOpctIvWKgPtrzZdJJK-J3sWE1RsfjZNwshCFgE_9fULcNpuXYTilIR2hjwN" alt="Google Cloud Colab Enterprise logo"><br> Open in Colab Enterprise
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://console.cloud.google.com/vertex-ai/workbench/deploy-notebook?download_url=https://raw.githubusercontent.com/GoogleCloudPlatform/cloud-solutions/main/projects/ai/gen-media/notebooks/product-recontext/product_recontext_gcs.ipynb">
#       <img src="https://www.gstatic.com/images/branding/gcpiconscolors/vertexai/v1/32px.svg" alt="Vertex AI logo"><br> Open in Vertex AI Workbench
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://github.com/GoogleCloudPlatform/cloud-solutions/tree/main/projects/ai/gen-media/notebooks/product-recontext">
#       <img width="32px" src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="GitHub logo"><br> View on GitHub
#     </a>
#   </td>
# </table>

# %% [markdown]
# ## Overview
#
# This notebook demonstrates how to use Google's Gemini models to recontextualize product images at scale using Google Cloud Storage (GCS). It takes product photos with simple backgrounds and generates lifestyle images with the products in realistic, contextual settings.
#
# ### What this notebook does:
# - **Reads** product images from GCS buckets
# - **Generates** recontextualized lifestyle images using Gemini 3 Pro
# - **Saves** output to GCS for easy access and sharing
# - **Processes** multiple products in parallel for efficiency
# - **Evaluates** image quality across 6 dimensions
# - **Retries** automatically on API failures
#
# ### Sample Images Available:
# This repository includes sample product images in the `./images/product_images_input/` folder with three product folders (product1, product2, product3). To use these samples, you need to upload them to your GCS bucket at `gs://your-bucket/product_images_input/` before running the pipeline. You can use gsutil or the Cloud Console to copy these folders to your bucket.
#
# ### GCS Structure:
# ```
# gs://your-bucket/
# ├── product_images_input/
# │   ├── product1/        # Upload your product images here
# │   ├── product2/
# │   └── product3/
# └── product_images_output/
#     ├── product1/        # Generated images saved here
#     ├── product2/
#     └── product3/
# ```
#
# ### Prerequisites:
# - Google Cloud Project with Vertex AI API enabled
# - GCS bucket with appropriate permissions
# - Product images organized in folders within the bucket
#
# ---

# %%
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

# %% [markdown] id="h8e0BAP5NlYs"
# ## Cell 1: Import Libraries
#
# **Purpose:** Install required packages and import all necessary libraries for the entire notebook.
#
# **What this does:**
# - Installs Google Cloud AI Platform, pandas, and widgets packages
# - Imports all required Python libraries organized by category
# - Sets up the foundation for all subsequent operations
#
# **Action Required:** None - just run this cell once at the start

# %% id="8ezo9snGNlYs"
# === INSTALL REQUIRED PACKAGES ===
# !pip install --upgrade --user google-cloud-aiplatform pandas ipywidgets

# Standard library imports
import base64
import concurrent.futures
import io
import json
import os
import re
import tempfile
import time
import timeit
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Generator, List

# Third-party imports
import ipywidgets as widgets
import matplotlib.pyplot as plt
import pandas as pd

# === ALL IMPORTS ===
# Google Cloud and AI imports
from google import genai
from google.cloud import aiplatform, storage
from google.cloud.aiplatform.gapic import PredictResponse
from google.colab import auth
from google.genai import types
from PIL import Image, UnidentifiedImageError

# Data processing and visualization

print("All imports completed successfully")
print(f"Notebook executed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# %% [markdown] id="5WXgrrH4NlYt"
# ## Cell 2: Configuration Settings
#
# **Purpose:** Central configuration hub for all notebook parameters.
#
# **What this does:**
# - Defines all configurable parameters in one place
# - Sets model names, paths, thresholds, and processing parameters
# - Configures safety settings and prompts
#
# **Action Required:**
# - **EDIT THIS CELL** to customize settings for your environment
# - Update PROJECT_ID, BUCKET_NAME, and paths as needed
# - Adjust model parameters and thresholds based on requirements
# - All other cells will automatically use these settings

# %% id="j4odEsItNlYt"
# ============================================================================
# CONFIGURATION SECTION - MODIFY PARAMETERS HERE
# ============================================================================

# === GOOGLE CLOUD CONFIGURATION ===
PROJECT_ID = "PROJECT_NAME"  # Your GCP project ID
LOCATION = "us-central1"  # GCP region for Vertex AI
GENAI_LOCATION = "global"  # Location for Genai client

# === STORAGE CONFIGURATION ===
BUCKET_NAME = "BUCKET_NAME"  # Your GCS bucket name
INPUT_PREFIX = (
    "product_images_input/"  # Input folder path (keep trailing slash)
)
OUTPUT_PREFIX = (
    "product_images_output/"  # Output folder path (keep trailing slash)
)

# === MODEL CONFIGURATION ===
# Image Generation Model
GENERATION_MODEL = "gemini-3-pro-image-preview"  # Model for image generation
GENERATION_TEMPERATURE = 0.2  # Temperature for generation
GENERATION_TOP_P = 0.95  # Top-p for generation
GENERATION_MAX_TOKENS = 8192  # Max output tokens

# Evaluation Model
EVALUATION_MODEL = "gemini-2.5-flash"  # Model for evaluation
EVALUATION_TEMPERATURE = 0.1  # Temperature for evaluation
EVALUATION_TOP_P = 0.95  # Top-p for evaluation
EVALUATION_MAX_TOKENS = 65535  # Max output tokens for evaluation
EVALUATION_SEED = 0  # Seed for reproducibility

# === PROCESSING CONFIGURATION ===
MAX_WORKERS = 10  # Number of parallel workers for generation
MAX_EVAL_WORKERS = 8  # Number of parallel workers for evaluation
MAX_IMAGES_PER_PRODUCT = 3  # Maximum input images per product
MAX_RETRIES = 1  # Number of retries on resource exhaustion
RETRY_DELAY = 5  # Seconds to wait before retry

# === IMAGE PROCESSING CONFIGURATION ===
THUMBNAIL_SIZE = (640, 640)  # Size for display thumbnails
OUTPUT_IMAGE_SIZE = (1024, 1024)  # Size for saved output images
OUTPUT_IMAGE_FORMAT = "JPEG"  # Format for output images
OUTPUT_IMAGE_QUALITY = 95  # JPEG quality (1-100)

# === EVALUATION CONFIGURATION ===
LOW_SCORE_THRESHOLD = 3.0  # Threshold for low-scoring products
REVIEW_THRESHOLD = 4.0  # Default threshold for review widget

# === SAFETY SETTINGS ===
SAFETY_THRESHOLD = (
    "BLOCK_NONE"  # Options: BLOCK_NONE, BLOCK_LOW, BLOCK_MEDIUM, BLOCK_HIGH
)
SAFETY_CATEGORIES = [
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_HARASSMENT",
]

# === PROMPT TEMPLATES ===
GENERATION_PROMPT = """Role: You are an expert visual analyst specializing in photo-realistic product visualization.

Task: Analyze the provided product images (up to 3 views) and generate a single, high-quality output image recontextualizing the product in a new, relatable, appropriate environment.

Core Constraint: The output image must render only the analyzed product within the new scene. Maintain product integrity by applying common-sense groupings (e.g., displaying both items of a pair of shoes). Crucially, the generation must completely exclude any visual reference to the source image's original background, lighting, human models, or clothing.

Output Format: Do not include any text in your output, only the generated image and its associated metadata."""

EVALUATION_SYSTEM_PROMPT = """You are an expert visual quality evaluator for AI-generated e-commerce images.
Your task is to compare three original product images (studio-style, white background)
to one AI-generated output image (recontextualized lifestyle photo).
Your goal is to assess if the output image faithfully and attractively represents the product
while adhering to commercial quality and brand standards.
Do not assume any information beyond what is visible in the images.

For each of the six evaluation dimensions, assign a score from 1 to 5 and provide a short justification.

Finally, calculate an overall quality score based on your judgment of the image's commercial viability.
This score should summarize the output's overall fitness for use in real-world e-commerce listings
(e.g., company's product pages). Return this score under the `overall_score` key in the JSON.

Use your understanding of visual coherence, aesthetic judgment, and product realism to make your assessments."""

# === DERIVED CONFIGURATIONS (DO NOT MODIFY) ===
INPUT_GCS_URI = f"gs://{BUCKET_NAME}/{INPUT_PREFIX}"
OUTPUT_GCS_URI = f"gs://{BUCKET_NAME}/{OUTPUT_PREFIX}"
OUTPUT_BUCKET = BUCKET_NAME

# === DISPLAY CONFIGURATION ===
print("=" * 70)
print("CONFIGURATION LOADED")
print("=" * 70)
print(f"Project ID:          {PROJECT_ID}")
print(f"Location:            {LOCATION}")
print(f"Bucket:              {BUCKET_NAME}")
print(f"Input Path:          {INPUT_GCS_URI}")
print(f"Output Path:         {OUTPUT_GCS_URI}")
print(f"Generation Model:    {GENERATION_MODEL}")
print(f"Evaluation Model:    {EVALUATION_MODEL}")
print(
    f"Max Workers:         {MAX_WORKERS} (generation), {MAX_EVAL_WORKERS} (evaluation)"
)
print(f"Retry Settings:      {MAX_RETRIES} retries with {RETRY_DELAY}s delay")
print(f"Images per Product:  {MAX_IMAGES_PER_PRODUCT}")
print("=" * 70)

# %% [markdown] id="vHd-ZnShNlYt"
# ## Cell 3: Google Cloud Authentication
#
# **Purpose:** Authenticate your Colab session with Google Cloud Platform.
#
# **What this does:**
# - Prompts for Google Cloud authentication
# - Establishes credentials for accessing GCS and Vertex AI
# - Required for all cloud operations in this notebook
#
# **Action Required:**
# - Run this cell and follow the authentication prompts
# - Sign in with an account that has access to your GCP project

# %% id="fFN9hSl0NlYt"
# Authenticate with Google Cloud
auth.authenticate_user()
print("Authenticated with Google Cloud")
print(f"Ready to work with project: {PROJECT_ID}")

# %% [markdown] id="a2eczCl8NlYt"
# ## Cell 4: Initialize Cloud Clients
#
# **Purpose:** Set up all necessary Google Cloud service clients.
#
# **What this does:**
# - Initializes Vertex AI with your project settings
# - Creates Storage client for GCS operations
# - Sets up Prediction client for model endpoints
# - Initializes Genai client for Gemini models
#
# **Action Required:** None - just run this cell to initialize all clients

# %% id="2oNVVTWONlYt"
# Initialize all clients using configuration from Cell 2
print("Initializing clients...")

# Initialize Vertex AI
aiplatform.init(project=PROJECT_ID, location=LOCATION)
print("  Vertex AI initialized")

# Storage client for GCS operations
storage_client = storage.Client()
print("  Storage client ready")

# Prediction client (for Vertex AI endpoints if needed)
predict_client = aiplatform.gapic.PredictionServiceClient(
    client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
)
print("  Prediction client ready")

# Genai client for Gemini models
genai_client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=GENAI_LOCATION,
)
print("  Genai client ready")

print("\nAll clients initialized successfully")
print(f"Ready to process images from: {INPUT_GCS_URI}")


# %% [markdown] id="QAQlWBH3NlYu"
# ## Cell 5: GCS Helper Functions
#
# **Purpose:** Define utility functions for Google Cloud Storage operations.
#
# **What this does:**
# - `get_mime_type()`: Determines file MIME types
# - `discover_product_batches()`: Scans GCS for product folders
# - `list_product_folders()`: Lists all product directories
# - `get_image_uris()`: Retrieves image URIs from GCS
# - `find_output_uri()`: Locates generated output images
#
# **Action Required:** None - these are helper functions used by other cells

# %% id="FKx90dT9NlYu"
def get_mime_type(uri: str) -> str:
    """Get MIME type from file extension."""
    ext = os.path.splitext(uri)[1].lower()
    if ext == ".png":
        return "image/png"
    elif ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    else:
        raise ValueError(f"Unsupported extension: {ext}")


def discover_product_batches(
    input_gcs_uri: str,
) -> Generator[Dict[str, object], None, None]:
    """
    Discovers and yields product batches from GCS.
    Yields dicts with:
      - product_folder (e.g. "product_5")
      - image_parts   (List[types.Part])
      - product_uris  (List[str])
    """
    m = re.match(r"gs://([^/]+)/(.+?)/?$", input_gcs_uri)
    if not m:
        raise ValueError(f"Invalid GCS URI: {input_gcs_uri}")
    bucket_name, base_prefix = m.groups()
    prefix = base_prefix.rstrip("/") + "/"
    client = storage.Client()
    print(f"Scanning bucket={bucket_name} prefix={prefix}")

    blobs = list(client.list_blobs(bucket_name, prefix=prefix))
    print(f"  Found {len(blobs)} total objects under {prefix}")

    folder_map: Dict[str, List[storage.blob.Blob]] = {}
    for b in blobs:
        rel = b.name[len(prefix) :]
        parts = rel.split("/", 1)
        if len(parts) != 2:
            continue
        folder, filename = parts
        if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        folder_map.setdefault(folder, []).append(b)

    print(f"  Discovered product folders: {list(folder_map.keys())}")

    for folder, blob_list in folder_map.items():
        blob_list.sort(key=lambda b: os.path.basename(b.name))
        blob_list = blob_list[:MAX_IMAGES_PER_PRODUCT]

        uris = [f"gs://{bucket_name}/{b.name}" for b in blob_list]
        parts = [
            types.Part(
                file_data=types.FileData(
                    file_uri=uri, mime_type=get_mime_type(uri)
                )
            )
            for uri in uris
        ]

        yield {
            "product_folder": folder,
            "image_parts": parts,
            "product_uris": uris,
        }


def list_product_folders(bucket_name: str, prefix: str) -> list[str]:
    """List all product folders in a GCS prefix."""
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
    prods = {
        b.name[len(prefix) :].split("/", 1)[0]
        for b in blobs
        if "/" in b.name[len(prefix) :]
    }
    return sorted(prods)


def get_image_uris(
    bucket_name: str, prefix: str, max_images: int = 3
) -> list[str]:
    """Get image URIs from a GCS prefix."""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
    files = [
        b.name
        for b in storage_client.list_blobs(bucket_name, prefix=prefix)
        if os.path.splitext(b.name)[1].lower() in exts
    ]
    return [f"gs://{bucket_name}/{n}" for n in sorted(files)[:max_images]]


def find_output_uri(bucket_name: str, product: str) -> str:
    """Find the output image for a product."""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
    prefix = f"{OUTPUT_PREFIX}{product}/"
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
    candidates = [
        b.name
        for b in blobs
        if "output" in b.name.lower()
        and os.path.splitext(b.name)[1].lower() in exts
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No output image under gs://{bucket_name}/{prefix}"
        )
    chosen = sorted(candidates)[0]
    return f"gs://{bucket_name}/{chosen}"


print("GCS helper functions loaded")


# %% [markdown] id="_MPiNKJ5NlYu"
# ## Cell 6: Image Processing Helper Functions
#
# **Purpose:** Define utility functions for image manipulation and display.
#
# **What this does:**
# - `download_gcs_image_bytes()`: Downloads images from GCS
# - `prediction_to_pil_image()`: Converts model output to PIL images
# - `display_row()`: Shows multiple images in a row
# - `display_product_images()`: Displays input and output images together
#
# **Action Required:** None - these are helper functions for image handling

# %% id="EiUNZffYNlYu"
def download_gcs_image_bytes(uri: str) -> bytes:
    """Download image bytes from GCS."""
    m = re.match(r"gs://([^/]+)/(.*)", uri)
    if not m:
        raise ValueError(f"Invalid GCS URI: {uri}")
    bucket_name, obj = m.groups()
    client = storage.Client()
    return client.bucket(bucket_name).blob(obj).download_as_bytes()


def prediction_to_pil_image(pred: Dict[str, Any], size=None) -> Image.Image:
    """
    Decodes image data into a PIL.Image.
    Supports both Vertex-style base64 and Gemini inline_data bytes.
    """
    if size is None:
        size = THUMBNAIL_SIZE

    if "bytesBase64Encoded" not in pred:
        raise ValueError(
            "Prediction dictionary missing 'bytesBase64Encoded' key."
        )

    payload = pred["bytesBase64Encoded"]

    try:
        if isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
        else:
            data = base64.b64decode(payload, validate=False)

        img = Image.open(io.BytesIO(data))

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.thumbnail(size)
        return img

    except (TypeError, UnidentifiedImageError, OSError) as e:
        print(f"Error decoding image data: {e}")
        raise UnidentifiedImageError(
            "Could not process image data from model response."
        )


def display_row(items: List[Any], figsize=(12, 4)):
    """Display a row of images."""
    if not items:
        print("No items to display.")
        return
    fig, axes = plt.subplots(1, len(items), figsize=figsize)
    if len(items) == 1:
        axes = [axes]
    for ax, it in zip(axes, items):
        if isinstance(it, Image.Image):
            ax.imshow(it)
        elif isinstance(it, dict) and "bytesBase64Encoded" in it:
            try:
                ax.imshow(prediction_to_pil_image(it))
            except UnidentifiedImageError:
                ax.text(
                    0.5,
                    0.5,
                    "Image Data Error",
                    ha="center",
                    va="center",
                    color="red",
                )
        else:
            ax.text(0.5, 0.5, str(it), ha="center", va="center", wrap=True)
        ax.axis("off")
    plt.tight_layout()
    plt.show()


def display_product_images(product: str):
    """Display input and output images for a product."""
    input_uris = get_image_uris(BUCKET_NAME, f"{INPUT_PREFIX}{product}/")
    try:
        output_uri = find_output_uri(BUCKET_NAME, product)
        all_uris = input_uris + [output_uri]
    except FileNotFoundError:
        print(f"Output image not found for {product}")
        all_uris = input_uris

    local_paths = []
    for uri in all_uris:
        key = uri.replace(f"gs://{BUCKET_NAME}/", "")
        local = os.path.join(tempfile.gettempdir(), os.path.basename(key))
        storage_client.bucket(BUCKET_NAME).blob(key).download_to_filename(local)
        local_paths.append(local)

    imgs = [Image.open(p) for p in local_paths]
    fig, axes = plt.subplots(1, len(imgs), figsize=(5 * len(imgs), 5))
    if len(imgs) == 1:
        axes = [axes]
    for ax, im, uri in zip(axes, imgs, all_uris):
        ax.imshow(im)
        ax.set_title(
            "Output" if "output" in uri.lower() else "Input", fontsize=10
        )
        ax.axis("off")
    plt.tight_layout()
    plt.show()


print("Image processing helper functions loaded")


# %% [markdown] id="Hmv4TcoWNlYu"
# ## Cell 7: Image Generation Functions
#
# **Purpose:** Core functions for generating recontextualized images using AI.
#
# **What this does:**
# - `generate_recontext_image()`: Calls Gemini to create lifestyle images
# - `save_and_upload_recontext_image()`: Saves and uploads results to GCS
# - `process_single_batch_with_retry()`: Processes products with retry logic
# - Includes automatic retry on resource exhaustion errors
#
# **Features:**
# - Automatic retry on API failures
# - Resource exhaustion handling
# - Local and cloud storage of results
#
# **Action Required:** None - these functions are called by the pipeline

# %% id="ETtAnlYbNlYu"
def generate_recontext_image(
    image_parts: List[types.Part],
) -> tuple[Dict[str, str], Dict[str, str]]:
    """
    Calls the Gemini model to recontextualize the image.
    Uses configuration from Cell 2.
    """
    user_instr = types.Part.from_text(text=GENERATION_PROMPT)
    contents = [types.Content(role="user", parts=[user_instr, *image_parts])]

    config = types.GenerateContentConfig(
        temperature=GENERATION_TEMPERATURE,
        top_p=GENERATION_TOP_P,
        max_output_tokens=GENERATION_MAX_TOKENS,
        response_modalities=["IMAGE", "TEXT"],
        safety_settings=[
            types.SafetySetting(category=cat, threshold=SAFETY_THRESHOLD)
            for cat in SAFETY_CATEGORIES
        ],
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

    response = genai_client.models.generate_content(
        model=GENERATION_MODEL, contents=contents, config=config
    )

    raw_text = (
        response.text
        if response.text
        else "--- EMPTY TEXT RESPONSE (Expected for image-only output) ---"
    )
    print(f"Raw Text Response (debug): {raw_text[:200]}...")

    image_output = None
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith(
                "image/"
            ):
                image_output = {"bytesBase64Encoded": part.inline_data.data}
                break

    if image_output:
        placeholder_text = {
            "Prompt": "Image successfully generated.",
            "product_description": "Recontextualized image output.",
        }
        return placeholder_text, image_output

    raise ValueError(
        f"Model did not return a valid image. Raw text: {raw_text}"
    )


def save_and_upload_recontext_image(
    prediction_response: Dict[str, Any],
    product_folder: str,
    output_bucket_name: str,
    image_index: int = 0,
):
    """Saves the prediction locally and uploads it to GCS."""
    out_pref = f"{OUTPUT_PREFIX}{product_folder}"

    try:
        img = prediction_to_pil_image(
            prediction_response, size=OUTPUT_IMAGE_SIZE
        )
    except UnidentifiedImageError:
        print(
            f"Skipping save for {product_folder} due to UnidentifiedImageError."
        )
        return

    local = (
        f"{product_folder}_output_{image_index}.{OUTPUT_IMAGE_FORMAT.lower()}"
    )

    if OUTPUT_IMAGE_FORMAT.upper() == "JPEG":
        img.save(
            local, format=OUTPUT_IMAGE_FORMAT, quality=OUTPUT_IMAGE_QUALITY
        )
    else:
        img.save(local, format=OUTPUT_IMAGE_FORMAT)

    print(f"Saved local: {local}")

    client = storage.Client()
    bucket = client.bucket(output_bucket_name)
    dst = bucket.blob(f"{out_pref}/{local}")
    dst.upload_from_filename(
        local, content_type=f"image/{OUTPUT_IMAGE_FORMAT.lower()}"
    )
    print(f"Uploaded to gs://{output_bucket_name}/{out_pref}/{local}")


def process_single_batch_with_retry(batch, output_bucket_name):
    """Processes a single product batch with retry logic for resource exhaustion."""
    product_folder = batch["product_folder"]
    print(f"\n=== [START] Processing {product_folder} ===")

    for attempt in range(MAX_RETRIES + 1):
        try:
            print(
                f"Calling {GENERATION_MODEL} for {product_folder} (Attempt {attempt + 1}/{MAX_RETRIES + 1})..."
            )
            gen, recontext_image_data = generate_recontext_image(
                batch["image_parts"]
            )
            print(f"Prompt for {product_folder}:", gen.get("Prompt", "N/A"))

            save_and_upload_recontext_image(
                recontext_image_data,
                product_folder=product_folder,
                output_bucket_name=output_bucket_name,
            )
            print(f"[DONE] Finished {product_folder}")
            return f"Success: {product_folder}"

        except Exception as e:
            error_str = str(e).lower()
            # Check for resource exhaustion errors
            if any(
                term in error_str
                for term in [
                    "resource",
                    "exhausted",
                    "quota",
                    "rate",
                    "limit",
                    "429",
                    "503",
                ]
            ):
                if attempt < MAX_RETRIES:
                    print(
                        f"Resource exhaustion for {product_folder}. Retrying in {RETRY_DELAY} seconds..."
                    )
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    print(
                        f"[ERROR] Failed {product_folder} after {MAX_RETRIES + 1} attempts: {e}"
                    )
                    return f"Error after retries: {product_folder} - {e}"
            else:
                # Non-retryable error
                print(
                    f"[ERROR] Failed {product_folder} with non-retryable error: {e}"
                )
                return f"Error: {product_folder} - {e}"


print("Image generation functions loaded with retry logic")

# %% [markdown] id="9hXgtuV1NlYu"
# ## Cell 8: Run Image Generation Pipeline
#
# **Purpose:** Execute the main image generation pipeline.
#
# **What this does:**
# - Discovers all product folders in your GCS bucket
# - Processes multiple products in parallel
# - Generates recontextualized lifestyle images
# - Saves results to GCS with automatic retry on failures
#
# **Features:**
# - Parallel processing with configurable workers
# - Automatic retry on resource exhaustion
# - Real-time progress tracking
# - Summary of all results
#
# **Action Required:** Run this cell to start the generation process

# %% id="c0dXmgFiNlYv"
# Discover and process all product batches
print("Starting Image Generation Pipeline")
print("=" * 70)

batches = list(discover_product_batches(INPUT_GCS_URI))
print(f"\nTotal product folders discovered: {len(batches)}")

if not batches:
    raise RuntimeError(
        "No product batches found—check your GCS path & permissions!"
    )

# Process in parallel with retry logic
generation_start_time = datetime.now()
print(
    f"\nGeneration started at: {generation_start_time.strftime('%Y-%m-%d %H:%M:%S')}"
)

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    print(f"Submitting {len(batches)} batches for parallel processing")
    print(
        f"  Workers: {MAX_WORKERS} | Retry: {MAX_RETRIES} attempts | Delay: {RETRY_DELAY}s\n"
    )

    future_to_folder = {
        executor.submit(
            process_single_batch_with_retry, batch, OUTPUT_BUCKET
        ): batch["product_folder"]
        for batch in batches
    }

    results = []
    completed = 0
    for future in concurrent.futures.as_completed(future_to_folder):
        folder_name = future_to_folder[future]
        completed += 1
        try:
            result = future.result()
            results.append(result)
            print(f"[{completed}/{len(batches)}] {result}")
        except Exception as exc:
            error_result = f"Fatal exception for {folder_name}: {exc}"
            results.append(error_result)
            print(f"[{completed}/{len(batches)}] {error_result}")

generation_end_time = datetime.now()
generation_duration = generation_end_time - generation_start_time

print("\n" + "=" * 70)
print("GENERATION SUMMARY")
print("=" * 70)
print(f"All parallel tasks completed")
print(f"Total time: {generation_duration}")
print(f"Products processed: {len(results)}")

# Count successes and failures
successes = [r for r in results if r.startswith("Success")]
failures = [r for r in results if not r.startswith("Success")]

print(f"Successful: {len(successes)}")
print(f"Failed: {len(failures)}")

if failures:
    print("\nFailed products:")
    for f in failures:
        print(f"  {f}")

# %% [markdown] id="SuGLo27ANlYv"
# ## Cell 9: Evaluation Functions
#
# **Purpose:** Define functions for evaluating generated images.
#
# **What this does:**
# - Sets up evaluation prompts and scoring criteria
# - Evaluates images across 6 dimensions:
#   - Product Fidelity
#   - Scene Realism
#   - Aesthetic Quality
#   - Brand Integrity
#   - Policy Compliance
#   - Imaging Quality
# - Includes retry logic for evaluation API calls
#
# **Action Required:** None - these functions are used by the evaluation pipeline

# %% id="pCS2NrNANlYv"
# Evaluation prompt
msg1_text1 = types.Part.from_text(
    text="""You will be shown up to 4 images:
• up to 3 input product photos
• 1 AI-generated lifestyle image of the same product (filename contains "_output.jpg")

Your task is to evaluate the output image across the following 6 dimensions.
Each dimension should be scored on a scale from 1 to 5, where:
- 5 = Excellent
- 4 = Good
- 3 = Acceptable
- 2 = Poor
- 1 = Unacceptable

For each dimension, explain your score with 1–2 sentences of justification.

### Evaluation Dimensions:

1. **Product Fidelity** – Does the product in the output match the shape, color, texture, and identity seen in the input images?
2. **Scene Realism** – Does the background setting make physical and spatial sense? Are lighting and shadows natural?
3. **Aesthetic Quality** – Is the image visually appealing? Consider composition, balance, lighting, and professional polish.
4. **Brand Integrity** – Are any visible logos, labels, or branding preserved, undistorted, and realistic?
5. **Policy Compliance** – Does the image follow content policies (no people, kids, unsafe objects, political/religious content)?
6. **Imaging Quality** – Is the image sharp, high-resolution, and free from noise, blurs, or compression artifacts?

Please return the results in the following JSON format:

{
  "product_fidelity": { "score": X, "comment": "..." },
  "scene_realism":   { "score": X, "comment": "..." },
  "aesthetic_quality": { "score": X, "comment": "..." },
  "brand_integrity":   { "score": X, "comment": "..." },
  "policy_compliance": { "score": X, "comment": "..." },
  "imaging_quality":   { "score": X, "comment": "..." },
  "overall_score":     { "score": X, "comment": "..." }
}

Guidelines for overall_score:
This should reflect the lowest common denominator (e.g., an otherwise perfect image
with policy violations would get a lower overall).
Use your judgment, not just the numeric average — it's OK to weight fidelity or
compliance more heavily than, say, aesthetic.
"""
)


def strip_code_fences(text: str) -> str:
    """Remove code fences from JSON response."""
    m = re.search(r"```(?:json)?\s*\n([\s\S]*?)```", text)
    return m.group(1) if m else text


def make_part(uri: str) -> types.Part:
    """Create a Part from a GCS URI."""
    ext = os.path.splitext(uri)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return types.Part(file_data=types.FileData(file_uri=uri, mime_type=mime))


def evaluate_image_with_retry(input_uris, output_uri) -> str:
    """Generate evaluation for images with retry logic."""

    generate_config = types.GenerateContentConfig(
        temperature=EVALUATION_TEMPERATURE,
        top_p=EVALUATION_TOP_P,
        seed=EVALUATION_SEED,
        max_output_tokens=EVALUATION_MAX_TOKENS,
        system_instruction=[
            types.Part.from_text(text=EVALUATION_SYSTEM_PROMPT)
        ],
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        safety_settings=[
            types.SafetySetting(category=cat, threshold="OFF")
            for cat in SAFETY_CATEGORIES
        ],
    )

    parts = (
        [msg1_text1]
        + [make_part(u) for u in input_uris]
        + [make_part(output_uri)]
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            full = ""
            for chunk in genai_client.models.generate_content_stream(
                model=EVALUATION_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=generate_config,
            ):
                full += chunk.text
            return full

        except Exception as e:
            error_str = str(e).lower()
            if any(
                term in error_str
                for term in [
                    "resource",
                    "exhausted",
                    "quota",
                    "rate",
                    "limit",
                    "429",
                    "503",
                ]
            ):
                if attempt < MAX_RETRIES:
                    print(
                        f"    ️ Resource exhaustion during evaluation. Retrying in {RETRY_DELAY}s..."
                    )
                    time.sleep(RETRY_DELAY)
                    continue
            raise e


def evaluate_product(product: str) -> dict:
    """Evaluate a single product."""
    in_pref = f"{INPUT_PREFIX}{product}/"
    inputs = get_image_uris(BUCKET_NAME, in_pref, MAX_IMAGES_PER_PRODUCT)
    output_uri = find_output_uri(BUCKET_NAME, product)
    print(f"  • input URIs: {len(inputs)} images")
    print(f"  • output URI: Found")

    raw = evaluate_image_with_retry(inputs, output_uri)
    if not raw.strip():
        raise ValueError(f"Empty response for {product}")

    clean = strip_code_fences(raw).strip()
    try:
        return json.loads(clean)
    except JSONDecodeError:
        print(f"Raw text for {product}:\n{raw}\n")
        raise


def process_product_evaluation(p):
    """Process a single product evaluation with error handling."""
    try:
        print(f" Evaluating {p} …")
        res = evaluate_product(p)
        json_str = json.dumps(res, indent=2)

        # Save JSON to GCS
        json_path = f"{OUTPUT_PREFIX}{p}/{p}_evaluation.json"
        storage_client.bucket(BUCKET_NAME).blob(json_path).upload_from_string(
            json_str, content_type="application/json"
        )
        print(f"   Saved evaluation to GCS")
        return (p, res)
    except Exception as err:
        print(f"   Failed to evaluate {p}: {err}")
        return (p, None)


print(" Evaluation functions loaded with retry logic")

# %% [markdown] id="fQz-RqmUNlYv"
# ## Cell 10: Run Evaluation Pipeline
#
# **Purpose:** Execute the evaluation pipeline on generated images.
#
# **What this does:**
# - Finds all products with generated images
# - Evaluates each image across 6 quality dimensions
# - Saves evaluation results as JSON files in GCS
# - Processes multiple evaluations in parallel
#
# **Features:**
# -  Parallel evaluation processing
# -  Automatic retry on API failures
# -  Progress tracking with timestamps
# -  Results saved to GCS
#
# **Action Required:** Run this cell to evaluate all generated images

# %% id="4X5BOxKeNlYv"
# Run parallel evaluation
print(" Starting Evaluation Pipeline")
print("=" * 70)

eval_start_time = datetime.now()
print(
    f" Evaluation started at {eval_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
)

products = list_product_folders(BUCKET_NAME, INPUT_PREFIX)
print(f" Found {len(products)} products to evaluate")
print(
    f" Configuration: {MAX_EVAL_WORKERS} workers | Model: {EVALUATION_MODEL}\n"
)

all_results = {}

# Run evaluations in parallel with retry logic
with concurrent.futures.ThreadPoolExecutor(
    max_workers=MAX_EVAL_WORKERS
) as executor:
    print(f" Starting parallel evaluation...\n")
    future_to_product = {
        executor.submit(process_product_evaluation, p): p for p in products
    }

    completed = 0
    for future in concurrent.futures.as_completed(future_to_product):
        completed += 1
        p, result = future.result()
        status = "" if result is not None else ""
        print(f"[{completed}/{len(products)}] {status} {p}")

        if result is not None:
            all_results[p] = result

eval_end_time = datetime.now()
eval_duration = eval_end_time - eval_start_time

print("\n" + "=" * 70)
print(" EVALUATION SUMMARY")
print("=" * 70)
print(f" Evaluation completed at {eval_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f" Total time: {eval_duration}")
print(f" Successfully evaluated: {len(all_results)}/{len(products)} products")

if len(all_results) < len(products):
    failed_products = set(products) - set(all_results.keys())
    print(f"\n️ Failed evaluations: {failed_products}")

# %% [markdown] id="8oDSn5VCNlYv"
# ## Cell 11: Generate Evaluation Summary Report
#
# **Purpose:** Create comprehensive summary of evaluation results.
#
# **What this does:**
# - Compiles all evaluation scores into a DataFrame
# - Calculates statistics (average, min, max, distribution)
# - Identifies low-scoring products
# - Saves summary CSV to GCS
# - Displays detailed analytics
#
# **Output:**
# -  Overall statistics and score distribution
# -  Average scores by dimension
# - ️ List of products needing attention
# -  CSV file with all evaluation data
#
# **Action Required:** Run this cell to generate the summary report

# %% id="0AwdufLgNlYv"
# Create summary DataFrame and analytics
if all_results:
    print(" Generating Evaluation Summary Report")
    print("=" * 70)

    rows = []
    for prod, metrics in all_results.items():
        input_product_uri = f"gs://{BUCKET_NAME}/{INPUT_PREFIX}{prod}/"
        try:
            output_product_uri = find_output_uri(BUCKET_NAME, prod)
        except FileNotFoundError:
            output_product_uri = "Not Found"

        overall = metrics.get("overall_score", {}).get("score")
        comment = metrics.get("overall_score", {}).get("comment")

        if overall is None or comment is None:
            print(f"️ Warning: {prod} missing overall_score fields")
            continue

        row = {
            "product": prod,
            "input_product_uri": input_product_uri,
            "output_product_uri": output_product_uri,
            "overall_score": overall,
            "overall_comment": comment,
        }

        for dim, info in metrics.items():
            if dim == "overall_score":
                continue
            row[f"{dim}_score"] = info.get("score", 0)
            row[f"{dim}_comment"] = info.get("comment", "")
        rows.append(row)

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Save CSV to GCS
    summary_path = f"{OUTPUT_PREFIX}evaluation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    storage_client.bucket(BUCKET_NAME).blob(summary_path).upload_from_string(
        df.to_csv(index=False), content_type="text/csv"
    )
    print(f" Saved evaluation summary to: gs://{BUCKET_NAME}/{summary_path}\n")

    # Display comprehensive statistics
    print(" OVERALL STATISTICS")
    print("-" * 40)
    print(f"Total products evaluated:    {len(df)}")
    print(f"Average overall score:       {df['overall_score'].mean():.2f}/5.00")
    print(
        f"Score range:                 {df['overall_score'].min():.2f} - {df['overall_score'].max():.2f}"
    )
    print(f"Standard deviation:          {df['overall_score'].std():.2f}")
    print(f"Median score:                {df['overall_score'].median():.2f}")

    # Score distribution
    print("\n SCORE DISTRIBUTION")
    print("-" * 40)
    for score in [5, 4, 3, 2, 1]:
        count = len(
            df[
                (df["overall_score"] >= score - 0.5)
                & (df["overall_score"] < score + 0.5)
            ]
        )
        pct = (count / len(df)) * 100 if len(df) > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"Score ~{score}: {count:3d} products ({pct:5.1f}%) {bar}")

    # Display dimension averages
    print("\n AVERAGE SCORES BY DIMENSION")
    print("-" * 40)
    dimensions = [
        "product_fidelity",
        "scene_realism",
        "aesthetic_quality",
        "brand_integrity",
        "policy_compliance",
        "imaging_quality",
    ]
    dim_scores = {}
    for dim in dimensions:
        col_name = f"{dim}_score"
        if col_name in df.columns:
            avg = df[col_name].mean()
            dim_scores[dim] = avg
            dim_name = dim.replace("_", " ").title()
            bar = "▓" * int(avg * 10)
            print(f"{dim_name:20s}: {avg:.2f}/5.00 {bar}")

    # Identify best and worst dimensions
    if dim_scores:
        best_dim = max(dim_scores, key=dim_scores.get)
        worst_dim = min(dim_scores, key=dim_scores.get)
        print(
            f"\n Strongest dimension: {best_dim.replace('_', ' ').title()} ({dim_scores[best_dim]:.2f})"
        )
        print(
            f"️  Weakest dimension:  {worst_dim.replace('_', ' ').title()} ({dim_scores[worst_dim]:.2f})"
        )

    # Show products below threshold
    low_scoring = df[df["overall_score"] <= LOW_SCORE_THRESHOLD]
    if not low_scoring.empty:
        print(f"\n PRODUCTS NEEDING ATTENTION (Score ≤ {LOW_SCORE_THRESHOLD})")
        print("-" * 40)
        for _, row in low_scoring.iterrows():
            comment_preview = (
                row["overall_comment"][:60] + "..."
                if len(row["overall_comment"]) > 60
                else row["overall_comment"]
            )
            print(
                f"• {row['product']:15s} [{row['overall_score']:.1f}] - {comment_preview}"
            )
    else:
        print(f"\n All products scored above {LOW_SCORE_THRESHOLD}")

    # Top performers
    top_performers = df.nlargest(3, "overall_score")
    if not top_performers.empty:
        print("\n TOP PERFORMERS")
        print("-" * 40)
        for _, row in top_performers.iterrows():
            print(f"• {row['product']:15s} [{row['overall_score']:.1f}]")

else:
    print(" No evaluation results available to summarize.")
    print("   Please run the evaluation pipeline first.")


# %% [markdown] id="0vWv5QgiNlYv"
# ## Cell 12: Interactive Review Widget
#
# **Purpose:** Interactive tool for reviewing evaluation results.
#
# **What this does:**
# - Creates an interactive slider to browse products
# - Shows products below a configurable score threshold
# - Displays input and output images side-by-side
# - Shows detailed scores and comments for each dimension
#
# **Features:**
# - ️ Slider navigation through products
# - ️ Visual comparison of input vs output
# -  Detailed breakdown of all scores
# -  Focus on products needing improvement
#
# **Action Required:** Run this cell and use the slider to review products

# %% id="ueZmd-Y7NlYv"
def review_threshold(threshold: float = None):
    """Interactive review of products below a score threshold."""
    if threshold is None:
        threshold = REVIEW_THRESHOLD

    if "df" not in globals() or df.empty:
        print(
            " No evaluation data available. Please run the evaluation pipeline first."
        )
        return

    if "overall_score" not in df.columns:
        raise RuntimeError("DataFrame missing 'overall_score' column.")

    filtered = df[df["overall_score"] <= threshold]
    prods = filtered["product"].tolist()

    if not prods:
        print(f" Great news! No products scored ≤ {threshold}")
        print(f"\nAll {len(df)} products exceed the threshold.")

        # Show option to review all products
        print(f"\n Tip: To review all products, increase the threshold or use:")
        print(f"   review_threshold({df['overall_score'].max():.1f})")
        return

    print(f" Interactive Product Review")
    print("=" * 70)
    print(f"Found {len(prods)} products with score ≤ {threshold}")
    print(f"Use the slider below to navigate through products:\n")

    slider = widgets.IntSlider(
        min=0,
        max=len(prods) - 1,
        value=0,
        description="Product:",
        continuous_update=False,
        style={"description_width": "initial"},
    )
    out = widgets.Output()

    def on_change(change):
        with out:
            out.clear_output(wait=True)
            idx = change["new"]
            prod = prods[idx]
            row = df[df["product"] == prod].iloc[0]

            print("=" * 70)
            print(f" Product {idx+1}/{len(prods)}: {prod}")
            print("=" * 70)

            # Overall score with visual indicator
            score = row["overall_score"]
            score_bar = "█" * int(score) + "░" * (5 - int(score))
            emoji = "" if score >= 4 else "" if score >= 3 else ""
            print(f"\n{emoji} Overall Score: {score:.2f}/5.00 [{score_bar}]")
            print(f"\n Overall Assessment:")
            print(f"   {row['overall_comment']}")

            print("\n Detailed Scores:")
            print("-" * 40)

            dimensions = [
                "product_fidelity",
                "scene_realism",
                "aesthetic_quality",
                "brand_integrity",
                "policy_compliance",
                "imaging_quality",
            ]

            for dim in dimensions:
                if f"{dim}_score" in row:
                    dim_score = row[f"{dim}_score"]
                    comment = row[f"{dim}_comment"]
                    dim_name = dim.replace("_", " ").title()

                    # Visual score indicator
                    score_indicator = "●" * int(dim_score) + "○" * (
                        5 - int(dim_score)
                    )

                    print(f"\n{dim_name}: {dim_score}/5 {score_indicator}")
                    print(f"  → {comment}")

            print("\n️ Visual Comparison:")
            print("-" * 40)
            display_product_images(prod)

    slider.observe(on_change, names="value")
    display(slider, out)
    on_change({"new": 0})


# Run the interactive review
print(" Starting Interactive Review Widget\n")
review_threshold()

# %% [markdown] id="7GrOZdmlNlYv"
# ## Cell 13: Export Results Locally
#
# **Purpose:** Save evaluation results to local files for offline analysis.
#
# **What this does:**
# - Exports full evaluation data to CSV file
# - Creates summary JSON with key metrics
# - Saves files to current working directory
# - Includes timestamp for version tracking
#
# **Output Files:**
# -  `evaluation_results.csv`: Complete evaluation data
# -  `evaluation_summary.json`: Statistical summary
#
# **Action Required:** Run this cell to export results locally (optional)

# %% id="zUnac7JcNlYv"
# Optional: Export evaluation results to local files
print(" Exporting Results Locally")
print("=" * 70)

if "df" in globals() and not df.empty:
    # Export CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_csv = f"evaluation_results_{timestamp}.csv"
    df.to_csv(local_csv, index=False)
    print(f" Evaluation data exported:")
    print(f"   File: {local_csv}")
    print(f"   Records: {len(df)} products")
    print(f"   Columns: {len(df.columns)} fields\n")

    # Create and save summary JSON
    summary = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "notebook_version": "2.0",
            "project_id": PROJECT_ID,
            "bucket": BUCKET_NAME,
            "generation_model": GENERATION_MODEL,
            "evaluation_model": EVALUATION_MODEL,
        },
        "statistics": {
            "total_products": len(df),
            "average_score": float(df["overall_score"].mean()),
            "median_score": float(df["overall_score"].median()),
            "min_score": float(df["overall_score"].min()),
            "max_score": float(df["overall_score"].max()),
            "std_deviation": float(df["overall_score"].std()),
            "products_below_threshold": len(
                df[df["overall_score"] <= LOW_SCORE_THRESHOLD]
            ),
        },
        "dimension_averages": {},
        "score_distribution": {},
    }

    # Add dimension averages
    dimensions = [
        "product_fidelity",
        "scene_realism",
        "aesthetic_quality",
        "brand_integrity",
        "policy_compliance",
        "imaging_quality",
    ]
    for dim in dimensions:
        col_name = f"{dim}_score"
        if col_name in df.columns:
            summary["dimension_averages"][dim] = float(df[col_name].mean())

    # Add score distribution
    for score in [5, 4, 3, 2, 1]:
        count = len(
            df[
                (df["overall_score"] >= score - 0.5)
                & (df["overall_score"] < score + 0.5)
            ]
        )
        summary["score_distribution"][f"score_{score}"] = count

    local_json = f"evaluation_summary_{timestamp}.json"
    with open(local_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(f" Summary statistics exported:")
    print(f"   File: {local_json}")
    print(f"   Average Score: {summary['statistics']['average_score']:.2f}")
    print(
        f"   Products Below Threshold: {summary['statistics']['products_below_threshold']}"
    )

    print("\n Files saved to current directory")
    print("   Use these files for offline analysis or reporting")

else:
    print(" No evaluation data available to export.")
    print("   Please run the evaluation pipeline first.")

# %% [markdown] id="ztJRMvBdNlYv"
# ##  Pipeline Complete!
#
# ### Next Steps:
# 1. Review low-scoring products using the interactive widget
# 2. Download exported files for detailed analysis
# 3. Check GCS bucket for all generated images and evaluations
# 4. Adjust configuration parameters and re-run if needed
#
# ### Resources:
# - Generated images: `gs://{BUCKET_NAME}/{OUTPUT_PREFIX}`
# - Evaluation JSONs: `gs://{BUCKET_NAME}/{OUTPUT_PREFIX}{product}/`
# - Summary CSV: Check GCS output folder
#
# ---
# **Thank you for using the Product Image Recontextualization Pipeline!**
