# Copyright 2026 Google LLC
# Author: Layolin Jesudhass
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

import os
from google import genai
from google.genai import types

client = genai.Client(
    vertexai=True,
    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "cloud-gtm"),
    location="global",
)

with open("ge_video/prompt.md", "r") as f:
    sys_prompt = f.read()

contents = [
    types.Content(role="user", parts=[types.Part.from_text(text="Here are my images. (Uploaded 4 images)")]),
    types.Content(role="model", parts=[types.Part.from_text(text="I've saved all 4 uploaded images and assigned them to your scenes! They are looking great.\nI'll now generate AI voiceover scripts using Gemini. If you'd prefer to provide your own scripts instead, just type them in this format:\n`1- Your script for scene 1, 2- ...`\nOtherwise, just say \"ai\" and I'll generate them using AI with Google Search.")]),
    types.Content(role="user", parts=[types.Part.from_text(text="ai")])
]

# Provide dummy tools
config = types.GenerateContentConfig(
    system_instruction=sys_prompt,
    temperature=0.0,
    tools=[types.Tool(function_declarations=[
        types.FunctionDeclaration(name="generate_ai_scripts", description="Generate AI scripts"),
        types.FunctionDeclaration(name="show_default_logo", description="Show default logo"),
        types.FunctionDeclaration(name="store_scene_script", description="Store a script")
    ])]
)

try:
    response = client.models.generate_content(
        model="gemini-3.1-pro-preview",
        contents=contents,
        config=config,
    )
    print("RESPONSE:")
    print("TEXT:", repr(response.text))
    if response.function_calls:
        for fc in response.function_calls:
            print(f"Function call: {fc.name}")
except Exception as e:
    print(f"Error: {e}")
