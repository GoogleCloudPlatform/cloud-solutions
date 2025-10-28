# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""AI-powered summary generation using Google Gemini."""

import json
import logging
import os

from config import GEMINI_MODEL, GEMINI_RECOMMENDATION_PROMPT, GEMINI_USER_AGENT
from google import genai
from google.genai.types import HttpOptions
from rich.console import Console
from rich.markdown import Markdown

logger = logging.getLogger(__name__)


class GeminiRecommender:
    """Generate AI-powered executive summaries using Gemini."""

    def __init__(self):
        """
        Initialize Gemini summary generator.
        """
        self.project_id = os.environ.get("GOOGLE_PROJECT_ID")
        self.region = os.environ.get("GOOGLE_REGION")
        self.external_context = os.environ.get("EXTERNAL_CONTEXT")
        if not self.project_id or not self.region:
            raise ValueError(
                "Please set the GOOGLE_PROJECT_ID and GOOGLE_REGION "
                "environment variables to generate a Gemini powered summary."
            )
        if not self.external_context:
            raise ValueError(
                "Please set the EXTERNAL_CONTEXT environment variable with "
                "the migration guide content."
            )

    def generate_recommendations(self, bucket_df, object_df):
        """
        Generate AI-powered summary.

        Args:
            bucket_df (pd.DataFrame): DataFrame of bucket inventory
            object_df (pd.DataFrame): DataFrame of object inventory

        Returns:
            str: summary text or None if generation fails
        """
        http_options = HttpOptions(headers={"user-agent": GEMINI_USER_AGENT})
        client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.region,
            http_options=http_options,
        )

        # Prepare inventory data
        inventory_data = {
            "buckets": bucket_df.to_json(orient="records"),
            "objects": object_df.to_json(orient="records"),
        }

        # Format prompt
        prompt = GEMINI_RECOMMENDATION_PROMPT.format(
            inventory_data=json.dumps(inventory_data, indent=2, default=str),
            external_context=self.external_context,
        )

        logging.info("Analyzing inventory data with Gemini AI...")

        # Generate content
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        if response and response.text:
            return response.text
        else:
            logging.error("Failed to generate recommendations")
            return None

    def print_recommendations(self, recommendations):
        """
        Print summary to console.

        Args:
            recommendations (str): recommendations text
        """
        console = Console()
        logging.info("\nRecommendations:")
        console.print(Markdown(recommendations))
