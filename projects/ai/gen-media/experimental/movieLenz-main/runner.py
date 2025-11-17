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


"""Runner module for video evaluation and processing."""

import logging
import os
import tempfile

import evaluate_media
import prompt_optimizer_main


def run_evaluate_media_for_video_path(
    video_query: str,
    video_path: str = None,
    video_bytes: bytes = None,
    input_image_path: str = None,
    input_image_bytes: bytes = None,
    duration: int = 8,
    dsg_questions: str = None,
    common_mistake_questions: str = None,
):
    """
    Evaluates a video based on a video query and either a video path or
    video bytes.

    Args:
        video_query: The query for the video.
        video_path: The path to the video file.
        video_bytes: The video content in bytes.
        input_image_path: The path to the input image file.
        input_image_bytes: The input image content in bytes.
        duration: The duration of the video.
        dsg_questions: DSG questions for VQA evaluation.
        common_mistake_questions: Common mistake questions for VQA evaluation.

    Returns:
        A dictionary containing the evaluation results.
    """
    temp_video_path = None
    temp_image_path = None
    try:
        if video_path:
            with open(video_path, "rb") as f:
                video_bytes = f.read()
        elif video_bytes:
            with tempfile.NamedTemporaryFile(
                suffix=".mp4", delete=False
            ) as temp_video:
                temp_video.write(video_bytes)
                video_path = temp_video.name
                temp_video_path = video_path
                logging.info(
                    "Video bytes written to temporary file: %s", video_path
                )
        else:
            raise ValueError(
                "Either video_path or video_bytes must be provided."
            )

        if input_image_path:
            with open(input_image_path, "rb") as f:
                input_image_bytes = f.read()
        elif input_image_bytes:
            with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False
            ) as temp_image:
                temp_image.write(input_image_bytes)
                input_image_path = temp_image.name
                temp_image_path = input_image_path
                logging.info(
                    "Image bytes written to temporary file: %s",
                    input_image_path,
                )
        else:
            raise ValueError(
                "Either input_image_path or input_image_bytes must be provided."
            )

        if dsg_questions is None:
            optimized_results = prompt_optimizer_main.get_dsg_cmq_questions(
                initial_prompt=video_query,
                start_bytes=input_image_bytes,
                video_duration=duration,
            )
            dsg_questions = optimized_results["dsg"]
            common_mistake_questions = optimized_results["cmq"]

        return evaluate_media.evaluate_video(
            prompt=video_query,
            video_duration=duration,
            video_path=video_path,
            video_bytes=video_bytes,
            dsg_questions=dsg_questions,
            common_mistake_questions=common_mistake_questions,
        )
    finally:
        if temp_video_path:
            os.remove(temp_video_path)
            logging.info("Removed temporary video file: %s", temp_video_path)
        if temp_image_path:
            os.remove(temp_image_path)
            logging.info("Removed temporary image file: %s", temp_image_path)


if __name__ == "__main__":
    # Example usage:
    # Create dummy files for testing
    # with open("dummy_video.mp4", "wb") as f:
    #     f.write(b"dummy video content")
    # with open("dummy_image.png", "wb") as f:
    #     f.write(b"dummy image content")

    results = run_evaluate_media_for_video_path(
        video_query="An old man frustrated about cleaning lawn",
        video_path="test.mp4",
        input_image_path="oldman_image.png",
        duration=5,
    )
    print(results)

    # # Clean up dummy files
    # os.remove("dummy_video.mp4")
    # os.remove("dummy_image.png")
