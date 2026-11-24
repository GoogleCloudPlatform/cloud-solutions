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

# pylint: disable=inconsistent-quotes,line-too-long,unused-argument

"""Stateless Model Context Protocol (MCP) Tool Server (Subsystem 7 / Hop 5).

Every tool executes statelessly without sticky session affinity:
1. Extracts `temp:tenant_id` and `temp:authorized_scopes` from the verified ADK `tool_context`.
2. Verifies 2LO (Cymbal internal APIs) or 3LO (Google Workspace Drive/Calendar/Gmail & Jira for
   FinVault Bank;
   Microsoft Entra ID SharePoint / ServiceNow for RetailStream Corp) scopes via Auth Manager.
3. Binds `SET LOCAL app.current_tenant_id` in AlloyDB RLS (`RLSDatabasePool`).
4. Applies Egress Gateway DLP redaction (`egress_dlp_and_nlc_guardrail`) before returning payloads.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from typing import Any

from agents import context as agent_context
from agents import interceptors, sandbox_execution
from agents.context import averify_signed_adk_state
from agents.context_token import AGENT_ID_CLAIM, AUDIENCE_MCP
from agents.interceptors import egress_dlp_and_nlc_guardrail
from agents.registry import (
    TOOL_REGISTRY,
    AgentRegistryPDP,
    is_tool_tenant_allowed,
)
from agents.workload_identity import CallerPrincipal, flag_enabled
from mcp_server.db import RLSDatabasePool

DEFAULT_DB_POOL = RLSDatabasePool()
DEFAULT_AGENT_REGISTRY = AgentRegistryPDP()
DEFAULT_SANDBOX_MANAGER = sandbox_execution.GeminiAgentSandboxManager()
MCP_REQUIRE_AGENT_BINDING_ENV = "MCP_REQUIRE_AGENT_BINDING"


_ERROR_CODE_RE = re.compile(r"\b(E_[A-Z0-9_]+)\b")


def _error_code(
    exc: BaseException, *, default: str = "E_TOOL_FORBIDDEN"
) -> str:
    match = _ERROR_CODE_RE.search(str(exc))
    return match.group(1) if match else default


def _verify_tool_authorization(
    tool_name: str, tool_context: Any
) -> tuple[str, list[str]]:
    """Verifies tenant context and 2LO/3LO Auth Manager scopes before executing any MCP tool."""
    state: dict[str, Any] = getattr(tool_context, "state", {})
    tenant_id: str | None = state.get("temp:tenant_id")
    if not tenant_id:
        raise PermissionError(
            f"403 Forbidden: Missing immutable temp:tenant_id when invoking '{tool_name}'."
        )

    tool_meta = TOOL_REGISTRY.get(tool_name)
    if tool_meta is None:
        raise KeyError(f"Unknown MCP tool: {tool_name}")

    if not is_tool_tenant_allowed(tenant_id, tool_meta):
        raise PermissionError(
            f"403 Forbidden: Tenant '{tenant_id}' is not entitled to invoke '{tool_name}'."
        )

    scopes: list[str] = list(state.get("temp:authorized_scopes", []))
    if tool_meta.required_scope not in scopes:
        if tool_name == "execute_diagnostic_sandbox":
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_SCOPE_DENIED: Missing "
                "required "
                f"{tool_meta.auth_mode}"
                " scope "
                f"'{tool_meta.required_scope}' for tool '{tool_name}'."
            )
        raise PermissionError(
            f"403 Forbidden: Missing required {tool_meta.auth_mode} scope "
            f"'{tool_meta.required_scope}' for tool '{tool_name}'."
        )
    return tenant_id, scopes


def _extract_rbac_context(
    tool_context: Any,
    *,
    default_shared_agent: bool = False,
) -> tuple[str, str | None]:
    """Extracts verified `user_role` and `agent_id` from `tool_context` for fail-closed DB GUCs."""
    state: dict[str, Any] = getattr(tool_context, "state", {})
    raw_role = state.get("temp:user_role")
    user_role = raw_role.strip() if isinstance(raw_role, str) else ""
    if not user_role:
        raise PermissionError(
            "403 Forbidden: E_MISSING_USER_ROLE: Verified temp:user_role is required for DB RBAC."
        )
    raw_agent_id = state.get("temp:agent_id")
    agent_id = raw_agent_id.strip() if isinstance(raw_agent_id, str) else ""
    if not agent_id:
        agent_obj = getattr(tool_context, "agent", None)
        raw_name = getattr(agent_obj, "name", None)
        agent_id = raw_name.strip() if isinstance(raw_name, str) else ""
    if not agent_id:
        if flag_enabled(MCP_REQUIRE_AGENT_BINDING_ENV):
            raise PermissionError(
                "403 Forbidden: E_MISSING_AGENT_ID: Verified temp:agent_id is required when "
                "MCP_REQUIRE_AGENT_BINDING=1."
            )
        if default_shared_agent:
            return user_role, "cymbal_shared_diagnostic_agent"
        return user_role, None
    return user_role, agent_id


async def query_telemetry_rls(
    severity: str | None = None,
    raw_sql: str | None = None,
    tool_context: Any = None,
    db_pool: RLSDatabasePool = DEFAULT_DB_POOL,
) -> dict[str, Any]:
    """2LO MCP Tool: Queries AlloyDB `tenant_incidents` with `SET LOCAL app.current_tenant_id` (+
    RBAC GUCs).
    """
    tenant_id, _ = _verify_tool_authorization(
        "query_telemetry_rls", tool_context
    )
    user_role, agent_id = _extract_rbac_context(
        tool_context, default_shared_agent=True
    )
    rows = await db_pool.query_incidents(
        tenant_id=tenant_id,
        user_role=user_role,
        agent_id=agent_id,
        severity_filter=severity,
        raw_sql=raw_sql,
    )
    sanitized_rows: list[dict[str, Any]] = []
    for row in rows:
        clean_row = dict(row)
        clean_row["pii_notes"] = egress_dlp_and_nlc_guardrail(
            tenant_id=tenant_id,
            tool_name="query_telemetry_rls",
            tool_args={"severity": severity},
            raw_output=str(row.get("pii_notes", "")),
        )
        sanitized_rows.append(clean_row)
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "rls_guc": db_pool.last_executed_guc,
        "incidents": sanitized_rows,
    }


async def read_runbook(
    tool_context: Any = None,
    db_pool: RLSDatabasePool = DEFAULT_DB_POOL,
) -> dict[str, Any]:
    """2LO MCP Tool: Reads tenant-scoped remediation runbooks from AlloyDB with RLS + RBAC."""
    tenant_id, _ = _verify_tool_authorization("read_runbook", tool_context)
    user_role, agent_id = _extract_rbac_context(
        tool_context, default_shared_agent=True
    )
    runbooks = await db_pool.query_runbooks(
        tenant_id=tenant_id,
        user_role=user_role,
        agent_id=agent_id,
    )
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "runbooks": runbooks,
    }


async def create_jira_incident(
    summary: str,
    priority: str = "P1",
    tool_context: Any = None,
) -> dict[str, Any]:
    """3LO MCP Tool (FinVault Bank only): Creates a Jira incident via delegated OAuth."""
    tenant_id, _ = _verify_tool_authorization(
        "create_jira_incident", tool_context
    )
    clean_summary = egress_dlp_and_nlc_guardrail(
        tenant_id=tenant_id,
        tool_name="create_jira_incident",
        tool_args={"summary": summary, "priority": priority},
        raw_output=summary,
    )
    return {
        "status": "created",
        "tenant_id": tenant_id,
        "provider": "jira-cloud-3lo",
        "ticket_key": "FINVAULT-901",
        "summary": clean_summary,
    }


async def send_gmail_brief(
    recipient: str,
    body: str,
    tool_context: Any = None,
) -> dict[str, Any]:
    """3LO MCP Tool (FinVault Bank only): Sends an executive incident brief via Google OIDC."""
    tenant_id, _ = _verify_tool_authorization("send_gmail_brief", tool_context)
    clean_body = egress_dlp_and_nlc_guardrail(
        tenant_id=tenant_id,
        tool_name="send_gmail_brief",
        tool_args={"recipient": recipient},
        raw_output=body,
    )
    return {
        "status": "sent",
        "tenant_id": tenant_id,
        "provider": "google-workspace-3lo-oidc",
        "recipient": recipient,
        "body": clean_body,
    }


async def schedule_calendar_postmortem(
    incident_id: str,
    title: str = "P1 Wire Settlement Post-Mortem",
    tool_context: Any = None,
) -> dict[str, Any]:
    """3LO MCP Tool (FinVault Bank only): Schedules a Google Calendar post-mortem via 3LO Google
    OIDC.
    """
    tenant_id, _ = _verify_tool_authorization(
        "schedule_calendar_postmortem", tool_context
    )
    clean_title = egress_dlp_and_nlc_guardrail(
        tenant_id=tenant_id,
        tool_name="schedule_calendar_postmortem",
        tool_args={"incident_id": incident_id},
        raw_output=title,
    )
    return {
        "status": "scheduled",
        "tenant_id": tenant_id,
        "provider": "google-calendar-3lo-oidc",
        "incident_id": incident_id,
        "title": clean_title,
    }


async def escalate_regulatory_filing(
    incident_id: str,
    regulator: str = "OCC",
    tool_context: Any = None,
) -> dict[str, Any]:
    """3LO MCP Tool (FinVault Agent Alpha only): Escalates banking incident to OCC/FDIC."""
    tenant_id, _ = _verify_tool_authorization(
        "escalate_regulatory_filing", tool_context
    )
    return {
        "status": "escalated",
        "tenant_id": tenant_id,
        "agent": "finvault_regulatory_escalation_agent",
        "incident_id": incident_id,
        "regulator": regulator,
    }


async def create_servicenow_incident(
    short_description: str,
    urgency: str = "1",
    tool_context: Any = None,
) -> dict[str, Any]:
    """3LO MCP Tool (RetailStream Corp only): Creates a ServiceNow ITOM ticket via Entra ID 3LO."""
    tenant_id, _ = _verify_tool_authorization(
        "create_servicenow_incident", tool_context
    )
    clean_desc = egress_dlp_and_nlc_guardrail(
        tenant_id=tenant_id,
        tool_name="create_servicenow_incident",
        tool_args={"short_description": short_description},
        raw_output=short_description,
    )
    return {
        "status": "created",
        "tenant_id": tenant_id,
        "provider": "servicenow-itom-entra-3lo",
        "incident_number": "INC0049281",
        "short_description": clean_desc,
    }


async def read_sharepoint_runbook(
    site_path: str,
    tool_context: Any = None,
) -> dict[str, Any]:
    """3LO MCP Tool (RetailStream Corp only): Reads runbook from SharePoint via Entra ID 3LO."""
    tenant_id, _ = _verify_tool_authorization(
        "read_sharepoint_runbook", tool_context
    )
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "provider": "microsoft-entra-sharepoint-3lo",
        "site_path": site_path,
    }


def _envelope_from_tool_context(
    tool_context: object,
    *,
    tenant_id: str,
    scopes: list[str],
    agent_id: str,
) -> agent_context.ContextEnvelope:
    """Rebuilds a verified `ContextEnvelope` from signed ADK `tool_context.state`."""
    state: Mapping[str, object] = getattr(tool_context, "state", {})
    tenant_meta = agent_context.TENANT_DIRECTORY.get(tenant_id)
    if tenant_meta is None:
        raise PermissionError(
            f"403 Forbidden: E_TENANT_OFFBOARDED: Tenant '{tenant_id}' is not active."
        )
    user_sub = str(state.get("temp:user_sub") or "").strip()
    session_id = str(state.get("temp:session_id") or "").strip()
    if not user_sub or not session_id:
        raise PermissionError(
            "403 Forbidden: E_MISSING_SESSION_PRINCIPAL: Verified user_sub and session_id required."
        )
    tier_raw = state.get("temp:tier") or tenant_meta.get("tier") or "standard"
    tier_enum = agent_context.SubscriptionTier(str(tier_raw))
    user_role = str(state.get("temp:user_role") or "").strip()
    if not user_role:
        raise PermissionError(
            "403 Forbidden: E_MISSING_USER_ROLE: Verified temp:user_role required."
        )
    thinking_raw = state.get("temp:thinking_budget")
    thinking_budget = (
        int(thinking_raw)
        if isinstance(thinking_raw, (int, str))
        else int(tenant_meta.get("thinking_budget", 4000))
    )
    return agent_context.ContextEnvelope(
        security=agent_context.SecurityContext(
            iss=str(
                state.get("temp:iss")
                or tenant_meta.get("iss")
                or "https://accounts.google.com"
            ),
            sub=user_sub,
            aud="https://agent-gateway.cymbal.internal",
            exp=0,
            jti=str(state.get("temp:jti") or "mcp-turn"),
            kid="mcp-verified",
            dpop_jkt=str(state.get("temp:dpop_jkt") or "mcp-verified"),
            user_role=user_role,
            idp_provider=str(
                state.get("temp:idp_provider") or "google_workspace_oidc"
            ),
        ),
        tenant=agent_context.TenantContext(
            tenant_id=tenant_id,
            subscription_tier=tier_enum,
            org_unit=str(
                state.get("temp:org_unit")
                or tenant_meta.get("org_unit")
                or "pooled"
            ),
            authorized_scopes=tuple(scopes),
            thinking_token_budget=thinking_budget,
            cmek_key_name=str(
                state.get("temp:cmek_key_name")
                or tenant_meta.get("cmek_key_name")
                or ""
            ),
        ),
        request=agent_context.RequestContext(
            trace_id=str(state.get("temp:trace_id") or "mcp-trace"),
            correlation_id=str(state.get("temp:correlation_id") or "mcp-corr"),
            session_id=session_id,
        ),
        context_token=str(state.get("temp:context_token") or ""),
        delegation_sig=str(state.get("temp:delegation_sig") or ""),
        agent_id=agent_id,
    )


async def execute_diagnostic_sandbox(
    code: str,
    language: str = "python",
    readonly_tool_output: Mapping[str, object] | None = None,
    tool_context: Any = None,
    sandbox_manager: sandbox_execution.GeminiAgentSandboxManager = DEFAULT_SANDBOX_MANAGER,
) -> dict[str, object]:
    """2LO MCP Tool: Executes diagnostic code inside a per-session Gemini `SandboxEnvironment`.

    Args:
        code: Diagnostic Python, JavaScript, or Bash snippet to execute in `/workspace`.
        language: Target sandbox language (`python`, `javascript`, or `bash`).
        readonly_tool_output: Optional sanitized MCP tool output passed into `/workspace`.
        tool_context: Verified ADK `tool_context` carrying `temp:tenant_id` and session claims.
        sandbox_manager: `GeminiAgentSandboxManager` enforcing Claim-and-Taint isolation.

    Returns:
        Sanitized agent sandbox execution receipt (`sandbox_id`, `taint`, `sanitized_stdout`).
    """
    tenant_id, scopes = _verify_tool_authorization(
        "execute_diagnostic_sandbox", tool_context
    )
    _, extracted_agent_id = _extract_rbac_context(tool_context)
    if not extracted_agent_id:
        raise PermissionError(
            "403 Forbidden: E_AGENT_ID_MISSING: "
            "Verified temp:agent_id or tool_context.agent.name is required."
        )
    resolved_agent_id = extracted_agent_id
    envelope = _envelope_from_tool_context(
        tool_context,
        tenant_id=tenant_id,
        scopes=scopes,
        agent_id=resolved_agent_id,
    )
    interceptors.ingress_model_armor_screen(
        prompt=code,
        caller_tenant_id=tenant_id,
        use_live_model_armor=True,
    )
    receipt = await asyncio.to_thread(
        sandbox_manager.execute_in_session_sandbox,
        envelope=envelope,
        agent_id=resolved_agent_id,
        code=code,
        language=language,
        readonly_tool_output=readonly_tool_output,
    )
    return {
        "status": "executed",
        "tenant_id": tenant_id,
        "provider": "gemini-agent-sandbox-2lo",
        "sandbox_execution": receipt,
    }


_MCP_TOOL_DISPATCH: dict[str, Any] = {
    "query_telemetry_rls": query_telemetry_rls,
    "read_runbook": read_runbook,
    "execute_diagnostic_sandbox": execute_diagnostic_sandbox,
    "create_jira_incident": create_jira_incident,
    "send_gmail_brief": send_gmail_brief,
    "schedule_calendar_postmortem": schedule_calendar_postmortem,
    "escalate_regulatory_filing": escalate_regulatory_filing,
    "create_servicenow_incident": create_servicenow_incident,
    "read_sharepoint_runbook": read_sharepoint_runbook,
}


class _MCPWireToolContext:
    """Minimal tool_context constructed from a cryptographically verified MCP wire envelope."""

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state


async def handle_mcp_jsonrpc_request(
    payload: dict[str, Any],
    *,
    verified_adk_state: dict[str, Any] | None = None,
    db_pool: RLSDatabasePool = DEFAULT_DB_POOL,
    sandbox_manager: sandbox_execution.GeminiAgentSandboxManager = DEFAULT_SANDBOX_MANAGER,
    context_verifier: Any | None = None,
    caller_principal: CallerPrincipal | None = None,
    agent_registry: AgentRegistryPDP | None = None,
) -> dict[str, Any]:
    """Model Context Protocol (MCP) JSON-RPC 2.0 wire handler (`tools/list` & `tools/call`).

    Verifies the gateway-signed context token (ES256, `aud` must include `mcp`, public key only)
    and that the wire state (tenant, scopes, CMEK key, identity) matches its claims before listing
    or executing any tool; a missing or invalid token gets -32001.

    ADR-0016 agent layer (`MCP_REQUIRE_AGENT_BINDING=1`, off by default; gates `tools/call` only,
    `tools/list` is unchanged): `tools/call` also needs
    the token's signed `agent_id`, a `caller_principal` (from the transport's verified ID token,
    see `agents.workload_identity`; never from the payload or headers) equal to that agent's
    registered principal, and the agent entitled to `mcp:<tool>`. The in-process handler has no
    transport identity, so this is enabled only once MCP runs as its own service (B5).
    """
    req_id = payload.get("id", 1)
    if payload.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32600,
                "message": "Invalid Request: jsonrpc must be '2.0'",
            },
        }

    state = dict(verified_adk_state or {})
    tenant_id = state.get("temp:tenant_id")
    try:
        # Presence is not enough: scopes and tenant are trusted below, so the signature over them
        # must verify (a forged scope list or tenant is refused at the wire boundary).
        # The depth tag is checked too while this handler runs in the gateway process; a
        # separately deployed MCP server (ADR-0014 B3) verifies only the token and never decides
        # access on depth.
        # Off the event loop (a key refresh may call KMS). A key outage is not caught here: it
        # propagates as `ContextKeyUnavailableError` and the gateway answers 503.
        verified_claims = await averify_signed_adk_state(
            state, audience=AUDIENCE_MCP, verifier=context_verifier
        )
    except PermissionError:
        tenant_id = None
        verified_claims = {}
    if not tenant_id:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32001,
                "message": (
                    "401 Unauthorized: Missing verified ContextEnvelope (temp:tenant_id / "
                    "temp:context_token) on MCP wire boundary."
                ),
            },
        }

    method = payload.get("method", "")
    params = payload.get("params") or {}

    if method == "tools/list":
        scopes = set(state.get("temp:authorized_scopes", []))
        visible_tools = []
        for name, meta in TOOL_REGISTRY.items():
            if (
                "*" in meta.allowed_tenants or tenant_id in meta.allowed_tenants
            ) and (meta.required_scope in scopes):
                visible_tools.append(
                    {
                        "name": name,
                        "auth_mode": meta.auth_mode,
                        "required_scope": meta.required_scope,
                        # Never list other tenants: only whether the tool is shared.
                        "shared": "*" in meta.allowed_tenants,
                    }
                )
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocol": "mcp-jsonrpc-2.0",
                "tenant_id": tenant_id,
                "tools": visible_tools,
            },
        }

    if method == "tools/call":
        tool_name = str(params.get("name", ""))
        arguments = dict(params.get("arguments") or {})
        fn = _MCP_TOOL_DISPATCH.get(tool_name)
        if fn is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method/Tool not found: {tool_name}",
                },
            }
        if verified_claims.get(AGENT_ID_CLAIM):
            state["temp:agent_id"] = str(verified_claims[AGENT_ID_CLAIM])
        wire_ctx = _MCPWireToolContext(state=state)
        try:
            if flag_enabled(MCP_REQUIRE_AGENT_BINDING_ENV):
                (agent_registry or DEFAULT_AGENT_REGISTRY).verify_agent_caller(
                    verified_claims.get(AGENT_ID_CLAIM),
                    caller_principal,
                    f"mcp:{tool_name}",
                )
            if tool_name in ("query_telemetry_rls", "read_runbook"):
                tool_output = await fn(
                    **arguments, tool_context=wire_ctx, db_pool=db_pool
                )
            elif tool_name == "execute_diagnostic_sandbox":
                tool_output = await fn(
                    **arguments,
                    tool_context=wire_ctx,
                    sandbox_manager=sandbox_manager,
                )
            else:
                tool_output = await fn(**arguments, tool_context=wire_ctx)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocol": "mcp-jsonrpc-2.0",
                    "tenant_id": tenant_id,
                    "tool_name": tool_name,
                    "content": tool_output,
                },
            }
        except PermissionError as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                # Code only: PEP messages must not reach the caller verbatim.
                "error": {
                    "code": -32003,
                    "message": f"403 Forbidden: {_error_code(exc)}",
                },
            }
        except (ValueError, TypeError) as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": (
                        f"Invalid params: {_error_code(exc, default='E_INVALID_TOOL_PARAMS')}"
                    ),
                },
            }
        except sandbox_execution.SandboxUnavailableError as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": f"503 Service Unavailable: {exc.code}",
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Unsupported MCP JSON-RPC method: {method}",
        },
    }
