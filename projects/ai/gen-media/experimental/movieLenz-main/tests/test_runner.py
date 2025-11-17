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

"""Tests for runner module functionality.

This module contains test cases for the run_evaluate_media_for_video_path
function and integration tests for the runner module.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, mock_open, patch

import runner

# Add parent directory to path to import runner
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

# Mock the dependencies before importing runner
sys.modules["evaluate_media"] = MagicMock()
sys.modules["prompt_optimizer_main"] = MagicMock()
sys.modules["uvq_pytorch"] = MagicMock()
sys.modules["uvq_pytorch.inference"] = MagicMock()
sys.modules["uvq_pytorch.utils"] = MagicMock()
sys.modules["uvq_pytorch.utils.aggregationnet"] = MagicMock()
sys.modules["uvq_pytorch.utils.compressionnet"] = MagicMock()
sys.modules["uvq_pytorch.utils.contentnet"] = MagicMock()
sys.modules["uvq_pytorch.utils.distortionnet"] = MagicMock()
sys.modules["torch"] = MagicMock()


class TestRunEvaluateMediaForVideoPath(unittest.TestCase):
    """Test suite for run_evaluate_media_for_video_path function."""

    def setUp(self):
        """Set up test fixtures."""
        self.video_query = "Test video query"
        self.video_path = "/path/to/video.mp4"
        self.input_image_path = "/path/to/image.png"
        self.video_bytes = b"fake video content"
        self.input_image_bytes = b"fake image content"
        self.duration = 8
        self.dsg_questions = "DSG question 1, DSG question 2"
        self.common_mistake_questions = "CMQ question 1, CMQ question 2"

    @patch("runner.evaluate_media.evaluate_video")
    @patch("runner.os.remove")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake content")
    def test_with_video_path_and_image_path(
        self, _mock_file, mock_remove, mock_evaluate
    ):
        """Test with video_path and input_image_path provided."""
        mock_evaluate.return_value = {"result": "success"}

        result = runner.run_evaluate_media_for_video_path(
            video_query=self.video_query,
            video_path=self.video_path,
            input_image_path=self.input_image_path,
            duration=self.duration,
            dsg_questions=self.dsg_questions,
            common_mistake_questions=self.common_mistake_questions,
        )

        self.assertEqual(result, {"result": "success"})
        mock_evaluate.assert_called_once()
        # No temporary files should be removed
        mock_remove.assert_not_called()

    @patch("runner.evaluate_media.evaluate_video")
    @patch("runner.prompt_optimizer_main.get_dsg_cmq_questions")
    @patch("runner.os.remove")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake content")
    def test_with_none_dsg_questions(
        self, _mock_file, _mock_remove, mock_optimizer, mock_evaluate
    ):
        """Test that DSG and CMQ questions are generated when not provided."""
        mock_optimizer.return_value = {
            "dsg": "Generated DSG questions",
            "cmq": "Generated CMQ questions",
        }
        mock_evaluate.return_value = {"result": "success"}

        result = runner.run_evaluate_media_for_video_path(
            video_query=self.video_query,
            video_path=self.video_path,
            input_image_path=self.input_image_path,
            duration=self.duration,
        )

        mock_optimizer.assert_called_once_with(
            initial_prompt=self.video_query,
            start_bytes=b"fake content",
            video_duration=self.duration,
        )
        self.assertEqual(result, {"result": "success"})

    @patch("runner.evaluate_media.evaluate_video")
    @patch("runner.os.remove")
    @patch("runner.tempfile.NamedTemporaryFile")
    @patch(
        "builtins.open", new_callable=mock_open, read_data=b"fake image content"
    )
    def test_with_video_bytes(
        self, _mock_file, mock_tempfile, mock_remove, mock_evaluate
    ):
        """Test with video_bytes instead of video_path."""
        # Mock temporary file
        temp_video = MagicMock()
        temp_video.name = "/tmp/temp_video.mp4"
        temp_video.__enter__ = MagicMock(return_value=temp_video)
        temp_video.__exit__ = MagicMock(return_value=False)

        mock_tempfile.return_value = temp_video
        mock_evaluate.return_value = {"result": "success"}

        result = runner.run_evaluate_media_for_video_path(
            video_query=self.video_query,
            video_bytes=self.video_bytes,
            input_image_path=self.input_image_path,
            duration=self.duration,
            dsg_questions=self.dsg_questions,
            common_mistake_questions=self.common_mistake_questions,
        )

        temp_video.write.assert_called_once_with(self.video_bytes)
        self.assertEqual(result, {"result": "success"})
        # Temporary video file should be removed
        mock_remove.assert_called_once_with("/tmp/temp_video.mp4")

    @patch("runner.evaluate_media.evaluate_video")
    @patch("runner.os.remove")
    @patch("runner.tempfile.NamedTemporaryFile")
    @patch(
        "builtins.open", new_callable=mock_open, read_data=b"fake video content"
    )
    def test_with_image_bytes(
        self, _mock_file, mock_tempfile, mock_remove, mock_evaluate
    ):
        """Test with input_image_bytes instead of input_image_path."""
        # Mock temporary file
        temp_image = MagicMock()
        temp_image.name = "/tmp/temp_image.png"
        temp_image.__enter__ = MagicMock(return_value=temp_image)
        temp_image.__exit__ = MagicMock(return_value=False)

        mock_tempfile.return_value = temp_image
        mock_evaluate.return_value = {"result": "success"}

        result = runner.run_evaluate_media_for_video_path(
            video_query=self.video_query,
            video_path=self.video_path,
            input_image_bytes=self.input_image_bytes,
            duration=self.duration,
            dsg_questions=self.dsg_questions,
            common_mistake_questions=self.common_mistake_questions,
        )

        temp_image.write.assert_called_once_with(self.input_image_bytes)
        self.assertEqual(result, {"result": "success"})
        # Temporary image file should be removed
        mock_remove.assert_called_once_with("/tmp/temp_image.png")

    @patch("runner.evaluate_media.evaluate_video")
    @patch("runner.os.remove")
    @patch("runner.tempfile.NamedTemporaryFile")
    def test_with_both_bytes(self, mock_tempfile, mock_remove, mock_evaluate):
        """Test with both video_bytes and input_image_bytes."""
        # Mock temporary files
        temp_video = MagicMock()
        temp_video.name = "/tmp/temp_video.mp4"
        temp_video.__enter__ = MagicMock(return_value=temp_video)
        temp_video.__exit__ = MagicMock(return_value=False)

        temp_image = MagicMock()
        temp_image.name = "/tmp/temp_image.png"
        temp_image.__enter__ = MagicMock(return_value=temp_image)
        temp_image.__exit__ = MagicMock(return_value=False)

        mock_tempfile.side_effect = [temp_video, temp_image]
        mock_evaluate.return_value = {"result": "success"}

        result = runner.run_evaluate_media_for_video_path(
            video_query=self.video_query,
            video_bytes=self.video_bytes,
            input_image_bytes=self.input_image_bytes,
            duration=self.duration,
            dsg_questions=self.dsg_questions,
            common_mistake_questions=self.common_mistake_questions,
        )

        temp_video.write.assert_called_once_with(self.video_bytes)
        temp_image.write.assert_called_once_with(self.input_image_bytes)
        self.assertEqual(result, {"result": "success"})
        # Both temporary files should be removed
        self.assertEqual(mock_remove.call_count, 2)
        mock_remove.assert_any_call("/tmp/temp_video.mp4")
        mock_remove.assert_any_call("/tmp/temp_image.png")

    def test_no_video_provided(self):
        """Test ValueError raised when neither video_path nor video_bytes
        is provided."""
        with self.assertRaises(ValueError) as context:
            runner.run_evaluate_media_for_video_path(
                video_query=self.video_query,
                input_image_path=self.input_image_path,
                duration=self.duration,
            )
        self.assertIn(
            "Either video_path or video_bytes must be provided",
            str(context.exception),
        )

    @patch(
        "builtins.open", new_callable=mock_open, read_data=b"fake video content"
    )
    def test_no_image_provided(self, _mock_file):
        """Test ValueError raised when neither input_image_path nor
        input_image_bytes is provided."""
        with self.assertRaises(ValueError) as context:
            runner.run_evaluate_media_for_video_path(
                video_query=self.video_query,
                video_path=self.video_path,
                duration=self.duration,
            )
        self.assertIn(
            "Either input_image_path or input_image_bytes must be provided",
            str(context.exception),
        )

    @patch("runner.evaluate_media.evaluate_video")
    @patch("runner.os.remove")
    @patch("runner.tempfile.NamedTemporaryFile")
    def test_cleanup_on_exception(
        self, mock_tempfile, mock_remove, mock_evaluate
    ):
        """Test that temporary files are cleaned up even when an exception
        occurs."""
        # Mock temporary files
        temp_video = MagicMock()
        temp_video.name = "/tmp/temp_video.mp4"
        temp_video.__enter__ = MagicMock(return_value=temp_video)
        temp_video.__exit__ = MagicMock(return_value=False)

        temp_image = MagicMock()
        temp_image.name = "/tmp/temp_image.png"
        temp_image.__enter__ = MagicMock(return_value=temp_image)
        temp_image.__exit__ = MagicMock(return_value=False)

        mock_tempfile.side_effect = [temp_video, temp_image]
        # Make evaluate_video raise an exception
        mock_evaluate.side_effect = Exception("Evaluation failed")

        with self.assertRaises(Exception):
            runner.run_evaluate_media_for_video_path(
                video_query=self.video_query,
                video_bytes=self.video_bytes,
                input_image_bytes=self.input_image_bytes,
                duration=self.duration,
                dsg_questions=self.dsg_questions,
                common_mistake_questions=self.common_mistake_questions,
            )

        # Temporary files should still be removed
        self.assertEqual(mock_remove.call_count, 2)
        mock_remove.assert_any_call("/tmp/temp_video.mp4")
        mock_remove.assert_any_call("/tmp/temp_image.png")

    @patch("runner.evaluate_media.evaluate_video")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake content")
    def test_default_duration(self, _mock_file, mock_evaluate):
        """Test that default duration is used when not specified."""
        mock_evaluate.return_value = {"result": "success"}

        runner.run_evaluate_media_for_video_path(
            video_query=self.video_query,
            video_path=self.video_path,
            input_image_path=self.input_image_path,
            dsg_questions=self.dsg_questions,
            common_mistake_questions=self.common_mistake_questions,
        )

        # Check that evaluate_video was called with default duration of 8
        call_args = mock_evaluate.call_args
        self.assertEqual(call_args.kwargs["video_duration"], 8)


class TestRunnerIntegration(unittest.TestCase):
    """Integration tests for runner module."""

    @patch("runner.evaluate_media.evaluate_video")
    @patch("runner.prompt_optimizer_main.get_dsg_cmq_questions")
    def test_full_workflow_with_optimization(
        self, mock_optimizer, mock_evaluate
    ):
        """Test the full workflow including prompt optimization."""
        mock_optimizer.return_value = {
            "dsg": "Optimized DSG",
            "cmq": "Optimized CMQ",
        }
        mock_evaluate.return_value = {"score": 0.95, "details": "Great video"}

        # Create temporary test files
        with tempfile.NamedTemporaryFile(
            suffix=".mp4", delete=False
        ) as video_file:
            video_file.write(b"test video content")
            temp_video_path = video_file.name

        with tempfile.NamedTemporaryFile(
            suffix=".png", delete=False
        ) as image_file:
            image_file.write(b"test image content")
            temp_image_path = image_file.name

        try:
            result = runner.run_evaluate_media_for_video_path(
                video_query="Test query",
                video_path=temp_video_path,
                input_image_path=temp_image_path,
                duration=10,
            )

            self.assertEqual(result, {"score": 0.95, "details": "Great video"})
            mock_optimizer.assert_called_once()
            mock_evaluate.assert_called_once()
        finally:
            # Clean up
            os.remove(temp_video_path)
            os.remove(temp_image_path)


if __name__ == "__main__":
    unittest.main()
