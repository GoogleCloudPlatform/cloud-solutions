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

"""5-Hop agent invocation, stateless MCP JSON-RPC, agent sandbox lifecycle, and model routing."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Any, Literal

from agents import gcp_live_bridge, interceptors, sandbox_execution
from agents.context import (
    _ACTIVE_TENANT_ENVELOPE,
    TENANT_DIRECTORY,
    ContextEnvelope,
)
from agents.interceptors import OTelAuditSpan
from agents.turn_engine import build_agent, run_agent_turn
from agents.workload_identity import resume_agent, suspend_agent
from app.runtime_state import (
    Caller,
    OptionalCaller,
    SandboxOnly,
    active_sandbox_mode,
    gateway_module,
    logger,
    metering,
    public_error_code,
    routed_agent_binding_enabled,
    stripped_header_names,
)
from app.schemas.gateway import (
    AgentSuspensionActionRequest,
    AskProEscalationRequest,
    InvokeAgentRequest,
    ModelRoutingDecideRequest,
    SandboxSessionActionRequest,
    ScenarioTurn,
)
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from mcp_server.server import handle_mcp_jsonrpc_request

router = APIRouter()


@router.post("/mcp/v1/jsonrpc")
async def mcp_jsonrpc_endpoint(
    payload: dict[str, Any], envelope: OptionalCaller
) -> dict[str, Any]:
    """Hop 5 stateless MCP JSON-RPC 2.0 wire endpoint (`tools/list` and `tools/call`)."""
    gateway = gateway_module()
    if "authenticated_tenant_id" in payload:
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "error": {
                "code": -32600,
                "message": "Identity comes from the Authorization header, not the payload.",
            },
        }
    verified_state = envelope.to_adk_state() if envelope else None
    if (
        verified_state is not None
        and envelope is not None
        and payload.get("method") == "tools/call"
        and "temp:agent_id" not in verified_state
        and "agent:cymbal_shared_diagnostic_agent"
        in envelope.tenant.authorized_scopes
    ):
        verified_state["temp:agent_id"] = "cymbal_shared_diagnostic_agent"
    return await handle_mcp_jsonrpc_request(
        payload,
        verified_adk_state=verified_state,
        db_pool=gateway.DB_POOL,
        sandbox_manager=gateway.SANDBOX_MANAGER,
    )


@router.post("/api/v1/invoke-agent")
async def invoke_agent(
    request: Request, req: InvokeAgentRequest, envelope: Caller
) -> dict[str, Any]:
    """Executes a full 5-Hop Context Chain turn as the verified caller (Hop 0 gateway token)."""
    if req.raw_sql_override is not None and not active_sandbox_mode():
        raise HTTPException(
            status_code=422, detail={"error": "E_RAW_SQL_SANDBOX_ONLY"}
        )
    return await execute_turn(
        req,
        envelope,
        stripped_headers=stripped_header_names(request.headers),
        identity_source="HOP0_VERIFIED",
    )


async def _handle_session_sandbox_lifecycle(
    *,
    action: Literal["pause", "release"],
    envelope: ContextEnvelope,
    agent_id: str,
    language: Literal["python", "javascript", "bash"] | None = None,
) -> JSONResponse:
    """Executes or forwards session sandbox lifecycle operations (`pause` / `release`)."""
    gateway = gateway_module()
    remote_runtime = gateway.REMOTE_RUNTIME
    try:
        if remote_runtime is not None and remote_runtime.handles(agent_id):
            gateway.REGISTRY_PDP.verify_agent_access(
                tenant_id=envelope.tenant.tenant_id,
                agent_id=agent_id,
                caller_scopes=envelope.tenant.authorized_scopes,
            )
            bound_envelope = gateway.EDGE_VERIFIER.bind_routed_agent(
                envelope, agent_id
            )
            remote_kwargs: dict[str, Any] = {
                "envelope": bound_envelope,
                "agent_id": agent_id,
            }
            if language is not None:
                remote_kwargs["language"] = language
            if action == "pause":
                receipt = await remote_runtime.pause_sandbox(**remote_kwargs)
            else:
                receipt = await remote_runtime.release_sandbox(**remote_kwargs)
        else:
            sandbox_mgr = gateway.SANDBOX_MANAGER
            lifecycle_fn = (
                sandbox_mgr.pause_session_sandbox
                if action == "pause"
                else sandbox_mgr.release_session_sandbox
            )
            lifecycle_kwargs: dict[str, Any] = {
                "envelope": envelope,
                "agent_id": agent_id,
            }
            if language is not None:
                lifecycle_kwargs["language"] = (
                    sandbox_execution.SandboxLanguage(language)
                )
            receipt = await asyncio.to_thread(lifecycle_fn, **lifecycle_kwargs)
    except PermissionError as exc:
        status_code, _ = _permission_error_status_and_headers(exc)
        raise HTTPException(
            status_code=status_code,
            detail={"error": public_error_code(exc)},
            headers={"Cache-Control": "no-store"},
        ) from exc
    return JSONResponse(content=receipt, headers={"Cache-Control": "no-store"})


@router.post("/api/v1/sandboxes/session/pause")
async def pause_session_sandbox_endpoint(
    req: SandboxSessionActionRequest,
    envelope: Caller,
) -> JSONResponse:
    """Transitions the caller session's active agent sandbox in Gemini to `STATE_PAUSED`."""
    return await _handle_session_sandbox_lifecycle(
        action="pause",
        envelope=envelope,
        agent_id=req.agent_id,
        language=req.language,
    )


@router.post("/api/v1/sandboxes/session/release")
async def release_session_sandbox_post_endpoint(
    req: SandboxSessionActionRequest,
    envelope: Caller,
) -> JSONResponse:
    """Permanently destroys (`STATE_DESTROYED`) the caller session's tainted agent sandbox."""
    return await _handle_session_sandbox_lifecycle(
        action="release",
        envelope=envelope,
        agent_id=req.agent_id,
        language=req.language,
    )


@router.delete("/api/v1/sandboxes/session")
async def delete_session_sandbox_endpoint(
    envelope: Caller,
    agent_id: str = "cymbal_shared_diagnostic_agent",
    language: Literal["python", "javascript", "bash"] | None = None,
) -> JSONResponse:
    """REST `DELETE` alias permanently destroying the caller session's tainted agent sandbox."""
    if (
        not agent_id
        or len(agent_id) > 64
        or not re.fullmatch(r"[a-z0-9_]+", agent_id)
    ):
        raise HTTPException(
            status_code=422, detail={"error": "E_INVALID_AGENT_ID"}
        )
    return await _handle_session_sandbox_lifecycle(
        action="release",
        envelope=envelope,
        agent_id=agent_id,
        language=language,
    )


def persona_envelope(turn: ScenarioTurn) -> ContextEnvelope:
    """SANDBOX ONLY: Mints a server-side envelope for a scripted synthetic workshop persona."""
    gateway = gateway_module()
    tenant_meta = TENANT_DIRECTORY.get(turn.authenticated_tenant_id, {})
    return gateway.EDGE_VERIFIER.exchange_obo_token(
        verified_idp_claims={
            "iss": turn.idp_issuer
            or str(tenant_meta.get("iss", "https://accounts.google.com")),
            "sub": turn.user_sub,
            "tenant_id": turn.authenticated_tenant_id,
            "user_role": turn.user_role,
            "exp": int(time.time()) + 3600,
            "jti": f"jwt-scenario-{uuid.uuid4().hex[:8]}",
        },
        dpop_proof={
            "jkt": f"scenario-{turn.authenticated_tenant_id}",
            "jti": f"dpop-scenario-{uuid.uuid4().hex}",
        },
        raw_client_headers=turn.spoofed_headers,
    )


async def run_scenario_turn(turn: ScenarioTurn) -> dict[str, Any]:
    """SANDBOX ONLY: Executes a scripted scenario turn and preserves verbose 403/429 telemetry."""
    try:
        envelope = persona_envelope(turn)
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "BLOCKED_BY_AGENT_SANDBOX_GOVERNANCE",
                "http_code": 403,
                "blocked_at_hop": 1,
                "error": str(exc),
                "completed_hops": [],
            },
        ) from exc
    try:
        return await execute_turn(
            turn,
            envelope,
            stripped_headers=stripped_header_names(turn.spoofed_headers),
            identity_source="SANDBOX_SCENARIO_PERSONA",
        )
    finally:
        _ACTIVE_TENANT_ENVELOPE.set(None)


_PEP_503_CODES = frozenset(
    {
        "E_BULKHEAD_BACKEND_UNAVAILABLE",
        "E_CONTROL_PLANE_REGISTRY_UNAVAILABLE_FAIL_CLOSED",
        "E_MCP_SERVER_CIRCUIT_OPEN",
    }
)
_PEP_429_CODES = frozenset(
    {
        "E_SESSION_LOOP_CIRCUIT_BREAKER",
        "E_EXCHANGE_RATE_LIMITED",
        "E_SANDBOX_BULKHEAD_EXHAUSTED",
        "E_SUBAGENT_SPAWN_DEPTH_EXCEEDED",
        "E_ASKPRO_CONSULTATION_CAP_EXCEEDED",
    }
)


def _permission_error_status_and_headers(
    exc: PermissionError,
) -> tuple[int, dict[str, str] | None]:
    """Maps a PEP `PermissionError` to its HTTP status code and optional `Retry-After` header."""
    error_message = str(exc).lstrip()
    code = public_error_code(exc)
    if (
        error_message.startswith("503 ")
        or error_message == "503"
        or code in _PEP_503_CODES
    ):
        return 503, {"Retry-After": "10"}
    if (
        error_message.startswith("429 ")
        or error_message == "429"
        or code in _PEP_429_CODES
    ):
        return 429, None
    return 403, None


async def execute_turn(
    req: InvokeAgentRequest,
    envelope: ContextEnvelope,
    *,
    stripped_headers: list[str],
    identity_source: str,
) -> dict[str, Any]:
    """Executes or disaggregates a 5-hop agent turn across QoS bulkheads, PDP, and runtime."""
    gateway = gateway_module()
    hops: list[dict[str, Any]] = []
    issuer = envelope.security.iss
    try:
        hops.append(
            {
                "hop_num": 1,
                "hop": "Hop 0 + 1: Identity (IdP federation, DPoP-bound gateway token)",
                "status": "PASSED",
                "detail": (
                    f"Verified IdP '{issuer}' for '{envelope.tenant.tenant_id}' "
                    f"({identity_source}). Stripped untrusted headers: "
                    f"{stripped_headers or 'none'}."
                ),
            }
        )

        active_metering = getattr(gateway, "_metering", metering)
        estimated_tokens, prompt_cache_hit = active_metering(req)
        finops = gateway.TOKEN_BULKHEAD.check_and_consume(
            tenant_id=envelope.tenant.tenant_id,
            requested_thinking_tokens=req.requested_thinking_tokens,
            estimated_total_tokens=estimated_tokens,
            prompt_cache_hit=prompt_cache_hit,
            session_id=envelope.request.session_id,
        )

        agent_obj = build_agent(req.agent_id)
        remote_runtime = gateway.REMOTE_RUNTIME
        forwarding = remote_runtime is not None and remote_runtime.handles(
            req.agent_id
        )
        active_binding_enabled = getattr(
            gateway,
            "routed_agent_binding_enabled",
            routed_agent_binding_enabled,
        )
        if forwarding or active_binding_enabled():
            built_agent_id = str(getattr(agent_obj, "name", ""))
            if built_agent_id != req.agent_id:
                raise PermissionError(
                    "403 Forbidden: E_AGENT_ROUTING_MISMATCH: the requested agent is not routable."
                )
            gateway.REGISTRY_PDP.verify_agent_access(
                tenant_id=envelope.tenant.tenant_id,
                agent_id=built_agent_id,
                caller_scopes=envelope.tenant.authorized_scopes,
            )
            envelope = gateway.EDGE_VERIFIER.bind_routed_agent(
                envelope, built_agent_id
            )
        if forwarding:
            if remote_runtime is None:
                raise HTTPException(
                    status_code=503, detail={"error": "E_RUNTIME_UNAVAILABLE"}
                )
            return await remote_runtime.run_turn(
                req,
                envelope,
                hops=hops,
                finops=finops,
                estimated_tokens=estimated_tokens,
                prompt_cache_hit=prompt_cache_hit,
                identity_source=identity_source,
            )
        return await run_agent_turn(
            req,
            envelope,
            services=gateway.TURN_SERVICES,
            agent_obj=agent_obj,
            hops=hops,
            finops=finops,
            estimated_tokens=estimated_tokens,
            prompt_cache_hit=prompt_cache_hit,
            identity_source=identity_source,
        )

    except PermissionError as exc:
        msg = str(exc)
        status_code, response_headers = _permission_error_status_and_headers(
            exc
        )
        blocked_at_hop = len(hops) + 1
        gateway.OTEL_SINK.record(
            OTelAuditSpan(
                trace_id=f"trace-blocked-{uuid.uuid4().hex[:8]}",
                tenant_id=envelope.tenant.tenant_id,
                subscription_tier=str(envelope.tenant.subscription_tier),
                agent_id=req.agent_id,
                model_id="blocked-at-pep",
                tool_name=req.tool_name,
                prompt_cache_hit=False,
                thinking_tokens_budget=req.requested_thinking_tokens,
                status=f"BLOCKED_{status_code}",
            )
        )
        if identity_source != "SANDBOX_SCENARIO_PERSONA":
            logger.info(
                "turn blocked at hop %s: %s",
                blocked_at_hop,
                public_error_code(exc),
            )
            raise HTTPException(
                status_code=status_code,
                detail={
                    "status": "BLOCKED_BY_AGENT_SANDBOX_GOVERNANCE",
                    "http_code": status_code,
                    "blocked_at_hop": blocked_at_hop,
                    "error": public_error_code(exc),
                },
                headers=response_headers,
            ) from exc
        raise HTTPException(
            status_code=status_code,
            detail={
                "status": "BLOCKED_BY_AGENT_SANDBOX_GOVERNANCE",
                "http_code": status_code,
                "blocked_at_hop": blocked_at_hop,
                "error": msg,
                "completed_hops": hops,
            },
            headers=response_headers,
        ) from exc


@router.post("/api/v1/invoke-agent-live")
async def invoke_agent_live(
    req: InvokeAgentRequest, envelope: Caller
) -> dict[str, Any]:
    """Runs a live ADK 2.0 `InMemoryRunner` + Gemini turn as the authenticated caller."""
    gateway = gateway_module()
    try:
        agent_obj = build_agent(req.agent_id)
        if str(getattr(agent_obj, "name", "")) != req.agent_id:
            raise PermissionError(
                "403 Forbidden: E_AGENT_ROUTING_MISMATCH: the requested agent is not routable."
            )
        gateway.REGISTRY_PDP.verify_agent_access(
            tenant_id=envelope.tenant.tenant_id,
            agent_id=req.agent_id,
            caller_scopes=envelope.tenant.authorized_scopes,
        )
        if req.sandbox_code is not None:
            if (
                not isinstance(req.sandbox_code, str)
                or not req.sandbox_code.strip()
            ):
                raise HTTPException(
                    status_code=422,
                    detail={"error": "E_SANDBOX_INVALID_CODE"},
                )
            try:
                resolved_lang = sandbox_execution.SandboxLanguage(
                    str(req.sandbox_language or "python").lower()
                )
            except ValueError as val_exc:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "E_SANDBOX_INVALID_CODE"},
                ) from val_exc
            gateway.SANDBOX_MANAGER._assert_caller_authorized(
                envelope=envelope,
                agent_id=req.agent_id,
                language=resolved_lang,
            )
            interceptors.ingress_model_armor_screen(
                prompt=req.sandbox_code,
                caller_tenant_id=envelope.tenant.tenant_id,
                use_live_model_armor=True,
            )
            try:
                sandbox_execution.assert_zero_credentials_and_egress_safe(
                    code=req.sandbox_code
                )
            except ValueError as val_exc:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "E_SANDBOX_INVALID_CODE"},
                ) from val_exc
    except HTTPException:
        raise
    except PermissionError as exc:
        status_code, response_headers = _permission_error_status_and_headers(
            exc
        )
        raise HTTPException(
            status_code=status_code,
            detail={"error": public_error_code(exc)},
            headers=response_headers,
        ) from exc

    def _simulated_live_payload(
        *,
        adc_note: str | None = None,
        sandbox_receipt: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        tool_calls = ["query_telemetry_rls"]
        if sandbox_receipt is not None:
            tool_calls.append("execute_live_gemini_diagnostic_sandbox")
        payload: dict[str, Any] = {
            "status": "LOCAL_ADK_SIMULATION",
            "mode": (
                "LOCAL_SANDBOX_FALLBACK"
                if adc_note
                else (
                    "LOCAL_SANDBOX_SIMULATION (Set CYMBAL_LIVE_GCP=1 for live Gemini execution)"
                )
            ),
            "tenant_id": envelope.tenant.tenant_id,
            "tier": str(envelope.tenant.subscription_tier),
            "agent_id": req.agent_id,
            "model": "gemini-4-hydrogen",
            "tool_calls": tool_calls,
            "final_response": (
                f"[Simulated ADK 2.0 InMemoryRunner for {envelope.tenant.tenant_id}] "
                "Correlated P1 telemetry under AlloyDB SET LOCAL app.current_tenant_id "
                "with all customer PII redacted via Cloud DLP."
            ),
        }
        if adc_note:
            payload["gcp_adc_note"] = adc_note
        if sandbox_receipt is not None:
            payload["sandbox_execution"] = sandbox_receipt
        return payload

    if not gcp_live_bridge.is_live_gcp_enabled():
        sandbox_receipt: dict[str, object] | None = None
        if req.sandbox_code is not None:
            try:
                sandbox_receipt = await asyncio.to_thread(
                    gateway.SANDBOX_MANAGER.execute_in_session_sandbox,
                    envelope=envelope,
                    agent_id=req.agent_id,
                    code=req.sandbox_code,
                    language=req.sandbox_language,
                )
            except PermissionError as exc:
                status_code, response_headers = (
                    _permission_error_status_and_headers(exc)
                )
                raise HTTPException(
                    status_code=status_code,
                    detail={"error": public_error_code(exc)},
                    headers=response_headers,
                ) from exc
            except ValueError as val_exc:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "E_SANDBOX_INVALID_CODE"},
                ) from val_exc
        return _simulated_live_payload(sandbox_receipt=sandbox_receipt)

    try:
        runner = gcp_live_bridge.LiveADKVertexRunner()
        if req.agent_id == "finvault_regulatory_escalation_agent":
            alpha_kwargs: dict[str, Any] = {
                "envelope": envelope,
                "user_prompt": req.prompt,
            }
            if req.sandbox_code is not None:
                alpha_kwargs["sandbox_code"] = req.sandbox_code
                alpha_kwargs["sandbox_language"] = req.sandbox_language
            return await runner.run_finvault_agent_alpha_turn(**alpha_kwargs)
        diag_kwargs: dict[str, Any] = {
            "envelope": envelope,
            "user_prompt": req.prompt,
            "agent_id": req.agent_id,
        }
        if req.sandbox_code is not None:
            diag_kwargs["sandbox_code"] = req.sandbox_code
            diag_kwargs["sandbox_language"] = req.sandbox_language
        return await runner.run_tenant_diagnostic_turn(**diag_kwargs)
    except HTTPException:
        raise
    except PermissionError as exc:
        status_code, response_headers = _permission_error_status_and_headers(
            exc
        )
        raise HTTPException(
            status_code=status_code,
            detail={"error": public_error_code(exc)},
            headers=response_headers,
        ) from exc
    except ValueError as val_exc:
        if "E_SANDBOX_" in str(val_exc):
            raise HTTPException(
                status_code=422,
                detail={"error": "E_SANDBOX_INVALID_CODE"},
            ) from val_exc
        logger.warning("live ADK turn failed: %s", type(val_exc).__name__)
        if not active_sandbox_mode():
            raise HTTPException(
                status_code=503,
                detail={"error": "E_LIVE_GCP_STEP_FAILED"},
            ) from val_exc
        return _simulated_live_payload(adc_note="E_LIVE_GCP_STEP_FAILED")
    except sandbox_execution.SandboxUnavailableError:
        raise
    except Exception as gcp_exc:
        logger.warning("live ADK turn failed: %s", type(gcp_exc).__name__)
        if not active_sandbox_mode():
            raise HTTPException(
                status_code=503,
                detail={"error": "E_LIVE_GCP_STEP_FAILED"},
            ) from gcp_exc
        return _simulated_live_payload(adc_note="E_LIVE_GCP_STEP_FAILED")


@router.post("/api/v1/model-routing/decide")
async def api_model_routing_decide(
    req: ModelRoutingDecideRequest,
    envelope: Caller,
) -> dict[str, Any]:
    """Evaluates Hop 3 task-aware model routing, FastSearch trimming, and history sanitization."""
    gateway = gateway_module()
    try:
        gateway.REGISTRY_PDP.verify_agent_access(
            tenant_id=envelope.tenant.tenant_id,
            agent_id=req.agent_id,
            caller_scopes=envelope.tenant.authorized_scopes,
        )
        entitled_tools = gateway.REGISTRY_PDP.get_entitled_tools(
            tenant_id=envelope.tenant.tenant_id,
            agent_id=req.agent_id,
            caller_scopes=envelope.tenant.authorized_scopes,
        )
        decision = gateway.MODEL_ROUTING_PDP.decide_route(
            envelope=envelope,
            agent_id=req.agent_id,
            tool_name=req.tool_name,
            prompt=req.prompt,
            entitled_tools=entitled_tools,
            requested_thinking_budget=req.requested_thinking_tokens,
            requested_mode=req.routing_mode,
            previous_model_id=req.previous_model_id,
            session_history=req.session_history,
        )
        return {
            "status": "ROUTING_DECIDED",
            "tenant_id": decision.tenant_id,
            "agent_id": decision.agent_id,
            "routing_mode": str(decision.routing_mode),
            "task_complexity": str(decision.task_complexity),
            "selected_model": decision.selected_model,
            "advisor_model": decision.advisor_model,
            "effective_thinking_budget": decision.effective_thinking_budget,
            "pruned_active_tools": list(decision.pruned_active_tools),
            "trimmed_write_tools_count": decision.trimmed_write_tools_count,
            "allow_subagent_delegation": decision.allow_subagent_delegation,
            "schema_tokens_saved": decision.schema_tokens_saved,
            "estimated_turn_usd_saved": decision.estimated_turn_usd_saved,
            "cross_family_thoughts_stripped": decision.cross_family_thoughts_stripped,
            "sanitized_session_history": list(
                decision.sanitized_session_history
            ),
        }
    except PermissionError as exc:
        status_code, _ = _permission_error_status_and_headers(exc)
        raise HTTPException(
            status_code=status_code,
            detail={"error": public_error_code(exc)},
        ) from exc


@router.post("/api/v1/model-routing/escalate-askpro")
async def api_model_routing_escalate_askpro(
    req: AskProEscalationRequest,
    envelope: Caller,
) -> dict[str, Any]:
    """Executes a bounded mid-task advisor consultation (capped at 1 consultation per turn)."""
    gateway = gateway_module()
    try:
        return gateway.MODEL_ROUTING_PDP.escalate_to_advisor(
            envelope=envelope,
            trace_id=req.trace_id,
            escalation_reason=req.escalation_reason,
            compact_evidence_digest=req.compact_evidence_digest,
        )
    except PermissionError as exc:
        status_code, _ = _permission_error_status_and_headers(exc)
        raise HTTPException(
            status_code=status_code,
            detail={"error": public_error_code(exc)},
        ) from exc


@router.get("/api/v1/model-routing/telemetry")
async def api_model_routing_telemetry(envelope: Caller) -> dict[str, Any]:
    """Returns the tenant-isolated Glass-Box Routing Savings Ledger for the caller."""
    gateway = gateway_module()
    try:
        return gateway.MODEL_ROUTING_PDP.ledger.get_tenant_summary(envelope)
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={"error": public_error_code(exc)},
        ) from exc


@router.post("/api/v1/sandbox/agents/suspend", dependencies=SandboxOnly)
async def api_sandbox_suspend_agent(
    req: AgentSuspensionActionRequest,
) -> dict[str, Any]:
    """Sandbox control-plane kill-switch: suspends an agent across gateway, runtime & broker."""
    from agents.registry import AGENT_CATALOG

    if req.agent_id not in AGENT_CATALOG:
        raise HTTPException(
            status_code=404, detail={"error": "E_AGENT_NOT_AVAILABLE"}
        )
    rec = suspend_agent(req.agent_id, reason=req.reason)
    return {
        "status": "AGENT_SUSPENDED",
        "agent_id": rec.agent_id,
        "reason": rec.reason,
        "suspended_at": rec.suspended_at,
    }


@router.post("/api/v1/sandbox/agents/resume", dependencies=SandboxOnly)
async def api_sandbox_resume_agent(
    req: AgentSuspensionActionRequest,
) -> dict[str, Any]:
    """Sandbox control-plane action: lifts an emergency suspension on a catalog agent."""
    from agents.registry import AGENT_CATALOG

    if req.agent_id not in AGENT_CATALOG:
        raise HTTPException(
            status_code=404, detail={"error": "E_AGENT_NOT_AVAILABLE"}
        )
    was_suspended = resume_agent(req.agent_id)
    return {
        "status": "AGENT_ACTIVE",
        "agent_id": req.agent_id,
        "resumed": was_suspended,
    }
