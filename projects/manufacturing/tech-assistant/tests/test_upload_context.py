# Copyright 2026 Google LLC
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

"""Unit tests for /upload-context endpoint."""

import os
import unittest
from unittest import mock

from app.main import app
from fastapi.testclient import TestClient


class UploadContextTest(unittest.TestCase):
    """Tests for /upload-context endpoint validation and functionality."""

    def setUp(self):
        """Set up test client and environment."""
        self.client = TestClient(app)
        self.server_path = "gs://test-bucket/test-prefix"
        self.env_patcher = mock.patch.dict(
            os.environ, {"GCS_STORAGE": self.server_path}
        )
        self.env_patcher.start()

    def tearDown(self):
        """Clean up environment patches."""
        self.env_patcher.stop()

    def test_upload_context_success(self):
        """Verify upload succeeds when destination matches GCS_STORAGE."""
        mock_client = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_prompt_blob = mock.MagicMock()
        mock_file_blob = mock.MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.side_effect = lambda name: (
            mock_prompt_blob
            if name == "test-prefix/prompt.txt"
            else mock_file_blob
        )

        with mock.patch("app.main.storage.Client", return_value=mock_client):
            response = self.client.post(
                "/upload-context",
                data={
                    "prompt": "Test instruction prompt",
                    "gcs_path": self.server_path,
                },
                files=[
                    (
                        "files",
                        (
                            "manual.pdf",
                            b"%PDF-1.4 test content",
                            "application/pdf",
                        ),
                    ),
                    (
                        "files",
                        ("notes.txt", b"Notes text content", "text/plain"),
                    ),
                    (
                        "files",
                        ("guide.md", b"# Markdown content", "text/markdown"),
                    ),
                ],
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Context saved to GCS")

        mock_client.bucket.assert_called_once_with("test-bucket")
        mock_prompt_blob.upload_from_string.assert_called_once_with(
            "Test instruction prompt"
        )
        self.assertEqual(mock_file_blob.upload_from_string.call_count, 3)

    def test_upload_context_mismatched_bucket_rejected(self):
        """Verify rejection when client submits unauthorized bucket."""
        with mock.patch("app.main.storage.Client") as mock_storage_cls:
            response = self.client.post(
                "/upload-context",
                data={
                    "prompt": "Test prompt",
                    "gcs_path": "gs://attacker-bucket/test-prefix",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("Upload destination must match", data["message"])
        mock_storage_cls.assert_not_called()

    def test_upload_context_mismatched_prefix_rejected(self):
        """Verify rejection when client submits a different path/prefix."""
        with mock.patch("app.main.storage.Client") as mock_storage_cls:
            response = self.client.post(
                "/upload-context",
                data={
                    "prompt": "Test prompt",
                    "gcs_path": "gs://test-bucket/other-prefix",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("Upload destination must match", data["message"])
        mock_storage_cls.assert_not_called()

    def test_upload_context_unconfigured_storage_rejected(self):
        """Verify rejection when server GCS_STORAGE is unset."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("app.main.storage.Client") as mock_storage_cls:
                response = self.client.post(
                    "/upload-context",
                    data={
                        "prompt": "Test prompt",
                        "gcs_path": "gs://any-bucket/prefix",
                    },
                )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn(
            "GCS storage is not configured on the server", data["message"]
        )
        mock_storage_cls.assert_not_called()

    def test_upload_context_disallowed_file_extension(self):
        """Verify rejection of files outside ALLOWED_EXTENSIONS."""
        with mock.patch("app.main.storage.Client") as mock_storage_cls:
            response = self.client.post(
                "/upload-context",
                data={
                    "prompt": "Test prompt",
                    "gcs_path": self.server_path,
                },
                files=[
                    (
                        "files",
                        (
                            "script.sh",
                            b"#!/bin/bash\necho test",
                            "application/x-sh",
                        ),
                    ),
                ],
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("unsupported extension '.sh'", data["message"])
        mock_storage_cls.assert_not_called()

    def test_upload_context_oversized_file(self):
        """Verify rejection of files exceeding MAX_FILE_SIZE_MB."""
        with mock.patch("app.main.MAX_FILE_SIZE_BYTES", 1024):  # 1 KB limit
            with mock.patch("app.main.storage.Client") as mock_storage_cls:
                response = self.client.post(
                    "/upload-context",
                    data={
                        "prompt": "Test prompt",
                        "gcs_path": self.server_path,
                    },
                    files=[
                        (
                            "files",
                            ("large.pdf", b"X" * 2048, "application/pdf"),
                        ),
                    ],
                )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("exceeds maximum allowed size", data["message"])
        mock_storage_cls.assert_not_called()

    def test_upload_context_oversized_prompt(self):
        """Verify rejection of prompts exceeding MAX_PROMPT_SIZE_BYTES."""
        with mock.patch("app.main.MAX_PROMPT_SIZE_BYTES", 50):  # 50 bytes limit
            with mock.patch("app.main.storage.Client") as mock_storage_cls:
                response = self.client.post(
                    "/upload-context",
                    data={
                        "prompt": "A" * 100,
                        "gcs_path": self.server_path,
                    },
                )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn(
            "Prompt payload exceeds maximum allowed size", data["message"]
        )
        mock_storage_cls.assert_not_called()

    def test_upload_context_pre_upload_validation_aborts_all_writes(self):
        """Verify pre-upload validation failure aborts all GCS writes."""
        with mock.patch("app.main.storage.Client") as mock_storage_cls:
            response = self.client.post(
                "/upload-context",
                data={
                    "prompt": "Test prompt",
                    "gcs_path": self.server_path,
                },
                files=[
                    (
                        "files",
                        ("valid.pdf", b"%PDF content", "application/pdf"),
                    ),
                    (
                        "files",
                        (
                            "malicious.exe",
                            b"binary content",
                            "application/x-msdownload",
                        ),
                    ),
                ],
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("unsupported extension '.exe'", data["message"])
        mock_storage_cls.assert_not_called()

    def test_upload_context_sanitizes_filename(self):
        """Verify filename traversal sequences are sanitized with basename."""
        mock_client = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_blob = mock.MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        created_blob_names = []

        def fake_blob(name):
            created_blob_names.append(name)
            return mock_blob

        mock_bucket.blob.side_effect = fake_blob

        with mock.patch("app.main.storage.Client", return_value=mock_client):
            response = self.client.post(
                "/upload-context",
                data={
                    "prompt": "Test prompt",
                    "gcs_path": self.server_path,
                },
                files=[
                    (
                        "files",
                        ("../../traversal.txt", b"Safe content", "text/plain"),
                    ),
                ],
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertIn("test-prefix/traversal.txt", created_blob_names)
        self.assertFalse(any(".." in name for name in created_blob_names))


if __name__ == "__main__":
    unittest.main()
