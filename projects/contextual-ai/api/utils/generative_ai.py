"""Utility functions for interacting with Google Generative AI."""

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

from google import genai
from google.genai import types


def ask_gemini(
    query: str,
    system: str,
    project_id: str,
    region: str = "global",
    model: str = "gemini-2.0-flash-001",
) -> str:
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=region,
    )

    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=query)])
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=1,
        seed=0,
        max_output_tokens=8192,
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
            ),
        ],
        system_instruction=[types.Part.from_text(text=system)],
    )
    resp = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        resp = resp + chunk.text
    return resp
