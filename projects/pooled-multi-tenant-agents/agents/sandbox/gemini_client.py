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

# pylint: disable=import-outside-toplevel,inconsistent-quotes,line-too-long
# pylint: disable=try-except-raise

"""Live Vertex AI / Gemini `sandboxEnvironments` control-plane REST adapter (`v1beta1`)."""

from __future__ import annotations

import base64
import binascii
import json
import os
import sys
import threading
import time
from collections.abc import Callable, Mapping

import google.auth
import google.auth.exceptions
import google.auth.transport.requests
import httpx
from agents.platform_config import (
    get_platform_config,
    is_live_mode,
    resolve_project_id,
)
from agents.sandbox.hermetic_backend import HermeticZeroCredentialSandboxBackend
from agents.sandbox.models import (
    SandboxBackendCreateResult,
    SandboxBackendExecutionResult,
    SandboxLanguage,
    SandboxTaintTuple,
    SandboxUnavailableError,
    _safe_int,
)


def _resolve_httpx_module() -> object:
    """Resolves `httpx` via `agents.sandbox_execution` when loaded so test monkeypatches apply."""
    facade = sys.modules.get("agents.sandbox_execution")
    return getattr(facade, "httpx", httpx) if facade is not None else httpx


def _resolve_adc_headers_hook(project_id: str) -> dict[str, str]:
    """Resolves `_control_plane_adc_headers` via `agents.sandbox_execution` when monkeypatched."""
    facade = sys.modules.get("agents.sandbox_execution")
    hook = getattr(
        facade, "_control_plane_adc_headers", _control_plane_adc_headers
    )
    return hook(project_id)


def _control_plane_adc_headers(project_id: str) -> dict[str, str]:
    """Fetches workload service-account control-plane headers (never a tenant `ct-*` token)."""
    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(google.auth.transport.requests.Request())
    except (
        google.auth.exceptions.GoogleAuthError,
        OSError,
        TimeoutError,
    ) as auth_exc:
        raise SandboxUnavailableError(
            f"agent sandbox in Gemini control-plane ADC unavailable ({type(auth_exc).__name__})."
        ) from auth_exc
    token_text = str(getattr(credentials, "token", "") or "")
    return {
        "Authorization": f"Bearer {token_text}",
        "X-Goog-User-Project": project_id,
    }


def _decode_chunk_output_item(
    chunk_item: object,
) -> tuple[str, str, int | None]:
    """Decodes one Gemini `ExecuteSandboxEnvironmentResponse` `Chunk` (`data` base64 or JSON)."""
    if not isinstance(chunk_item, Mapping):
        return (str(chunk_item), "", None)
    raw_data = chunk_item.get("data")
    decoded_bytes: bytes
    if isinstance(raw_data, bytes):
        decoded_bytes = raw_data
    elif isinstance(raw_data, str):
        try:
            decoded_bytes = base64.b64decode(raw_data, validate=True)
        except (binascii.Error, ValueError):
            decoded_bytes = raw_data.encode("utf-8")
    else:
        return ("", "", None)

    decoded_text = decoded_bytes.decode("utf-8", errors="replace")
    try:
        parsed_json = json.loads(decoded_text)
    except ValueError:
        return (decoded_text, "", None)

    if isinstance(parsed_json, Mapping):
        stdout_part = str(
            parsed_json.get("msg_out") or parsed_json.get("stdout") or ""
        )
        stderr_part = str(
            parsed_json.get("msg_err") or parsed_json.get("stderr") or ""
        )
        exit_raw = parsed_json.get(
            "exit_status_int",
            parsed_json.get("exitCode", parsed_json.get("returncode")),
        )
        exit_int = _safe_int(exit_raw, default=None)
        return (stdout_part, stderr_part, exit_int)
    return (decoded_text, "", None)


class LiveGeminiAgentSandboxClient:
    """Hop 3 Gemini `sandboxEnvironments` client (`aiplatform.googleapis.com/v1beta1`)."""

    def __init__(
        self,
        *,
        project_id: str | None = None,
        location: str | None = None,
        reasoning_engine_name: str | None = None,
        headers_provider: Callable[[str], dict[str, str]] | None = None,
        http_client: object | None = None,
        live_mode_fn: Callable[[], bool] = is_live_mode,
    ) -> None:
        """Initializes the live/hermetic Gemini `sandboxEnvironments` backend adapter.

        Args:
            project_id: Optional target Google Cloud project ID (resolved lazily if omitted).
            location: Optional regional Vertex AI / Gemini endpoint (`us-central1`).
            reasoning_engine_name: Optional full `reasoningEngines/{id}` resource name.
            headers_provider: Optional control-plane auth header provider for REST calls.
            http_client: Optional synchronous `httpx`-compatible client for live tests.
            live_mode_fn: Callable returning `True` when live GCP calls are active.
        """
        self._explicit_project_id = project_id
        self._explicit_location = location
        self._reasoning_engine_name = reasoning_engine_name
        self._explicit_headers_provider = headers_provider
        self._headers_provider = headers_provider or _resolve_adc_headers_hook
        self._http_client = http_client
        self._live_mode_fn = live_mode_fn
        self._hermetic_fallback = HermeticZeroCredentialSandboxBackend()
        self._template_lock = threading.Lock()
        self._shell_template_cache: dict[str, str] = {}

    def _use_live_api(self) -> bool:
        return bool(self._live_mode_fn()) or self._http_client is not None

    def _resolved_project_id(self, override_project: str | None = None) -> str:
        return resolve_project_id(override_project or self._explicit_project_id)

    def _resolved_location(self, override_location: str | None = None) -> str:
        if override_location:
            return override_location
        if self._explicit_location:
            return self._explicit_location
        return os.getenv(
            "GOOGLE_CLOUD_REGION", get_platform_config().gcp.region
        )

    def _resolved_engine_name(self) -> str:
        configured_engine = (
            self._reasoning_engine_name
            or os.getenv("AGENT_SANDBOX_REASONING_ENGINE_NAME", "").strip()
        )
        if not configured_engine:
            raise SandboxUnavailableError(
                "AGENT_SANDBOX_REASONING_ENGINE_NAME must be configured in live GCP mode.",
                code="E_SANDBOX_UNAVAILABLE",
            )
        return configured_engine.strip("/")

    def _api_base_url(self, location: str) -> str:
        from agents.kms_rest import workload_spiffe_mtls_active

        if self._http_client is None and workload_spiffe_mtls_active():
            return f"https://{location}-aiplatform.mtls.googleapis.com/v1beta1"
        return f"https://{location}-aiplatform.googleapis.com/v1beta1"

    def _request_json(
        self,
        *,
        method: str,
        url: str,
        project_id: str,
        payload: Mapping[str, object] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> dict[str, object]:
        from agents.kms_rest import (
            build_spiffe_mtls_session,
            workload_spiffe_mtls_active,
        )

        use_spiffe_mtls = (
            self._http_client is None
            and self._explicit_headers_provider is None
            and workload_spiffe_mtls_active()
        )
        mtls_session = build_spiffe_mtls_session() if use_spiffe_mtls else None
        client_obj = (
            self._http_client
            if self._http_client is not None
            else _resolve_httpx_module()
        )
        request_fn = getattr(client_obj, "request", None)
        if not use_spiffe_mtls and not callable(request_fn):
            raise SandboxUnavailableError(
                "Configured http_client lacks a callable request method."
            )
        parsed: object = {}
        max_attempts = (
            5
            if (
                self._http_client is None
                and method == "POST"
                and url.endswith("/:execute")
            )
            else 1
        )
        for attempt_idx in range(max_attempts):
            try:
                if mtls_session is not None:
                    headers: dict[str, str] = {
                        "Content-Type": "application/json"
                    }
                    if extra_headers is not None:
                        headers.update(extra_headers)
                    http_response = mtls_session.request(
                        method,
                        url,
                        headers=headers,
                        json=dict(payload) if payload is not None else None,
                        timeout=60.0,
                    )
                else:
                    headers = dict(self._headers_provider(project_id))
                    headers["Content-Type"] = "application/json"
                    if extra_headers is not None:
                        headers.update(extra_headers)
                    assert callable(request_fn)
                    http_response = request_fn(
                        method,
                        url,
                        headers=headers,
                        json=dict(payload) if payload is not None else None,
                        timeout=60.0,
                    )
                status_code = int(getattr(http_response, "status_code", 500))
                if status_code >= 400:
                    err_body = str(getattr(http_response, "text", "") or "")
                    if (
                        attempt_idx + 1 < max_attempts
                        and status_code == 400
                        and (
                            "UNAVAILABLE on URL" in err_body
                            or "URL_UNREACHABLE" in err_body
                        )
                    ):
                        time.sleep(2.0)
                        continue
                    raise SandboxUnavailableError(
                        f"Gemini sandboxEnvironments HTTP {status_code}."
                    )
                raw_content = getattr(http_response, "content", b"")
                json_fn = getattr(http_response, "json", None)
                parsed = json_fn() if raw_content and callable(json_fn) else {}
                break
            except SandboxUnavailableError:
                raise
            except (
                google.auth.exceptions.GoogleAuthError,
                httpx.HTTPError,
                OSError,
                TimeoutError,
                ValueError,
                TypeError,
            ) as transport_exc:
                raise SandboxUnavailableError(
                    f"Gemini sandboxEnvironments request failed ({type(transport_exc).__name__})."
                ) from transport_exc
        if not isinstance(parsed, dict):
            raise SandboxUnavailableError(
                "Gemini sandboxEnvironments returned non-object JSON payload."
            )
        return parsed

    def _await_operation_if_needed(
        self,
        *,
        initial_response: dict[str, object],
        location: str,
        project_id: str,
    ) -> dict[str, object]:
        """Polls a Gemini `RuntimeSandboxOperation` LRO until `done` is `True`.

        Note: Proto3 JSON serialization omits `"done": false` on in-progress LROs, so any
        `/operations/` payload without `"done": True` must be polled.
        """
        current_payload = initial_response
        operation_name = str(current_payload.get("name") or "").strip("/")
        if "/operations/" not in operation_name:
            return current_payload
        if current_payload.get("error"):
            raise SandboxUnavailableError(
                "agent sandbox in Gemini operation returned error."
            )
        if current_payload.get("done") is True:
            return current_payload

        default_timeout = 15.0 if self._http_client is not None else 300.0
        timeout_seconds = float(
            os.getenv("AGENT_SANDBOX_LRO_TIMEOUT_SECONDS", str(default_timeout))
        )
        poll_interval = 0.02 if self._http_client is not None else 2.0
        deadline = time.monotonic() + timeout_seconds
        operation_url = f"{self._api_base_url(location)}/{operation_name}"
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            current_payload = self._request_json(
                method="GET",
                url=operation_url,
                project_id=project_id,
                payload=None,
            )
            if current_payload.get("error"):
                raise SandboxUnavailableError(
                    "agent sandbox in Gemini operation returned error."
                )
            if current_payload.get("done") is True:
                return current_payload
        raise SandboxUnavailableError(
            "Timed out awaiting agent sandbox in Gemini operation."
        )

    def _normalized_engine_name(self, *, project_id: str, location: str) -> str:
        """Returns `projects/{project}/locations/{location}/reasoningEngines/{id}`."""
        engine_name = self._resolved_engine_name()
        if engine_name.startswith("projects/"):
            return engine_name
        return f"projects/{project_id}/locations/{location}/{engine_name}"

    def _ensure_shell_sandbox_template(
        self,
        *,
        engine_name: str,
        location: str,
        project_id: str,
    ) -> str:
        """Reuses or provisions a `DEFAULT_CONTAINER_CATEGORY_SHELL_SANDBOX` template on Gemini.

        Vertex AI `v1beta1` rejects `spec.shellEnvironment` requests without a
        `sandboxEnvironmentTemplate` (`HTTP 400 INVALID_ARGUMENT`). Matching `agentplatform` 2.7.0
        (`Sandboxes.create`), this helper discovers an existing shell template on `engine_name` or
        provisions `shell-sandbox-template` once and caches the resource name per engine.
        """
        with self._template_lock:
            cached_template = self._shell_template_cache.get(engine_name)
            if cached_template:
                return cached_template

            templates_url = f"{self._api_base_url(location)}/{engine_name}/sandboxEnvironmentTemplates"
            list_payload = self._request_json(
                method="GET",
                url=templates_url,
                project_id=project_id,
                payload=None,
            )
            existing_templates = list_payload.get("sandboxEnvironmentTemplates")
            if isinstance(existing_templates, list):
                for entry in existing_templates:
                    if not isinstance(entry, Mapping):
                        continue
                    entry_name = str(entry.get("name") or "").strip()
                    default_env = entry.get("defaultContainerEnvironment")
                    category = (
                        str(default_env.get("defaultContainerCategory") or "")
                        if isinstance(default_env, Mapping)
                        else ""
                    )
                    if (
                        "/sandboxEnvironmentTemplates/" in entry_name
                        and category
                        == "DEFAULT_CONTAINER_CATEGORY_SHELL_SANDBOX"
                    ):
                        self._shell_template_cache[engine_name] = entry_name
                        return entry_name

            initial_tpl = self._request_json(
                method="POST",
                url=templates_url,
                project_id=project_id,
                payload={
                    "displayName": "shell-sandbox-template",
                    "defaultContainerEnvironment": {
                        "defaultContainerCategory": "DEFAULT_CONTAINER_CATEGORY_SHELL_SANDBOX",
                    },
                },
            )
            completed_tpl = self._await_operation_if_needed(
                initial_response=initial_tpl,
                location=location,
                project_id=project_id,
            )
            nested_tpl_resp = completed_tpl.get("response")
            nested_tpl_name = (
                nested_tpl_resp.get("name")
                if isinstance(nested_tpl_resp, Mapping)
                else None
            )
            resolved_template = str(
                nested_tpl_name or completed_tpl.get("name") or ""
            ).strip()
            if (
                not resolved_template
                or "/sandboxEnvironmentTemplates/" not in resolved_template
            ):
                raise SandboxUnavailableError(
                    "agent sandbox in GeminiEnvironmentTemplates response missing "
                    "valid template resource name."
                )
            self._shell_template_cache[engine_name] = resolved_template
            return resolved_template

    def create_sandbox(
        self,
        *,
        project_id: str,
        location: str,
        taint: SandboxTaintTuple,
        language: SandboxLanguage,
        ttl_seconds: float,
    ) -> SandboxBackendCreateResult:
        """Creates an isolated Gemini `SandboxEnvironment` with explicit TTL and zero secrets.

        Args:
            project_id: Google Cloud project ID.
            location: Regional Vertex AI location.
            taint: Session taint tuple `(tenant_id, user_sub, agent_id, session_id)`.
            language: Target sandbox language (`python`, `javascript`, or `bash`).
            ttl_seconds: Server-side automatic garbage-collection TTL.

        Returns:
            `SandboxBackendCreateResult` naming the created `sandboxEnvironments/{id}` resource.

        Raises:
            SandboxUnavailableError: `AGENT_SANDBOX_REASONING_ENGINE_NAME` unset, or the API failed.
        """
        if not self._use_live_api():
            return self._hermetic_fallback.create_sandbox(
                project_id=project_id,
                location=location,
                taint=taint,
                language=language,
                ttl_seconds=ttl_seconds,
            )

        effective_project = self._resolved_project_id(project_id)
        effective_location = self._resolved_location(location)
        engine_name = self._normalized_engine_name(
            project_id=effective_project, location=effective_location
        )
        raw_template = (
            os.getenv("AGENT_SANDBOX_SHELL_TEMPLATE", "")
            if language == SandboxLanguage.BASH
            else os.getenv("AGENT_SANDBOX_CODE_TEMPLATE", "")
        ).strip()
        template_resource_name = (
            (
                raw_template
                if raw_template.startswith("projects/")
                else f"{engine_name}/sandboxEnvironmentTemplates/{raw_template}"
            )
            if raw_template
            else ""
        )
        create_body: dict[str, object] = {
            "displayName": f"cymbal-{taint.tenant_id[:20]}-{taint.session_id[:16]}",
            "ttl": f"{int(ttl_seconds)}s",
        }
        if language == SandboxLanguage.BASH:
            if not template_resource_name:
                template_resource_name = self._ensure_shell_sandbox_template(
                    engine_name=engine_name,
                    location=effective_location,
                    project_id=effective_project,
                )
            create_body["sandboxEnvironmentTemplate"] = template_resource_name
            create_body["spec"] = {"shellEnvironment": {}}
        elif template_resource_name:
            create_body["sandboxEnvironmentTemplate"] = template_resource_name
        elif language == SandboxLanguage.JAVASCRIPT:
            create_body["spec"] = {
                "codeExecutionEnvironment": {
                    "codeLanguage": "LANGUAGE_JAVASCRIPT",
                }
            }
            template_resource_name = "inline:codeExecutionEnvironment"
        else:
            create_body["spec"] = {
                "codeExecutionEnvironment": {
                    "codeLanguage": "LANGUAGE_PYTHON",
                }
            }
            template_resource_name = "inline:codeExecutionEnvironment"

        create_url = f"{self._api_base_url(effective_location)}/{engine_name}/sandboxEnvironments"
        initial_response = self._request_json(
            method="POST",
            url=create_url,
            project_id=effective_project,
            payload=create_body,
        )
        completed_response = self._await_operation_if_needed(
            initial_response=initial_response,
            location=effective_location,
            project_id=effective_project,
        )
        nested_resp = completed_response.get("response")
        nested_name = (
            nested_resp.get("name")
            if isinstance(nested_resp, Mapping)
            else None
        )
        resource_name = str(
            nested_name or completed_response.get("name") or ""
        ).strip()
        if not resource_name or "/sandboxEnvironments/" not in resource_name:
            raise SandboxUnavailableError(
                "Gemini create_sandbox response missing valid sandboxEnvironments resource name."
            )
        nested_tpl = (
            nested_resp.get("sandboxEnvironmentTemplate")
            if isinstance(nested_resp, Mapping)
            else None
        )
        resolved_tpl = str(
            nested_tpl
            or completed_response.get("sandboxEnvironmentTemplate")
            or ""
        ).strip()
        if resolved_tpl:
            template_resource_name = resolved_tpl
        sandbox_id = resource_name.rsplit("/", 1)[-1]
        return SandboxBackendCreateResult(
            sandbox_id=sandbox_id,
            sandbox_resource_name=resource_name,
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
        """Executes `code` inside `sandbox_resource_name` via the Gemini `:execute` proxy.

        Args:
            sandbox_resource_name: Full `sandboxEnvironments/{id}` resource name.
            language: Target execution language.
            code: Validated code or diagnostic command.
            readonly_input_json: Sanitized read-only JSON input payload.

        Returns:
            `SandboxBackendExecutionResult` containing stdout, stderr, and exit code.

        Raises:
            SandboxUnavailableError: When the agent sandbox in Gemini execution call fails.
        """
        if not self._use_live_api():
            return self._hermetic_fallback.execute_workload(
                sandbox_resource_name=sandbox_resource_name,
                language=language,
                code=code,
                readonly_input_json=readonly_input_json,
            )

        effective_project = self._resolved_project_id()
        effective_location = self._resolved_location()
        exec_url = f"{self._api_base_url(effective_location)}/{sandbox_resource_name.strip('/')}/:execute"
        if language == SandboxLanguage.BASH:
            # Vertex Gemini `execute_bash` routes through the control-plane `:execute` proxy using
            # three ordered Chunks, avoiding direct data-plane URL access or ADC forwarding.
            input_chunks: list[dict[str, object]] = [
                {
                    "mimeType": "application/x.sandbox-request-uri",
                    "data": base64.b64encode(b"/exec").decode("ascii"),
                },
                {
                    "mimeType": "application/x.sandbox-request-port",
                    "data": base64.b64encode(b"8080").decode("ascii"),
                },
                {
                    "mimeType": "application/json",
                    "data": base64.b64encode(
                        json.dumps({"command": code}).encode("utf-8")
                    ).decode("ascii"),
                },
            ]
            backend_mode = "LIVE_AGENT_SANDBOX_SHELL_SANDBOX_ENVIRONMENT"
        else:
            encoded_code_chunk = base64.b64encode(
                json.dumps({"code": code}).encode("utf-8")
            ).decode("ascii")
            input_chunks = [
                {"mimeType": "application/json", "data": encoded_code_chunk},
            ]
            if readonly_input_json:
                input_chunks.append(
                    {
                        "mimeType": "application/json",
                        "data": base64.b64encode(
                            readonly_input_json.encode("utf-8")
                        ).decode("ascii"),
                        "metadata": {
                            "attributes": {
                                "file_name": base64.b64encode(
                                    b"readonly_input.json"
                                ).decode("ascii")
                            }
                        },
                    }
                )
            backend_mode = "LIVE_AGENT_SANDBOX_SANDBOX_ENVIRONMENT"

        response_data = self._request_json(
            method="POST",
            url=exec_url,
            project_id=effective_project,
            payload={"inputs": input_chunks},
        )
        outputs_raw = response_data.get("outputs")
        if isinstance(outputs_raw, list):
            stdout_parts: list[str] = []
            stderr_parts: list[str] = []
            resolved_exit = 0
            for chunk_entry in outputs_raw:
                out_part, err_part, exit_candidate = _decode_chunk_output_item(
                    chunk_entry
                )
                if out_part:
                    stdout_parts.append(out_part)
                if err_part:
                    stderr_parts.append(err_part)
                if exit_candidate is not None:
                    resolved_exit = exit_candidate
            return SandboxBackendExecutionResult(
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
                exit_code=resolved_exit,
                backend_mode=backend_mode,
            )

        outputs_map = (
            outputs_raw if isinstance(outputs_raw, Mapping) else response_data
        )
        stdout_text = str(
            outputs_map.get("stdout")
            or outputs_map.get("msg_out")
            or json.dumps(dict(outputs_map), sort_keys=True)
        )
        stderr_text = str(
            outputs_map.get("stderr") or outputs_map.get("msg_err") or ""
        )
        exit_code_raw = outputs_map.get(
            "exitCode",
            outputs_map.get("exit_code", outputs_map.get("returncode", 0)),
        )
        exit_code_int = _safe_int(exit_code_raw, default=0) or 0
        return SandboxBackendExecutionResult(
            stdout=stdout_text,
            stderr=stderr_text,
            exit_code=exit_code_int,
            backend_mode=backend_mode,
        )

    def pause_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Pauses `sandbox_resource_name` (`STATE_PAUSED`) to release active compute.

        Args:
            sandbox_resource_name: Full `sandboxEnvironments/{id}` resource name.

        Returns:
            `True` when paused cleanly.
        """
        if not self._use_live_api():
            return self._hermetic_fallback.pause_sandbox(
                sandbox_resource_name=sandbox_resource_name
            )
        effective_location = self._resolved_location()
        effective_project = self._resolved_project_id()
        pause_url = f"{self._api_base_url(effective_location)}/{sandbox_resource_name.strip('/')}/:pause"
        initial_pause = self._request_json(
            method="POST",
            url=pause_url,
            project_id=effective_project,
            payload={},
        )
        self._await_operation_if_needed(
            initial_response=initial_pause,
            location=effective_location,
            project_id=effective_project,
        )
        return True

    def resume_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Resumes a `STATE_PAUSED` `sandbox_resource_name` back to `STATE_RUNNING`.

        Args:
            sandbox_resource_name: Full `sandboxEnvironments/{id}` resource name.

        Returns:
            `True` when resumed cleanly.
        """
        if not self._use_live_api():
            return self._hermetic_fallback.resume_sandbox(
                sandbox_resource_name=sandbox_resource_name
            )
        effective_location = self._resolved_location()
        effective_project = self._resolved_project_id()
        resume_url = f"{self._api_base_url(effective_location)}/{sandbox_resource_name.strip('/')}/:resume"
        initial_resume = self._request_json(
            method="POST",
            url=resume_url,
            project_id=effective_project,
            payload={},
        )
        self._await_operation_if_needed(
            initial_response=initial_resume,
            location=effective_location,
            project_id=effective_project,
        )
        return True

    def delete_sandbox(self, *, sandbox_resource_name: str) -> bool:
        """Permanently deletes `sandbox_resource_name` so it is never recycled.

        Args:
            sandbox_resource_name: Full `sandboxEnvironments/{id}` resource name.

        Returns:
            `True` when deleted cleanly.
        """
        if not self._use_live_api():
            return self._hermetic_fallback.delete_sandbox(
                sandbox_resource_name=sandbox_resource_name
            )
        effective_location = self._resolved_location()
        effective_project = self._resolved_project_id()
        delete_url = f"{self._api_base_url(effective_location)}/{sandbox_resource_name.strip('/')}"
        initial_delete = self._request_json(
            method="DELETE",
            url=delete_url,
            project_id=effective_project,
            payload=None,
        )
        self._await_operation_if_needed(
            initial_response=initial_delete,
            location=effective_location,
            project_id=effective_project,
        )
        return True
