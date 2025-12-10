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

# pylint: disable=C0114, C0301

import os
import time

import google.auth
from google.adk.agents import Agent
from google.adk.apps.app import App
from google.adk.tools import ToolContext
from google.genai import types
from google.genai.client import Client

# Set up Google Cloud project and location
_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

# Initialize the GenAI client for the image generation tool
client = Client()

# =========================================
# SPECIALIZED TOOLS
# =========================================

async def generate_image(prompt: str, tool_context: ToolContext) -> str:
    """Generates an image based on the prompt using Gemini image generation.

    Args:
        prompt: A detailed text description of the image to generate. Be specific about
                style, composition, colors, mood, and any other visual details.
        tool_context: The tool context for saving artifacts.

    Returns:
        A confirmation message that the image was generated and saved.
    """
    print(f"[Tool Log] Generating image for prompt: {prompt}")
    # Generate image using Gemini 3 Pro Image model
    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[prompt],
    )

    image_bytes = None
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_bytes = part.inline_data.data
                break

    if not image_bytes:
        return "I'm sorry, I couldn't generate an image for that prompt."

    filename = f"generated_image_{int(time.time() * 1000)}.png"

    await tool_context.save_artifact(
        filename,
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
    )

    return f"Image generated successfully and saved as '{filename}'."

# =========================================
# AGENT DEFINITION
# =========================================

# --- Creative Assistant Agent ---
root_agent = Agent(
    name="creative_assistant",
    model="gemini-3-pro-preview",
    instruction="""
    You are a friendly and helpful creative assistant. You can have natural conversations
    with users and help them generate images of any kind.

    When users want to create images, use the `generate_image` tool. You can generate:
    - Artwork and illustrations (any style: realistic, cartoon, abstract, etc.)
    - Photos and realistic scenes
    - Logos and graphics
    - Infographics and diagrams
    - Character designs
    - Landscapes and environments
    - Product mockups
    - And much more!

    When generating images, craft detailed prompts that include:
    - Subject and composition
    - Style (e.g., photorealistic, watercolor, digital art, oil painting)
    - Mood and lighting
    - Colors and visual details
    - Any specific artistic references if relevant

    Be conversational and helpful. Ask clarifying questions if the user's request is vague.
    After generating an image, offer to make adjustments or create variations if they'd like.
    """,
    tools=[generate_image],
)

app = App(root_agent=root_agent, name="app")
