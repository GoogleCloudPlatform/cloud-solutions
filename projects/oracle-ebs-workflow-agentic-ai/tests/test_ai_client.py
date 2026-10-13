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

"""Unit tests for Google GenAI client initialization and model fallback."""

from typing import Any, cast

import pytest
from google.genai import types
from src.a2a import ai_client
from src.a2a.ai_client import (
    WrappedResponse,
    extract_json_from_text,
    generate_content_with_models,
    get_ai_client,
    get_candidate_models,
)
from src.config import get_settings


class _DummyRawResponse:
    """Minimal response double for testing WrappedResponse."""

    def __init__(self, text: str, usage: int = 42) -> None:
        self.text = text
        self.usage = usage


def test_extract_json_from_text() -> None:
    """Verify JSON extraction strips Markdown fences and trailing text."""
    assert extract_json_from_text(None) == ""
    assert extract_json_from_text("") == ""
    fenced = '```json\n{"action": "list_notifications", "limit": 10}\n```'
    assert (
        extract_json_from_text(fenced)
        == '{"action": "list_notifications", "limit": 10}'
    )
    embedded = 'Here is the result: {"status": "OK"} thank you!'
    assert extract_json_from_text(embedded) == '{"status": "OK"}'
    plain = "Non-JSON response text"
    assert extract_json_from_text(plain) == "Non-JSON response text"


def test_wrapped_response_delegation() -> None:
    """Verify WrappedResponse exposes clean text and delegates attributes."""
    raw = _DummyRawResponse(text="```json\n{}\n```", usage=99)
    wrapped = WrappedResponse(raw, "{}")
    assert wrapped.text == "{}"
    assert wrapped.usage == 99
    assert "WrappedResponse" in repr(wrapped)


def test_get_candidate_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify candidate model ordering for fast_tier and standard modes."""
    monkeypatch.setenv("GEMINI_FLASH_LITE_MODEL", "model-lite")
    monkeypatch.setenv("GEMINI_MODEL", "model-primary")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "model-fallback")
    get_settings.cache_clear()

    fast_models = get_candidate_models(fast_tier=True)
    assert fast_models == ["model-lite", "model-primary", "model-fallback"]

    std_models = get_candidate_models(fast_tier=False)
    assert std_models == ["model-primary", "model-fallback"]
    get_settings.cache_clear()


def test_get_ai_client_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_ai_client returns None when client initialization fails."""
    get_ai_client.cache_clear()

    def _raise_value_error(**_kwargs: Any) -> Any:
        raise ValueError("Invalid Vertex AI configuration")

    monkeypatch.setattr(ai_client.genai, "Client", _raise_value_error)
    assert get_ai_client() is None
    get_ai_client.cache_clear()


def test_generate_content_with_models_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify generate_content_with_models falls back on primary failure."""
    monkeypatch.setattr(
        ai_client,
        "get_candidate_models",
        lambda _fast_tier=True: ["primary-m", "fallback-m"],
    )
    calls: list[str] = []

    class _FakeModels:
        def generate_content(
            self, model: str, contents: Any, config: Any
        ) -> _DummyRawResponse:
            _ = (contents, config)
            calls.append(model)
            if model == "primary-m":
                raise OSError("Primary model unavailable")
            return _DummyRawResponse('```json\n{"ok": true}\n```')

    class _FakeClient:
        def __init__(self) -> None:
            self.models = _FakeModels()

    cfg = types.GenerateContentConfig(temperature=0.0)
    fake_client = cast(ai_client.genai.Client, _FakeClient())
    resp = generate_content_with_models(
        fake_client,
        "prompt",
        cfg,
        fast_tier=True,
    )
    assert calls == ["primary-m", "fallback-m"]
    assert resp.text == '{"ok": true}'
