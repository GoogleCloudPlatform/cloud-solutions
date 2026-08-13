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

# pylint: skip-file
"""Module to analyze image mock."""

from typing import Any


def analyze_image(image_url: str) -> dict[str, Any]:
    """
    Analyzes an image provided via a URL and returns a description.

    Args:
        image_url (str): The URL of the image to be analyzed.

    Returns:
        dict[str, Any]: A dictionary containing the image analysis description.
              Example: {"image_analysis": "Screenshot of Xact Web Portal login page showing an error message."}
    """
    # MOCK: This is a mock implementation. In a real scenario, this would call an external
    # image analysis API (e.g., Google Cloud Vision API, AWS Rekognition).
    if "login_error" in image_url.lower():
        return {
            "image_analysis": "Screenshot of Xact Web Portal login page showing an 'Invalid Credentials' error."
        }
    elif "settlement_screen" in image_url.lower():
        return {
            "image_analysis": "Screenshot of a settlement instruction screen with a pending status."
        }
    elif "xact_dashboard" in image_url.lower():
        return {
            "image_analysis": "Screenshot of the Xact Web Portal dashboard with various widgets."
        }
    else:
        return {
            "image_analysis": "Generic image analysis: The image appears to be a screenshot related to a financial portal."
        }
