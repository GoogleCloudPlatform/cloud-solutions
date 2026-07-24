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
"""Performs quality assurance checks on generated media using a generative model."""

import time
import datetime
from typing import List, Optional, Tuple, cast
import asyncio

from .evaluation_prompts import (
    get_image_evaluation_prompt,
    get_video_evaluation_prompt,
)

from .constants import get_required_env_var
from .utils_logging import Severity, log_message, log_function_call
from google import genai
from google.api_core import exceptions as api_exceptions
from google.genai import types

from .eval_result import EvalResult

LLM_GEMINI_MODEL_EVALUATION = get_required_env_var("LLM_GEMINI_MODEL_EVALUATION")

EVALUATION_CONCURRENCY_LIMIT = 5
# Cache semaphores per event loop to avoid "Semaphore bound to a different event loop" errors
_loop_semaphores: dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}


def get_evaluation_semaphore() -> asyncio.Semaphore:
    """Returns a semaphore bound to the current event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Fallback for non-async contexts or initialization (though unlikely for this usage)
        loop = asyncio.new_event_loop()

    if loop not in _loop_semaphores:
        _loop_semaphores[loop] = asyncio.Semaphore(EVALUATION_CONCURRENCY_LIMIT)
    return _loop_semaphores[loop]


# @log_function_call
def _get_internal_prompt(
    mime_type: str,
    evaluation_criteria: str,
    reference_image_descriptions: Optional[list[str]],
    allow_collage: bool = False,
) -> str:
    """Constructs the internal prompt for the evaluation model.

    Args:
        mime_type: The MIME type of the media being evaluated.
        evaluation_criteria: The specific criteria for evaluation.
        allow_collage: If True, allows collages and storyboards. Defaults to False.

    Returns:
        The formatted prompt string.
    """
    if mime_type == "image/png" or mime_type == "image/jpeg":
        return get_image_evaluation_prompt(
            evaluation_criteria, reference_image_descriptions, allow_collage
        )
    elif mime_type == "video/mp4":
        return get_video_evaluation_prompt(
            evaluation_criteria, reference_image_descriptions
        )
    else:
        return f"""
        You are a strict Quality Assurance specialist.
        Evaluate the following media based on this single criterion: '{evaluation_criteria}'.

        Your response must be in JSON.
        - If the media passes, respond with: {{"decision": "Pass"}}
        - If it fails, respond with: {{"decision": "Fail", "reason": "A concise explanation."}}
        """


# @log_function_call
async def evaluate_media(
    media_bytes: bytes,
    mime_type: str,
    evaluation_criteria: str,
    reference_images: Optional[List[Tuple[genai.types.Part, str]]] = None,
    allow_collage: bool = False,
) -> EvalResult:
    """Performs a quality assurance check on media bytes.

    Args:
        media_bytes: The media content as bytes.
        mime_type: The MIME type of the media.
        evaluation_criteria: The rule or question to evaluate the media against.
        allow_collage: If True, allows collages and storyboards. Defaults to False.

    Returns:
        An instance of EvalResult, or None on failure.
    """
    try:
        log_message(
            f"Evaluating media STARTING with criteria: {evaluation_criteria}. Time: {datetime.datetime.now().strftime('%H:%M:%S.%f')}",
            Severity.INFO,
        )
        async with get_evaluation_semaphore():
            images: List[genai.types.Part] = []
            descriptions: List[str] = []

            if reference_images:
                for image_part, description in reference_images:
                    images.append(image_part)
                    descriptions.append(description)

            from .gemini_utils import get_gemini_client

            client = get_gemini_client()
            internal_prompt = _get_internal_prompt(
                mime_type=mime_type,
                evaluation_criteria=evaluation_criteria,
                reference_image_descriptions=descriptions,
                allow_collage=allow_collage,
            )

            contents = [
                internal_prompt,
                types.Part.from_bytes(data=media_bytes, mime_type=mime_type),
            ]

            if images:
                contents.extend(images)

            response = await client.aio.models.generate_content(
                model=LLM_GEMINI_MODEL_EVALUATION,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EvalResult,
                ),
            )

            result = cast(EvalResult, response.parsed)
            if not result:
                message = (
                    f"Media evaluation failed. Could not parse response: {response}"
                )
                log_message(message, Severity.ERROR)
                return EvalResult(
                    decision="Fail",
                    reason=message,
                    improvement_prompt="Evaluation failed due to parsing error.",
                    subject_adherence="Fail",
                    attribute_matching="Fail",
                    spatial_accuracy="Fail",
                    style_fidelity="Fail",
                    quality_and_coherence="Fail",
                    no_storyboard="Fail",
                    consistency="Fail",
                    llm_evaluation_score=0,
                )

            if result.decision.lower() == "fail":
                log_message(
                    f"Evaluation failed reason: {result.reason}", Severity.WARNING
                )
            else:
                log_message(f"Overall succeeded reason: {result.reason}", Severity.INFO)

            return result
    except (api_exceptions.GoogleAPICallError, ValueError) as e:
        message = f"Media evaluation failed: {e}"
        log_message(message, Severity.ERROR)
        return EvalResult(
            decision="Fail",
            reason=message,
            improvement_prompt="Evaluation failed due to parsing error.",
            subject_adherence="Fail",
            attribute_matching="Fail",
            spatial_accuracy="Fail",
            style_fidelity="Fail",
            quality_and_coherence="Fail",
            no_storyboard="Fail",
            consistency="Fail",
            llm_evaluation_score=0,
        )
    finally:
        log_message(
            f"Evaluating media ENDING. Time: {datetime.datetime.now().strftime('%H:%M:%S.%f')}",
            Severity.INFO,
        )
