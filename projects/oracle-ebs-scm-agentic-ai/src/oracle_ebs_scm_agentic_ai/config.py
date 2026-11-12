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

"""Runtime settings read from environment variables.

Every value comes from the Cloud Run environment that Terraform configures.
Missing variables fail fast at startup instead of falling back to defaults.
"""

import base64
import binascii
import os
from functools import cache
from typing import Annotated, Final
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PositiveFloat,
    SecretStr,
    field_validator,
)

ENVIRONMENT_VARIABLES: Final[dict[str, str]] = {
    "project_id": "GOOGLE_CLOUD_PROJECT",
    "gemini_model": "GEMINI_MODEL",
    "gemini_fallback_models": "GEMINI_FALLBACK_MODELS",
    "gemini_location": "GEMINI_LOCATION",
    "mcp_server_url": "MCP_SERVER_URL",
    "a2a_public_url": "A2A_PUBLIC_URL",
    "mcp_timeout_seconds": "MCP_TIMEOUT_SECONDS",
    "maps_static_api_key": "MAPS_STATIC_API_KEY",
    "maps_static_signing_secret": "MAPS_STATIC_SIGNING_SECRET",
    "artifact_bucket": "ARTIFACT_BUCKET",
}
# Maps URL-safe Base64 to the standard alphabet for strict validation.
URLSAFE_TO_STANDARD: Final[bytes] = bytes.maketrans(b"-_", b"+/")


class MissingSettingError(RuntimeError):
    """A required environment variable that isn't set."""


class Settings(BaseModel):
    """Validated configuration for the agent service.

    Attributes:
        project_id: The Google Cloud project that runs the agent.
        gemini_model: The primary Gemini model.
        gemini_fallback_models: The models that take over, in order, when
            the primary model has no capacity or is unavailable.
        gemini_location: The Vertex AI location that serves Gemini.
        mcp_server_url: The MCP Toolbox endpoint.
        a2a_public_url: The public URL that the A2A agent card advertises.
        mcp_timeout_seconds: The timeout of each MCP Toolbox request.
        maps_static_api_key: The Maps Static API key.
        maps_static_signing_secret: The Maps Static API URL signing secret.
        artifact_bucket: The Cloud Storage bucket for chart and map images.
    """

    # Errors never echo inputs, so a malformed secret stays out of the logs.
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    project_id: str
    gemini_model: str
    gemini_fallback_models: Annotated[tuple[str, ...], Field(min_length=1)]
    gemini_location: str
    mcp_server_url: HttpUrl
    a2a_public_url: HttpUrl
    mcp_timeout_seconds: PositiveFloat
    maps_static_api_key: SecretStr
    maps_static_signing_secret: SecretStr
    artifact_bucket: str

    @field_validator("gemini_fallback_models", mode="before")
    @classmethod
    def split_model_list(cls, value: object) -> object:
        """Split the comma-separated GEMINI_FALLBACK_MODELS value.

        Args:
            value: The raw setting.

        Returns:
            The model names without blanks, or a value that isn't text
            unchanged.
        """
        if isinstance(value, str):
            names = (name.strip() for name in value.split(","))
            return tuple(name for name in names if name)
        return value

    @field_validator("maps_static_signing_secret")
    @classmethod
    def check_signing_secret(cls, value: SecretStr) -> SecretStr:
        """Require the URL-safe Base64 secret that URL signing decodes.

        Args:
            value: The signing secret.

        Returns:
            The signing secret, unchanged.

        Raises:
            ValueError: If MAPS_STATIC_SIGNING_SECRET isn't URL-safe Base64.
        """
        encoded = value.get_secret_value().encode("ascii", errors="replace")
        try:
            base64.b64decode(
                encoded.translate(URLSAFE_TO_STANDARD), validate=True
            )
        except binascii.Error as exc:
            raise ValueError(
                "MAPS_STATIC_SIGNING_SECRET is not URL-safe Base64."
            ) from exc
        return value

    @property
    def mcp_audience(self) -> str:
        """The OpenID Connect audience of the MCP Toolbox service."""
        parts = urlsplit(str(self.mcp_server_url))
        return f"{parts.scheme}://{parts.netloc}"


def load_settings(environ: dict[str, str]) -> Settings:
    """Build settings from an environment mapping.

    Args:
        environ: The environment variables.

    Returns:
        The validated settings.

    Raises:
        MissingSettingError: If any required variable is unset or empty.
        pydantic.ValidationError: If a value is invalid.
    """
    missing = [
        name for name in ENVIRONMENT_VARIABLES.values() if not environ.get(name)
    ]
    if missing:
        raise MissingSettingError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    return Settings.model_validate(
        {field: environ[name] for field, name in ENVIRONMENT_VARIABLES.items()}
    )


@cache
def get_settings() -> Settings:
    """Load the process-wide settings from ``os.environ`` once.

    Returns:
        The validated settings.
    """
    return load_settings(dict(os.environ))
