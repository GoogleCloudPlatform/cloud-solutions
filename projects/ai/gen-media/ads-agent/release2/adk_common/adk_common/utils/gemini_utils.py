# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# pylint: disable=C0301, C0303, C0412, W0611, W0718, W1405
"""Utility functions for interacting with the Gemini API."""

import asyncio
import datetime
import mimetypes
import random
import time
from typing import Any, Dict, List, Optional, cast

from adk_common.utils.constants import get_required_env_var
from adk_common.utils.eval_result import EvalResult
from adk_common.utils.evaluate_media import evaluate_media
from adk_common.utils.utils_logging import (
    Severity,
    log_function_call,
    log_message,
)
from google import auth, genai
from google.api_core import exceptions as api_exceptions
from google.auth import exceptions as auth_exceptions
from google.genai import types
from google.genai.types import HarmBlockThreshold, HarmCategory
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

IMAGE_MIME_TYPE = "image/png"


def get_image_generation_tenacity_attempts() -> int:
    return int(get_required_env_var("IMAGE_GENERATION_TENACITY_ATTEMPTS"))


def get_image_generation_eval_reattempts() -> int:
    return int(get_required_env_var("IMAGE_GENERATION_EVAL_REATTEMPTS"))


def get_image_generation_concurrency_limit() -> int:
    return int(get_required_env_var("IMAGE_GENERATION_CONCURRENCY_LIMIT"))


def get_image_generation_retry_delay_seconds() -> int:
    return int(get_required_env_var("IMAGE_GENERATION_RETRY_DELAY_SECONDS"))


def get_storyboard_generation_model() -> str:
    return get_required_env_var("STORYBOARD_GENERATION_MODEL")


def get_google_cloud_project() -> str:
    return get_required_env_var("GOOGLE_CLOUD_PROJECT")


def get_models_cloud_location() -> str:
    return get_required_env_var("MODELS_CLOUD_LOCATION")


def get_google_genai_use_vertexai() -> bool:
    return bool(get_required_env_var("GOOGLE_GENAI_USE_VERTEXAI"))


def get_image_default_aspect_ratio() -> str:
    return get_required_env_var("IMAGE_DEFAULT_ASPECT_RATIO")


def get_gemini_client() -> genai.Client:
    """Initializes and returns a Gemini client.

    Returns:
        A genai.Client instance or None if initialization fails.
    """
    # We do not cache the client globally because it binds to the current event loop.
    # In environments like Reasoning Engine where loops might be recreated or distinct per request,
    # reusing a client created in a different loop causes "Future attached to a different loop" errors.
    try:
        return genai.Client(
            vertexai=get_google_genai_use_vertexai(),
            project=get_google_cloud_project(),
            location=get_models_cloud_location(),
        )
    except (auth_exceptions.DefaultCredentialsError, ValueError) as e:
        log_message(
            f"ERROR: Failed to initialize Gemini client: {e}", Severity.ERROR
        )
        raise e


SAFETY_SETTINGS = [
    types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=HarmBlockThreshold.OFF,
    ),
    types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=HarmBlockThreshold.OFF,
    ),
    types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=HarmBlockThreshold.OFF,
    ),
    types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=HarmBlockThreshold.OFF,
    ),
]

GENERATE_CONTENT_CONFIG = types.GenerateContentConfig(
    safety_settings=SAFETY_SETTINGS,
    image_config=types.ImageConfig(
        aspect_ratio=get_image_default_aspect_ratio(),
    ),
)


# @log_function_call
async def generate_and_select_best_image(
    prompt: str,
    input_images: List[types.Part],
    filename_without_extension: str,
    allow_collage: bool = False,
) -> Dict[str, Any]:
    """Generates a single image using Gemini, handling retries for errors or low evaluation scores.

    Args:
        prompt (str): The prompt for image generation.
        input_images (List[types.Part]): A list of input images as Part objects.
        filename_without_extension (str): The filename for the output image, without extension.
        allow_collage (bool): If True, allows collages and storyboards. Defaults to False.

    Returns:
        Dict[str, Any]: A dictionary containing the result of the image generation.
            - "status" (str): "success" if the image was generated successfully.
            - "detail" (str): A message describing the result.
            - "file_name" (str): The filename of the generated image.
            - "image_bytes" (bytes): The binary content of the generated image.
            - "mime_type" (str): The MIME type of the generated image.
            Returns an empty dictionary if generation fails.
    """
    if not input_images:
        raise RuntimeError("Input image(s) are required for image generation.")

    # Create a semaphore for this specific generation task to limit concurrency
    # within this event loop context.
    image_semaphore = asyncio.Semaphore(
        get_image_generation_concurrency_limit()
    )

    contents = [prompt, *input_images]
    overall_best_attempt = None
    overall_best_attempt_evaluation = None
    for i in range(get_image_generation_eval_reattempts() + 1):
        log_message(
            f"Generating image attempt {i + 1} of {get_image_generation_eval_reattempts()+1} eval attempts",
            Severity.INFO,
        )
        if i > 0:
            log_message(
                f"Waiting for {get_image_generation_retry_delay_seconds()} seconds before retry...",
                Severity.INFO,
            )
            await asyncio.sleep(get_image_generation_retry_delay_seconds())

        tasks = [
            _call_gemini_image_api(
                client=get_gemini_client(),
                model=get_storyboard_generation_model(),
                contents=contents,
                image_prompt=prompt,
                mime_type=IMAGE_MIME_TYPE,
                should_evaluate=get_image_generation_eval_reattempts() > 0,
                allow_collage=allow_collage,
                semaphore=image_semaphore,
            )
        ]
        results = await asyncio.gather(*tasks)
        successful_attempts = [res for res in results if res]

        if not successful_attempts:
            log_message(
                f"All image generation attempts failed for prompt: '{prompt}'.",
                Severity.ERROR,
            )
            continue

        current_best_attempt = max(
            successful_attempts,
            key=lambda x: int(
                cast(EvalResult, x.get("evaluation")).averaged_evaluation_score
                if x.get("evaluation")
                else -1
            ),
        )

        if not current_best_attempt:
            log_message(
                f"All image generation attempts failed for prompt: '{prompt}'.",
                Severity.ERROR,
            )
            continue

        current_best_attempt_evaluation = cast(
            EvalResult, current_best_attempt["evaluation"]
        )

        if (
            not overall_best_attempt
            or not overall_best_attempt_evaluation
            or current_best_attempt_evaluation.averaged_evaluation_score
            > overall_best_attempt_evaluation.averaged_evaluation_score
        ):
            overall_best_attempt = current_best_attempt
            overall_best_attempt_evaluation = current_best_attempt_evaluation

        # if the best overall did not pass (whether it be this last run or a previous one, append the improvement prompt from the last evaluation).
        if (
            overall_best_attempt_evaluation
            and overall_best_attempt_evaluation.decision.lower() != "pass"
        ):
            improvement_prompt = f"An image was already generated and the evaluator deemed it did not pass quality and suggested the following to improve the image: {current_best_attempt_evaluation.improvement_prompt}"
            contents.append(improvement_prompt)

            log_message(
                f"No image passed evaluation. Best Averaged Score: {overall_best_attempt_evaluation.averaged_evaluation_score}. LLM Score: {overall_best_attempt_evaluation.llm_evaluation_score}. Calculated Score: {overall_best_attempt_evaluation.calculated_evaluation_score}",
                Severity.WARNING,
            )

            log_message(
                f"Calling again for (it will be call #{i+2}) with the following improvement prompt: `{improvement_prompt}`",
                Severity.WARNING,
            )
            continue

        else:
            break

    extension = mimetypes.guess_extension(IMAGE_MIME_TYPE) or ".png"
    filename = f"{filename_without_extension}{extension}"
    if overall_best_attempt:
        log_message(
            f"Image generated. Best averaged score: {overall_best_attempt_evaluation.averaged_evaluation_score if overall_best_attempt_evaluation else '[No Eval]'}. Filename: {filename}.",
            Severity.INFO,
        )
        return {
            "status": "success",
            "detail": f"Image generated successfully for {filename}.",
            "file_name": filename,
            "image_bytes": overall_best_attempt["image_bytes"],
            "mime_type": IMAGE_MIME_TYPE,
            "best_eval": overall_best_attempt_evaluation,
        }
    else:
        log_message(
            f"Failed to generate image after an initial attempt, {get_image_generation_eval_reattempts()} EVAL reattempts and {get_image_generation_tenacity_attempts()} TENACITY attempts",
            Severity.ERROR,
        )
        return {}


# @log_function_call
# @retry(
#     stop=stop_after_attempt(get_image_generation_tenacity_attempts()),
#     wait=wait_random_exponential(multiplier=2, min=get_image_generation_retry_delay_seconds(), max=35),
#     retry=retry_if_exception_type((ClientError, api_exceptions.ResourceExhausted)),
# )
async def _call_gemini_image_api(
    client: genai.Client,
    model: str,
    contents: List[Any],
    image_prompt: str,
    mime_type: str,
    should_evaluate: bool = True,
    allow_collage: bool = False,
    semaphore: asyncio.Semaphore | None = None,
) -> dict[str, Any]:
    """
    Calls the Gemini API to generate an image.
    Wrapped with retry logic for 429 RESOURCE_EXHAUSTED errors.

    Args:
        client: The Gemini API client.
        model: The name of the model to use for image generation.
        contents: The content to send to the model.
        image_prompt: The prompt used for image generation.
        allow_collage: If True, allows collages and storyboards. Defaults to False.
        semaphore: Optional semaphore to limit concurrency.

    Returns:
        A dictionary with the image bytes, evaluation, and MIME type.
    """

    response: types.GenerateContentResponse | None = None
    for i in range(get_image_generation_tenacity_attempts()):
        log_message(
            f"Calling _call_gemini_image_api attempt {i+1} of {get_image_generation_tenacity_attempts()} tenacity attempts. Time: {datetime.datetime.now().strftime('%H:%M:%S.%f')}",
            Severity.INFO,
        )
        try:
            if semaphore:
                async with semaphore:
                    log_message(
                        f"Calling client.aio.models.generate_content with semaphore. Time: {datetime.datetime.now().strftime('%H:%M:%S.%f')}",
                        Severity.DEBUG,
                    )
                    response = await client.aio.models.generate_content(
                        model=model,
                        contents=contents,
                        config=GENERATE_CONTENT_CONFIG,
                    )
            else:
                log_message(
                    f"Calling client.aio.models.generate_content without semaphore. Time: {datetime.datetime.now().strftime('%H:%M:%S.%f')}",
                    Severity.DEBUG,
                )
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=GENERATE_CONTENT_CONFIG,
                )
            if (
                response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts
            ):
                log_message(
                    f"Reviewing response from call to client.aio.models.generate_content. Time: {datetime.datetime.now().strftime('%H:%M:%S.%f')}",
                    Severity.DEBUG,
                )
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        image_bytes = part.inline_data.data
                        evaluation = None
                        if should_evaluate:
                            log_message(
                                f"Will run eval on call to client.aio.models.generate_content. Time: {datetime.datetime.now().strftime('%H:%M:%S.%f')}",
                                Severity.DEBUG,
                            )
                            evaluation = await evaluate_media(
                                image_bytes,
                                mime_type,
                                image_prompt,
                                allow_collage=allow_collage,
                            )

                        log_message(
                            f"Successfully generated image. Size: {len(image_bytes)} bytes, Evaluation: {evaluation}. Time: {datetime.datetime.now().strftime('%H:%M:%S.%f')}",
                            Severity.INFO,
                        )
                        return {
                            "image_bytes": image_bytes,
                            "evaluation": evaluation,
                            "mime_type": mime_type,
                        }
        except api_exceptions.ResourceExhausted as e:
            log_message(
                f"In _call_gemini_image_api received an api_exceptions.ResourceExhausted. Will attempt again: {e}",
                Severity.WARNING,
            )
            time.sleep(
                random.uniform(0, get_image_generation_retry_delay_seconds())
            )
            continue
        except Exception as e:
            log_message(f"Error in _call_gemini_image_api: {e}", Severity.ERROR)
            return {}

    if not response:
        candidates_info = "Response is None"
    elif not response.candidates:
        candidates_info = "Candidates is None or empty"
    else:
        candidates_info = f"Candidates: {len(response.candidates)}"
        if (
            response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            candidates_info += (
                f", Parts: {len(response.candidates[0].content.parts)}"
            )
        else:
            candidates_info += ", No content or parts"

    error_msg = (
        f"ERROR: no images were generated. Prompt: {image_prompt}, "
        f"Content count: {len(contents)}, Response info: {candidates_info}"
    )
    log_message(error_msg, Severity.ERROR)
    return {}
