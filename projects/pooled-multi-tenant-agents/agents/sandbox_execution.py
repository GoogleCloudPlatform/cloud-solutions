# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=line-too-long

"""Public backward-compatible facade for Agent Sandbox in Gemini (`agents.sandbox` subpackage)."""

from __future__ import annotations

import google.auth
import httpx
from agents.sandbox import (
    _FORBIDDEN_CODE_SUBSTRINGS,
    _FORBIDDEN_ENV_KEYS,
    DEFAULT_SANDBOX_TTL_SECONDS,
    ENTERPRISE_MAX_ACTIVE_SANDBOXES,
    MAX_SANDBOX_CODE_CHARS,
    MAX_SANDBOX_TTL_SECONDS,
    STANDARD_MAX_ACTIVE_SANDBOXES,
    GeminiAgentSandboxManager,
    HermeticZeroCredentialSandboxBackend,
    LiveGeminiAgentSandboxClient,
    SandboxBackendClient,
    SandboxBackendCreateResult,
    SandboxBackendExecutionResult,
    SandboxEnvironmentRecord,
    SandboxLanguage,
    SandboxLifecycleState,
    SandboxTaintTuple,
    SandboxUnavailableError,
    _assert_synchronous_backend,
    _control_plane_adc_headers,
    _decode_chunk_output_item,
    assert_zero_credentials_and_egress_safe,
)

__all__ = [
    "DEFAULT_SANDBOX_TTL_SECONDS",
    "ENTERPRISE_MAX_ACTIVE_SANDBOXES",
    "MAX_SANDBOX_CODE_CHARS",
    "MAX_SANDBOX_TTL_SECONDS",
    "STANDARD_MAX_ACTIVE_SANDBOXES",
    "_FORBIDDEN_CODE_SUBSTRINGS",
    "_FORBIDDEN_ENV_KEYS",
    "GeminiAgentSandboxManager",
    "HermeticZeroCredentialSandboxBackend",
    "LiveGeminiAgentSandboxClient",
    "SandboxBackendClient",
    "SandboxBackendCreateResult",
    "SandboxBackendExecutionResult",
    "SandboxEnvironmentRecord",
    "SandboxLanguage",
    "SandboxLifecycleState",
    "SandboxTaintTuple",
    "SandboxUnavailableError",
    "_assert_synchronous_backend",
    "_control_plane_adc_headers",
    "_decode_chunk_output_item",
    "assert_zero_credentials_and_egress_safe",
    "google",
    "httpx",
]
