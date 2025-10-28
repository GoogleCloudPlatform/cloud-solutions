"""This module contains tests for the utility functions."""

import os
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from botocore.exceptions import ClientError
from utils import (
    get_bucket_inventory,
    get_object_details,
    get_object_inventory,
    get_report_file_path,
)


class TestUtils(unittest.TestCase):
    """Tests for the utility functions."""

    @patch("utils.boto3.client")
    def test_get_bucket_inventory_success(self, mock_boto_client):
        """
        Tests that the 'get_bucket_inventory' function returns a DataFrame of
        S3 buckets when the AWS API call is successful.
        """
        # Mock the S3 client and its 'list_buckets' method
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {
            "Buckets": [
                {
                    "Name": "test-bucket-1",
                    "CreationDate": "2023-01-01T00:00:00Z",
                },
                {
                    "Name": "test-bucket-2",
                    "CreationDate": "2023-01-02T00:00:00Z",
                },
            ]
        }
        # Configure mocks for other S3 client methods used in the function
        mock_s3.get_bucket_location.return_value = {
            "LocationConstraint": "us-west-2"
        }
        mock_s3.get_bucket_encryption.return_value = {}
        mock_s3.get_bucket_policy.return_value = {}
        mock_s3.get_public_access_block.return_value = {}
        mock_s3.get_bucket_tagging.return_value = {}
        mock_s3.get_object_lock_configuration.return_value = {}
        mock_s3.get_bucket_request_payment.return_value = {}
        mock_s3.get_bucket_versioning.return_value = {}
        mock_s3.list_bucket_intelligent_tiering_configurations.return_value = {}
        mock_s3.get_bucket_replication.return_value = {}
        mock_s3.get_bucket_lifecycle_configuration.return_value = {}
        mock_boto_client.return_value = mock_s3

        # Call the function and assert the result
        df = get_bucket_inventory()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertEqual(df["Bucket Name"][0], "test-bucket-1")

    @patch("utils.boto3.client")
    def test_get_bucket_inventory_error(self, mock_boto_client):
        """
        Tests that 'get_bucket_inventory' returns an empty DataFrame
        when the AWS API call fails.
        """
        # Mock the S3 client to raise an error
        mock_s3 = MagicMock()
        mock_s3.list_buckets.side_effect = ClientError({}, "ListBuckets")
        mock_boto_client.return_value = mock_s3

        # Call the function and assert the result
        df = get_bucket_inventory()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    @patch("utils.boto3.client")
    def test_get_object_inventory_success(self, mock_boto_client):
        """
        Tests that 'get_object_inventory' returns a DataFrame of S3 objects
        when the AWS API call is successful.
        """
        # Mock the S3 client and its paginator
        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "test-object-1", "Size": 100},
                    {"Key": "test-object-2", "Size": 200},
                ]
            }
        ]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_boto_client.return_value = mock_s3

        # Call the function and assert the result
        df = get_object_inventory("test-bucket")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertEqual(df["Key"][0], "test-object-1")

    @patch("utils.boto3.client")
    def test_get_object_inventory_error(self, mock_boto_client):
        """
        Tests that 'get_object_inventory' returns an empty DataFrame
        when the AWS API call fails.
        """
        # Mock the S3 client to raise an error
        mock_s3 = MagicMock()
        mock_s3.get_paginator.side_effect = ClientError({}, "ListObjectsV2")
        mock_boto_client.return_value = mock_s3

        # Call the function and assert the result
        df = get_object_inventory("test-bucket")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    @patch("utils.boto3.client")
    def test_get_object_details(self, mock_boto_client):
        """
        Tests that 'get_object_details' returns a dictionary of object details
        when the AWS API call is successful.
        """
        # Mock the S3 client and its 'head_object' method
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {
            "ContentLength": 150,
            "LastModified": "2023-01-01T00:00:00Z",
            "Metadata": {},
            "StorageClass": "STANDARD",
        }
        mock_boto_client.return_value = mock_s3

        # Call the function and assert the result
        details = get_object_details(mock_s3, "test-bucket", "test-object")
        self.assertIsInstance(details, dict)
        self.assertEqual(details["Size"], 150)
        self.assertEqual(details["Storage Class"], "STANDARD")


class TestGetReportFilePath(unittest.TestCase):
    """Tests for the get_report_file_path function."""

    @patch.dict(os.environ, {"REPORT_FILE_PATH": "/tmp"})
    def test_get_report_file_path_with_env_var(self):
        """Tests that the function returns the correct path when the environment
        variable is set."""
        self.assertEqual(get_report_file_path(), "/tmp")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_report_file_path_without_env_var(self):
        """Tests returns the current working directory when the
        environment variable is not set."""
        self.assertEqual(get_report_file_path(), os.getcwd())

    @patch.dict(os.environ, {"REPORT_FILE_PATH": "/non_existent_dir"})
    @patch("utils.logging.warning")
    def test_get_report_file_path_with_invalid_dir(self, mock_logging_warning):
        """Tests that the function prints a message when the specified directory
        does not exist."""
        get_report_file_path()
        mock_logging_warning.assert_called_with(
            "The directory '%s' does not exist.", "/non_existent_dir"
        )


if __name__ == "__main__":
    unittest.main()
