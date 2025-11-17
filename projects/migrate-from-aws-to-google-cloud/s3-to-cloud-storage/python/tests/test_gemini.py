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
"""This module contains tests for the GeminiRecommender class."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from gemini import GeminiRecommender


class TestGemini(unittest.TestCase):
    """Tests for the GeminiRecommender class."""

    @patch.dict(
        "os.environ",
        {
            "GOOGLE_PROJECT_ID": "test-project",
            "GOOGLE_REGION": "test-region",
            "EXTERNAL_CONTEXT": "test-context",
        },
    )
    @patch("gemini.genai.Client")
    def test_generate_recommendations_success(self, mock_genai_client):
        """
        Tests that 'generate_recommendations' returns a recommendations string
        when the Gemini API call is successful.
        """
        # Mock the Gemini client and its 'generate_content' method
        mock_gemini = MagicMock()
        mock_gemini.models.generate_content.return_value.text = (
            "Test recommendations"
        )
        mock_genai_client.return_value = mock_gemini

        # Create dummy DataFrames for testing
        bucket_df = pd.DataFrame({"Bucket Name": ["test-bucket"]})
        object_df = pd.DataFrame({"Key": ["test-object"]})

        # Call the function and assert the result
        gemini = GeminiRecommender()
        recommendations = gemini.generate_recommendations(bucket_df, object_df)
        self.assertEqual(recommendations, "Test recommendations")

    @patch.dict(
        "os.environ",
        {
            "GOOGLE_PROJECT_ID": "test-project",
            "GOOGLE_REGION": "test-region",
            "EXTERNAL_CONTEXT": "test-context",
        },
    )
    @patch("gemini.genai.Client")
    def test_generate_recommendations_failure(self, mock_genai_client):
        """
        Tests that 'generate_recommendations' returns None
        when the Gemini API call fails.
        """
        # Mock the Gemini client to return a failed response
        mock_gemini = MagicMock()
        mock_gemini.models.generate_content.return_value = None
        mock_genai_client.return_value = mock_gemini

        # Create dummy DataFrames for testing
        bucket_df = pd.DataFrame({"Bucket Name": ["test-bucket"]})
        object_df = pd.DataFrame({"Key": ["test-object"]})

        # Call the function and assert the result
        gemini = GeminiRecommender()
        recommendations = gemini.generate_recommendations(bucket_df, object_df)
        self.assertIsNone(recommendations)


if __name__ == "__main__":
    unittest.main()
