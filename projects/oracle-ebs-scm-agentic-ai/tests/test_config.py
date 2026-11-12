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

"""Tests for the settings that the agent reads from the environment."""

import pytest
from oracle_ebs_scm_agentic_ai.config import (
    ENVIRONMENT_VARIABLES,
    MissingSettingError,
    Settings,
    get_settings,
    load_settings,
)
from pydantic import ValidationError
from tests.conftest import TEST_ENVIRONMENT


def test_settings_load_from_environment(settings: Settings) -> None:
    assert settings.gemini_location == "global"
    assert settings.mcp_audience == "https://ebs-mcp-toolbox.example.run.app"
    assert settings.mcp_timeout_seconds == 60
    secret = TEST_ENVIRONMENT["MAPS_STATIC_SIGNING_SECRET"]
    assert settings.maps_static_signing_secret.get_secret_value() == secret
    assert secret not in repr(settings)


@pytest.mark.parametrize("secret", ["zz*not-base64*zz", "QUJDRA", "Zm9vYmFy="])
def test_malformed_signing_secrets_fail_at_startup(secret: str) -> None:
    environment = {**TEST_ENVIRONMENT, "MAPS_STATIC_SIGNING_SECRET": secret}
    with pytest.raises(ValidationError) as raised:
        load_settings(environment)
    assert "not URL-safe Base64" in str(raised.value)
    assert secret not in str(raised.value)


def test_missing_settings_fail_fast() -> None:
    incomplete = {**TEST_ENVIRONMENT, "MCP_SERVER_URL": ""}
    incomplete.pop("GEMINI_MODEL")
    with pytest.raises(MissingSettingError) as raised:
        load_settings(incomplete)
    assert "GEMINI_MODEL" in str(raised.value)
    assert "MCP_SERVER_URL" in str(raised.value)


def test_fallback_models_keep_their_order(settings: Settings) -> None:
    assert settings.gemini_fallback_models == (
        "gemini-test-fallback",
        "gemini-test-lite",
    )


def test_blank_fallback_model_list_is_invalid() -> None:
    with pytest.raises(ValidationError):
        load_settings({**TEST_ENVIRONMENT, "GEMINI_FALLBACK_MODELS": " , "})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MCP_TIMEOUT_SECONDS", "0"),
        ("MCP_TIMEOUT_SECONDS", "soon"),
        ("MCP_SERVER_URL", "not a url"),
        ("A2A_PUBLIC_URL", "ftp://agent.example"),
    ],
)
def test_invalid_settings_fail_at_startup(name: str, value: str) -> None:
    with pytest.raises(ValidationError):
        load_settings({**TEST_ENVIRONMENT, name: value})


def test_get_settings_reads_the_environment_once(settings: Settings) -> None:
    first = get_settings()
    assert first is get_settings()
    assert first == settings


def test_fallback_models_accept_a_list() -> None:
    fields = {
        field: TEST_ENVIRONMENT[name]
        for field, name in ENVIRONMENT_VARIABLES.items()
    }
    settings = Settings.model_validate(
        {**fields, "gemini_fallback_models": ["model-a", "model-b"]}
    )
    assert settings.gemini_fallback_models == ("model-a", "model-b")
