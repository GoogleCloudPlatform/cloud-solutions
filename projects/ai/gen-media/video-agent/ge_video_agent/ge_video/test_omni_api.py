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
from dotenv import load_dotenv

load_dotenv()

def test_omni():
    client = genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT", "PROJECT_ID"), location="us-central1")
    model = "gemini-omni-flash-preview"

    # Try generate_content
    try:
        print("Trying models.generate_content...")
        response = client.models.generate_content(
            model=model,
            contents="Hello, generate a 1 second black video.",
        )
        print("generate_content success!")
    except Exception as e:
        print(f"generate_content error: {e}")

    # Try interactions.create
    try:
        print("\nTrying interactions.create...")
        interaction = client.interactions.create(
            model=model,
            input=[{"type": "text", "text": "Hello, generate a 1 second black video."}]
        )
        print("interactions.create success!")
    except Exception as e:
        print(f"interactions.create error: {e}")

if __name__ == "__main__":
    test_omni()
