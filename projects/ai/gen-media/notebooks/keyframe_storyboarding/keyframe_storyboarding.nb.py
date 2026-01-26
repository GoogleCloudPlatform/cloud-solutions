# ---
# jupyter:
#   jupytext:
#     formats: ipynb,nb.py
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: .venv
#     language: python
#     name: python3
# ---

# %% id="ijGzTHJJUCPY"
# Copyright 2025 Google LLC
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

# %% [markdown] id="VEqbX8OhE8y9"
# # Keyframe Storyboarding

# %% [markdown] id="G1KDmM_PBAXz"
# | Author |
# | --- |
# | [Tony DiGangi](https://github.com/tdigangi) |
# | [Harkanwal Bedi](hsbedi@google.com)|

# %% [markdown]
# # Overview
#
# This notebook demonstrates a **complete animation pre-production workflow** using generative AI to create keyframes (critical frames in animated sequences) for a short film. You'll learn how to transform rough black-and-white sketches into polished, production-ready visual assets.
#
# ## What You'll Learn
#
# By the end of this notebook, you'll be able to:
#
# 1. **Transform sketches into colored concept art** - Generate character designs and setting concepts from simple drawings
# 2. **Create production-quality keyframes** - Use three progressive approaches (simple → advanced) to generate final shots
# 3. **Explore cinematic variations** - Experiment with different camera angles, lighting, and compositions
# 4. **Build a scene reference library** - Generate diverse character scenarios for storytelling and visual development
#
# ## Who This Is For
#
# - **Animation Studios** exploring AI-assisted pre-production workflows
# - **Visual Development Artists** looking to accelerate concept exploration  
# - **Technical Directors** implementing AI pipelines for animation projects
# - **Researchers** studying generative AI applications in creative industries
#
# ## Prerequisites
#
# Before starting, ensure you have:
#
# ### Technical Requirements:
# - ✅ **Google Cloud Project** with Vertex AI API enabled ([Setup Guide](https://console.cloud.google.com/flows/enableapi?apiid=aiplatform.googleapis.com))
# - ✅ **Python environment** with Jupyter notebook support
#
# ### Required Files:
# You'll need these black-and-white sketch files in `./images/storyboard_sketches/`:
# - `small_large_blob_sketch.png` - Character sketch (two blob characters)
# - `setting_sketch_1.png` - Setting sketch (carnival fair)
# - `key_frame_sketch_1.png` - Keyframe composition sketch
#
# *Don't have sketch files? The notebook will guide you through the process - you can use your own sketches or follow along with the provided examples.*
#
# ## The Workflow
#
# This notebook follows a **4-section progressive workflow**:
#
# ### **Section 1: Character & Setting Development** 
# Transform rough sketches into full-color concept art
# - **Input**: Black-and-white character and setting sketches
# - **Output**: Colored reference images for characters and settings
# - **Purpose**: Establish the visual "North Star" for your project
#
# ### **Section 2: Keyframe Generation** 
# Create production-quality keyframes using three approaches:
# - **2.a Zero-Shot** - Direct generation (fast, simple scenes)
# - **2.b Scene Description** - AI-enhanced prompts (complex scenes)
# - **2.c Critique & Refinement** - Creative director feedback loop (hero shots)
# - **Purpose**: Learn when to use simple vs. sophisticated approaches
#
# ### **Section 3: Camera Angles & Lighting** 
# Explore cinematic variations of your keyframes
# - **3.a Lighting Variations** - Apply different moods (chiaroscuro, golden hour, etc.)
# - **3.b Camera Angles** - Generate 12+ perspectives (close-ups, wide shots, bird's eye, etc.)
# - **Purpose**: Create comprehensive shot lists for storyboarding
#
# ### **Section 4: Scene Variations & Character Exploration**
# Generate diverse character scenarios for visual development
# - **Output**: Scene library with characters in varied settings, activities, and moods
# - **Purpose**: Build visual reference library and explore storytelling possibilities
# - **Bonus**: CSV catalog can be used for future model training (LoRA/Dreambooth)
#
# ## Key Terminology
#
# Understanding these terms will help you navigate the notebook:
#
# - **Keyframe**: A critical frame in an animation sequence that defines the main poses, composition, and emotional beats of a scene. Keyframes serve as anchor points that animators use to create motion.
#
# - **Setting**: The physical location or environment where a scene takes place (e.g., carnival fair, diner, park). Settings provide the backdrop and spatial context for character actions.
#
# - **Scene**: A complete narrative unit combining characters, actions, and a setting. A scene tells a small part of the story and may contain multiple keyframes showing different moments.
#
# - **Visual Development (VisualDev)**: The pre-production process of establishing a project's visual style, color palette, and aesthetic direction through concept art and reference materials.
#
# ## Getting Started
#
# Ready to begin? Follow these steps:
#
# 1. **Run all setup cells** (dependencies, imports, authentication)
# 2. **Validate your file structure** (check that sketch files exist)
# 3. **Start with Section 1** (character and setting development)
# 4. **Progress sequentially** (each section builds on previous work)
#
# Let's get started! 👇

# %% [markdown]
# ## Get Started 

# %% [markdown]
# ### Install Dependancies
#
# If you are using VS Code read more on how to [Manage Jupyter Kernels in VS Code](https://code.visualstudio.com/docs/datascience/jupyter-kernel-management). You will need to ensure you have executed `pip install ipykernel` on the local terminal.

# %%
# # %pip install --upgrade --quiet google-genai google-adk ipywidgets ipython matplotlib

# %% [markdown]
# ## Imports

# %%
import asyncio
import json
import os
from io import BytesIO
from typing import Dict, List, Optional, Union

import google.auth
import ipywidgets as widgets
import matplotlib.image as img
import matplotlib.pyplot as plt
import pandas as pd
import requests
from google import genai
from google.genai.types import (
    FunctionDeclaration,
    GenerateContentConfig,
    GoogleSearch,
    HarmBlockThreshold,
    HarmCategory,
    ImageConfig,
    Part,
    SafetySetting,
    ThinkingConfig,
    Tool,
    ToolCodeExecution,
)
from IPython.display import Image, Markdown, display
from PIL import Image as PIL_Image
from pydantic import BaseModel

# %% [markdown]
# ## Project Setup & Authentication

# %% [markdown]
# ### Authenticate your notebook environment (Colab only)

# %%
import sys

if "google.colab" in sys.modules:
    from google.colab import auth

    auth.authenticate_user()
    print("Authenticated as a user from colab.")

# %% [markdown]
# ### Set Google Cloud project information
#
# To get started using Vertex AI, you must have an existing Google Cloud project and [enable the Vertex AI API](https://console.cloud.google.com/flows/enableapi?apiid=aiplatform.googleapis.com).
#
# Learn more about [setting up a project and a development environment](https://cloud.google.com/vertex-ai/docs/start/cloud-environment).

# %%
PROJECT_ID = "[your-project-id]"  # @param {type: "string", placeholder: "[your-project-id]", isTemplate: true}
if not PROJECT_ID or PROJECT_ID == "[your-project-id]":
    PROJECT_ID = str(os.environ.get("GOOGLE_CLOUD_PROJECT"))

LOCATION = (
    "global"  # @param {type: "string", placeholder: "global", isTemplate: true}
)

# %% [markdown]
# ### Create GenAI SDK Client

# %%
client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)


### Set the Model
GEMINI_PRO_MODEL_ID = "gemini-2.5-pro"
MODEL_ID = "gemini-2.5-flash-image"

# %% [markdown]
# ### Configuration Constants

# %%
# Keyframe Generation Configuration
KEYFRAME_NUM_GENERATIONS = 1
KEYFRAME_TEMPERATURE = 1.0
KEYFRAME_ASPECT_RATIO = "16:9"
IMAGE_MIME_TYPE = "image/png"

# File prefixes for different keyframe generation approaches
PREFIX_ZERO_SHOT = "keyframe_zero_shot"
PREFIX_SCENE_DESC = "keyframe_scene_desc"
PREFIX_CRITIQUE = "keyframe_critique"

# Scene Exploration Configuration
SCENE_EXPLORATION_NUM_SCENES = 5
SCENE_EXPLORATION_TEMPERATURE = 0  # Deterministic for consistent results
SCENE_EXPLORATION_ASPECT_RATIO = "16:9"
SCENE_EXPLORATION_OUTPUT_DIR = "scene_library"
SCENE_EXPLORATION_FILE_PREFIX = "scene"


# %% [markdown]
# ## Utilities & Helper Functions
#
# <small>*This section contains all helper functions. Collapse cells below to reduce clutter.*</small>

# %%
def build_scene_exploration_prompt(num_scenes: int) -> str:
    """
    Build a prompt for generating diverse scene descriptions for character exploration.

    Args:
        num_scenes: Number of scene prompts to generate

    Returns:
        Formatted prompt string for scene generation
    """
    return f"""### You are an expert in creating text-to-image prompts for character exploration and visual development. Your task is to analyze the provided reference images of a large blob and a small blob, and then generate a list of {num_scenes} diverse and detailed prompts.

The goal is to create a visual reference library that captures both the large blob and the small blob from various angles, performing different activities, and situated in a range of appropriate scenes, often interacting or co-existing. This diversity in actions, environments, and character interaction is essential for storytelling and visual development.

**Instructions:**

1.  **Analyze and Maintain Character Consistency:**
    * **large blob:** Refer to the provided images for the large blob's appearance: A larger generic blob that is inflated with air.
    * **small blob:** Refer to the provided image for the small blob's appearance: A smaller generic blob that is inflated with air.
    * **Sizing:** Ensure the relative sizing between the large blob and the small blob in the generated images remains consistent with the visual cues in the provided reference images (i.e., the small blob should be a realistic size in relation to the large blob).

2.  **Focus on Activities, Interactions, and Scenes:** Generate prompts that place both the large blob and the small blob in different, yet generic, environments and engaged in generic, characteristic behaviors, often together.
    * **Examples of scenes include:**
        * Playing games at the Fair
        * Winning a stuffed animal at a Fair game
        * Walking to the diner for a late night meal
    
    * **Examples of activities and interactions include:**
        * large blob and small blob running together (walking, running)
        * small blob holding hands with the large blob
        * large blob and small blob singing
        * large blob feeding small blob

3.  **Ensure Diversity:** The set of prompts must be highly varied. Mix up the scenes, activities, interactions, and camera angles (close-ups, medium shots, wide shots) to prevent repetition.

4.  **Maintain Realism/Quality:** Each prompt should aim for a "photorealistic," "cinematic fantasy," or "stylized render" quality, suitable for generating high-resolution, detailed images.

5.  **Output Format:** Provide the final output as a single list of text-to-image prompts. Each prompt should be a concise, descriptive phrase ready for an image generation model.
"""


def local_image_to_bytes(image_full_path: str) -> bytes:
    """
    Convert an image file from the local filesystem to bytes.

    Args:
        image_full_path: Absolute or relative path to the image file

    Returns:
        Image data as bytes

    Raises:
        FileNotFoundError: If the image file doesn't exist at the specified path
        IOError: If there's an error reading the file

    Example:
        >>> image_bytes = local_image_to_bytes("./images/character.png")
        >>> print(f"Image size: {len(image_bytes)} bytes")
    """
    if not os.path.exists(image_full_path):
        raise FileNotFoundError(
            f"Image not found at path: {image_full_path}\n"
            f"Please ensure the file exists and the path is correct."
        )

    try:
        with open(image_full_path, "rb") as f:
            image_bytes = f.read()
        return image_bytes
    except IOError as e:
        raise IOError(f"Error reading image file {image_full_path}: {e}")


def prepare_keyframe_images(
    sketch_path: str,
    character_path: str,
    setting_path: str,
    mime_type: str = IMAGE_MIME_TYPE,
) -> List[Dict[str, Union[bytes, str]]]:
    """
    Prepare a list of image dictionaries for keyframe generation.

    Args:
        sketch_path: Path to keyframe sketch image
        character_path: Path to character reference image
        setting_path: Path to setting reference image
        mime_type: MIME type for all images (default: IMAGE_MIME_TYPE constant)

    Returns:
        List of dicts with 'data' and 'mime_type' keys, ready for generate_image()
    """
    return [
        {"data": local_image_to_bytes(sketch_path), "mime_type": mime_type},
        {"data": local_image_to_bytes(character_path), "mime_type": mime_type},
        {"data": local_image_to_bytes(setting_path), "mime_type": mime_type},
    ]


def extract_json_field(
    response, field_name: str, default_value: Optional[str] = None
) -> str:
    """
    Safely extract a field from JSON response with error handling.

    Args:
        response: API response object with .text attribute
        field_name: Name of the field to extract from JSON
        default_value: Value to return if extraction fails (default: None)

    Returns:
        Extracted field value or default_value

    Raises:
        ValueError: If extraction fails and no default_value provided
    """
    try:
        parsed = json.loads(response.text)
        if field_name not in parsed:
            if default_value is not None:
                print(
                    f"⚠️  Field '{field_name}' not found in response. Using default."
                )
                return default_value
            raise ValueError(f"Field '{field_name}' not found in JSON response")
        return parsed[field_name]
    except json.JSONDecodeError as e:
        if default_value is not None:
            print(f"⚠️  JSON decode error: {e}. Using default value.")
            return default_value
        raise ValueError(f"Failed to parse JSON response: {e}")


def display_local_image(image_full_path: str, figsize: tuple = (6, 12)) -> None:
    """
    Display an image from the local filesystem using matplotlib.

    Args:
        image_full_path: Absolute or relative path to the image file
        figsize: Figure size as (width, height) in inches. Default is (6, 12)

    Returns:
        None

    Raises:
        FileNotFoundError: If the image file doesn't exist at the specified path

    Example:
        >>> display_local_image("./images/character.png")
        >>> display_local_image("./images/scene.png", figsize=(8, 10))
    """
    if not os.path.exists(image_full_path):
        raise FileNotFoundError(
            f"Image not found at path: {image_full_path}\n"
            f"Please ensure the file exists and the path is correct."
        )

    try:
        image_data = img.imread(image_full_path)
        fig, axis = plt.subplots(1, 1, figsize=figsize)
        axis.imshow(image_data)
        axis.set_title(image_full_path)
        axis.axis("off")
        plt.show()
    except Exception as e:
        print(f"Error displaying image: {e}")


async def generate_image_async(
    client,
    model_id: str,
    images: Union[Dict[str, bytes], List[Dict[str, bytes]]],
    prompt: str,
    response_modalities: Optional[List[str]] = None,
    candidate_count: int = 1,
    temperature: float = 1.0,
    aspect_ratio: str = "16:9",
) -> any:
    """
    Async version of generate_image() for parallel image generation.

    Args:
        client: The generative AI client instance
        model_id: Model identifier string (e.g., "gemini-2.5-flash-image")
        images: Either a single dict or list of dicts with 'data' and 'mime_type' keys
        prompt: Text prompt to send with images
        response_modalities: List of response types. Default is ["TEXT", "IMAGE"]
        candidate_count: Number of candidates to generate. Default is 1
        temperature: Controls randomness (0.0 to 1.0). Default is 1.0
        aspect_ratio: Image aspect ratio (e.g., "16:9"). Default is "16:9"

    Returns:
        Response object from the model containing generated content
    """
    if response_modalities is None:
        response_modalities = ["TEXT", "IMAGE"]

    # Normalize images to list format
    if isinstance(images, dict):
        images = [images]

    # Build content parts
    content_parts = []
    for image in images:
        content_parts.append(
            Part.from_bytes(
                data=image["data"],
                mime_type=image.get("mime_type", "image/png"),
            )
        )
    content_parts.append(prompt)

    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model=model_id,
            contents=content_parts,
            config=GenerateContentConfig(
                response_modalities=response_modalities,
                candidate_count=candidate_count,
                temperature=temperature,
                image_config=ImageConfig(aspect_ratio=aspect_ratio),
            ),
        ),
    )
    return response


async def generate_and_save_image_async(
    client,
    model_id: str,
    images: Union[Dict[str, bytes], List[Dict[str, bytes]]],
    prompt: str,
    save_dir: str,
    file_prefix: str,
    index: int,
    file_extension: str = "png",
    temperature: float = 1.0,
    aspect_ratio: str = "16:9",
    verbose: bool = True,
) -> Optional[str]:
    """
    Generate a single image asynchronously and save it.

    Args:
        client: Generative AI client
        model_id: Model identifier
        images: Image data
        prompt: Text prompt
        save_dir: Directory to save the image
        file_prefix: Filename prefix
        index: Index number for filename
        file_extension: File extension (default: "png")
        temperature: Randomness (default: 1.0)
        aspect_ratio: Aspect ratio (default: "16:9")
        verbose: Print progress (default: True)

    Returns:
        File path if successful, None if failed
    """
    try:
        if verbose:
            print(f"🎨 Generating {file_prefix}_{index}...")

        response = await generate_image_async(
            client=client,
            model_id=model_id,
            images=images,
            prompt=prompt,
            temperature=temperature,
            aspect_ratio=aspect_ratio,
        )

        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    filename = f"{file_prefix}_{index}.{file_extension}"
                    filepath = os.path.join(save_dir, filename)

                    # Write file in executor
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: _write_file_sync(
                            filepath, part.inline_data.data
                        ),
                    )

                    if verbose:
                        print(f"✅ Saved: {filepath}")
                    return filepath

        if verbose:
            print(f"⚠️  No image generated for {file_prefix}_{index}")
        return None

    except Exception as e:
        print(f"❌ Error generating {file_prefix}_{index}: {e}")
        return None


def _write_file_sync(filepath: str, data: bytes) -> None:
    """Helper to write file synchronously."""
    with open(filepath, "wb") as f:
        f.write(data)


async def generate_and_save_images_async(
    client,
    model_id: str,
    images: Union[Dict[str, bytes], List[Dict[str, bytes]]],
    prompts: Union[str, List[str]],
    save_dir: str,
    file_prefix: str,
    num_generations: Optional[int] = None,
    file_extension: str = "png",
    temperature: float = 1.0,
    aspect_ratio: str = "16:9",
    max_concurrent: int = 5,
) -> List[str]:
    """
    Generate multiple images in PARALLEL

    Args:
        client: Generative AI client
        model_id: Model identifier
        images: Image data (dict or list of dicts)
        prompts: Single prompt (string) OR list of prompts
                 If string: generates num_generations images with same prompt
                 If list: generates one image per prompt
        save_dir: Directory to save images
        file_prefix: Filename prefix
        num_generations: Number of images (only if prompts is string)
        file_extension: File extension (default: "png")
        temperature: Randomness (default: 1.0)
        aspect_ratio: Aspect ratio (default: "16:9")
        max_concurrent: Max concurrent API calls (default: 5)

    Returns:
        List of saved file paths

    Example (same prompt, multiple generations):
        >>> saved = await generate_and_save_images_async(
        ...     client=client,
        ...     model_id=MODEL_ID,
        ...     images=image_data,
        ...     prompts="Create a scene",
        ...     num_generations=12,
        ...     save_dir="./output",
        ...     file_prefix="scene"
        ... )

    Example (different prompts):
        >>> prompts = ["Scene 1", "Scene 2", "Scene 3"]
        >>> saved = await generate_and_save_images_async(
        ...     client=client,
        ...     model_id=MODEL_ID,
        ...     images=image_data,
        ...     prompts=prompts,
        ...     save_dir="./output",
        ...     file_prefix="scene"
        ... )
    """
    os.makedirs(save_dir, exist_ok=True)

    tasks = []

    if isinstance(prompts, str):
        # Single prompt, multiple generations
        if num_generations is None:
            num_generations = 1

        print(f"🚀 Starting PARALLEL generation of {num_generations} images...")
        print(f"⚡ Max concurrent requests: {max_concurrent}\n")

        for i in range(1, num_generations + 1):
            tasks.append(
                generate_and_save_image_async(
                    client=client,
                    model_id=model_id,
                    images=images,
                    prompt=prompts,
                    save_dir=save_dir,
                    file_prefix=file_prefix,
                    index=i,
                    file_extension=file_extension,
                    temperature=temperature,
                    aspect_ratio=aspect_ratio,
                )
            )
    else:
        # Multiple prompts
        print(f"🚀 Starting PARALLEL generation of {len(prompts)} images...")
        print(f"⚡ Max concurrent requests: {max_concurrent}\n")

        for i, prompt in enumerate(prompts, 1):
            tasks.append(
                generate_and_save_image_async(
                    client=client,
                    model_id=model_id,
                    images=images,
                    prompt=prompt,
                    save_dir=save_dir,
                    file_prefix=file_prefix,
                    index=i,
                    file_extension=file_extension,
                    temperature=temperature,
                    aspect_ratio=aspect_ratio,
                )
            )

    # Run with semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_task(task):
        async with semaphore:
            return await task

    results = await asyncio.gather(*[bounded_task(task) for task in tasks])

    # Filter out None results
    saved_paths = [path for path in results if path is not None]

    print(
        f"\n🎉 PARALLEL Complete! Generated {len(saved_paths)}/{len(tasks)} images."
    )
    return saved_paths


# %% [markdown]
# ## 1. Character and Setting Exploration from Sketch
#
# ### Overview
# This section demonstrates the foundational step in the animation pre-production workflow: transforming rough black-and-white sketches into fully-realized, colored concept art. This is a critical stage where early creative ideas evolve from simple drawings into polished visual references.
#
# ### What This Section Does
# We take two types of initial sketches:
# 1. **Character Sketches**: Simple black-and-white drawings defining character shapes, proportions, and basic features
# 2. **Setting Sketches**: Rough environment layouts showing composition and spatial relationships
#
# Using generative AI, we transform these sketches into:
# - **Full-color character designs** with proper lighting, texture, and material properties
# - **Detailed setting concepts** with atmospheric lighting and rich visual detail
#
# ### Why This Matters
# In traditional animation pipelines, this "sketch-to-concept" phase can take days or weeks as artists manually paint and refine ideas. By using AI to generate variations quickly, we can:
# - **Explore multiple design directions** in minutes rather than days
# - **Establish visual style** early in the production process  
# - **Create reference material** that guides all subsequent work (keyframes, final shots, etc.)
# - **Enable rapid iteration** on character and setting designs
#
# ### The Workflow
# 1. Load black-and-white sketches (characters and settings)
# 2. Use AI image generation to create colored, detailed variations
# 3. Review and select the best outputs as our visual "North Star"
# 4. Use these selected assets as references for all downstream experiments
#
# Think of this as creating your **visual development library** - the core assets that define what your characters and world should look like in the final production.

# %% [markdown]
# ### Load Character Sketch
#
# First, we'll load the black-and-white character sketch. This sketch shows the basic shapes and proportions of our two blob characters - a large blob and a small blob standing side-by-side.

# %%
image_path = "./images"

# %%
# Load sketch of the characters
character_large_small_sketch = os.path.join(
    f"{image_path}/storyboard_sketches/small_large_blob_sketch.png"
)
display_local_image(character_large_small_sketch)

# %% [markdown]
# ### Load Setting Sketch
#
# Next, we'll load the setting sketch showing a carnival/fair environment. This sketch defines the composition, layout of game stalls, and spatial relationships in our scene.

# %%
# Load sketch of one of the setting
setting_fair_sketch = os.path.join(
    f"{image_path}/storyboard_sketches/setting_sketch_1.png"
)
display_local_image(setting_fair_sketch)

# %% [markdown]
# ### Generate Character Variations
#
# Now we'll use Gemini's image generation capabilities to create colored, detailed variations of our character sketch.
#
# **What's happening:**
# - The AI takes the black-and-white sketch as reference
# - Generates 3 different colored variations with realistic lighting and materials
# - Each variation explores slightly different interpretations of the characters
#
# **The prompt:**
# - As the original sketch does not capture the entire details, specify details such as:
# - Color, texture, appearance
# ?- Notable characteristics
#
# **After generation:**
# - Review all 3 variations below
# - Note which one best matches your creative vision
# - You can rerun this cell to generate 3 more variations if needed
# - The selected variation will be used as reference in later experiments

# %%
prompt = """
Input Materials (Reference Only):
[SKETCH]: Black and white sketch defining the character.

**Core Task**: 
You are a visual development artist at a animation studio.Create a realistic colored photo of Two matte, light blue, 
blob-shaped characters stand side-by-side.They resemble simple inflatable toys, featuring rounded bodies, 
short limbs, and visible seams on their arms.Use a neutral background
"""

saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images={
        "data": local_image_to_bytes(character_large_small_sketch),
        "mime_type": "image/png",
    },
    prompts=prompt,
    num_generations=3,
    save_dir=os.path.join(f"{image_path}/generated/character_setting"),
    file_prefix="character",
    max_concurrent=3,  # Generate all 3 in parallel
)

print(f"Saved: {saved_files}")

# %% [markdown]
# ### Review Character Variations
#
# The cell above displays all 3 generated character variations. 
#
# **To select your preferred version:**
# 1. Examine each variation carefully
# 2. Consider: lighting quality, material appearance, character expression, overall aesthetic
# 3. Note which file name you prefer (e.g., `character_1.png`, `character_2.png`, or `character_3.png`)
# 4. You'll use this selection in the experiments below
#
# **Need more options?** Simply rerun the generation cell above to create 3 additional variations with different creative interpretations.

# %%
for file in saved_files:
    display_local_image(file)

# %% [markdown]
# ### Generate Setting Variations
#
# Now we'll generate colored, detailed variations of the carnival fair setting.
#
# **What's happening:**
# - The AI transforms the black-and-white fair sketch into a full-color setting
# - Generates 3 variations exploring different lighting and atmospheric conditions
# - Each maintains the core composition while adding rich visual detail
#
# **The prompt specifies:**
# - As the original sketch does not capture the entire details, specify details such as:
#   - Time of day and lighting conditions (e.g., afternoon sun, golden hour)
#   - Atmospheric mood and weather
#   - Color palette and visual tone
#   - Specific environmental elements and their characteristics
#   - Material properties and textures
#
# **After generation:**
# - Review all 3 setting variations
# - Compare lighting, color palette, and mood
# - Note your preferred version (e.g., `setting_1.png`, `setting_2.png`, or `setting_3.png`)
# - Rerun this cell if you want to explore different interpretations
# - Your selected setting will be paired with the character design in later experiments

# %%
prompt = """
Input Materials (Reference Only):
[SKETCH]: Black and white storyboard sketch defining a setting from a state fair

**Core Task**: 
You are a visual development artist at a animation studio.
Create a realistic colored photo at an outdoor state fair.Under the warm afternoon sun, 
a dirt path leads between two colorful carnival game stalls at the state fair. The central attraction is a 
"BULLSEYE" dart game, its sign glowing under fluorescent lights above a row of untouched dartboards. To the left, 
stacks of silver cans are neatly arranged for a toss game, while a pond of rubber ducks waits patiently on the right. 
Hundreds of plush stuffed animals hang as prizes, creating a vibrant canopy over the empty, expectant booths. 
The scene is one of quiet anticipation, a momentary lull in the fair's usual bustling energy.
"""

saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images={
        "data": local_image_to_bytes(setting_fair_sketch),
        "mime_type": "image/png",
    },
    prompts=prompt,
    num_generations=3,
    save_dir=os.path.join(f"{image_path}/generated/character_setting"),
    file_prefix="setting",
    max_concurrent=3,  # Generate all 3 in parallel
)

print(f"Saved: {saved_files}")

# %% [markdown]
# ### Review Setting Variations & Move Forward
#
# Above you can see all 3 generated setting variations displayed.
#
# **Selection Process:**
# 1. Examine each setting variation for atmosphere, lighting quality, and visual appeal
# 2. Consider which setting best supports the emotional tone of your story
# 3. Note your preferred file (e.g., `setting_1.png`, `setting_2.png`, or `setting_3.png`)
#
# **What's Next:**
# The subsequent experiments will automatically use:
# - `character_1.png` as the character reference
# - `setting_1.png` as the setting reference
#
# **To use different selections:**
# Modify the file paths in the next section below to point to your preferred variations (e.g., change `character_1.png` to `character_2.png` if you prefer that version).
#
# ---
#
# With our **visual development library** now complete (character designs + setting concepts), we're ready to move into the keyframe generation experiments where we'll combine these elements into final shots!

# %%
for file in saved_files:
    display_local_image(file)

# %% [markdown]
# ### Optional: Generate Character Expression Sheets and/or turnarounds
#
# If you need facial expression references showing emotional range for each character, you can create expression sheets here.
#
# **What expression sheets provide:**
# - Multiple views of the same character showing different emotions (happy, sad, surprised, angry, etc.)
# - Consistent character design across different emotional states
# - Reference material for animators to maintain character consistency
#
# **Note:** This is optional for this workflow. Since our blob characters have minimal facial features, expression work may be less critical. However, for characters with more complex faces, expression sheets are essential in production pipelines.
#
# ---
#

# %%
selected_character_image = os.path.join(
    f"{image_path}/generated/character_setting/character_1.png"
)
display_local_image(selected_character_image)


selected_setting_image = os.path.join(
    f"{image_path}/generated/character_setting/setting_1.png"
)
display_local_image(selected_setting_image)

# %%
expression_sheet_prompt = f"""
Facial expression sheet for Large Blob.

**Expressions to Show**: Happy, Sad, Surprised, Worried, Angry, Neutral

**Requirements**:
- Layout: 2x3 or 3x2 grid showing all 6 expressions clearly labeled
- Consistency: Use the SAME character design as the model sheet reference (exact same colors, proportions, features)
- Angle: All expressions from the same 3/4 front angle
- Lighting: Consistent, neutral lighting across all expressions
- Style: Match the animation style from the model sheet
- Background: Clean white background
- Labels: Each expression clearly labeled

The reference image shows the character's base design - maintain perfect consistency with it.
"""

saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images={
        "data": local_image_to_bytes(selected_character_image),
        "mime_type": "image/png",
    },
    prompts=expression_sheet_prompt,
    num_generations=1,
    save_dir=os.path.join(f"{image_path}/generated/character_setting"),
    file_prefix="character_expression_sheet",
)

for file in saved_files:
    display_local_image(file)

# %% [markdown]
#
# With our **visual development library** now complete (character designs + environment concepts), we're ready to move into the keyframe generation experiments where we'll combine these elements into final shots!

# %% [markdown]
# ## 2. Keyframe Generation
#
# ### Overview
# This section demonstrates three progressive approaches to generating production-quality keyframes for animation. A **keyframe** is a crucial frame in an animated sequence that defines the main poses, composition, and emotional beats of a scene.
#
# We'll explore three methods of increasing sophistication:
# 1. **Zero-shot generation** (simple, direct)
# 2. **AI-assisted scene description** (enhanced detail)
# 3. **Critique-based refinement** (highest quality)
#
# ### Understanding the Approaches
#
# **When to use each approach:**
#
# - **Zero-Shot (2.a)**: Best for simple scenes with clear composition
#   - Works well when sketch, characters, and setting are straightforward
#   - Our carnival scene is relatively simple, so this approach yields good results
#   - Fast and efficient for basic keyframes
#   
# - **Scene Description (2.b)**: Better for complex scenes needing rich detail
#   - Uses AI to analyze references and generate detailed text prompts
#   - Adds atmospheric details, lighting nuance, and emotional context
#   - Useful when you need more cinematic specificity
#   
# - **Critique & Refinement (2.c)**: Best for critical hero shots and complex compositions
#   - Simulates a creative director review process
#   - Ensures fidelity to the original sketch while enhancing artistry
#   - Essential for complex scenes with multiple characters, intricate lighting, or specific emotional requirements
#   - Takes more time but produces highest quality results
#
# ### Why Progressive Complexity Matters
#
# For **simple scenes** like our carnival keyframe:
# - Zero-shot often produces excellent results immediately
# - The additional steps may provide marginal improvements
#
# For **complex scenes** (multiple characters, dynamic action, intricate environments):
# - Zero-shot may miss important details or misinterpret composition
# - Scene description adds crucial context and specificity
# - Critique ensures accuracy and elevates artistic quality
#
# ### The Workflow
# In this section, you'll:
# 1. Load your keyframe sketch (the composition reference)
# 2. Try all three approaches with the same inputs
# 3. Compare the results to understand which approach works best for your needs
# 4. Learn when to invest in more sophisticated prompting techniques

# %% [markdown]
# ### Load Keyframe Sketch
#
# First, we'll load the black-and-white keyframe sketch that defines our desired composition - showing the two blob characters from behind, looking at carnival games.

# %%
# Load sketch of one of the Key Frame
key_frame_sketch = os.path.join(
    f"{image_path}/storyboard_sketches/key_frame_sketch_1.png"
)
display_local_image(key_frame_sketch)

# %% [markdown]
# ### Review Reference Materials
#
# Below we'll display the character and setting references we generated in Section 1. These will be provided to the AI along with the keyframe sketch to generate the final shot.

# %%
display_local_image(selected_character_image)
display_local_image(selected_setting_image)

# %% [markdown]
# ## 2.a Zero-Shot Generation Using Sketch, Character & Setting Images
#
# ### What is Zero-Shot Generation?
#
# Zero-shot generation is the simplest approach: we provide the AI with:
# - The **keyframe sketch** (composition reference)
# - The **character reference** (from Section 1)
# - The **setting reference** (from Section 1)
# - A **simple text prompt** describing the task

# %%
# Common prompt templates
ROLE_DESCRIPTION = """**Role & Goal**: 
You are a visual development artist at a animation studio. Your goal is to create one definitive,
emotionally powerful "final frame" image that will serve as the primary visual and benchmark for a blob short film."""

INPUT_MATERIALS_TEMPLATE = """**Input Materials (Reference Only)**
[SKETCH]: Black and white storyboard sketch defining the composition and character poses.
[CHARACTER_MODEL]: Full-color character model sheet for the small & blob.
[SETTING]: Full-color concept art for the background/environment."""

# %%
# Prepare images using helper function
keyframe_images = prepare_keyframe_images(
    sketch_path=key_frame_sketch,
    character_path=selected_character_image,
    setting_path=selected_setting_image,
)

# Build zero-shot prompt
zero_shot_prompt = f"""
{ROLE_DESCRIPTION}

{INPUT_MATERIALS_TEMPLATE}

**Core Task**: 
Using the provided assets as reference, create an image that describes a single,
cinematic, high-quality final frame. This frame must capture the scene's emotional weight and composition, camera angle, 
frame as depicted in the [SKETCH], while incorporating the character details from the [CHARACTER_MODEL]
and the environmental feel from the [SETTING]
"""

# Generate keyframe using zero-shot approach with ASYNC
zero_shot_saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images=keyframe_images,
    prompts=zero_shot_prompt,
    num_generations=KEYFRAME_NUM_GENERATIONS,
    save_dir=os.path.join(f"{image_path}/generated/keyframe"),
    file_prefix=PREFIX_ZERO_SHOT,
    temperature=KEYFRAME_TEMPERATURE,
    aspect_ratio=KEYFRAME_ASPECT_RATIO,
)

print(f"Saved: {zero_shot_saved_files}")

# Display generated images
for file in zero_shot_saved_files:
    display_local_image(file)

# %% [markdown]
# ## 2.b Using Gemini for Scene Description and Key Shot Generation
#
# ### What Makes This Different?
#
# This approach adds an **intermediate AI step** that acts as a "scene descriptor":
#
# **Two-Step Process:**
# 1. **First call**: Analyzes your references and generates a detailed, cinematic text-to-image prompt
# 2. **Second call**: Uses that enhanced prompt to generate the final keyframe

# %% [markdown]
# ### Scene Descriptor System Instructions

# %%
scene_descriptor_system_instructions = """
**Role & Goal** 
You are a visual development artist at a animation studio. Your goal is to create one definitive,
emotionally powerful "final frame" image that will serve as the primary visual and benchmark for a blob short film.

**Core Task**
Synthesize the provided reference materials into a single, cohesive, and highly descriptive prompt.
Your output must be a text prompt that can be used to generate a high-fidelity piece of keyframe art in the style
of a modern 3D animated feature film.

**Input Materials (Reference Only)**
[SKETCH]: Black and white storyboard sketch defining the composition and character poses.
[CHARACTER_MODEL]: Full-color character model sheet for the small & blob.
[SETTING]: Full-color concept art for the background/environment.

**Process & Constraints**
Analyze Composition from [SKETCH]: Begin by describing the shot type (e.g., "cinematic wide shot," "intimate close-up"),
camera angle, and the precise positioning of the characters within the frame. Focus exclusively on their poses
and spatial relationship as depicted in the sketch.
**Integrate Character Details from [CHARACTER_MODEL]**
Apply the visual details from the model sheets to the posed
characters. Describe the characters with emphasis on texture, material, and how they interact with the
light. Describe their facial expressions as seen in the sketch, amplified by the emotional context.

**Establish Environment and Atmosphere from [SETTING]** 
Detail the background and foreground elements. Describe the mood
(e.g., "somber," "majestic," "tense") and specify the time of day and weather conditions.
Define Lighting: This is critical. Act as a lighting artist. Describe the primary light source, its direction, quality (hard/soft),
and color. Mention how this light creates highlights, shadows, and rim lighting on the characters and the environment to enhance
the emotional impact and visual drama.

**Synthesize into a Final Prompt** 
Combine all elements into a single, eloquent, and detailed paragraph. The final output should be
only the text-to-image prompt itself, ready for an image generation model. Do not include your analysis or any conversational text.
Output Example (Stylistic Reference):
{
  "prompt": "A highly stylized digital painting featuring two amorphous blue blobs. 
            The composition is dominated by the golden hour sunset, which bleeds into a deep indigo sky, 
            casting long, exaggerated shadows across the deserted fair games. 
            The blobs are intently facing away from the fair and into the distant, 
            hazy void where the sun dips below the horizon. The atmosphere is one of nostalgic melancholy and quiet observation, 
            rendered in the art style of Syd Mead mixed with the soft lighting of a cinematic scene. 
            Dust motes hang heavy in the air, catching the last shafts of light, 
            emphasizing the finality of their shared, silent "Funday.""
}

"""

# %% [markdown]
# ### Prompt Output

# %%
print("🎯 Step 1/2: Generating enhanced scene description...")


class TextToImage(BaseModel):
    prompt: str


scene_description_response = client.models.generate_content(
    model=GEMINI_PRO_MODEL_ID,
    contents=[
        Part.from_bytes(
            data=local_image_to_bytes(key_frame_sketch),
            mime_type=IMAGE_MIME_TYPE,
        ),
        Part.from_bytes(
            data=local_image_to_bytes(selected_character_image),
            mime_type=IMAGE_MIME_TYPE,
        ),
        Part.from_bytes(
            data=local_image_to_bytes(selected_setting_image),
            mime_type=IMAGE_MIME_TYPE,
        ),
        "Output:",
    ],
    config=GenerateContentConfig(
        system_instruction=scene_descriptor_system_instructions,
        response_mime_type="application/json",
        response_schema=TextToImage,
        thinking_config=ThinkingConfig(
            include_thoughts=True,
        ),
    ),
)

print("✅ Step 1 complete: Scene description generated")
print(scene_description_response.text)

# %%
# Extract enhanced scene prompt with error handling
enhanced_scene_prompt = extract_json_field(scene_description_response, "prompt")
print(f"📝 Enhanced prompt length: {len(enhanced_scene_prompt)} characters\n")
print(enhanced_scene_prompt)

# %%
print("🎯 Step 2/2: Generating keyframe from enhanced description...")

# Build scene description prompt
scene_desc_prompt = f"""
{ROLE_DESCRIPTION}

{INPUT_MATERIALS_TEMPLATE}

{enhanced_scene_prompt}
"""

# Generate keyframe using scene description approach with ASYNC
scene_desc_saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images=keyframe_images,
    prompts=scene_desc_prompt,
    num_generations=KEYFRAME_NUM_GENERATIONS,
    save_dir=os.path.join(f"{image_path}/generated/keyframe"),
    file_prefix=PREFIX_SCENE_DESC,
    temperature=KEYFRAME_TEMPERATURE,
    aspect_ratio=KEYFRAME_ASPECT_RATIO,
)

print("✅ Step 2 complete: Keyframe generated successfully")
print(f"Saved: {scene_desc_saved_files}")

# Display generated images
for file in scene_desc_saved_files:
    display_local_image(file)

# %% [markdown]
# ## 2.c Using Gemini to Critique Text-to-Image Prompt and Key Shot Generation
#
# ### The Creative Director Feedback Loop
#
# This is the most sophisticated approach, simulating a real production workflow where a creative director reviews and refines work.
#
# **Three-Step Process:**
# 1. **Generate scene description** (from approach 2.b)
# 2. **AI critique**: Analyze the prompt against the sketch for accuracy and artistic quality
# 3. **Generate final keyframe** using the refined, critique-enhanced prompt
#
# ### Comparison Strategy
#
# After completing all three approaches (2.a, 2.b, 2.c):
# - Compare the three keyframe results side-by-side
# - Evaluate which approach gave the best results for THIS scene
# - Use that knowledge to choose the right approach for future scenes based on complexity

# %%
system_instruction_critique = """
**Role & Goal**
You are the Creative Director and lead story artist at a premier animation studio.
Your primary responsibility is to ensure absolute fidelity to the established vision while elevating the final product.
You will review a text-to-image prompt and compare it against the foundational storyboard sketch.
Your goal is to deliver a revised prompt that is both accurate to the sketch's composition and
artistically superior in its descriptive power.

**Input**
[ARTIST_PROMPT]: A text-to-image prompt generated by a senior artist (the first AI model).
[SKETCH]: Black and white storyboard sketch defining the composition and character poses.

**Other Input Materials (Reference Only)**
[CHARACTER_MODEL]: Full-color character model sheet for the small & blob.
[SETTING]: Full-color concept art for the background/environment.

**Core Task: Your task is a sequential, two-step process**
Provide a Fidelity-First Critique: First, analyze the [ARTIST_PROMPT] strictly against the [SKETCH].
Identify any discrepancies in composition, character posing, or camera angle. After confirming fidelity,
provide notes for artistic enhancement.

**Deliver a Revised, High-Fidelity Prompt**
Rewrite the prompt. Your new version must first correct any
deviations from the sketch and then incorporate your artistic notes to maximize the prompt's cinematic and emotional impact.

**Critique & Refinement Framework**
Part A: Fidelity Check (Mandatory First Step)
Your first duty is to check for discrepancies. Treat the [SKETCH] as the blueprint.
Compositional Fidelity: Does the prompt's description of the shot (e.g., "rule of thirds," character placement)
perfectly match the layout in the sketch?
Pose Accuracy: Is every limb, the tilt of the head, and the arch of the back described exactly as it is drawn?
Scrutinize hand placements, gaze direction, and body language. Note any mismatch.
Camera & Perspective: Does the prompt's description of the camera angle (low, high, eye-level) and distance (wide, medium, close-up)
 accurately reflect the perspective shown in the sketch?
Part B: Artistic Enhancement (Only after Fidelity is Confirmed/Corrected)
Once the prompt aligns with the sketch, elevate it.
Cinematic Specificity: Can you define a lens choice (e.g., "shot on a 35mm lens") that would achieve the perspective
seen in the sketch and enhance the mood?
Emotional Nuance: Use stronger, more evocative verbs and adjectives to describe the emotions and actions depicted in
the drawing.
Dynamic Lighting: Build upon the basic lighting. Introduce professional concepts like "motivated key light," "subsurface
 scattering," "volumetric fog," and "specular highlights" to create a richer visual texture.
Sensory Atmosphere: Add details that make the scene feel tangible. Mention the "biting cold," the "soundless howl," or
 the "gritty texture of the cliffside."
Output Structure:
Your final output must follow this format precisely:
Comments:
Fidelity Check: [Start with your analysis of how well the prompt matches the sketch. Example: "Pose Accuracy: High.
 The kneeling stance is correct. However, the prompt specifies the left hand on the small blob, while the sketch clearly
 shows the right hand. This is the primary correction needed."]
Artistic Notes: [Provide 2-3 bullet points for enhancement. Example: "Lighting could be more dramatic by specifying
volumetric rays cutting through the fog."]
Modified Prompt:
[Your completely rewritten, superior, and 100% sketch-accurate version of the prompt goes here as a single, detailed paragraph.]
Output Example (Stylistic Reference):
{
  "comments": ""
  "modified_prompt": ""
}

"""

# %%
print("🎯 Step 2/3: Running creative director critique...")


class TextToImageCritique(BaseModel):
    comments: list[str]
    modified_prompt: str


critique_response = client.models.generate_content(
    model=GEMINI_PRO_MODEL_ID,
    contents=[
        Part.from_bytes(
            data=local_image_to_bytes(key_frame_sketch),
            mime_type=IMAGE_MIME_TYPE,
        ),
        Part.from_bytes(
            data=local_image_to_bytes(selected_character_image),
            mime_type=IMAGE_MIME_TYPE,
        ),
        Part.from_bytes(
            data=local_image_to_bytes(selected_setting_image),
            mime_type=IMAGE_MIME_TYPE,
        ),
        f"[ARTIST_PROMPT]:{enhanced_scene_prompt}",
    ],
    config=GenerateContentConfig(
        system_instruction=system_instruction_critique,
        response_mime_type="application/json",
        response_schema=TextToImageCritique,
        thinking_config=ThinkingConfig(
            include_thoughts=True,
        ),
    ),
)

print("✅ Step 2 complete: Critique received")
print(critique_response.text)

# %%
# Extract refined prompt with error handling
refined_prompt = extract_json_field(critique_response, "modified_prompt")
critique_comments = extract_json_field(
    critique_response, "comments", default_value=[]
)

print(f"📝 Critique comments: {len(critique_comments)} items")
print(f"📝 Refined prompt length: {len(refined_prompt)} characters\n")
print(refined_prompt)

# %%
print("🎯 Step 3/3: Generating keyframe from refined prompt...")

# Build critique-refined prompt
critique_prompt = f"""
{ROLE_DESCRIPTION}

{INPUT_MATERIALS_TEMPLATE}

{refined_prompt}
"""

# Generate keyframe using critique approach with ASYNC
critique_saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images=keyframe_images,
    prompts=critique_prompt,
    num_generations=KEYFRAME_NUM_GENERATIONS,
    save_dir=os.path.join(f"{image_path}/generated/keyframe"),
    file_prefix=PREFIX_CRITIQUE,
    temperature=KEYFRAME_TEMPERATURE,
    aspect_ratio=KEYFRAME_ASPECT_RATIO,
)

print("✅ Step 3 complete: Final keyframe generated successfully")
print(f"Saved: {critique_saved_files}")

# Display generated images
for file in critique_saved_files:
    display_local_image(file)

# %% [markdown]
# ## 3. Adjusting Camera angles & framing

# %% [markdown]
# ### Overview
#
# This section demonstrates how to take a generated keyframe and explore different cinematic variations by:
# 1. **Adjusting lighting and color palette** - Apply different mood-altering lighting styles
# 2. **Exploring camera angles** - Generate the same scene from different camera perspectives
#
# This is useful for:
# - Creating shot lists and storyboards with varied compositions
# - Exploring which camera angle best serves the narrative
# - Building a visual reference library with diverse perspectives
#
# **Prerequisites:** You must have completed at least one of the keyframe generation approaches (2.a, 2.b, or 2.c) before running this section.

# %% [markdown]
# ### Select Base Keyframe
#
# Choose which keyframe generation approach you want to use as the base for camera angle exploration:
# - **Zero-shot** (2.a): Simple, direct generation
# - **Scene description** (2.b): Enhanced with AI-generated description
# - **Critique** (2.c): Refined by creative director feedback

# %%
# Select which keyframe approach to use as base
# Options: "zero_shot", "scene_desc", or "critique"
selected_keyframe_approach = (
    "zero_shot"  # Change this to your preferred approach
)

# Build the path to the selected keyframe
keyframe_mapping = {
    "zero_shot": PREFIX_ZERO_SHOT,
    "scene_desc": PREFIX_SCENE_DESC,
    "critique": PREFIX_CRITIQUE,
}

selected_keyframe_path = os.path.join(
    f"{image_path}/generated/keyframe",
    f"{keyframe_mapping[selected_keyframe_approach]}_1.png",
)

# Verify the file exists
if not os.path.exists(selected_keyframe_path):
    print(f"❌ Error: Selected keyframe not found at {selected_keyframe_path}")
    print(
        f"Please run section 2.{selected_keyframe_approach} first to generate this keyframe."
    )
else:
    print(f"✅ Selected keyframe: {selected_keyframe_path}")
    display_local_image(selected_keyframe_path)

# %% [markdown]
# ### 3.a Apply Different Lighting Styles
#
# This subsection demonstrates how to take an existing keyframe and relight it with different lighting moods.

# %%
# Define lighting style to apply
lighting_style = "chiaroscuro"
lighting_description = (
    "The scene is illuminated by strong, directional **chiaroscuro** lighting, "
    "favoring deep blues, rich violets, and stark white highlights, creating a mood of intense psychological drama."
)

# Build lighting adjustment prompt
lighting_prompt = f"""
**Role & Goal**: You are a master cinematic storyboard artist and colorist for a prestigious animation film.
Your objective is to generate a single, highly-detailed **keyframe** that defines the mood, atmosphere, and 
color design for a pivotal dramatic moment.
**Crucially, you must strictly adhere to the specific lighting conditions and color palette detailed below.**

[KEYFRAME_IMAGE]: Full-color, high-resolution keyframe image. This is your input image

[LIGHTING_AND_COLOR_PALETTE]: {lighting_description}
"""

# Generate relit keyframe with ASYNC
print(f"🎨 Applying {lighting_style} lighting to keyframe...")

relit_saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images=[
        {
            "data": local_image_to_bytes(selected_keyframe_path),
            "mime_type": IMAGE_MIME_TYPE,
        }
    ],
    prompts=lighting_prompt,
    num_generations=1,
    save_dir=os.path.join(f"{image_path}/generated/keyframe"),
    file_prefix=f"keyframe_{lighting_style}",
    temperature=KEYFRAME_TEMPERATURE,
    aspect_ratio=KEYFRAME_ASPECT_RATIO,
)

print(f"✅ Saved: {relit_saved_files}")

# Display generated images
for file in relit_saved_files:
    display_local_image(file)

# %% [markdown]
# ### 3.b Generate Camera Angle Variations
#
# This subsection generates 12 different camera angles and shot types from the same keyframe, useful for:
# - Exploring different visual storytelling approaches
# - Creating comprehensive storyboards
# - Building visual reference library with varied perspectives

# %%
# Define camera angles and shot types to explore
camera_shot_types = [
    # Shot Types (Distance)
    "Medium Close-Up (MCU)",
    "Close Up (CU)",
    "Extreme Close-Up (ECU)",
    # Camera Angles (Vertical)
    "Bird's Eye View",
    "High Angle Shot (looking down on subject)",
    "Eye-Level Angle",
    "Low Angle Shot (looking up at subject)",
    "Worm's Eye View",
    # Lens & Focus
    "Deep Focus Shot",
    "Shallow Depth of Field",
    # Composition Styles
    "Rule of Thirds Composition",
    "Centered Composition",
]

print(f"🎬 Generating {len(camera_shot_types)} camera angle variations...")
print(f"📸 Base keyframe: {selected_keyframe_path}\n")

# Prepare reference images for camera angle generation
camera_angle_images = [
    {
        "data": local_image_to_bytes(selected_keyframe_path),
        "mime_type": IMAGE_MIME_TYPE,
    },
]

# Build ALL prompts first for parallel generation
camera_angle_prompts = []
safe_shot_names = []

for shot_type in camera_shot_types:
    # Build camera angle prompt
    camera_angle_prompt = f"""
**Role & Goal**: You are a senior-level visual development artist at a premier animation studio.
Your goal is to create one definitive, highly-polished **final frame** image that serves as a visual and tonal benchmark for an animated short film.
**Crucially, you must render the scene using the precise camera angle and shot type specified below.**

[SHOT_IMAGE]: Full-color generated shot image. This is your input image

[CAMERA_ANGLE_AND_SHOT_TYPE]: {shot_type}
"""
    camera_angle_prompts.append(camera_angle_prompt)

    # Create safe filename from shot type
    safe_shot_name = (
        shot_type.lower().replace(" ", "_").replace("(", "").replace(")", "")
    )
    safe_shot_names.append(safe_shot_name)

# Generate ALL 12 camera angles in PARALLEL! 🚀
saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images=camera_angle_images,
    prompts=camera_angle_prompts,
    save_dir=os.path.join(f"{image_path}/generated/camera_angles"),
    file_prefix="camera_angle",
    temperature=KEYFRAME_TEMPERATURE,
    aspect_ratio=KEYFRAME_ASPECT_RATIO,
    max_concurrent=5,  # Generate 5 at a time to avoid overwhelming the API
)

# Build results for display
camera_angle_results = []
for shot_type, filepath in zip(camera_shot_types, saved_files):
    camera_angle_results.append({"shot_type": shot_type, "filepath": filepath})

print(
    f"\n🎉 Complete! Generated {len(camera_angle_results)} camera angle variations."
)

# %% [markdown]
# ### Review Camera Angle Variations
#
# Below are all the generated camera angles. You can review them to understand how different camera perspectives affect the storytelling and visual impact of the scene.

# %%
# Display all generated camera angle variations
print(f"Displaying {len(camera_angle_results)} camera angle variations:\n")

for result in camera_angle_results:
    print(f"📸 {result['shot_type']}")
    display_local_image(result["filepath"])
    print()  # Add spacing between images

# %% [markdown]
# ## 4. Scene Variations and Character Exploration
#
# ### Overview
#
# This section demonstrates how to explore your characters across diverse scenarios and settings. By generating multiple scene variations, you'll create a comprehensive visual reference library that showcases your characters' versatility and helps develop your story's visual language.
#
# **Scene variations explore:**
# - **Different settings** (carnival, diner, park, street, home, etc.) - varied physical locations
# - **Different activities** (playing, eating, reading, exploring, resting, etc.) - character behaviors
# - **Different moods** (playful, contemplative, dramatic, cozy, adventurous, etc.) - emotional tones
# - **Different interactions** (holding hands, playing together, sharing moments, etc.) - relationship dynamics
#
# ### Why Explore Scene Variations?
#
# After creating keyframes and exploring camera angles, generating diverse scene variations helps you:
#
# 1. **Develop your visual storytelling** - See how characters work in different contexts and discover new story moments
# 2. **Build a comprehensive reference library** - Create a visual catalog for pitches, concept presentations, and production planning
# 3. **Test character consistency** - Ensure your characters maintain their identity across varied scenarios
# 4. **Discover narrative opportunities** - Unexpected scene combinations often inspire new story directions
# 5. **Create marketing materials** - Generate diverse imagery for pitch decks, social media, and promotional content
#
# **Bonus:** The generated scene library can also be used as training data for fine-tuning custom AI models (LoRA, Dreambooth) if you decide to pursue that in the future.
#
# ### The Two-Step Process
#
# 1. **Generate Diverse Scene Prompts** - AI analyzes your character reference and creates varied scene descriptions exploring different settings, activities, and moods
# 2. **Generate Scene Images** - Each prompt becomes a visual exploration, building your reference library
#
# ### Output Format
#
# The notebook generates:
# - **Images**: Saved to `./images/generated/scenes/` - your visual reference library
# - **CSV catalog**: Organized record of all scenes
#   - Column 1: `prompt` - Description of each scene
#   - Column 2: `image_path` - Path to the image
#
# ### How to Use Your Scene Library
#
# **For Storytelling & Production:**
# - Review scenes to discover narrative moments
# - Use as reference for consistent character design
# - Share with collaborators for creative feedback
# - Include in pitch decks and presentations

# %% [markdown]
# ### Configure Scene Exploration
#
# Set the number of scene variations to generate for your character exploration library.

# %%
# Scene exploration configuration
num_scenes = (
    SCENE_EXPLORATION_NUM_SCENES  # Number of diverse scenes to generate
)
output_dir = SCENE_EXPLORATION_OUTPUT_DIR  # Directory for CSV and images

print(f"📊 Scene Exploration Configuration:")
print(f"   • Number of scenes: {num_scenes}")
print(f"   • Output directory: {output_dir}")
print(f"   • File prefix: {SCENE_EXPLORATION_FILE_PREFIX}")

# %% [markdown]
# ### Step 1: Generate Diverse Scene Prompts
#
# Using AI to analyze your character reference and create varied scene descriptions with different:
# - Settings (carnival, park, diner, etc.)
# - Activities (playing, eating, running, etc.)
# - Camera angles (wide shot, close-up, medium shot)

# %%
print("🎯 Step 1/2: Generating diverse scene prompts...")


class Scenes(BaseModel):
    scenes: list[str]


# Build the prompt using helper function
scene_exploration_prompt = build_scene_exploration_prompt(num_scenes)

# Generate scene prompts
scene_generation_response = client.models.generate_content(
    model=GEMINI_PRO_MODEL_ID,
    contents=[
        Part.from_bytes(
            data=local_image_to_bytes(selected_character_image),
            mime_type=IMAGE_MIME_TYPE,
        ),
        scene_exploration_prompt,
    ],
    config=GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=Scenes,
        thinking_config=ThinkingConfig(
            include_thoughts=True,
        ),
    ),
)

print("✅ Step 1 complete: Scene prompts generated")
print(scene_generation_response.text)

# %%
# Extract generated prompts with error handling
generated_scene_prompts = extract_json_field(
    scene_generation_response, "scenes", default_value=[]
)

print(f"📝 Generated {len(generated_scene_prompts)} scene prompts:\n")
for idx, prompt in enumerate(generated_scene_prompts, 1):
    print(f"{idx}. {prompt}\n")

# %% [markdown]
# ### Step 2: Generate Scene Images and Catalog
#
# For each prompt generated above, we'll:
# 1. Generate an image using the character reference
# 2. Save the image to disk
# 3. Record the prompt-image pair in a CSV catalog

# %%
print("🎯 Step 2/2: Generating images from prompts...\n")

# Create output directory
os.makedirs(output_dir, exist_ok=True)
scenes_dir = os.path.join(f"{image_path}/generated/scenes")

# Prepare ALL prompts with prefix for parallel generation
scene_prompts_with_prefix = [
    f"Using the provided small blob & large blob image as a reference generate image with these specs. {scene_prompt}"
    for scene_prompt in generated_scene_prompts
]

# Generate ALL scenes in PARALLEL! 🚀
saved_files = await generate_and_save_images_async(
    client=client,
    model_id=MODEL_ID,
    images=[
        {
            "data": local_image_to_bytes(selected_character_image),
            "mime_type": IMAGE_MIME_TYPE,
        }
    ],
    prompts=scene_prompts_with_prefix,
    save_dir=scenes_dir,
    file_prefix=SCENE_EXPLORATION_FILE_PREFIX,
    temperature=SCENE_EXPLORATION_TEMPERATURE,
    aspect_ratio=SCENE_EXPLORATION_ASPECT_RATIO,
    max_concurrent=5,  # Generate 5 at a time
)

# Build catalog records
scene_catalog_records = []
for scene_prompt, filepath in zip(generated_scene_prompts, saved_files):
    scene_catalog_records.append(
        {"prompt": scene_prompt, "image_path": filepath}
    )

# Save scene catalog to CSV
if scene_catalog_records:
    from datetime import datetime

    df_scene_catalog = pd.DataFrame(scene_catalog_records)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = os.path.join(output_dir, f"scene_catalog_{timestamp}.csv")
    df_scene_catalog.to_csv(csv_filename, index=False)

    print(f"\n✅ Step 2 complete!")
    print(f"📁 CSV catalog created: {csv_filename}")
    print(f"📊 Total scenes: {len(scene_catalog_records)}")
    print(f"\n📋 Preview of scene catalog:")
    display(df_scene_catalog.head())
else:
    print("\n❌ No images were generated. No CSV catalog was created.")

# %% [markdown]
# # Conclusion
#
# This notebook demonstrated a comprehensive workflow for generating keyframes for an animated short film using generative AI. We progressed through a series of experiments, starting with foundational character and setting development, then iteratively refining keyframes through multiple approaches.
#
# ## Key Takeaways:
#
# * **Iterative Refinement is Essential**: The quality of the final keyframe is significantly improved through a process of iterative refinement, incorporating feedback and exploring different creative approaches (zero-shot → scene description → critique).
#
# * **The Power of System Instructions**: Well-crafted system instructions and prompts are crucial for guiding the generative models to produce the desired output with high fidelity to your creative vision.
#
# * **Creative Collaboration with AI**: This notebook showcases a collaborative workflow where AI serves as a powerful tool for creative exploration and rapid asset generation, accelerating pre-production timelines.
#
# * **Approach Selection Matters**: Simple scenes work well with zero-shot generation, while complex compositions benefit from scene description or critique-based refinement approaches.
#
# ## Future Work:
#
# * **Fine-tune a Custom Model (Optional)**: The scene library CSV catalog from Section 4 can be used to fine-tune a model (e.g., using LoRA or Dreambooth) to create a highly specialized model for generating these blob characters with consistent style and appearance.
#
# * **Storyboarding and Animatics**: The generated keyframes can be used as a foundation for creating a full storyboard and animatic for the short film, maintaining visual consistency throughout production.
#
# * **Exploring Different Artistic Styles**: The same workflow can be applied to explore different artistic styles for the short film by modifying the prompts, reference images, and system instructions to achieve varied visual aesthetics.
#
# * **Production Pipeline Integration**: Integrate this workflow into existing animation pipelines to accelerate visual development, concept art generation, and pre-visualization phases.
