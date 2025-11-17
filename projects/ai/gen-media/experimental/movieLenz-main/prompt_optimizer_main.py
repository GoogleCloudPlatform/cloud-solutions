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

"""Main module for prompt optimization with video rating functionality."""

import logging  # Import logging
import time
from collections.abc import Sequence

# Import necessary classes
import llm_interaction_vertex
import prompt_optimizer
from absl import app, flags

DEFAULT_VERTEX_AI_SCOPES = "https://www.googleapis.com/auth/cloud-platform"

_PROJECT = flags.DEFINE_string(
    "project", None, "The project to use for the Vertex AI API."
)
_LOCATION = flags.DEFINE_string(
    "location", "global", "The location to use for the Vertex AI API."
)
_START_FRAME = flags.DEFINE_string(
    "start_frame", None, "Path to the optional start frame image."
)
_END_FRAME = flags.DEFINE_string(
    "end_frame", None, "Path to the optional end frame image."
)
_PROMPT = flags.DEFINE_string("prompt", None, "The initial prompt to optimize.")
# Add flags for duration and technical notes used by PromptOptimizer
_VIDEO_DURATION = flags.DEFINE_integer(
    "video_duration", None, "Optional target duration of the video in seconds."
)
_TECHNICAL_NOTES = flags.DEFINE_string(
    "technical_notes",
    None,
    "Optional technical notes or creative brief for optimization context.",
)
_VIDEO_PATH = flags.DEFINE_string(
    "video_path", None, "Path to the video to be evaluated."
)
_MODE = flags.DEFINE_string(
    "mode",
    None,
    'The mode of the "optimization" or "create" prompts.',
)

_ROBOT_ACCOUNT_EMAIL = flags.DEFINE_string(
    "robot_account_email",
    None,
    "The email address of the robot service account to use for Vertex AI API"
    " calls. If not provided, Application Default Credentials (ADC) will be"
    " used.",
)
_ROBOT_SCOPES = flags.DEFINE_list(
    "robot_scopes",
    DEFAULT_VERTEX_AI_SCOPES,
    "Comma-separated list of OAuth scopes to request for the robot account.",
)

# Remove unused flags
# _CREATIVE_BRIEF = flags.DEFINE_string(...)
# _NUM_PROMPTS = flags.DEFINE_integer(...)


def runner_single_run(
    initial_prompt: str,
    start_frame_path: str | None = None,
    end_frame_path: str | None = None,
    video_duration: int | None = None,
    technical_notes: str | None = None,
) -> str:
    """Optimizes a prompt using PromptOptimizer.

    Args:
        initial_prompt: The initial text prompt to optimize.
        start_frame_path: Optional path to the start frame image.
        end_frame_path: Optional path to the end frame image.
        video_duration: Optional target duration in seconds.
        technical_notes: Optional technical notes.

    Returns:
        The optimized prompt string.
    """
    start_bytes = None
    end_bytes = None

    # Read frame bytes if paths are provided
    try:
        if start_frame_path:
            logging.info("Reading start frame from: %s", start_frame_path)
            with open(start_frame_path, "rb") as f:
                start_bytes = f.read()
        if end_frame_path:
            logging.info("Reading end frame from: %s", end_frame_path)
            with open(end_frame_path, "rb") as f:
                end_bytes = f.read()
    except IOError as e:
        logging.exception("Error reading frame file: %s", e)
        raise  # Re-raise the exception

    # Initialize GeminiCaller and PromptOptimizer
    gemini_client = llm_interaction_vertex.GeminiVertexCaller(
        project=_PROJECT.value,
        location=_LOCATION.value,
    )
    optimizer = prompt_optimizer.PromptOptimizer(gemini_client)
    # Call the optimizer
    optimized_prompt = optimizer.optimize_prompt(
        initial_prompt=initial_prompt,
        start_frame_bytes=start_bytes,
        end_frame_bytes=end_bytes,
        video_duration=video_duration,
        technical_notes=technical_notes,
    )
    print("----DSG Questions----")
    print(optimizer.dsg_questions)
    print("----Common Mistake Questions----")
    print(optimizer.common_mistake_questions)

    return optimized_prompt


def runner_optimization(
    initial_prompt: str,
    start_frame_path: str | None = None,
    end_frame_path: str | None = None,
    video_duration: int | None = None,
    technical_notes: str | None = None,
    video_path: str | None = None,
) -> str:
    """Optimizes a prompt using PromptOptimizer.

    Args:
        initial_prompt: The initial text prompt to optimize.
        start_frame_path: Optional path to the start frame image.
        end_frame_path: Optional path to the end frame image.
        video_duration: Optional target duration in seconds.
        technical_notes: Optional technical notes.
        video_path:  video to be evaluated.

    Returns:
        The optimized prompt string.
    """
    start_bytes = None
    end_bytes = None
    video_bytes = None
    # Read frame bytes if paths are provided
    try:
        if start_frame_path:
            logging.info("Reading start frame from: %s", start_frame_path)
            with open(start_frame_path, "rb") as f:
                start_bytes = f.read()
        if end_frame_path:
            logging.info("Reading end frame from: %s", end_frame_path)
            with open(end_frame_path, "rb") as f:
                end_bytes = f.read()
        if video_path:
            logging.info("Reading video from: %s", video_path)
            with open(video_path, "rb") as f:
                video_bytes = f.read()
    except IOError as e:
        logging.exception("Error reading frame file: %s", e)
        raise  # Re-raise the exception

    # Initialize GeminiCaller and PromptOptimizer
    gemini_client = llm_interaction_vertex.GeminiVertexCaller(
        project=_PROJECT.value,
        location=_LOCATION.value,
    )
    optimizer = prompt_optimizer.PromptOptimizer(gemini_client)
    # Call the optimizer
    optimized_prompt_first_run = optimizer.optimize_prompt(
        initial_prompt=initial_prompt,
        start_frame_bytes=start_bytes,
        end_frame_bytes=end_bytes,
        video_duration=video_duration,
        technical_notes=technical_notes,
    )
    print("--- Optimized Prompt ---")
    print(optimized_prompt_first_run)
    print("------------------------")
    print("--- DSG Questions ---")
    print(optimizer.dsg_questions)
    print("------------------------")
    print("--- Common Mistake Questions ---")
    print(optimizer.common_mistake_questions)
    print("------------------------")
    optimized_prompt_from_video, evaluation_score, feedback_text = (
        optimizer.rate_and_refine_prompt(
            video_bytes=video_bytes,
            video_mime_type="video/mp4",
            original_prompt=optimized_prompt_first_run,
            dsg_questions=optimizer.dsg_questions,
            common_mistake_questions=optimizer.common_mistake_questions,
        )
    )
    return (
        f"Refined Prompt:\n{optimized_prompt_from_video}\n\n"
        f"Evaluation Score: {evaluation_score:.2f}\n\n"
        f"Feedback:\n{feedback_text}"
    )


def get_dsg_cmq_questions(
    initial_prompt: str,
    start_bytes: bytes | None = None,
    start_frame_path: str | None = None,
    end_frame_path: str | None = None,
    end_bytes: bytes | None = None,
    video_duration: int | None = None,
    technical_notes: str | None = None,
    project: str | None = None,
    location: str | None = None,
) -> dict:
    """Optimizes a prompt using PromptOptimizer.

    Args:
        initial_prompt: The initial text prompt to optimize.
        start_frame_path: Optional path to the start frame image.
        end_frame_path: Optional path to the end frame image.
        video_duration: Optional target duration in seconds.
        technical_notes: Optional technical notes.

    Returns:
        The optimized prompt string.
    """
    #   start_bytes = None
    #   end_bytes = None

    # Read frame bytes if paths are provided
    try:
        if start_frame_path:
            logging.info("Reading start frame from: %s", start_frame_path)
            with open(start_frame_path, "rb") as f:
                start_bytes = f.read()
        if end_frame_path:
            logging.info("Reading end frame from: %s", end_frame_path)
            with open(end_frame_path, "rb") as f:
                end_bytes = f.read()
    except IOError as e:
        logging.exception("Error reading frame file: %s", e)
        raise  # Re-raise the exception

    # Initialize GeminiCaller and PromptOptimizer
    if not flags.FLAGS.is_parsed():
        flags.FLAGS.mark_as_parsed()
    gemini_client = llm_interaction_vertex.GeminiVertexCaller(
        project=project or _PROJECT.value,
        location=location or _LOCATION.value,
    )
    optimizer = prompt_optimizer.PromptOptimizer(gemini_client)
    # Call the optimizer
    dsg_cmq_start_time = time.time()
    optimized_prompt = optimizer.optimize_prompt(
        initial_prompt=initial_prompt,
        start_frame_bytes=start_bytes,
        end_frame_bytes=end_bytes,
        video_duration=video_duration,
        technical_notes=technical_notes,
    )
    dsg_cmq_end_time = time.time()
    logging.info(
        "DSG and CMQ question generation took %f seconds.",
        dsg_cmq_end_time - dsg_cmq_start_time,
    )
    print("----DSG Questions----")
    print(optimizer.dsg_questions)
    print("----Common Mistake Questions----")
    print(optimizer.common_mistake_questions)

    return {
        "dsg": optimizer.dsg_questions,
        "cmq": optimizer.common_mistake_questions,
        "optimized_prompt": optimized_prompt,
    }


def runner_rate(
    video_bytes: bytes | None = None,
    video_mime_type: str = "video/mp4",
    original_prompt: str = "",
    dsg_questions: str = "",
    common_mistake_questions: str = "",
    project: str | None = None,
    location: str | None = None,
) -> str:
    """Optimizes a prompt using PromptOptimizer.

    Args:
        initial_prompt: The initial text prompt to optimize.
        start_frame_path: Optional path to the start frame image.
        end_frame_path: Optional path to the end frame image.
        video_duration: Optional target duration in seconds.
        technical_notes: Optional technical notes.
        video_path:  video to be evaluated.

    Returns:
          The evaluation score, feedback text, and parsed feedback.
    """

    # Initialize GeminiCaller and PromptOptimizer
    gemini_client = llm_interaction_vertex.GeminiVertexCaller(
        project=project or _PROJECT.value,
        location=location or _LOCATION.value,
    )
    optimizer = prompt_optimizer.PromptOptimizer(gemini_client)
    # Call the optimizer

    optimized_prompt_from_video, evaluation_score, feedback_text = (
        optimizer.rate_and_refine_prompt(
            video_bytes=video_bytes,
            video_mime_type=video_mime_type,
            original_prompt=original_prompt,
            dsg_questions=dsg_questions,
            common_mistake_questions=common_mistake_questions,
        )
    )
    return {
        "Refined Prompt": optimized_prompt_from_video,
        "Evaluation Score": evaluation_score,
        "Feedback": feedback_text,
    }


def main(argv: Sequence[str]) -> None:
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments.")

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Get required flags
    initial_prompt = _PROMPT.value
    if not initial_prompt:
        raise app.UsageError("Flag --prompt is required.")

    # Get optional flags
    start_frame = _START_FRAME.value
    end_frame = _END_FRAME.value
    video_duration = _VIDEO_DURATION.value
    technical_notes = _TECHNICAL_NOTES.value
    video_path = _VIDEO_PATH.value

    try:
        if _MODE.value == "create":
            result = runner_single_run(
                initial_prompt=initial_prompt,
                start_frame_path=start_frame,
                end_frame_path=end_frame,
                video_duration=video_duration,
                technical_notes=technical_notes,
            )
            print("--- Optimized Prompt ---")
            print(result)
            print("------------------------")
        elif _MODE.value == "optimization":
            result = runner_optimization(
                initial_prompt=initial_prompt,
                start_frame_path=start_frame,
                end_frame_path=end_frame,
                video_duration=video_duration,
                technical_notes=technical_notes,
                video_path=video_path,
            )
            print("--- Optimized Prompt from video evaluation ---")
            print(result)
            print("------------------------")
    except IOError:
        # Error already logged in runner
        print("Exiting due to error reading frame files.")
    except (ValueError, RuntimeError) as e:
        logging.exception(
            "An unexpected error occurred during optimization: %s", e
        )
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    app.run(main)
