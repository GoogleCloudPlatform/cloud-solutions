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

# pylint: disable=import-outside-toplevel,line-too-long,try-except-raise

"""Session-tainted Claim-and-Taint lifecycle manager (`GeminiAgentSandboxManager`)."""

from __future__ import annotations

import inspect
import json
import threading
import time
from collections.abc import Callable, Mapping

from agents import context as agent_context
from agents import interceptors
from agents.platform_config import get_platform_config, resolve_project_id
from agents.registry import (
    TOOL_REGISTRY,
    AgentRegistryPDP,
    is_tool_tenant_allowed,
)
from agents.sandbox.gemini_client import LiveGeminiAgentSandboxClient
from agents.sandbox.models import (
    DEFAULT_SANDBOX_TTL_SECONDS,
    ENTERPRISE_MAX_ACTIVE_SANDBOXES,
    MAX_SANDBOX_TTL_SECONDS,
    STANDARD_MAX_ACTIVE_SANDBOXES,
    SandboxBackendClient,
    SandboxBackendCreateResult,
    SandboxBackendExecutionResult,
    SandboxEnvironmentRecord,
    SandboxLanguage,
    SandboxLifecycleState,
    SandboxTaintTuple,
    SandboxUnavailableError,
)
from agents.sandbox.screener import assert_zero_credentials_and_egress_safe


def _assert_synchronous_backend(backend: object) -> None:
    """Rejects coroutine objects or async methods on `backend` so checks never fail open."""
    if inspect.iscoroutine(backend) or inspect.iscoroutinefunction(backend):
        raise TypeError(
            "E_ASYNC_SANDBOX_BACKEND_FORBIDDEN: SandboxBackendClient must be synchronous."
        )
    for method_name in (
        "create_sandbox",
        "execute_workload",
        "pause_sandbox",
        "resume_sandbox",
        "delete_sandbox",
    ):
        method_attr = getattr(backend, method_name, None)
        if not callable(method_attr):
            raise TypeError(
                f"E_INVALID_SANDBOX_BACKEND: Missing required method '{method_name}'."
            )
        if inspect.iscoroutinefunction(method_attr):
            raise TypeError(
                f"E_ASYNC_SANDBOX_BACKEND_FORBIDDEN: Method '{method_name}' cannot be async."
            )


class GeminiAgentSandboxManager:
    """Manages per-session Gemini `sandboxEnvironments` with Claim-and-Taint isolation."""

    def __init__(
        self,
        *,
        backend: SandboxBackendClient | None = None,
        registry_pdp: AgentRegistryPDP | None = None,
        clock_fn: Callable[[], float] = time.monotonic,
        default_ttl_seconds: float = DEFAULT_SANDBOX_TTL_SECONDS,
        standard_max_sandboxes: int = STANDARD_MAX_ACTIVE_SANDBOXES,
        enterprise_max_sandboxes: int = ENTERPRISE_MAX_ACTIVE_SANDBOXES,
        project_id: str | None = None,
        location: str | None = None,
    ) -> None:
        """Initializes the session-tainted Agent Sandbox in Gemini manager.

        Args:
            backend: `SandboxBackendClient` (`LiveGeminiAgentSandboxClient` in live mode).
            registry_pdp: `AgentRegistryPDP` enforcing `Tenant ∩ User ∩ Agent` access.
            clock_fn: Monotonic clock callable returning seconds (`time.monotonic`).
            default_ttl_seconds: Per-sandbox TTL (`<= 3600s`, default `900s`).
            standard_max_sandboxes: Max concurrent sandboxes for Standard-tier tenants (`5`).
            enterprise_max_sandboxes: Max concurrent sandboxes for Enterprise-tier tenants (`20`).
            project_id: Optional GCP project override (defaults to `resolve_project_id()`).
            location: Optional GCP region override (defaults to platform config region).

        Raises:
            TypeError: If `backend` is a coroutine or exposes async methods.
            ValueError: If `default_ttl_seconds` or tier limits are non-positive or out of bounds.
        """
        resolved_backend: SandboxBackendClient = (
            LiveGeminiAgentSandboxClient(
                project_id=project_id, location=location
            )
            if backend is None
            else backend
        )
        _assert_synchronous_backend(resolved_backend)
        if (
            default_ttl_seconds <= 0
            or default_ttl_seconds > MAX_SANDBOX_TTL_SECONDS
        ):
            raise ValueError(
                f"default_ttl_seconds must be in (0, {MAX_SANDBOX_TTL_SECONDS}], "
                f"got {default_ttl_seconds}."
            )
        if (
            standard_max_sandboxes < 1
            or enterprise_max_sandboxes < standard_max_sandboxes
        ):
            raise ValueError("Invalid per-tenant sandbox bulkhead limits.")

        self._backend = resolved_backend
        self._registry_pdp = (
            AgentRegistryPDP() if registry_pdp is None else registry_pdp
        )
        self._clock = clock_fn
        self._default_ttl = float(default_ttl_seconds)
        self._standard_max = int(standard_max_sandboxes)
        self._enterprise_max = int(enterprise_max_sandboxes)
        self._explicit_project_id = project_id
        self._explicit_location = location

        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._in_flight_taints: set[SandboxTaintTuple] = set()
        self._session_sandboxes: dict[
            SandboxTaintTuple, SandboxEnvironmentRecord
        ] = {}
        self._sandbox_id_owners: dict[str, SandboxTaintTuple] = {}
        self._destroyed_sandbox_ids: set[str] = set()
        self._eviction_generation: dict[str, int] = {}

        from agents.workload_identity import register_agent_eviction_target

        agent_context.register_tenant_eviction_target(self)
        register_agent_eviction_target(self)

    def _assert_caller_authorized(
        self,
        *,
        envelope: agent_context.ContextEnvelope,
        agent_id: str,
        language: SandboxLanguage | None = None,
    ) -> SandboxTaintTuple:
        """Runs synchronous onboarding, `AgentRegistryPDP`, scope, and role RBAC checks."""
        if not isinstance(envelope, agent_context.ContextEnvelope):
            raise PermissionError(
                "403 Forbidden: E_UNVERIFIED_ENVELOPE: ContextEnvelope required."
            )

        tenant_id = envelope.tenant.tenant_id
        if not tenant_id or tenant_id not in agent_context.TENANT_DIRECTORY:
            raise PermissionError(
                "403 Forbidden: E_TENANT_OFFBOARDED: Tenant is not active in TENANT_DIRECTORY."
            )
        if not envelope.security.sub or not envelope.request.session_id:
            raise PermissionError(
                "403 Forbidden: E_MISSING_SESSION_PRINCIPAL: Verified sub and session_id required."
            )

        self._registry_pdp.verify_agent_access(
            tenant_id=tenant_id,
            agent_id=agent_id,
            caller_scopes=envelope.tenant.authorized_scopes,
        )

        sandbox_tool = TOOL_REGISTRY.get("execute_diagnostic_sandbox")
        required_scope = (
            sandbox_tool.required_scope
            if sandbox_tool is not None
            else "2lo:cymbal.sandbox.execute"
        )
        caller_scopes = set(envelope.tenant.authorized_scopes)
        tenant_allowed = sandbox_tool is None or is_tool_tenant_allowed(
            tenant_id, sandbox_tool
        )
        entitled_tools = self._registry_pdp.get_entitled_tools(
            tenant_id=tenant_id,
            agent_id=agent_id,
            caller_scopes=envelope.tenant.authorized_scopes,
        )
        if (
            not tenant_allowed
            or required_scope not in caller_scopes
            or "execute_diagnostic_sandbox" not in entitled_tools
        ):
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_SCOPE_DENIED: "
                f"Caller lacks '{required_scope}' entitlement for sandbox execution."
            )

        if (
            language == SandboxLanguage.BASH
            and envelope.security.user_role != "sre_admin"
        ):
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_SHELL_ROLE_DENIED: "
                "Interactive bash sandboxes require role 'sre_admin'."
            )

        return SandboxTaintTuple(
            tenant_id=tenant_id,
            user_sub=envelope.security.sub,
            agent_id=agent_id,
            session_id=envelope.request.session_id,
            language=(
                language if language is not None else SandboxLanguage.PYTHON
            ),
        )

    def _tier_bulkhead_limit(
        self, envelope: agent_context.ContextEnvelope
    ) -> int:
        if (
            envelope.tenant.subscription_tier
            == agent_context.SubscriptionTier.ENTERPRISE
        ):
            return self._enterprise_max
        return self._standard_max

    def _wait_and_reserve_taint_locked(self, taint: SandboxTaintTuple) -> None:
        """Serializes concurrent lifecycle operations on the same session `taint`."""
        while taint in self._in_flight_taints:
            self._cond.wait()

    def _release_taint_reservation(self, taint: SandboxTaintTuple) -> None:
        """Releases an in-flight session taint reservation and wakes waiting threads."""
        with self._cond:
            self._in_flight_taints.discard(taint)
            self._cond.notify_all()

    def _release_taints_reservation(
        self, taints: list[SandboxTaintTuple]
    ) -> None:
        """Releases multiple in-flight session taint reservations and wakes waiters."""
        if not taints:
            return
        with self._cond:
            for taint in taints:
                self._in_flight_taints.discard(taint)
            self._cond.notify_all()

    def _purge_expired_locked(
        self, now: float
    ) -> list[SandboxEnvironmentRecord]:
        """Removes sandboxes whose `expires_at_monotonic <= now` while holding `self._lock`."""
        expired_records: list[SandboxEnvironmentRecord] = []
        expired_taints = [
            taint
            for taint, record in self._session_sandboxes.items()
            if record.expires_at_monotonic <= now
            and taint not in self._in_flight_taints
        ]
        for taint in expired_taints:
            record = self._session_sandboxes.pop(taint)
            self._destroyed_sandbox_ids.add(record.sandbox_id)
            expired_records.append(record)
        return expired_records

    def _destroy_backend_records(
        self, records: list[SandboxEnvironmentRecord]
    ) -> None:
        """Invokes `delete_sandbox` outside `self._lock` for expired or evicted sandboxes."""
        for record in records:
            try:
                delete_result = self._backend.delete_sandbox(
                    sandbox_resource_name=record.sandbox_resource_name
                )
                if inspect.iscoroutine(delete_result):
                    delete_result.close()
            except (OSError, TimeoutError, SandboxUnavailableError):
                continue

    def _call_backend_bool(
        self, fn: Callable[..., object], **kwargs: object
    ) -> bool:
        """Calls a boolean backend method and enforces strict `True` vs `(False, None)` contract."""
        try:
            raw_result = fn(**kwargs)
        except (OSError, TimeoutError) as transport_exc:
            raise SandboxUnavailableError(
                f"Sandbox backend transport error ({type(transport_exc).__name__})."
            ) from transport_exc
        if inspect.iscoroutine(raw_result):
            raw_result.close()
            raise SandboxUnavailableError(
                "Async coroutine returned by synchronous sandbox backend."
            )
        if raw_result is True:
            return True
        if raw_result in (False, None):
            return False
        raise SandboxUnavailableError(
            f"Unexpected boolean return type from sandbox backend: {type(raw_result).__name__}."
        )

    def _screen_and_redact_output(
        self,
        *,
        tenant_id: str,
        language: SandboxLanguage,
        raw_text: str,
    ) -> str:
        """Screens sandbox output for indirect prompt injection and runs DLP redaction."""
        if not raw_text:
            return ""
        interceptors.screen_tool_output_for_indirect_injection(
            tool_name="gemini_agent_sandbox",
            raw_output=raw_text,
        )
        return str(
            interceptors.egress_dlp_and_nlc_guardrail(
                tenant_id=tenant_id,
                tool_name="gemini_agent_sandbox",
                tool_args={"language": str(language)},
                raw_output=raw_text,
            )
        )

    def execute_in_session_sandbox(
        self,
        *,
        envelope: agent_context.ContextEnvelope,
        agent_id: str,
        code: str,
        language: SandboxLanguage | str = SandboxLanguage.PYTHON,
        readonly_tool_output: Mapping[str, object] | None = None,
        environment_variables: Mapping[str, str] | None = None,
        expected_sandbox_id: str | None = None,
    ) -> dict[str, object]:
        """Claims or reuses the caller session's tainted agent sandbox and runs `code` safely.

        Args:
            envelope: Verified `ContextEnvelope` for the active HTTP/MCP turn.
            agent_id: Verified routed `agent_id` executing the turn.
            code: Diagnostic Python, JavaScript, or Bash snippet to run inside `/workspace`.
            language: Target sandbox language (`python`, `javascript`, or `bash`).
            readonly_tool_output: Optional sanitized MCP tool output passed as read-only JSON.
            environment_variables: Optional non-secret env vars checked for zero tokens.
            expected_sandbox_id: Optional pinned `sandbox_id` to verify against cross-tenant hijack.

        Returns:
            Dictionary receipt containing sandbox resource identifiers, taint metadata, execution
            counters, indirect-injection status, and Cloud DLP-redacted stdout and stderr.

        Raises:
            ValueError: If `code`, `language`, or `readonly_tool_output` is invalid.
            PermissionError: On offboarded tenant, unentitled agent/role, credential/metadata
                injection, cross-tenant sandbox hijack, or per-tenant bulkhead exhaustion (`429`).
            SandboxUnavailableError: On backend transport failure or warm-pool exhaustion (`503`).
        """
        resolved_language = SandboxLanguage(str(language).lower())
        taint = self._assert_caller_authorized(
            envelope=envelope,
            agent_id=agent_id,
            language=resolved_language,
        )
        if readonly_tool_output is not None and not isinstance(
            readonly_tool_output, Mapping
        ):
            raise ValueError(
                "E_SANDBOX_INVALID_INPUT: readonly_tool_output must be a JSON object mapping."
            )
        serialized_input = json.dumps(
            readonly_tool_output or {}, sort_keys=True, default=str
        )
        assert_zero_credentials_and_egress_safe(
            code=code,
            environment_variables=environment_variables,
            readonly_input_json=serialized_input,
        )

        expired_records: list[SandboxEnvironmentRecord] = []
        reserved = False
        created_new_record: SandboxEnvironmentRecord | None = None
        try:
            with self._cond:
                self._wait_and_reserve_taint_locked(taint)
                now = float(self._clock())
                generation_before = self._eviction_generation.get(
                    taint.tenant_id, 0
                )
                expired_records = self._purge_expired_locked(now)
                existing_record = self._session_sandboxes.get(taint)

                if expected_sandbox_id is not None:
                    known_owner = self._sandbox_id_owners.get(
                        expected_sandbox_id
                    )
                    if known_owner is not None and known_owner != taint:
                        raise PermissionError(
                            "403 Forbidden: E_CROSS_TENANT_SANDBOX_TAINT_VIOLATION: "
                            "Requested sandbox_id is permanently tainted to a different session."
                        )
                    if expected_sandbox_id in self._destroyed_sandbox_ids:
                        raise PermissionError(
                            "403 Forbidden: E_SANDBOX_ALREADY_DESTROYED: Tainted sandboxes "
                            "are destroyed after TTL/release and cannot be reattached."
                        )
                    if (
                        existing_record is None
                        or existing_record.sandbox_id != expected_sandbox_id
                    ):
                        raise PermissionError(
                            "403 Forbidden: E_SANDBOX_SESSION_PIN_MISMATCH: "
                            "Session does not own the requested pinned sandbox_id."
                        )

                if existing_record is None:
                    active_tenant_taints = {
                        active_taint
                        for active_taint in self._session_sandboxes
                        if active_taint.tenant_id == taint.tenant_id
                    } | {
                        pending_taint
                        for pending_taint in self._in_flight_taints
                        if pending_taint.tenant_id == taint.tenant_id
                    }
                    tier_limit = self._tier_bulkhead_limit(envelope)
                    if len(active_tenant_taints) >= tier_limit:
                        raise PermissionError(
                            "429 Too Many Requests: E_SANDBOX_BULKHEAD_EXHAUSTED: "
                            f"Tenant exceeded active sandbox bulkhead ({tier_limit})."
                        )

                self._in_flight_taints.add(taint)
                reserved = True
        finally:
            if expired_records:
                self._destroy_backend_records(expired_records)

        reused_session_sandbox = existing_record is not None
        try:
            if existing_record is not None:
                working_record = existing_record
                if existing_record.state == SandboxLifecycleState.PAUSED:
                    resumed = self._call_backend_bool(
                        self._backend.resume_sandbox,
                        sandbox_resource_name=existing_record.sandbox_resource_name,
                    )
                    if not resumed:
                        raise SandboxUnavailableError(
                            "Failed to resume paused Gemini SandboxEnvironment."
                        )
                    working_record = SandboxEnvironmentRecord(
                        sandbox_id=existing_record.sandbox_id,
                        sandbox_resource_name=existing_record.sandbox_resource_name,
                        template_resource_name=existing_record.template_resource_name,
                        taint=existing_record.taint,
                        state=SandboxLifecycleState.RUNNING,
                        created_at_monotonic=existing_record.created_at_monotonic,
                        expires_at_monotonic=existing_record.expires_at_monotonic,
                        execution_count=existing_record.execution_count,
                        language=resolved_language,
                        internet_access_enabled=False,
                        runtime_class="gvisor",
                    )
                    with self._cond:
                        current_existing = self._session_sandboxes.get(taint)
                        if (
                            current_existing is not None
                            and current_existing.sandbox_id
                            == working_record.sandbox_id
                            and working_record.sandbox_id
                            not in self._destroyed_sandbox_ids
                        ):
                            self._session_sandboxes[taint] = working_record
            else:
                effective_project = (
                    self._explicit_project_id or resolve_project_id()
                )
                effective_location = (
                    self._explicit_location or get_platform_config().gcp.region
                )
                try:
                    created_raw = self._backend.create_sandbox(
                        project_id=effective_project,
                        location=effective_location,
                        taint=taint,
                        language=resolved_language,
                        ttl_seconds=self._default_ttl,
                    )
                except (OSError, TimeoutError) as create_exc:
                    raise SandboxUnavailableError(
                        f"Gemini SandboxEnvironment creation failed ({type(create_exc).__name__})."
                    ) from create_exc

                if inspect.iscoroutine(created_raw):
                    created_raw.close()
                    raise SandboxUnavailableError(
                        "Async coroutine returned from create_sandbox."
                    )
                if not isinstance(created_raw, SandboxBackendCreateResult):
                    raise SandboxUnavailableError(
                        "Backend create_sandbox violated SandboxBackendCreateResult contract."
                    )

                created_now = float(self._clock())
                created_new_record = SandboxEnvironmentRecord(
                    sandbox_id=created_raw.sandbox_id,
                    sandbox_resource_name=created_raw.sandbox_resource_name,
                    template_resource_name=created_raw.template_resource_name,
                    taint=taint,
                    state=SandboxLifecycleState.RUNNING,
                    created_at_monotonic=created_now,
                    expires_at_monotonic=created_now + self._default_ttl,
                    execution_count=0,
                    language=resolved_language,
                    internet_access_enabled=False,
                    runtime_class="gvisor",
                )
                with self._cond:
                    prior_owner = self._sandbox_id_owners.get(
                        created_raw.sandbox_id
                    )
                    if prior_owner is not None and prior_owner != taint:
                        raise PermissionError(
                            "403 Forbidden: E_CROSS_TENANT_SANDBOX_TAINT_VIOLATION: "
                            "Backend returned a sandbox_id already tainted to another session."
                        )
                    if created_raw.sandbox_id in self._destroyed_sandbox_ids:
                        raise SandboxUnavailableError(
                            "Backend attempted to recycle a destroyed sandbox_id."
                        )
                    current_generation = self._eviction_generation.get(
                        taint.tenant_id, 0
                    )
                    if (
                        taint.tenant_id not in agent_context.TENANT_DIRECTORY
                        or current_generation != generation_before
                    ):
                        raise PermissionError(
                            "403 Forbidden: E_TENANT_OFFBOARDED: "
                            "Tenant was offboarded during sandbox claim."
                        )
                working_record = created_new_record

            try:
                execution_raw = self._backend.execute_workload(
                    sandbox_resource_name=working_record.sandbox_resource_name,
                    language=resolved_language,
                    code=code,
                    readonly_input_json=serialized_input,
                )
            except PermissionError:
                raise
            except ValueError:
                raise
            except (OSError, TimeoutError) as exec_exc:
                raise SandboxUnavailableError(
                    f"Gemini SandboxEnvironment execution failed ({type(exec_exc).__name__})."
                ) from exec_exc

            if inspect.iscoroutine(execution_raw):
                execution_raw.close()
                raise SandboxUnavailableError(
                    "Async coroutine returned from execute_workload."
                )
            if not isinstance(execution_raw, SandboxBackendExecutionResult):
                raise SandboxUnavailableError(
                    "Backend execute_workload violated SandboxBackendExecutionResult contract."
                )

            dlp_redacted_stdout = self._screen_and_redact_output(
                tenant_id=taint.tenant_id,
                language=resolved_language,
                raw_text=execution_raw.stdout,
            )
            dlp_redacted_stderr = self._screen_and_redact_output(
                tenant_id=taint.tenant_id,
                language=resolved_language,
                raw_text=execution_raw.stderr,
            )

            committed_record = SandboxEnvironmentRecord(
                sandbox_id=working_record.sandbox_id,
                sandbox_resource_name=working_record.sandbox_resource_name,
                template_resource_name=working_record.template_resource_name,
                taint=working_record.taint,
                state=SandboxLifecycleState.RUNNING,
                created_at_monotonic=working_record.created_at_monotonic,
                expires_at_monotonic=working_record.expires_at_monotonic,
                execution_count=working_record.execution_count + 1,
                language=resolved_language,
                internet_access_enabled=False,
                runtime_class="gvisor",
            )
            with self._cond:
                current_generation = self._eviction_generation.get(
                    taint.tenant_id, 0
                )
                if (
                    taint.tenant_id not in agent_context.TENANT_DIRECTORY
                    or current_generation != generation_before
                ):
                    raise PermissionError(
                        "403 Forbidden: E_TENANT_OFFBOARDED: "
                        "Tenant was offboarded during sandbox execution."
                    )
                self._session_sandboxes[taint] = committed_record
                self._sandbox_id_owners[committed_record.sandbox_id] = taint
                created_new_record = None
        except Exception:
            if created_new_record is not None:
                with self._cond:
                    self._session_sandboxes.pop(taint, None)
                    self._destroyed_sandbox_ids.add(
                        created_new_record.sandbox_id
                    )
                self._destroy_backend_records([created_new_record])
            raise
        finally:
            if reserved:
                self._release_taint_reservation(taint)

        return {
            "sandbox_id": committed_record.sandbox_id,
            "sandbox_resource_name": committed_record.sandbox_resource_name,
            "template_resource_name": committed_record.template_resource_name,
            "state": str(committed_record.state),
            "runtime_class": committed_record.runtime_class,
            "language": str(resolved_language),
            "reused_session_sandbox": reused_session_sandbox,
            "execution_count": committed_record.execution_count,
            "ttl_seconds": self._default_ttl,
            "zero_credentials_mounted": True,
            "internet_access_enabled": committed_record.internet_access_enabled,
            "taint": {
                "tenant_id": taint.tenant_id,
                "agent_id": taint.agent_id,
                "session_id": taint.session_id,
                "language": str(taint.language),
            },
            "exit_code": execution_raw.exit_code,
            "backend_mode": execution_raw.backend_mode,
            "sanitized_stdout": dlp_redacted_stdout,
            "sanitized_stderr": dlp_redacted_stderr,
        }

    def _acquire_lifecycle_records(
        self,
        *,
        envelope: agent_context.ContextEnvelope,
        agent_id: str,
        language: SandboxLanguage | str | None,
    ) -> list[SandboxEnvironmentRecord]:
        """Authorizes caller, purges expired sandboxes, and reserves matching records."""
        resolved_language = (
            SandboxLanguage(str(language).lower())
            if language is not None
            else None
        )
        base_taint = self._assert_caller_authorized(
            envelope=envelope,
            agent_id=agent_id,
            language=resolved_language,
        )
        expired_records: list[SandboxEnvironmentRecord] = []
        try:
            with self._cond:
                if resolved_language is not None:
                    self._wait_and_reserve_taint_locked(base_taint)
                else:
                    while any(
                        pending.matches_session_principal(base_taint)
                        for pending in self._in_flight_taints
                    ):
                        self._cond.wait()
                now = float(self._clock())
                expired_records = self._purge_expired_locked(now)
                if resolved_language is not None:
                    rec = self._session_sandboxes.get(base_taint)
                    records = [rec] if rec is not None else []
                else:
                    records = sorted(
                        (
                            rec
                            for cand_taint, rec in self._session_sandboxes.items()
                            if cand_taint.matches_session_principal(base_taint)
                        ),
                        key=lambda r: (
                            r.created_at_monotonic,
                            str(r.language),
                            r.sandbox_id,
                        ),
                    )
                for rec in records:
                    self._in_flight_taints.add(rec.taint)
        finally:
            if expired_records:
                self._destroy_backend_records(expired_records)
        return records

    def pause_session_sandbox(
        self,
        *,
        envelope: agent_context.ContextEnvelope,
        agent_id: str,
        language: SandboxLanguage | str | None = None,
    ) -> dict[str, object]:
        """Pauses the caller session's active Gemini `SandboxEnvironment` (`STATE_PAUSED`).

        Args:
            envelope: Verified `ContextEnvelope` for the caller.
            agent_id: Verified `agent_id` bound to the session sandbox.
            language: Optional language filter (`python`, `javascript`, `bash`); when `None`,
                pauses all active sandboxes for `(tenant_id, user_sub, agent_id, session_id)`.

        Returns:
            Status receipt indicating `STATE_PAUSED` or `NO_ACTIVE_SANDBOX`.

        Raises:
            PermissionError: If caller is unauthorized or tenant is offboarded.
            SandboxUnavailableError: If the backend fails to pause the sandbox.
        """
        records = self._acquire_lifecycle_records(
            envelope=envelope,
            agent_id=agent_id,
            language=language,
        )
        if not records:
            return {"status": "NO_ACTIVE_SANDBOX", "paused": False}

        reserved_taints = [rec.taint for rec in records]
        paused_ids: list[str] = []
        try:
            for record in records:
                if record.state == SandboxLifecycleState.PAUSED:
                    paused_ids.append(record.sandbox_id)
                    continue
                paused_ok = self._call_backend_bool(
                    self._backend.pause_sandbox,
                    sandbox_resource_name=record.sandbox_resource_name,
                )
                if not paused_ok:
                    raise SandboxUnavailableError(
                        "Backend refused to pause active SandboxEnvironment."
                    )

                paused_record = SandboxEnvironmentRecord(
                    sandbox_id=record.sandbox_id,
                    sandbox_resource_name=record.sandbox_resource_name,
                    template_resource_name=record.template_resource_name,
                    taint=record.taint,
                    state=SandboxLifecycleState.PAUSED,
                    created_at_monotonic=record.created_at_monotonic,
                    expires_at_monotonic=record.expires_at_monotonic,
                    execution_count=record.execution_count,
                    language=record.language,
                    internet_access_enabled=record.internet_access_enabled,
                    runtime_class=record.runtime_class,
                )
                with self._cond:
                    current = self._session_sandboxes.get(record.taint)
                    if (
                        current is not None
                        and current.sandbox_id == record.sandbox_id
                        and record.sandbox_id not in self._destroyed_sandbox_ids
                        and record.taint.tenant_id
                        in agent_context.TENANT_DIRECTORY
                    ):
                        self._session_sandboxes[record.taint] = paused_record
                paused_ids.append(record.sandbox_id)
        finally:
            self._release_taints_reservation(reserved_taints)

        receipt: dict[str, object] = {
            "status": str(SandboxLifecycleState.PAUSED),
            "sandbox_id": paused_ids[0],
            "paused": True,
        }
        if len(paused_ids) > 1:
            receipt["sandbox_ids"] = paused_ids
        return receipt

    def release_session_sandbox(
        self,
        *,
        envelope: agent_context.ContextEnvelope,
        agent_id: str,
        language: SandboxLanguage | str | None = None,
    ) -> dict[str, object]:
        """Destroys the caller session's tainted Gemini `SandboxEnvironment` (`STATE_DESTROYED`).

        Args:
            envelope: Verified `ContextEnvelope` for the caller.
            agent_id: Verified `agent_id` bound to the session sandbox.
            language: Optional language filter (`python`, `javascript`, `bash`); when `None`,
                destroys all matching sandboxes for `(tenant_id, user_sub, agent_id, session_id)`.

        Returns:
            Destruction receipt proving the sandbox was destroyed and never returned to a warm pool.

        Raises:
            PermissionError: If caller is unauthorized or tenant is offboarded.
            SandboxUnavailableError: If backend destruction refuses or fails.
        """
        records = self._acquire_lifecycle_records(
            envelope=envelope,
            agent_id=agent_id,
            language=language,
        )
        if not records:
            return {"status": "NO_ACTIVE_SANDBOX", "destroyed": False}

        reserved_taints = [rec.taint for rec in records]
        destroyed_ids: list[str] = []
        try:
            for record in records:
                deleted_ok = self._call_backend_bool(
                    self._backend.delete_sandbox,
                    sandbox_resource_name=record.sandbox_resource_name,
                )
                with self._cond:
                    already_evicted = (
                        record.sandbox_id in self._destroyed_sandbox_ids
                    )
                    if not deleted_ok and not already_evicted:
                        raise SandboxUnavailableError(
                            "Backend refused to delete active SandboxEnvironment."
                        )
                    current = self._session_sandboxes.get(record.taint)
                    if (
                        current is not None
                        and current.sandbox_id == record.sandbox_id
                    ):
                        self._session_sandboxes.pop(record.taint, None)
                    self._destroyed_sandbox_ids.add(record.sandbox_id)
                destroyed_ids.append(record.sandbox_id)
        finally:
            self._release_taints_reservation(reserved_taints)

        receipt: dict[str, object] = {
            "status": str(SandboxLifecycleState.DESTROYED),
            "sandbox_id": destroyed_ids[0],
            "destroyed": True,
            "returned_to_warm_pool": False,
        }
        if len(destroyed_ids) > 1:
            receipt["sandbox_ids"] = destroyed_ids
        return receipt

    def evict_tenant(self, tenant_id: str) -> int:
        """Immediately destroys every active or paused sandbox belonging to `tenant_id`.

        Wired automatically into `offboard_tenant(tenant_id)` via `register_tenant_eviction_target`.

        Args:
            tenant_id: Tenant identifier being offboarded or suspended.

        Returns:
            Count of active/paused sandboxes destroyed for `tenant_id`.
        """
        with self._cond:
            self._eviction_generation[tenant_id] = (
                self._eviction_generation.get(tenant_id, 0) + 1
            )
            matching_taints = [
                taint
                for taint in self._session_sandboxes
                if taint.tenant_id == tenant_id
            ]
            evicted_records: list[SandboxEnvironmentRecord] = []
            for taint in matching_taints:
                record = self._session_sandboxes.pop(taint)
                self._destroyed_sandbox_ids.add(record.sandbox_id)
                evicted_records.append(record)
            self._cond.notify_all()

        self._destroy_backend_records(evicted_records)
        return len(evicted_records)

    def evict_agent(self, agent_id: str) -> int:
        """Immediately destroys every active or paused sandbox tainted to `agent_id` (`C17`)."""
        with self._cond:
            matching_taints = [
                taint
                for taint in self._session_sandboxes
                if taint.agent_id == agent_id
            ]
            evicted_records: list[SandboxEnvironmentRecord] = []
            for taint in matching_taints:
                record = self._session_sandboxes.pop(taint)
                self._destroyed_sandbox_ids.add(record.sandbox_id)
                evicted_records.append(record)
            self._cond.notify_all()

        self._destroy_backend_records(evicted_records)
        return len(evicted_records)
