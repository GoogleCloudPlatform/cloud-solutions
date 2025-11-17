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

"""Module for evaluating media quality using various metrics."""

import logging
import sys
import time
from typing import Any, Dict, Optional

import prompt_optimizer_main
from absl import flags
from uvq_pytorch import inference as uvq_inference


def evaluate_video(
    prompt: str,
    video_duration: int = 5,
    video_path: str = None,
    video_bytes: Optional[bytes] = None,
    _storyboard: Optional[str] = None,
    dsg_questions: Optional[str] = None,
    common_mistake_questions: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates a video based on UVQ and VQA metrics.

    Args:
        video_path: The path to the video file.
        prompt: The prompt used to generate the video.
        storyboard: The storyboard for the video.

    Returns:
        A dictionary containing the evaluation results.
    """
    # Initialize flags if they haven't been parsed.
    if not flags.FLAGS.is_parsed():
        flags.FLAGS(sys.argv)

    # UVQ evaluation
    uvq_start_time = time.time()
    woz_uvq_results = uvq_inference.UVQInference().infer(
        video_filename=video_path, video_length=video_duration
    )
    uvq_end_time = time.time()
    logging.info(
        "UVQ evaluation took %f seconds.", uvq_end_time - uvq_start_time
    )

    # VQA evaluation
    vqa_start_time = time.time()
    woz_vqa_results = prompt_optimizer_main.runner_rate(
        video_bytes=video_bytes,
        video_mime_type="video/mp4",
        original_prompt=prompt,
        dsg_questions=dsg_questions,
        common_mistake_questions=common_mistake_questions,
    )
    vqa_end_time = time.time()
    logging.info(
        "VQA evaluation took %f seconds.", vqa_end_time - vqa_start_time
    )

    return {
        "woz-uvq": woz_uvq_results,
        "woz-vqa": woz_vqa_results,
    }
