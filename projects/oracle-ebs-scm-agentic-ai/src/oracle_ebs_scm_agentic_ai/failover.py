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

"""Gemini model that fails over to the next model when Vertex AI is busy."""

import logging
from collections.abc import AsyncGenerator
from typing import Final

from google.adk.models import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import errors

logger = logging.getLogger(__name__)

# Quota, overload, and timeout errors that another model can absorb.
TRANSIENT_STATUS_CODES: Final[frozenset[int]] = frozenset(
    {408, 429, 500, 502, 503, 504}
)


class FailoverGemini(Gemini):
    """Gemini that retries a request on the fallback models, in order.

    Quota saturation or a transient outage of one model moves the request to
    the next model before any response reaches the agent. Other errors, and
    errors after a partial response, propagate unchanged.
    """

    fallback_models: tuple[str, ...] = ()

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Send the request to each model in turn until one answers.

        Args:
            llm_request: The model request. Its model changes to each
                fallback model in turn.
            stream: Whether to stream partial responses.

        Yields:
            The responses of the first model that answers.

        Raises:
            google.genai.errors.APIError: If the error isn't transient, a
                response already reached the agent, or the last model
                fails.
        """
        models = (llm_request.model or self.model, *self.fallback_models)
        for attempt, model in enumerate(models, start=1):
            llm_request.model = model
            responded = False
            try:
                async for response in super().generate_content_async(
                    llm_request, stream
                ):
                    responded = True
                    yield response
                return
            except errors.APIError as error:
                if (
                    responded
                    or attempt == len(models)
                    or error.code not in TRANSIENT_STATUS_CODES
                ):
                    raise
                logger.warning(
                    "Gemini model %s failed with HTTP %s, so the request "
                    "moves to %s",
                    model,
                    error.code,
                    models[attempt],
                )
