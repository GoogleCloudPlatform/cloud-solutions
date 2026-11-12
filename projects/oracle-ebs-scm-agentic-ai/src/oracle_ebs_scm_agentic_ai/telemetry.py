# Copyright 2026 Google LLC
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

"""Gemini call telemetry: latency and token usage for every model call.

The callbacks log one line per call to Cloud Logging, so you can break
response times down into model time and tool time without tracing.
"""

import logging
import time
from typing import Final

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

logger = logging.getLogger(__name__)

# The temp: prefix keeps the start time out of the persisted session state.
STARTED_KEY: Final[str] = "temp:gemini_call_started"


def start_model_call(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> LlmResponse | None:
    """Record the start time of a model call (ADK before_model_callback).

    Args:
        callback_context: The ADK callback context.
        llm_request: The model request, which the callback doesn't read.

    Returns:
        None, so the model call proceeds.
    """
    del llm_request
    callback_context.state[STARTED_KEY] = time.monotonic()
    return None


def log_model_call(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    """Log the latency and token usage of a model call.

    ADK runs this as the after_model_callback. Partial streamed responses
    and responses without usage metadata log nothing.

    Args:
        callback_context: The ADK callback context.
        llm_response: The model response.

    Returns:
        None, so the response reaches the agent unchanged.
    """
    usage = llm_response.usage_metadata
    if llm_response.partial or usage is None:
        return None
    started = callback_context.state.get(STARTED_KEY)
    elapsed = time.monotonic() - started if started is not None else -1.0
    logger.info(
        "Gemini call: %.1fs prompt=%s cached=%s thoughts=%s output=%s",
        elapsed,
        usage.prompt_token_count,
        usage.cached_content_token_count,
        usage.thoughts_token_count,
        usage.candidates_token_count,
    )
    return None
