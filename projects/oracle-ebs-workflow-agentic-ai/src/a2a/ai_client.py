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

"""Vertex AI Gemini Client using Application Default Credentials (ADC)."""

import json
import logging
import re
from functools import lru_cache
from typing import Any

import httpx
from google import genai
from google.auth import exceptions as google_auth_exceptions
from google.genai import errors as genai_errors
from google.genai import types
from src.config import get_settings

logger = logging.getLogger(__name__)

GENAI_CALL_EXCEPTIONS = (
    genai_errors.APIError,
    google_auth_exceptions.GoogleAuthError,
    httpx.HTTPError,
    OSError,
)


def extract_json_from_text(text: str | None) -> str:
    """Extract clean JSON string, stripping Markdown code fences if present."""
    if not text:
        return ""
    clean = text.strip()
    if "```" in clean:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
        if match:
            clean = match.group(1).strip()
    if "{" in clean and "}" in clean:
        first_brace = clean.find("{")
        last_brace = clean.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            for i in range(last_brace, first_brace, -1):
                if clean[i] == "}":
                    candidate = clean[first_brace : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except ValueError:
                        pass
    return clean


class WrappedResponse:
    """Delegating wrapper that provides sanitized, unwrapped JSON text."""

    def __init__(self, raw_resp: Any, clean_text: str) -> None:
        self._raw = raw_resp
        self.text = clean_text

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)

    def __repr__(self) -> str:
        return f"<WrappedResponse text={self.text!r}>"


@lru_cache
def get_ai_client() -> genai.Client | None:
    """Lazy initializer for Google GenAI client using Vertex AI ADC."""
    settings = get_settings()
    try:
        project = settings.gemini.project
        location = settings.gemini.location
        if project:
            return genai.Client(
                vertexai=True, project=project, location=location
            )
        return genai.Client(vertexai=True, location=location)
    except (
        google_auth_exceptions.GoogleAuthError,
        genai_errors.APIError,
        ValueError,
        OSError,
    ) as exc:
        logger.warning("Failed to initialize Vertex AI GenAI client: %s", exc)
        return None


def get_candidate_models(fast_tier: bool = True) -> list[str]:
    """Retrieve ordered list of Gemini model names to try."""
    settings = get_settings()
    models: list[str] = []
    if fast_tier and settings.gemini.flash_lite_model:
        models.append(settings.gemini.flash_lite_model)
    if (
        settings.gemini.primary_model
        and settings.gemini.primary_model not in models
    ):
        models.append(settings.gemini.primary_model)
    if (
        settings.gemini.fallback_model
        and settings.gemini.fallback_model not in models
    ):
        models.append(settings.gemini.fallback_model)
    return models


def generate_content_with_models(
    ai_client: genai.Client,
    contents: Any,
    config: types.GenerateContentConfig,
    fast_tier: bool = True,
) -> Any:
    """Generate content targeting primary then fallback model."""
    models_to_try = get_candidate_models(fast_tier)
    last_exc: Exception | None = None

    for model_name in models_to_try:
        try:
            resp = ai_client.models.generate_content(
                model=model_name, contents=contents, config=config
            )
            if resp is not None and hasattr(resp, "text"):
                return WrappedResponse(resp, extract_json_from_text(resp.text))
            return resp
        except GENAI_CALL_EXCEPTIONS as exc:
            last_exc = exc
            logger.warning(
                "Generation with model '%s' failed: %s; attempting fallback",
                model_name,
                exc,
            )

    if last_exc:
        raise last_exc
    raise RuntimeError("No configured Gemini models available")
