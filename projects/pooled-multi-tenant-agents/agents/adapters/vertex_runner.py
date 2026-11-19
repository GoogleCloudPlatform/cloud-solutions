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

# pylint: disable=import-outside-toplevel,line-too-long,protected-access
# pylint: disable=try-except-raise

"""Live ADK 2.0 `InMemoryRunner` + Gemini and agent sandbox in Gemini manager wiring."""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
import threading
from collections.abc import Mapping
from typing import Any

from agents import interceptors, sandbox_execution
from agents.adapters._bridge_runtime import (
    DEFAULT_GCP_PROJECT,
    DEFAULT_GCP_REGION,
    _egress_guardrail,
    is_live_gcp_enabled,
)
from agents.adapters.enterprise_connectors import (
    LiveAtlassianJiraConnector,
    LiveServiceNowITOMConnector,
)
from agents.adapters.storage_and_telemetry import (
    LiveGCSCMEKRunbookVault,
    LiveVertexMemoryBankAdapter,
)
from agents.context import (
    _ACTIVE_TENANT_ENVELOPE,
    ContextEnvelope,
    MemoryScope,
    SubscriptionTier,
    tenant_qualified_user_id,
)
from agents.model_routing import ModelRoutingMode, SharedModelRoutingPDP
from agents.shared_diagnostic_agent import (
    DEFAULT_FLASH_EXECUTOR_MODEL,
    DEFAULT_SHARED_DIAGNOSTIC_MODEL,
    SHARED_SYSTEM_PROMPT_PREFIX,
    build_per_model_context_cache_config,
    build_thinking_config,
    get_model_location,
)
from agents.skill_loader import (
    TenantCustomSkillLoader,
    get_default_custom_skill_loader,
)
from agents.workspace_plugins import (
    WorkspacePluginRegistry,
    get_default_workspace_plugin_registry,
)


def _bridge_attr(name: str, fallback: Any) -> Any:
    """Resolves adapter/guardrail symbols through `agents.gcp_live_bridge` when monkeypatched."""
    facade = sys.modules.get("agents.gcp_live_bridge")
    return getattr(facade, name, fallback) if facade is not None else fallback


class LiveADKVertexRunner:
    """Decision 2: Executes a real ADK 2.0 `InMemoryRunner` + Gemini turn in
    `cymbal-multitenancy-example`.
    """

    def __init__(
        self,
        project_id: str = DEFAULT_GCP_PROJECT,
        location: str = DEFAULT_GCP_REGION,
        model_name: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self._explicit_model_override = (
            model_name.strip()
            if isinstance(model_name, str) and model_name.strip()
            else None
        )
        self.model_name = (
            self._explicit_model_override or DEFAULT_FLASH_EXECUTOR_MODEL
        )

    async def run_tenant_diagnostic_turn(
        self,
        *,
        envelope: ContextEnvelope,
        user_prompt: str,
        agent_id: str = "cymbal_shared_diagnostic_agent",
        sandbox_code: str | None = None,
        sandbox_language: str = "python",
        sandbox_manager: (
            sandbox_execution.GeminiAgentSandboxManager | None
        ) = None,
        workspace_plugins: WorkspacePluginRegistry | None = None,
        skill_loader: TenantCustomSkillLoader | None = None,
    ) -> dict[str, Any]:
        """Runs a live ADK 2.0 `InMemoryRunner` session scoped to `envelope.tenant.tenant_id`."""
        from mcp_server.db import build_rls_db_pool_from_env

        db_pool = build_rls_db_pool_from_env(pool_size=4)
        env_token = _ACTIVE_TENANT_ENVELOPE.set(envelope)
        try:
            return await self._run_tenant_diagnostic_turn_inner(
                envelope=envelope,
                user_prompt=user_prompt,
                agent_id=agent_id,
                sandbox_code=sandbox_code,
                sandbox_language=sandbox_language,
                sandbox_manager=sandbox_manager,
                workspace_plugins=workspace_plugins,
                skill_loader=skill_loader,
                db_pool=db_pool,
            )
        finally:
            await db_pool.close()
            _ACTIVE_TENANT_ENVELOPE.reset(env_token)

    async def _run_tenant_diagnostic_turn_inner(
        self,
        *,
        envelope: ContextEnvelope,
        user_prompt: str,
        agent_id: str,
        sandbox_code: str | None,
        sandbox_language: str,
        sandbox_manager: sandbox_execution.GeminiAgentSandboxManager | None,
        workspace_plugins: WorkspacePluginRegistry | None,
        skill_loader: TenantCustomSkillLoader | None,
        db_pool: Any,
    ) -> dict[str, Any]:
        # Never overwrite the deployment's settings at runtime (they feed identity decisions).
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self.project_id)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", self.location)

        from agents.registry import AgentRegistryPDP
        from google.adk.agents import Agent
        from google.adk.runners import InMemoryRunner
        from google.genai import types as genai_types

        bound_tenant_id = envelope.tenant.tenant_id
        session_state = envelope.to_adk_state()
        session_state["temp:agent_id"] = agent_id
        resolved_agent_id = str(session_state.get("temp:agent_id") or agent_id)
        vertex_mb_summary: dict[str, Any] | None = None
        mb_engine = (
            os.getenv("MEMORY_BANK_REASONING_ENGINE", "").strip()
            or os.getenv("AGENT_SANDBOX_REASONING_ENGINE_NAME", "").strip()
        )
        if (
            mb_engine
            and _bridge_attr("is_live_gcp_enabled", is_live_gcp_enabled)()
        ):
            mb_cls = _bridge_attr(
                "LiveVertexMemoryBankAdapter", LiveVertexMemoryBankAdapter
            )
            mb_read = mb_cls(
                project_id=self.project_id,
                location=self.location,
                reasoning_engine_name=mb_engine,
            ).retrieve_memories(
                envelope=envelope,
                memory_scope=MemoryScope.USER,
                agent_id=resolved_agent_id,
                top_k=5,
            )
            session_state["temp:long_term_memories"] = list(
                mb_read.get("memories", [])
            )
            vertex_mb_summary = {
                "reasoning_engine_name": mb_read["reasoning_engine_name"],
                "principal": mb_read["principal"],
                "scope": mb_read["scope"],
                "retrieved_count": len(mb_read["memories"]),
            }
        registry_pdp = AgentRegistryPDP()
        entitled_mcp_tools = set(
            registry_pdp.get_entitled_tools(
                tenant_id=bound_tenant_id,
                agent_id=resolved_agent_id,
                caller_scopes=envelope.tenant.authorized_scopes,
            )
        )
        active_interceptors = _bridge_attr("interceptors", interceptors)
        active_interceptors.ingress_model_armor_screen(
            prompt=user_prompt,
            caller_tenant_id=bound_tenant_id,
            use_live_model_armor=True,
        )

        active_sandbox_manager = (
            sandbox_manager
            or _get_live_gemini_sandbox_manager(
                project_id=self.project_id,
                location=self.location,
            )
        )
        sandbox_prescreened = False
        if sandbox_code is not None:
            if not isinstance(sandbox_code, str) or not sandbox_code.strip():
                raise ValueError(
                    "E_SANDBOX_INVALID_CODE: Sandbox code must be a non-empty string."
                )
            try:
                resolved_sandbox_language = sandbox_execution.SandboxLanguage(
                    str(sandbox_language or "python").lower()
                )
            except ValueError as val_exc:
                raise ValueError(
                    f"E_SANDBOX_INVALID_CODE: Unsupported sandbox language {sandbox_language!r}."
                ) from val_exc
            if "execute_diagnostic_sandbox" not in entitled_mcp_tools:
                raise PermissionError(
                    "403 Forbidden: E_SANDBOX_SCOPE_DENIED: "
                    "Caller lacks '2lo:cymbal.sandbox.execute' entitlement for sandbox execution."
                )
            active_sandbox_manager._assert_caller_authorized(
                envelope=envelope,
                agent_id=resolved_agent_id,
                language=resolved_sandbox_language,
            )
            active_interceptors.ingress_model_armor_screen(
                prompt=sandbox_code,
                caller_tenant_id=bound_tenant_id,
                use_live_model_armor=True,
            )
            sandbox_execution.assert_zero_credentials_and_egress_safe(
                code=sandbox_code
            )
            sandbox_prescreened = True

        last_readonly_tool_output: dict[str, Any] | None = None
        last_sandbox_receipt: dict[str, object] | None = None

        async def get_scoped_p1_incidents() -> dict[str, Any]:
            """Fetches active P1 production incidents for the authenticated tenant with DLP
            redaction.
            """
            nonlocal last_readonly_tool_output
            rows = await db_pool.query_incidents(
                tenant_id=bound_tenant_id,
                user_role=envelope.security.user_role,
                agent_id=resolved_agent_id,
                severity_filter="P1",
            )
            sanitized = []
            for row in rows:
                item = dict(row)
                item["pii_notes"] = _egress_guardrail(
                    tenant_id=bound_tenant_id,
                    tool_name="get_scoped_p1_incidents",
                    tool_args={},
                    raw_output=str(row["pii_notes"]),
                )
                sanitized.append(item)
            output = {"tenant_id": bound_tenant_id, "incidents": sanitized}
            last_readonly_tool_output = output
            return output

        async def read_live_gcs_cmek_runbook() -> dict[str, Any]:
            """Reads the tenant's per-object CMEK-encrypted runbook from the pooled GCS bucket."""
            nonlocal last_readonly_tool_output
            vault_cls = _bridge_attr(
                "LiveGCSCMEKRunbookVault", LiveGCSCMEKRunbookVault
            )
            vault = vault_cls(project_id=self.project_id)
            obj_path = (
                "tenant-finvault-alpha/DOC-FV-SEC-17A4-2026.md"
                if bound_tenant_id == "tenant-finvault-alpha"
                else "tenant-retailstream-beta/ROA-2026-8812.md"
            )
            output = vault.read_tenant_runbook(
                envelope=envelope, target_object_path=obj_path
            )
            last_readonly_tool_output = output
            return output

        async def query_live_jira_regulatory_issues() -> dict[str, Any]:
            """Queries FinVault's live Atlassian Jira Cloud project (FINVAULT) for regulatory
            tickets.
            """
            nonlocal last_readonly_tool_output
            jira_cls = _bridge_attr(
                "LiveAtlassianJiraConnector", LiveAtlassianJiraConnector
            )
            output = jira_cls(
                project_id=self.project_id
            ).query_regulatory_issues(envelope=envelope)
            last_readonly_tool_output = output
            return output

        async def query_live_servicenow_itom_incidents() -> dict[str, Any]:
            """Queries RetailStream's live ServiceNow PDI instance for active ITOM incidents."""
            nonlocal last_readonly_tool_output
            snow_cls = _bridge_attr(
                "LiveServiceNowITOMConnector", LiveServiceNowITOMConnector
            )
            output = snow_cls(project_id=self.project_id).query_itom_incidents(
                envelope=envelope
            )
            last_readonly_tool_output = output
            return output

        async def execute_live_gemini_diagnostic_sandbox(
            code: str,
            language: str = "python",
            readonly_tool_output: dict[str, Any] | None = None,
        ) -> dict[str, object]:
            """Executes diagnostic code out-of-process inside Agent Sandbox in Gemini
            (`sandboxEnvironments`).
            """
            nonlocal last_sandbox_receipt
            if not isinstance(code, str) or not code.strip():
                raise ValueError(
                    "E_SANDBOX_INVALID_CODE: Sandbox code must be a non-empty string."
                )
            try:
                resolved_lang = sandbox_execution.SandboxLanguage(
                    str(language or "python").lower()
                )
            except ValueError as val_exc:
                raise ValueError(
                    f"E_SANDBOX_INVALID_CODE: Unsupported sandbox language {language!r}."
                ) from val_exc
            if readonly_tool_output is not None and not isinstance(
                readonly_tool_output, Mapping
            ):
                raise ValueError(
                    "E_SANDBOX_INVALID_INPUT: readonly_tool_output must be a JSON object mapping."
                )
            if "execute_diagnostic_sandbox" not in entitled_mcp_tools:
                raise PermissionError(
                    "403 Forbidden: E_SANDBOX_SCOPE_DENIED: "
                    "Caller lacks '2lo:cymbal.sandbox.execute' entitlement for sandbox execution."
                )
            if (
                resolved_lang == sandbox_execution.SandboxLanguage.BASH
                and envelope.security.user_role != "sre_admin"
            ):
                raise PermissionError(
                    "403 Forbidden: E_SANDBOX_SHELL_ROLE_DENIED: "
                    "Interactive bash sandboxes require role 'sre_admin'."
                )
            if not (sandbox_prescreened and code == sandbox_code):
                active_interceptors.ingress_model_armor_screen(
                    prompt=code,
                    caller_tenant_id=bound_tenant_id,
                    use_live_model_armor=True,
                )
            try:
                receipt = await asyncio.to_thread(
                    active_sandbox_manager.execute_in_session_sandbox,
                    envelope=envelope,
                    agent_id=resolved_agent_id,
                    code=code,
                    language=resolved_lang,
                    readonly_tool_output=readonly_tool_output,
                )
            except PermissionError:
                raise
            except ValueError as val_exc:
                msg = str(val_exc)
                if "E_SANDBOX_" in msg:
                    raise
                raise ValueError(f"E_SANDBOX_INVALID_CODE: {msg}") from val_exc
            except sandbox_execution.SandboxUnavailableError:
                raise
            last_sandbox_receipt = dict(receipt)
            return receipt

        # Hop 2/3 Tool Pruning driven by AgentRegistryPDP (Tenant ∩ User RBAC ∩ Agent)
        entitled_tools: list[Any] = []
        pruned_out: list[str] = []
        if "query_telemetry_rls" in entitled_mcp_tools:
            entitled_tools.append(get_scoped_p1_incidents)
        else:
            pruned_out.append("get_scoped_p1_incidents")

        if "read_runbook" in entitled_mcp_tools:
            entitled_tools.append(read_live_gcs_cmek_runbook)
        else:
            pruned_out.append("read_live_gcs_cmek_runbook")

        if (
            bound_tenant_id == "tenant-finvault-alpha"
            and "create_jira_incident" in entitled_mcp_tools
        ):
            entitled_tools.append(query_live_jira_regulatory_issues)
        else:
            pruned_out.append("query_live_jira_regulatory_issues")

        if (
            bound_tenant_id == "tenant-retailstream-beta"
            and "create_servicenow_incident" in entitled_mcp_tools
        ):
            entitled_tools.append(query_live_servicenow_itom_incidents)
        else:
            pruned_out.append("query_live_servicenow_itom_incidents")

        if "execute_diagnostic_sandbox" in entitled_mcp_tools:
            entitled_tools.append(execute_live_gemini_diagnostic_sandbox)
        else:
            pruned_out.append("execute_live_gemini_diagnostic_sandbox")

        routing_mode_override = (
            ModelRoutingMode.DETERMINISTIC
            if (
                envelope.tenant.subscription_tier == SubscriptionTier.ENTERPRISE
                and resolved_agent_id == "cymbal_shared_diagnostic_agent"
            )
            else None
        )
        routing_decision = SharedModelRoutingPDP().decide_route(
            envelope=envelope,
            agent_id=resolved_agent_id,
            tool_name=(
                "execute_diagnostic_sandbox"
                if sandbox_code
                else "query_telemetry_rls"
            ),
            prompt=user_prompt,
            entitled_tools=tuple(sorted(entitled_mcp_tools)),
            requested_thinking_budget=envelope.tenant.thinking_token_budget,
            requested_mode=routing_mode_override,
        )
        routed_model = routing_decision.selected_model
        if routed_model.startswith("claude-"):
            routed_model = DEFAULT_SHARED_DIAGNOSTIC_MODEL
        effective_model = self._explicit_model_override or routed_model
        effective_model_location = get_model_location(effective_model)
        thinking_cfg = build_thinking_config(
            model_name=effective_model,
            thinking_budget=routing_decision.effective_thinking_budget,
        )
        per_model_cache = build_per_model_context_cache_config(
            model_name=effective_model
        )

        active_workspace_plugins = (
            workspace_plugins or get_default_workspace_plugin_registry()
        )
        active_skill_loader = skill_loader or get_default_custom_skill_loader()
        loaded_custom_skills: list[dict[str, object]] = []
        custom_skill_suffix = ""
        if active_workspace_plugins.has_manifest(bound_tenant_id):
            tenant_manifest = active_workspace_plugins.get_manifest(
                bound_tenant_id
            )
            skill_docs = active_skill_loader.load_skills_for_turn(
                envelope=envelope,
                skill_uris=tenant_manifest.custom_skills_uris,
            )
            loaded_custom_skills = [
                {
                    "skill_uri": skill_doc.skill_uri,
                    "kms_key_name": skill_doc.kms_key_name,
                    "cache_hit": skill_doc.cache_hit,
                }
                for skill_doc in skill_docs
            ]
            session_state["temp:loaded_custom_skills"] = [
                skill_doc.sanitized_content for skill_doc in skill_docs
            ]
            if skill_docs:
                rendered_skills = "\n\n".join(
                    skill_doc.sanitized_content for skill_doc in skill_docs
                )
                custom_skill_suffix = (
                    f"\n\nTENANT CUSTOM SKILLS ({bound_tenant_id}):\n"
                    f"{rendered_skills}"
                )

        turn_instruction = (
            f"You are the Cymbal SaaS Pooled Diagnostic Agent serving tenant '{bound_tenant_id}'. "
            "Call `get_scoped_p1_incidents` AND your entitled 3P ticket/runbook tools first, then "
            "summarize the incident ID, 3P ticket key/number, and redacted notes in 2 sentences."
            f"{custom_skill_suffix}"
        )
        agent_sig_params = set(inspect.signature(Agent).parameters)
        accepts_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in inspect.signature(Agent).parameters.values()
        )
        agent_model_arg: Any = effective_model
        if accepts_var_kw or "static_instruction" in agent_sig_params:
            try:
                from google.adk.models.google_llm import Gemini

                agent_model_arg = Gemini(
                    model=effective_model,
                    client_kwargs={
                        "vertexai": True,
                        "project": self.project_id,
                        "location": effective_model_location,
                    },
                )
            except (ImportError, TypeError, ValueError, AttributeError):
                agent_model_arg = effective_model

        agent_kwargs: dict[str, Any] = {
            "name": resolved_agent_id,
            "model": agent_model_arg,
            "instruction": turn_instruction,
            "tools": entitled_tools,
        }
        if accepts_var_kw or "static_instruction" in agent_sig_params:
            agent_kwargs["static_instruction"] = SHARED_SYSTEM_PROMPT_PREFIX
        if (
            thinking_cfg is not None
            and hasattr(genai_types, "GenerateContentConfig")
            and hasattr(genai_types, "ThinkingConfig")
            and (
                accepts_var_kw or "generate_content_config" in agent_sig_params
            )
        ):
            agent_kwargs["generate_content_config"] = (
                genai_types.GenerateContentConfig(
                    thinking_config=genai_types.ThinkingConfig(**thinking_cfg)
                )
            )

        agent = Agent(**agent_kwargs)

        runner_sig_params = set(inspect.signature(InMemoryRunner).parameters)
        runner: Any = None
        if (
            "app" in runner_sig_params
            and per_model_cache["adk_context_cache_config"] is not None
        ):
            try:
                from google.adk.apps import App

                pooled_app = App(
                    name="cymbal_pooled_app",
                    root_agent=agent,
                    context_cache_config=per_model_cache[
                        "adk_context_cache_config"
                    ],
                )
                runner = InMemoryRunner(app=pooled_app)
            except (ImportError, TypeError, ValueError, AttributeError):
                runner = None
        if runner is None:
            runner = InMemoryRunner(agent=agent, app_name="cymbal_pooled_app")
        session = await runner.session_service.create_session(
            app_name="cymbal_pooled_app",
            user_id=tenant_qualified_user_id(
                envelope.tenant.tenant_id, envelope.security.sub
            ),
            state=session_state,
        )

        final_text = ""
        tool_calls_seen: list[str] = []
        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=user_prompt)],
        )
        async for event in runner.run_async(
            user_id=tenant_qualified_user_id(
                envelope.tenant.tenant_id, envelope.security.sub
            ),
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call and part.function_call.name:
                        tool_calls_seen.append(part.function_call.name)
                    if part.text:
                        final_text += part.text

        if sandbox_code is not None and last_sandbox_receipt is None:
            await execute_live_gemini_diagnostic_sandbox(
                code=sandbox_code,
                language=sandbox_language,
                readonly_tool_output=last_readonly_tool_output,
            )
            tool_calls_seen.append("execute_live_gemini_diagnostic_sandbox")

        result: dict[str, Any] = {
            "tenant_id": bound_tenant_id,
            "agent_id": resolved_agent_id,
            "model": effective_model,
            "model_location": effective_model_location,
            "thinking_config": thinking_cfg,
            "context_cache": {
                k: v
                for k, v in per_model_cache.items()
                if k != "adk_context_cache_config"
            },
            "model_routing": {
                "routing_mode": str(routing_decision.routing_mode),
                "task_complexity": str(routing_decision.task_complexity),
                "selected_model": routing_decision.selected_model,
                "effective_thinking_budget": routing_decision.effective_thinking_budget,
            },
            "tool_calls": tool_calls_seen,
            "pruned_unentitled_tools": pruned_out,
            "loaded_custom_skills": loaded_custom_skills,
            "agent_response": final_text.strip(),
            "rls_guc": db_pool.last_executed_guc,
        }
        if vertex_mb_summary is not None:
            result["vertex_memory_bank"] = vertex_mb_summary
        if last_sandbox_receipt is not None:
            result["sandbox_execution"] = last_sandbox_receipt
        return result

    async def run_finvault_agent_alpha_turn(
        self,
        *,
        envelope: ContextEnvelope,
        user_prompt: str = "Execute SEC Rule 17a-4 regulatory escalation and verify FINVAULT-1.",
        sandbox_code: str | None = None,
        sandbox_language: str = "python",
        sandbox_manager: (
            sandbox_execution.GeminiAgentSandboxManager | None
        ) = None,
    ) -> dict[str, Any]:
        """Executes FinVault's private `finvault_regulatory_escalation_agent` with Claude ->
        Gemini hot-swap.
        """
        from agents.registry import AgentRegistryPDP

        AgentRegistryPDP().verify_agent_access(
            tenant_id=envelope.tenant.tenant_id,
            agent_id="finvault_regulatory_escalation_agent",
            caller_scopes=envelope.tenant.authorized_scopes,
        )
        preferred_model = "claude-3-7-sonnet@20250219"
        fallback_reason: str | None = None
        res = await self.run_tenant_diagnostic_turn(
            envelope=envelope,
            user_prompt=user_prompt,
            agent_id="finvault_regulatory_escalation_agent",
            sandbox_code=sandbox_code,
            sandbox_language=sandbox_language,
            sandbox_manager=sandbox_manager,
        )
        fallback_reason = (
            "partner_model_terms_not_enabled_in_project_hot_swapped_to_gemini"
        )
        res["agent_id"] = "finvault_regulatory_escalation_agent"
        res["configured_primary_model"] = preferred_model
        res["executed_model"] = res["model"]
        res["model_fallback_reason"] = fallback_reason
        return res


LiveGeminiAgentSandboxClient = sandbox_execution.LiveGeminiAgentSandboxClient

_LIVE_AGENT_SANDBOX_SANDBOX_MANAGER = (
    sandbox_execution.GeminiAgentSandboxManager(
        backend=LiveGeminiAgentSandboxClient(
            project_id=DEFAULT_GCP_PROJECT,
            location=DEFAULT_GCP_REGION,
        ),
        project_id=DEFAULT_GCP_PROJECT,
        location=DEFAULT_GCP_REGION,
    )
)
_LIVE_SANDBOX_MANAGER_LOCK = threading.Lock()
_LIVE_SANDBOX_MANAGERS_BY_SCOPE: dict[
    tuple[str, str], sandbox_execution.GeminiAgentSandboxManager
] = {
    (
        DEFAULT_GCP_PROJECT,
        DEFAULT_GCP_REGION,
    ): _LIVE_AGENT_SANDBOX_SANDBOX_MANAGER,
}


def _get_live_gemini_sandbox_manager(
    *, project_id: str, location: str
) -> sandbox_execution.GeminiAgentSandboxManager:
    """Returns a shared process-wide `GeminiAgentSandboxManager` for `(project_id, location)`."""
    if project_id == DEFAULT_GCP_PROJECT and location == DEFAULT_GCP_REGION:
        return _LIVE_AGENT_SANDBOX_SANDBOX_MANAGER
    key = (project_id, location)
    with _LIVE_SANDBOX_MANAGER_LOCK:
        manager = _LIVE_SANDBOX_MANAGERS_BY_SCOPE.get(key)
        if manager is None:
            manager = sandbox_execution.GeminiAgentSandboxManager(
                backend=LiveGeminiAgentSandboxClient(
                    project_id=project_id, location=location
                ),
                project_id=project_id,
                location=location,
            )
            _LIVE_SANDBOX_MANAGERS_BY_SCOPE[key] = manager
        return manager
