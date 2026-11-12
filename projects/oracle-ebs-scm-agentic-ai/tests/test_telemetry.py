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

"""Tests for the Gemini call telemetry callbacks."""

import logging
from types import SimpleNamespace
from typing import Any, cast

import pytest
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from oracle_ebs_scm_agentic_ai import telemetry


def context() -> CallbackContext:
    state: dict[str, Any] = {}
    return cast(CallbackContext, SimpleNamespace(state=state))


def usage_response(partial: bool = False) -> LlmResponse:
    return LlmResponse(
        partial=partial,
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=16000,
            cached_content_token_count=12000,
            thoughts_token_count=300,
            candidates_token_count=150,
        ),
    )


def test_model_call_logs_latency_and_tokens(
    caplog: pytest.LogCaptureFixture,
) -> None:
    callback_context = context()
    caplog.set_level(logging.INFO, logger=telemetry.__name__)
    assert telemetry.start_model_call(callback_context, LlmRequest()) is None
    assert telemetry.STARTED_KEY in callback_context.state
    assert telemetry.log_model_call(callback_context, usage_response()) is None
    assert "prompt=16000 cached=12000 thoughts=300 output=150" in caplog.text


def test_partial_responses_are_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=telemetry.__name__)
    response = usage_response(partial=True)
    assert telemetry.log_model_call(context(), response) is None
    assert "Gemini call" not in caplog.text
