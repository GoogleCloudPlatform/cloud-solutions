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

"""Domain models, lifecycle states, and backend protocol for Agent Sandbox in Gemini (ADR-0012)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

DEFAULT_SANDBOX_TTL_SECONDS: Final[float] = 900.0
MAX_SANDBOX_TTL_SECONDS: Final[float] = 3600.0
MAX_SANDBOX_CODE_CHARS: Final[int] = 8192
STANDARD_MAX_ACTIVE_SANDBOXES: Final[int] = 5
ENTERPRISE_MAX_ACTIVE_SANDBOXES: Final[int] = 20


class SandboxUnavailableError(RuntimeError):
    """Raised when agent sandboxes or the GKE gVisor warm pool are unreachable or exhausted."""

    code: str = "E_SANDBOX_UNAVAILABLE"

    def __init__(
        self, message: str, code: str = "E_SANDBOX_UNAVAILABLE"
    ) -> None:
        """Initializes a fail-closed 503 sandbox availability exception.

        Args:
            message: Internal diagnostic detail logged server-side.
            code: Stable public error code returned in HTTP 503 responses.
        """
        super().__init__(message)
        self.code = code


class SandboxLifecycleState(StrEnum):
    """Lifecycle states of a session-tainted Gemini `SandboxEnvironment`."""

    UNCLAIMED = "STATE_UNCLAIMED"
    RUNNING = "STATE_RUNNING"
    PAUSED = "STATE_PAUSED"
    DESTROYED = "STATE_DESTROYED"


class SandboxLanguage(StrEnum):
    """Supported execution languages inside Gemini `sandboxEnvironments`."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    BASH = "bash"


@dataclass(frozen=True)
class SandboxTaintTuple:
    """Immutable 5-tuple locking one sandbox environment to a single session and language."""

    tenant_id: str
    user_sub: str
    agent_id: str
    session_id: str
    language: SandboxLanguage = SandboxLanguage.PYTHON

    def matches_session_principal(self, other: SandboxTaintTuple) -> bool:
        """Returns `True` when `(tenant_id, user_sub, agent_id, session_id)` match."""
        return (
            self.tenant_id == other.tenant_id
            and self.user_sub == other.user_sub
            and self.agent_id == other.agent_id
            and self.session_id == other.session_id
        )


@dataclass(frozen=True)
class SandboxEnvironmentRecord:
    """Immutable snapshot of a claimed Gemini `SandboxEnvironment` instance."""

    sandbox_id: str
    sandbox_resource_name: str
    template_resource_name: str
    taint: SandboxTaintTuple
    state: SandboxLifecycleState
    created_at_monotonic: float
    expires_at_monotonic: float
    execution_count: int
    language: SandboxLanguage = SandboxLanguage.PYTHON
    internet_access_enabled: bool = False
    runtime_class: str = "gvisor"


@dataclass(frozen=True)
class SandboxBackendCreateResult:
    """Strict return contract for `SandboxBackendClient.create_sandbox`."""

    sandbox_id: str
    sandbox_resource_name: str
    template_resource_name: str


@dataclass(frozen=True)
class SandboxBackendExecutionResult:
    """Strict return contract for `SandboxBackendClient.execute_workload`."""

    stdout: str
    stderr: str
    exit_code: int
    backend_mode: str


class SandboxBackendClient(Protocol):
    """Synchronous protocol implemented by live Gemini and hermetic zero-credential backends."""

    def create_sandbox(
        self,
        *,
        project_id: str,
        location: str,
        taint: SandboxTaintTuple,
        language: SandboxLanguage,
        ttl_seconds: float,
    ) -> SandboxBackendCreateResult:
        """Creates an isolated Gemini `SandboxEnvironment` or claims a GKE `SandboxWarmPool` pod."""

    def execute_workload(
        self,
        *,
        sandbox_resource_name: str,
        language: SandboxLanguage,
        code: str,
        readonly_input_json: str,
    ) -> SandboxBackendExecutionResult:
        """Executes `code` inside `sandbox_resource_name` with zero mounted credentials."""

    def pause_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Transitions `sandbox_resource_name` to `STATE_PAUSED`, releasing active compute."""

    def resume_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Resumes a `STATE_PAUSED` sandbox back to `STATE_RUNNING` with `/workspace` intact."""

    def delete_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Permanently destroys `sandbox_resource_name` so it is never returned to a warm pool."""


def _safe_int(value: object, *, default: int | None) -> int | None:
    """Parses integer exit codes without accepting Python booleans as integers."""
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(stripped)
        except ValueError:
            return default
    return default
