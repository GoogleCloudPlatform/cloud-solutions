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

# pylint: disable=broad-exception-caught,import-outside-toplevel
# pylint: disable=inconsistent-quotes,line-too-long,protected-access

"""The agent turn (Hops 3-5), shared by the in-process gateway and the agent runtime service.

ADR-0014 B5 / plan S1: the gateway does admission (Hop 0-2: identity, limits, agent selection and
binding) and then either runs this turn in process (default) or forwards it to the agent's own
runtime service (`runtime_service/main.py`), which runs exactly this function. Keeping one copy
means the two paths cannot drift.

Nothing here signs anything: the turn only reads the (already verified) envelope.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from agents import interceptors, sandbox_execution
from agents.agent_alpha import build_agent_alpha
from agents.context import (
    _ACTIVE_TENANT_ENVELOPE,
    ContextEnvelope,
    MemoryBankPartitioner,
    MemoryScope,
)
from agents.interceptors import enforce_tenant_isolation_interceptor
from agents.model_routing import SharedModelRoutingPDP
from agents.platform_config import is_live_mode
from agents.registry import AgentRegistryPDP
from agents.shared_diagnostic_agent import build_shared_diagnostic_agent
from agents.testing_fakes import MockADKCallbackContext
from fastapi import HTTPException
from mcp_server import server as mcp_tools
from mcp_server.db import RLSDatabasePool

logger = logging.getLogger(__name__)


@dataclass
class TurnServices:
    """Per-process state the turn uses (each runtime service has its own)."""

    registry_pdp: AgentRegistryPDP
    otel_sink: interceptors.OTelAuditSink
    memory_bank: MemoryBankPartitioner
    model_routing_pdp: SharedModelRoutingPDP
    db_pool: RLSDatabasePool
    sandbox_mode_active: Callable[[], bool]
    sandbox_manager: sandbox_execution.GeminiAgentSandboxManager = field(
        default_factory=sandbox_execution.GeminiAgentSandboxManager
    )


def build_agent(agent_id: str) -> Any:
    """The ADK agent object for a requested id (unknown ids get the shared agent, as before; the
    gateway refuses that mismatch when it binds the agent id)."""
    if agent_id == "finvault_regulatory_escalation_agent":
        return build_agent_alpha()
    return build_shared_diagnostic_agent()


def _resolve_topology_route(envelope: ContextEnvelope) -> dict[str, Any]:
    """Return the public view of the tenant's pool/silo/hybrid topology routing decision."""
    from agents.topology_router import (
        IN_PROCESS,
        RoutingDecision,
        TopologyRefused,
        TopologyRouter,
        configured_topology,
    )

    try:
        return (
            TopologyRouter()
            .route(
                envelope.context_token,
                expected_tenant_id=envelope.tenant.tenant_id,
            )
            .public_view()
        )
    except TopologyRefused:
        topology = configured_topology(envelope.tenant.tenant_id) or {
            "pattern": "pool"
        }
        return RoutingDecision(
            tenant_id=envelope.tenant.tenant_id,
            pattern=str(topology.get("pattern", "pool")),
            runtime_target=IN_PROCESS,
            data_target=IN_PROCESS,
        ).public_view()


async def run_agent_turn(
    req: Any,
    envelope: ContextEnvelope,
    *,
    services: TurnServices,
    hops: list[dict[str, Any]],
    finops: dict[str, Any],
    estimated_tokens: int,
    prompt_cache_hit: bool,
    identity_source: str,
    agent_obj: Any | None = None,
) -> dict[str, Any]:
    """Hops 3-5 for an admitted turn. `hops` is appended to in place (the caller reports where a
    `PermissionError` stopped the turn). `req` carries agent_id, prompt, tool_name,
    requested_thinking_tokens, raw_sql_override and live_cloud."""
    env_token = _ACTIVE_TENANT_ENVELOPE.set(envelope)
    try:
        return await _run_agent_turn_inner(
            req,
            envelope,
            services=services,
            hops=hops,
            finops=finops,
            estimated_tokens=estimated_tokens,
            prompt_cache_hit=prompt_cache_hit,
            identity_source=identity_source,
            agent_obj=agent_obj,
        )
    finally:
        _ACTIVE_TENANT_ENVELOPE.reset(env_token)


async def _run_agent_turn_inner(
    req: Any,
    envelope: ContextEnvelope,
    *,
    services: TurnServices,
    hops: list[dict[str, Any]],
    finops: dict[str, Any],
    estimated_tokens: int,
    prompt_cache_hit: bool,
    identity_source: str,
    agent_obj: Any | None = None,
) -> dict[str, Any]:
    issuer = envelope.security.iss
    if agent_obj is None:
        agent_obj = build_agent(req.agent_id)
    state = envelope.to_adk_state()
    state["temp:last_user_prompt"] = req.prompt
    state.setdefault("temp:agent_id", req.agent_id)
    # Run with the budget that was metered (clamped to the signed cap by the interceptor).
    state["temp:requested_thinking_budget"] = req.requested_thinking_tokens
    state["temp:use_live_model_armor"] = True
    ctx = MockADKCallbackContext(state=state, agent=agent_obj)

    await enforce_tenant_isolation_interceptor(
        ctx, registry_pdp=services.registry_pdp, otel_sink=services.otel_sink
    )
    pruned_tools = [
        getattr(t, "name", getattr(t, "__name__", "")) for t in ctx.active_tools
    ]
    hops.append(
        {
            "hop_num": 2,
            "hop": "Hop 2: Ingress PEP (Model Armor + Registry PDP)",
            "status": "PASSED",
            "detail": (
                f"Prompt passed Model Armor screen. Entitled agent '{req.agent_id}'. "
                f"Pruned active tools to: {pruned_tools}"
            ),
        }
    )

    mem_key = services.memory_bank.write_memory(
        envelope=envelope,
        scope=MemoryScope.SESSION,
        actor=req.agent_id,
        content={"last_prompt": req.prompt},
    )
    if is_live_mode() and "pytest" not in sys.modules:
        from agents.gcp_live_bridge import (
            LiveFirestoreMemoryBank,
            LiveVertexMemoryBankAdapter,
        )

        mem_key = LiveFirestoreMemoryBank().write_memory(
            envelope=envelope,
            scope=MemoryScope.SESSION,
            actor=req.agent_id,
            content={"last_prompt": req.prompt},
        )
        mb_engine = (
            os.getenv("MEMORY_BANK_REASONING_ENGINE", "").strip()
            or os.getenv("AGENT_SANDBOX_REASONING_ENGINE_NAME", "").strip()
        )
        if mb_engine:
            mb_retrieved = LiveVertexMemoryBankAdapter(
                reasoning_engine_name=mb_engine
            ).retrieve_memories(
                envelope=envelope,
                memory_scope=MemoryScope.USER,
                agent_id=req.agent_id,
                top_k=5,
            )
            state["temp:long_term_memories"] = list(
                mb_retrieved.get("memories", [])
            )
    routing_decision = services.model_routing_pdp.decide_route(
        envelope=envelope,
        agent_id=req.agent_id,
        tool_name=req.tool_name,
        prompt=req.prompt,
        entitled_tools=pruned_tools,
        requested_thinking_budget=int(
            finops.get(
                "effective_thinking_budget", req.requested_thinking_tokens
            )
        ),
    )
    hops.append(
        {
            "hop_num": 3,
            "hop": "Hop 3: ADK 2.0 Runtime & 5-Level Memory Bank",
            "status": "PASSED",
            "detail": (
                f"Bound temp:tenant_id='{envelope.tenant.tenant_id}'. "
                f"Memory key='{mem_key}' encrypted with CMEK. "
                "Routed model='"
                f"{routing_decision.selected_model}"
                "' ("
                f"{routing_decision.task_complexity}"
                "). "
                f"Billable tokens={finops['billable_tokens']} (cache_hit={prompt_cache_hit})."
            ),
        }
    )

    sandbox_receipt: dict[str, object] | None = None
    requested_sandbox_code = getattr(req, "sandbox_code", None)
    requested_sandbox_language = str(
        getattr(req, "sandbox_language", "python") or "python"
    )
    sandbox_prescreened = False
    if (
        requested_sandbox_code is not None
        and req.tool_name != "execute_diagnostic_sandbox"
    ):
        if (
            not isinstance(requested_sandbox_code, str)
            or not requested_sandbox_code.strip()
        ):
            raise HTTPException(
                status_code=422,
                detail={"error": "E_SANDBOX_INVALID_CODE"},
            )
        try:
            resolved_sandbox_language = sandbox_execution.SandboxLanguage(
                requested_sandbox_language.lower()
            )
        except ValueError as val_exc:
            raise HTTPException(
                status_code=422,
                detail={"error": "E_SANDBOX_INVALID_CODE"},
            ) from val_exc
        services.sandbox_manager._assert_caller_authorized(
            envelope=envelope,
            agent_id=req.agent_id,
            language=resolved_sandbox_language,
        )
        interceptors.ingress_model_armor_screen(
            prompt=requested_sandbox_code,
            caller_tenant_id=envelope.tenant.tenant_id,
            use_live_model_armor=True,
        )
        try:
            sandbox_execution.assert_zero_credentials_and_egress_safe(
                code=requested_sandbox_code,
            )
        except ValueError as val_exc:
            raise HTTPException(
                status_code=422,
                detail={"error": "E_SANDBOX_INVALID_CODE"},
            ) from val_exc
        sandbox_prescreened = True

    if req.tool_name == "query_telemetry_rls":
        tool_result = await mcp_tools.query_telemetry_rls(
            severity="P1",
            raw_sql=req.raw_sql_override,
            tool_context=ctx,
            db_pool=services.db_pool,
        )
    elif req.tool_name == "read_runbook":
        tool_result = await mcp_tools.read_runbook(
            tool_context=ctx, db_pool=services.db_pool
        )
    elif req.tool_name == "execute_diagnostic_sandbox":
        requested_code = getattr(req, "sandbox_code", None)
        if not isinstance(requested_code, str) or not requested_code.strip():
            raise HTTPException(
                status_code=422,
                detail={"error": "E_SANDBOX_INVALID_CODE"},
            )
        requested_lang = str(
            getattr(req, "sandbox_language", "python") or "python"
        )
        try:
            tool_result = await mcp_tools.execute_diagnostic_sandbox(
                code=requested_code,
                language=requested_lang,
                tool_context=ctx,
                sandbox_manager=services.sandbox_manager,
            )
        except ValueError as val_exc:
            raise HTTPException(
                status_code=422,
                detail={"error": "E_SANDBOX_INVALID_CODE"},
            ) from val_exc
        if isinstance(tool_result, Mapping):
            raw_receipt = tool_result.get("sandbox_execution")
            if isinstance(raw_receipt, Mapping):
                sandbox_receipt = dict(raw_receipt)
    elif req.tool_name == "create_jira_incident":
        tool_result = await mcp_tools.create_jira_incident(
            summary=req.prompt, tool_context=ctx
        )
    elif req.tool_name == "create_servicenow_incident":
        tool_result = await mcp_tools.create_servicenow_incident(
            short_description=req.prompt, tool_context=ctx
        )
    elif req.tool_name == "schedule_calendar_postmortem":
        tool_result = await mcp_tools.schedule_calendar_postmortem(
            incident_id="INC-FV-1001", title=req.prompt, tool_context=ctx
        )
    elif req.tool_name == "escalate_regulatory_filing":
        tool_result = await mcp_tools.escalate_regulatory_filing(
            incident_id="INC-FV-1001", tool_context=ctx
        )
    elif req.tool_name == "send_gmail_brief":
        tool_result = await mcp_tools.send_gmail_brief(
            recipient=envelope.security.sub,
            body=req.prompt,
            tool_context=ctx,
        )
    elif req.tool_name == "read_sharepoint_runbook":
        tool_result = await mcp_tools.read_sharepoint_runbook(
            site_path="ROA-2026-8812", tool_context=ctx
        )
    else:
        raise PermissionError(f"403 Forbidden: Unknown tool '{req.tool_name}'")

    hops.append(
        {
            "hop_num": 4,
            "hop": "Hop 4 & 5: Egress DLP + Stateless MCP + AlloyDB RLS",
            "status": "PASSED",
            "detail": (
                f"Executed '{req.tool_name}' with '{services.db_pool.last_executed_guc}'. "
                "PII redacted via Cloud DLP."
            ),
        }
    )

    if sandbox_receipt is None and requested_sandbox_code is not None:
        if not sandbox_prescreened:
            interceptors.ingress_model_armor_screen(
                prompt=str(requested_sandbox_code),
                caller_tenant_id=envelope.tenant.tenant_id,
                use_live_model_armor=True,
            )
        readonly_output: Mapping[str, object] = (
            dict(tool_result)
            if isinstance(tool_result, Mapping)
            else {"tool_output": tool_result}
        )
        try:
            sandbox_receipt = await asyncio.to_thread(
                services.sandbox_manager.execute_in_session_sandbox,
                envelope=envelope,
                agent_id=req.agent_id,
                code=str(requested_sandbox_code),
                language=requested_sandbox_language,
                readonly_tool_output=readonly_output,
            )
        except ValueError as val_exc:
            raise HTTPException(
                status_code=422,
                detail={"error": "E_SANDBOX_INVALID_CODE"},
            ) from val_exc

    live_cloud_receipt: dict[str, Any] | None = None
    if req.live_cloud:
        from agents.gcp_live_bridge import (
            FINVAULT_KMS_KEY,
            RETAILSTREAM_KMS_KEY,
            LiveAtlassianJiraConnector,
            LiveBigQueryOTelSink,
            LiveCloudDLPGuardrail,
            LiveCloudKMSCMEKVerifier,
            LiveFirestoreMemoryBank,
            LiveGCSCMEKRunbookVault,
            LiveMicrosoftEntraOIDCConnector,
            LiveModelArmorGuardrail,
            LiveServiceNowITOMConnector,
            LiveVertexMemoryBankAdapter,
            is_live_gcp_enabled,
        )

        tenant_id = envelope.tenant.tenant_id
        # 1. Execute 3P SaaS & IdP calls (uses .env if configured, or deterministic local
        # simulation)
        if tenant_id == "tenant-finvault-alpha":
            saas_live = LiveAtlassianJiraConnector().query_regulatory_issues(
                envelope=envelope
            )
            runbook_obj = "tenant-finvault-alpha/DOC-FV-SEC-17A4-2026.md"
            idp_live: dict[str, Any] = {
                "provider": "Google Workspace OIDC",
                "issuer": issuer,
            }
        else:
            saas_live = LiveServiceNowITOMConnector().query_itom_incidents(
                envelope=envelope
            )
            runbook_obj = "tenant-retailstream-beta/ROA-2026-8812.md"
            idp_live = LiveMicrosoftEntraOIDCConnector().verify_live_entra_oidc_and_jwks(
                envelope=envelope
            )

        kms_key = envelope.tenant.cmek_key_name or (
            FINVAULT_KMS_KEY
            if tenant_id == "tenant-finvault-alpha"
            else RETAILSTREAM_KMS_KEY
        )
        live_cloud_receipt = {
            "mode": (
                "LIVE_3P_AND_GCP_EXECUTION"
                if is_live_gcp_enabled()
                else "LOCAL_DETERMINISTIC_SIMULATION"
            ),
            "hop1_live_idp": idp_live,
            "hop5_live_3p_saas": saas_live,
        }

        # 2. Only execute outbound GCP Control Plane SDK calls when CYMBAL_LIVE_GCP=1 is explicitly
        # enabled
        if is_live_gcp_enabled():
            try:
                ma_live = LiveModelArmorGuardrail().sanitize_prompt(req.prompt)
                kms_verifier = LiveCloudKMSCMEKVerifier()
                kms_receipt = kms_verifier.verify_key_access(
                    kms_key_name=kms_key,
                    tenant_id=tenant_id,
                    envelope=envelope,
                )
                fs_live_key = LiveFirestoreMemoryBank().write_memory(
                    envelope=envelope,
                    scope=MemoryScope.SESSION,
                    actor=req.agent_id,
                    content={"prompt": req.prompt, "live_verified": True},
                )
                mb_live_receipt: dict[str, Any] | None = None
                mb_live_engine = (
                    os.getenv("MEMORY_BANK_REASONING_ENGINE", "").strip()
                    or os.getenv(
                        "AGENT_SANDBOX_REASONING_ENGINE_NAME", ""
                    ).strip()
                )
                if mb_live_engine:
                    mb_read = LiveVertexMemoryBankAdapter(
                        reasoning_engine_name=mb_live_engine
                    ).retrieve_memories(
                        envelope=envelope,
                        memory_scope=MemoryScope.USER,
                        agent_id=req.agent_id,
                        top_k=5,
                    )
                    mb_live_receipt = {
                        "reasoning_engine_name": mb_read[
                            "reasoning_engine_name"
                        ],
                        "principal": mb_read["principal"],
                        "scope": mb_read["scope"],
                        "memories_count": len(mb_read["memories"]),
                        "quarantined_count": mb_read["quarantined_count"],
                    }
                dlp_payload = (
                    {k: v for k, v in tool_result.items() if k != "rls_guc"}
                    if isinstance(tool_result, Mapping)
                    else tool_result
                )
                dlp_live = LiveCloudDLPGuardrail().deidentify_tool_output(
                    raw_output=str(dlp_payload),
                    tool_name=req.tool_name,
                    tenant_id=tenant_id,
                )
                gcs_live = LiveGCSCMEKRunbookVault().read_tenant_runbook(
                    envelope=envelope,
                    target_object_path=runbook_obj,
                )
                LiveBigQueryOTelSink().insert_span(
                    trace_id=envelope.request.trace_id,
                    tenant_id=tenant_id,
                    subscription_tier=str(envelope.tenant.subscription_tier),
                    agent_id=req.agent_id,
                    model_id=routing_decision.selected_model,
                    tool_name=req.tool_name,
                    prompt_cache_hit=prompt_cache_hit,
                    thinking_tokens_budget=finops["effective_thinking_tokens"],
                    raw_input_tokens=estimated_tokens,
                    billable_tokens=finops["billable_tokens"],
                    status="LIVE_5HOP_AUTHORIZED",
                )
                live_cloud_receipt.update(
                    {
                        "hop2_4_live_model_armor": ma_live,
                        "hop3_live_kms_cmek_key": kms_key,
                        "hop3_live_kms_probe_ciphertext_bytes": int(
                            kms_receipt.get("ciphertext_bytes", 0)
                        ),
                        "hop3_live_kms_cache_hit": bool(
                            kms_receipt.get("cache_hit", False)
                        ),
                        "hop3_live_firestore_doc_key": fs_live_key,
                        **(
                            {"hop3_live_vertex_memory_bank": mb_live_receipt}
                            if mb_live_receipt is not None
                            else {}
                        ),
                        "hop4_live_cloud_dlp": dlp_live,
                        "hop5_live_gcs_cmek_runbook": {
                            "bucket": gcs_live["bucket"],
                            "object": gcs_live["object_name"],
                            "kms_key_name": gcs_live["kms_key_name"],
                        },
                        "hop5_live_bigquery_table": "cymbal_agent_analytics.tenant_otel_spans",
                    }
                )
            except PermissionError:
                raise
            except Exception as gcp_exc:
                logger.warning(
                    "live GCP step failed: %s", type(gcp_exc).__name__
                )
                if not services.sandbox_mode_active():
                    raise HTTPException(
                        status_code=503,
                        detail={"error": "E_LIVE_GCP_STEP_FAILED"},
                    ) from gcp_exc
                live_cloud_receipt["gcp_adc_note"] = (
                    str(gcp_exc)
                    if identity_source == "SANDBOX_SCENARIO_PERSONA"
                    else "E_LIVE_GCP_STEP_FAILED"
                )
        else:
            live_cloud_receipt.update(
                {
                    "hop3_kms_cmek_key": kms_key,
                    "hop3_firestore_doc_key": mem_key,
                    "hop5_gcs_cmek_runbook_object": runbook_obj,
                    "hop5_bigquery_table": "cymbal_agent_analytics.tenant_otel_spans",
                    "gcp_control_plane_mode": "LOCAL_SANDBOX_SIMULATION (Set CYMBAL_LIVE_GCP=1 "
                    "for live GCP SDK "
                    "calls)",
                }
            )

        if sandbox_receipt is not None:
            live_cloud_receipt["hop3_gemini_agent_sandbox"] = sandbox_receipt

    turn_response: dict[str, Any] = {
        "status": "SUCCESS",
        "identity_source": identity_source,
        "tenant_id": envelope.tenant.tenant_id,
        "tier": str(envelope.tenant.subscription_tier),
        "agent_id": req.agent_id,
        "entitled_tools": pruned_tools,
        "model_routing": {
            "routing_mode": str(routing_decision.routing_mode),
            "task_complexity": str(routing_decision.task_complexity),
            "selected_model": routing_decision.selected_model,
            "advisor_model": routing_decision.advisor_model,
            "effective_thinking_budget": routing_decision.effective_thinking_budget,
            "pruned_active_tools": list(routing_decision.pruned_active_tools),
            "trimmed_write_tools_count": routing_decision.trimmed_write_tools_count,
            "allow_subagent_delegation": routing_decision.allow_subagent_delegation,
            "schema_tokens_saved": routing_decision.schema_tokens_saved,
            "estimated_turn_usd_saved": routing_decision.estimated_turn_usd_saved,
        },
        "finops": finops,
        "topology_route": _resolve_topology_route(envelope),
        "hops": hops,
        "tool_output": tool_result,
        "live_cloud_receipt": live_cloud_receipt,
    }
    if sandbox_receipt is not None:
        turn_response["sandbox_execution"] = sandbox_receipt
    return turn_response
