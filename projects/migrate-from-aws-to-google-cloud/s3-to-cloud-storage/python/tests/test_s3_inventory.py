"""This module contains tests for the s3_inventory script."""

import unittest
from unittest.mock import patch

import pandas as pd
from s3_inventory import main


class TestS3Inventory(unittest.TestCase):
    """Tests for the S3 inventory script."""

    @patch("sys.argv", ["s3_inventory.py"])
    @patch("s3_inventory.web_fetch")
    @patch("s3_inventory.get_bucket_inventory")
    @patch("s3_inventory.get_object_inventory")
    @patch("s3_inventory.GeminiRecommender")
    def test_main_success(
        self,
        mock_gemini_recommender,
        mock_get_object_inventory,
        mock_get_bucket_inventory,
        mock_web_fetch,
    ):
        """
        Tests that the 'main' function executes successfully and generates a
        recommendation.
        """
        # Mock the return values of the inventory and summary functions
        mock_web_fetch.return_value = "test context"
        mock_get_bucket_inventory.return_value = pd.DataFrame(
            {"Bucket Name": ["test-bucket"]}
        )
        mock_get_object_inventory.return_value = pd.DataFrame(
            {"Key": ["test-object"]}
        )
        mock_gemini = mock_gemini_recommender.return_value
        mock_gemini.generate_recommendations.return_value = (
            "Test recommendations"
        )

        # Mock the built-in 'open' function to avoid file I/O
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            # Call the main function
            main()

            # Assert that the summary file was written to
            mock_file.assert_called_once_with(
                "migration_recommendations.md", "w", encoding="utf-8"
            )
            mock_file().write.assert_called_once_with("Test recommendations")

    @patch("sys.argv", ["s3_inventory.py"])
    @patch("s3_inventory.web_fetch")
    @patch("s3_inventory.get_bucket_inventory")
    def test_main_no_buckets(self, mock_get_bucket_inventory, mock_web_fetch):
        """
        Tests that the 'main' function handles the case where no buckets are
        found.
        """
        # Mock the web fetch
        mock_web_fetch.return_value = "test context"
        # Mock the bucket inventory to be empty
        mock_get_bucket_inventory.return_value = pd.DataFrame()

        # Call the main function and assert that it completes without errors
        main()


if __name__ == "__main__":
    unittest.main()
