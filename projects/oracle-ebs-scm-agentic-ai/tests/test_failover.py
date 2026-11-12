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

"""Tests for the Gemini failover model."""

from collections.abc import AsyncGenerator

import pytest
from google.adk.models import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import errors, types
from oracle_ebs_scm_agentic_ai.failover import FailoverGemini

MODELS = ("gemini-primary", "gemini-fallback", "gemini-lite")


def answer(text: str) -> LlmResponse:
    """Build a model response with one text part."""
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)])
    )


def failover_model() -> FailoverGemini:
    """Build the failover model under test."""
    return FailoverGemini(model=MODELS[0], fallback_models=MODELS[1:])


def patch_backend(
    monkeypatch: pytest.MonkeyPatch,
    failures: dict[str, int],
    calls: list[str],
    partial_before_failure: bool = False,
) -> None:
    """Replace Gemini calls: listed models fail with their HTTP status."""

    async def generate(
        self: Gemini, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del self, stream
        model = str(llm_request.model)
        calls.append(model)
        if model in failures:
            if partial_before_failure:
                yield answer("partial")
            raise errors.APIError(failures[model], {"error": {"message": "x"}})
        yield answer(f"answer from {model}")

    monkeypatch.setattr(Gemini, "generate_content_async", generate)


async def collect(model: FailoverGemini) -> list[str]:
    """Run one request and return the response texts."""
    request = LlmRequest(model=model.model)
    return [
        str(response.content.parts[0].text)
        async for response in model.generate_content_async(request)
        if response.content and response.content.parts
    ]


@pytest.mark.asyncio
async def test_primary_model_answers_without_failover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch_backend(monkeypatch, {}, calls)
    assert await collect(failover_model()) == ["answer from gemini-primary"]
    assert calls == ["gemini-primary"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
async def test_transient_error_moves_to_the_next_model(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    status: int,
) -> None:
    calls: list[str] = []
    patch_backend(monkeypatch, {"gemini-primary": status}, calls)
    assert await collect(failover_model()) == ["answer from gemini-fallback"]
    assert calls == ["gemini-primary", "gemini-fallback"]
    assert "so the request moves to gemini-fallback" in caplog.text


@pytest.mark.asyncio
async def test_lite_model_takes_over_when_both_flash_models_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch_backend(
        monkeypatch, {"gemini-primary": 429, "gemini-fallback": 503}, calls
    )
    assert await collect(failover_model()) == ["answer from gemini-lite"]
    assert calls == list(MODELS)


@pytest.mark.asyncio
async def test_last_model_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch_backend(monkeypatch, dict.fromkeys(MODELS, 503), calls)
    with pytest.raises(errors.APIError) as raised:
        await collect(failover_model())
    assert raised.value.code == 503
    assert calls == list(MODELS)


@pytest.mark.asyncio
async def test_request_errors_do_not_fail_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch_backend(monkeypatch, {"gemini-primary": 400}, calls)
    with pytest.raises(errors.APIError) as raised:
        await collect(failover_model())
    assert raised.value.code == 400
    assert calls == ["gemini-primary"]


@pytest.mark.asyncio
async def test_error_after_a_partial_response_does_not_fail_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch_backend(
        monkeypatch,
        {"gemini-primary": 503},
        calls,
        partial_before_failure=True,
    )
    with pytest.raises(errors.APIError):
        await collect(failover_model())
    assert calls == ["gemini-primary"]
