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

"""Hermetic zero-credential in-memory sandbox backend for offline CI and unit tests."""

from __future__ import annotations

import json
import threading
import uuid

from agents.sandbox.ast_interpreter import _evaluate_restricted_diagnostic_ast
from agents.sandbox.models import (
    SandboxBackendCreateResult,
    SandboxBackendExecutionResult,
    SandboxLanguage,
    SandboxLifecycleState,
    SandboxTaintTuple,
    SandboxUnavailableError,
)
from agents.sandbox.syntax_validators import (
    _validate_bash_syntax,
    _validate_javascript_syntax,
)


class HermeticZeroCredentialSandboxBackend:
    """Offline stand-in modeling Gemini `sandboxEnvironments` without `exec`/`eval` or secrets."""

    def __init__(self) -> None:
        """Initializes the hermetic in-memory agent sandbox in Gemini simulator."""
        self._lock = threading.Lock()
        self._states: dict[str, SandboxLifecycleState] = {}
        self._workspaces: dict[str, dict[str, object]] = {}

    def create_sandbox(
        self,
        *,
        project_id: str,
        location: str,
        taint: SandboxTaintTuple,
        language: SandboxLanguage,
        ttl_seconds: float,
    ) -> SandboxBackendCreateResult:
        """Allocates a simulated `sandboxEnvironments/{id}` under `SandboxEnvironmentTemplate`.

        Args:
            project_id: Google Cloud project ID.
            location: Regional endpoint (`us-central1`).
            taint: Verified `(tenant_id, user_sub, agent_id, session_id, language)` taint tuple.
            language: Requested execution language (`python`, `javascript`, or `bash`).
            ttl_seconds: Server-side garbage-collection TTL in seconds.

        Returns:
            `SandboxBackendCreateResult` naming the isolated sandbox and template resources.
        """
        del taint, ttl_seconds
        sandbox_id = f"sbx-{uuid.uuid4().hex[:16]}"
        template_slug = (
            "cymbal-shell-sandbox-tpl"
            if language == SandboxLanguage.BASH
            else "cymbal-code-sandbox-tpl"
        )
        sandbox_resource_name = f"projects/{project_id}/locations/{location}/sandboxEnvironments/{sandbox_id}"
        template_resource_name = (
            f"projects/{project_id}/locations/{location}/reasoningEngines/"
            f"hermetic/sandboxEnvironmentTemplates/{template_slug}"
        )
        with self._lock:
            self._states[sandbox_resource_name] = SandboxLifecycleState.RUNNING
            self._workspaces[sandbox_resource_name] = {}
        return SandboxBackendCreateResult(
            sandbox_id=sandbox_id,
            sandbox_resource_name=sandbox_resource_name,
            template_resource_name=template_resource_name,
        )

    def execute_workload(
        self,
        *,
        sandbox_resource_name: str,
        language: SandboxLanguage,
        code: str,
        readonly_input_json: str,
    ) -> SandboxBackendExecutionResult:
        """Runs a safe AST-verified diagnostic workload inside the simulated `/workspace`.

        Args:
            sandbox_resource_name: Full `sandboxEnvironments/{id}` resource path.
            language: Execution runtime (`python`, `javascript`, or `bash`).
            code: Validated code or diagnostic command.
            readonly_input_json: JSON-serialized sanitized MCP tool output.

        Returns:
            `SandboxBackendExecutionResult` with deterministic stdout and exit code.

        Raises:
            SandboxUnavailableError: If the sandbox does not exist or is not `STATE_RUNNING`.
            ValueError: If `code` fails syntax validation (`E_SANDBOX_SYNTAX_ERROR`).
            PermissionError: If Python AST inspection blocks disallowed imports/dunders/calls.
        """
        with self._lock:
            current_state = self._states.get(sandbox_resource_name)
            workspace_snapshot = dict(
                self._workspaces.get(sandbox_resource_name, {})
            )
        if current_state != SandboxLifecycleState.RUNNING:
            raise SandboxUnavailableError(
                f"Sandbox '{sandbox_resource_name}' is not in "
                f"STATE_RUNNING (got {current_state!r})."
            )

        parsed_input = (
            json.loads(readonly_input_json) if readonly_input_json else {}
        )
        if not isinstance(parsed_input, dict):
            parsed_input = {"value": parsed_input}

        if language == SandboxLanguage.PYTHON:
            execution_result = _evaluate_restricted_diagnostic_ast(
                code,
                parsed_input,
                session_workspace=workspace_snapshot,
            )
            if execution_result.exit_code == 0:
                with self._lock:
                    if (
                        self._states.get(sandbox_resource_name)
                        == SandboxLifecycleState.RUNNING
                    ):
                        self._workspaces[sandbox_resource_name] = dict(
                            workspace_snapshot
                        )
            return execution_result
        if language == SandboxLanguage.JAVASCRIPT:
            _validate_javascript_syntax(code)
            stdout_payload = json.dumps(
                {
                    "workspace": "/workspace",
                    "user": "appuser",
                    "runtime": "javascript",
                    "code_length": len(code),
                    "input_keys": sorted(str(key) for key in parsed_input),
                },
                sort_keys=True,
            )
        else:
            _validate_bash_syntax(code)
            stdout_payload = json.dumps(
                {
                    "workspace": "/workspace",
                    "user": "appuser",
                    "runtime": "shell_sandbox_non_root",
                    "sudo_available": False,
                    "input_keys": sorted(str(key) for key in parsed_input),
                },
                sort_keys=True,
            )

        return SandboxBackendExecutionResult(
            stdout=stdout_payload,
            stderr="",
            exit_code=0,
            backend_mode="HERMETIC_AGENT_SANDBOX_SANDBOX_SIMULATION",
        )

    def pause_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Transitions a running sandbox to `STATE_PAUSED`.

        Args:
            sandbox_resource_name: Full `sandboxEnvironments/{id}` resource path.

        Returns:
            `True` when transitioned to `STATE_PAUSED`, `False` otherwise.
        """
        with self._lock:
            if (
                self._states.get(sandbox_resource_name)
                != SandboxLifecycleState.RUNNING
            ):
                return False
            self._states[sandbox_resource_name] = SandboxLifecycleState.PAUSED
            return True

    def resume_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Resumes a paused sandbox back to `STATE_RUNNING`.

        Args:
            sandbox_resource_name: Full `sandboxEnvironments/{id}` resource path.

        Returns:
            `True` when transitioned back to `STATE_RUNNING`, `False` otherwise.
        """
        with self._lock:
            if (
                self._states.get(sandbox_resource_name)
                != SandboxLifecycleState.PAUSED
            ):
                return False
            self._states[sandbox_resource_name] = SandboxLifecycleState.RUNNING
            return True

    def delete_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Marks a sandbox `STATE_DESTROYED` and removes its compute allocation.

        Args:
            sandbox_resource_name: Full `sandboxEnvironments/{id}` resource path.

        Returns:
            `True` if an active or paused sandbox was destroyed, `False` if already absent.
        """
        with self._lock:
            previous = self._states.get(sandbox_resource_name)
            if previous is None or previous == SandboxLifecycleState.DESTROYED:
                return False
            self._states[sandbox_resource_name] = (
                SandboxLifecycleState.DESTROYED
            )
            self._workspaces.pop(sandbox_resource_name, None)
            return True
