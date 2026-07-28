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

def test():
    client = genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT", "PROJECT_ID"), location="us-central1")
    try:
        response = client.models.generate_content(
            model="gemini-omni-flash-preview",
            contents="Create a 1 second black video.",
            config=types.GenerateContentConfig(
                response_modalities=["VIDEO"]
            )
        )
        print("Success!")
        for part in response.parts:
            if part.inline_data:
                print(f"Got video! Size: {len(part.inline_data.data)} bytes")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
