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

"""Shared Google GenAI client initializer using Vertex AI ADC."""

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from google import genai
from google.genai import types
from src.a2a.schemas import SAFE_EXCEPTIONS

logger = logging.getLogger(__name__)


def extract_json_from_text(text: Optional[str]) -> str:
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
                    sub = clean[first_brace : i + 1]
                    try:
                        json.loads(sub)
                        return sub
                    except ValueError:
                        pass
    return clean


class WrappedResponse:
    """Delegating wrapper that provides sanitized, unwrapped JSON text."""

    def __init__(self, raw_resp: Any, clean_text: str):
        self._raw = raw_resp
        self.text = clean_text

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)

    def __repr__(self) -> str:
        return f"<WrappedResponse text={self.text!r}>"


@lru_cache
def _load_tfvars() -> Dict[str, str]:
    """Read key-value pairs from terraform.tfvars."""
    res: Dict[str, str] = {}
    tfvars_path = (
        Path(__file__).resolve().parent.parent.parent
        / "terraform"
        / "terraform.tfvars"
    )
    if tfvars_path.is_file():
        try:
            with open(tfvars_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if "=" in stripped and not stripped.startswith("#"):
                        k, v = stripped.split("=", 1)
                        res[k.strip()] = v.strip().strip('"').strip("'")
        except OSError as exc:
            logger.debug("Failed to read terraform.tfvars: %s", exc)
    return res


@lru_cache
def get_gemini_models() -> Tuple[str, str]:
    """Retrieve primary and fallback Gemini models from terraform.tfvars or
    env."""
    tfvars = _load_tfvars()
    primary = os.environ.get("GEMINI_MODEL") or tfvars.get("gemini_model")
    fallback = os.environ.get("GEMINI_FALLBACK_MODEL") or tfvars.get(
        "gemini_fallback_model"
    )
    return (
        primary or "gemini-3.8-flash",
        fallback or "gemini-3.7-flash",
    )


@lru_cache
def get_gemini_flash_lite_model() -> str:
    """Retrieve fast Gemini Flash Lite model from terraform.tfvars or env."""
    tfvars = _load_tfvars()
    fast_model = os.environ.get("GEMINI_FLASH_LITE_MODEL") or tfvars.get(
        "gemini_flash_lite_model"
    )
    return fast_model or "gemini-3.5-flash-lite"


def get_candidate_models(fast_tier: bool = True) -> list[str]:
    """Retrieve ordered list of Gemini model names to try."""
    models: list[str] = []
    if fast_tier:
        lite = get_gemini_flash_lite_model()
        if lite:
            models.append(lite)
    for m in get_gemini_models():
        if m and m not in models:
            models.append(m)
    return models


@lru_cache
def get_ai_client() -> Optional[genai.Client]:
    """Lazy initializer for Google GenAI client using Vertex AI ADC."""
    try:
        tfvars = _load_tfvars()
        project = (
            os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("PROJECT_ID")
            or tfvars.get("project_id", "")
        )
        location = os.environ.get("VERTEX_LOCATION", "global")
        if location in ("northamerica-northeast2", "northamerica-northeast1"):
            location = "global"
        if project:
            return genai.Client(
                vertexai=True, project=project, location=location
            )
        return genai.Client(vertexai=True, location=location)
    except SAFE_EXCEPTIONS as exc:
        logger.warning("Failed to initialize GenAI client: %s", exc)
        return None


def _prepare_tool_call_config(
    config: types.GenerateContentConfig, contents: Any
) -> Tuple[types.GenerateContentConfig, Any]:
    """Configure thinking budget and schema mandate for tool-enabled calls."""
    call_config = config
    call_contents = contents

    if (
        call_config
        and getattr(call_config, "thinking_config", None) is None
        and hasattr(types, "ThinkingConfig")
    ):
        try:
            call_config.thinking_config = types.ThinkingConfig(
                thinking_budget=0
            )
        except (AttributeError, TypeError, ValueError):
            pass

    if not (config and getattr(config, "tools", None)):
        return call_config, call_contents

    schema_obj = getattr(config, "response_schema", None)
    schema_desc = ""
    if schema_obj:
        if hasattr(schema_obj, "model_json_schema"):
            schema_desc = json.dumps(schema_obj.model_json_schema())
        else:
            schema_desc = str(schema_obj)

    config_kwargs: dict[str, Any] = {}
    for k in (
        "temperature",
        "top_p",
        "top_k",
        "system_instruction",
        "tools",
        "max_output_tokens",
        "stop_sequences",
        "thinking_config",
    ):
        val = getattr(config, k, None)
        if val is not None:
            config_kwargs[k] = val
    if "thinking_config" not in config_kwargs and hasattr(
        types, "ThinkingConfig"
    ):
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_budget=0
        )
    call_config = types.GenerateContentConfig(**config_kwargs)

    if schema_desc and isinstance(contents, str):
        call_contents = (
            f"{contents}\n\n"
            "CRITICAL JSON OUTPUT MANDATE:\n"
            "After executing any necessary tools, output strictly valid "
            "JSON conforming to this schema:\n"
            f"{schema_desc}\n"
            "Do not include commentary outside the JSON."
        )

    return call_config, call_contents


def _invoke_model_generation(
    ai_client: genai.Client,
    model_name: str,
    contents: Any,
    config: types.GenerateContentConfig,
) -> Any:
    """Execute generation via chats or generate_content."""
    has_tools = bool(config and getattr(config, "tools", None))
    is_mock = (
        hasattr(ai_client, "_mock_return_value")
        or type(ai_client).__name__ == "MagicMock"
    )
    if is_mock:
        return ai_client.models.generate_content(
            model=model_name, contents=contents, config=config
        )
    if has_tools and hasattr(ai_client, "chats"):
        chat = ai_client.chats.create(model=model_name, config=config)
        return chat.send_message(contents)
    return ai_client.models.generate_content(
        model=model_name, contents=contents, config=config
    )


def generate_content_with_models(
    ai_client: genai.Client,
    contents: Any,
    config: types.GenerateContentConfig,
    fast_tier: bool = True,
) -> Any:
    """Generate content targeting primary then fallback model from
    terraform.tfvars."""
    models_to_try = get_candidate_models(fast_tier)
    call_config, call_contents = _prepare_tool_call_config(config, contents)
    last_exc: Optional[Exception] = None

    for model_name in models_to_try:
        try:
            resp = _invoke_model_generation(
                ai_client, model_name, call_contents, call_config
            )
            if resp is not None and hasattr(resp, "text"):
                return WrappedResponse(resp, extract_json_from_text(resp.text))
            return resp
        except SAFE_EXCEPTIONS as exc:
            last_exc = exc
            logger.warning(
                "Generation with model '%s' failed: %s; attempting fallback",
                model_name,
                exc,
            )

    if last_exc:
        raise last_exc
    raise RuntimeError("No configured Gemini models available")
