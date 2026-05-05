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

# pylint: disable=C0114, C0301

import os

from google.genai import types as genai_types
from google.genai.types import HarmBlockThreshold, HarmCategory

BQ_DATASET: str = os.getenv("BQ_DATASET", "retail_analytics")

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "your-project-id")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("GOOGLE_CLOUD_REGION", "global"))
GEMINI_MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.1-pro-preview")
IMAGE_MODEL_NAME = os.getenv("IMAGE_MODEL_NAME", "gemini-3-pro-image-preview")

STANDARD_GENERATION_CONFIG = {
    "response_mime_type": "application/json",
    "temperature": 0.2,
}

PROTOTYPE_SAFETY_SETTINGS: list = [
    genai_types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=HarmBlockThreshold.OFF,
    ),
    genai_types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=HarmBlockThreshold.OFF,
    ),
    genai_types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=HarmBlockThreshold.OFF,
    ),
    genai_types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=HarmBlockThreshold.OFF,
    ),
]
