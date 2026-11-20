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

"""Agent Registry & Agent Resource Discovery (ARD) Entitlement Policy Decision Point (PDP).

Implements Governance Pillar 1 (Catalog & Visibility — Hop 2):
- Dynamic catalog query protocol (`/.well-known/ai-catalog.json`)
- Supports both static anchor tenants (`FinVault Bank`, `RetailStream Corp`) and dynamically
  onboarded pooled tenants ($N=1,000+$) via `allowed_tenants=("*",)` for shared 2LO tools while
  strictly locking 3LO and private tools (`Agent Alpha`) to their explicit owner tenants.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from agents.auth.tenant_directory import _BASE_TENANT_DIRECTORY
from agents.context import TENANT_DIRECTORY, SubscriptionTier
from agents.platform_config import get_platform_config
from agents.workload_identity import (
    AgentAuthorizationError,
    AgentBinding,
    CallerPrincipal,
    bindings_from_config,
    check_agent_binding,
    is_agent_suspended,
)


@dataclass(frozen=True)
class CatalogAgentEntry:
    """Agent entry in the ARD catalog (`/.well-known/ai-catalog.json`)."""

    agent_id: str
    display_name: str
    model: str
    visibility: str  # "pooled" or "private"
    owner_tenant_id: str | None
    required_tier: SubscriptionTier
    entitled_tools: tuple[str, ...]
    # ADR-0016 agent layer, per environment from `agent_identity.bindings` in the platform config
    # (see `AgentRegistryPDP.agent_identity`): the agent's expected workload principal and the
    # purposes it may use (`broker:access_token`, `mcp:<tool>`, ...). Unset = not bound.
    workload_principal: str | None = None
    allowed_purposes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CatalogToolEntry:
    """MCP Tool entry in the Agent Registry in Gemini."""

    tool_name: str
    auth_mode: str  # "2LO" or "3LO"
    required_scope: str
    allowed_tenants: tuple[str, ...]


AGENT_CATALOG: dict[str, CatalogAgentEntry] = {
    "cymbal_shared_diagnostic_agent": CatalogAgentEntry(
        agent_id="cymbal_shared_diagnostic_agent",
        display_name="Cymbal Shared Diagnostic Agent",
        model=get_platform_config().models.default_shared_model,
        visibility="pooled",
        owner_tenant_id=None,
        required_tier=SubscriptionTier.STANDARD,
        entitled_tools=(
            "query_telemetry_rls",
            "read_runbook",
            "execute_diagnostic_sandbox",
            "create_jira_incident",
            "send_gmail_brief",
            "create_servicenow_incident",
            "read_sharepoint_runbook",
        ),
    ),
    "finvault_regulatory_escalation_agent": CatalogAgentEntry(
        agent_id="finvault_regulatory_escalation_agent",
        display_name="Agent Alpha — FinVault Regulatory Escalation Agent",
        model="claude-3-7-sonnet@20250219",
        visibility="private",
        owner_tenant_id="tenant-finvault-alpha",
        required_tier=SubscriptionTier.ENTERPRISE,
        entitled_tools=(
            "query_telemetry_rls",
            "read_runbook",
            "execute_diagnostic_sandbox",
            "create_jira_incident",
            "send_gmail_brief",
            "schedule_calendar_postmortem",
            "escalate_regulatory_filing",
        ),
    ),
}

TOOL_REGISTRY: dict[str, CatalogToolEntry] = {
    "query_telemetry_rls": CatalogToolEntry(
        tool_name="query_telemetry_rls",
        auth_mode="2LO",
        required_scope="2lo:cymbal.telemetry.read",
        allowed_tenants=("*",),
    ),
    "read_runbook": CatalogToolEntry(
        tool_name="read_runbook",
        auth_mode="2LO",
        required_scope="2lo:cymbal.runbooks.read",
        allowed_tenants=("*",),
    ),
    "execute_diagnostic_sandbox": CatalogToolEntry(
        tool_name="execute_diagnostic_sandbox",
        auth_mode="2LO",
        required_scope="2lo:cymbal.sandbox.execute",
        allowed_tenants=("*",),
    ),
    "create_jira_incident": CatalogToolEntry(
        tool_name="create_jira_incident",
        auth_mode="3LO",
        required_scope="3lo:jira.incidents.write",
        allowed_tenants=("tenant-finvault-alpha",),
    ),
    "send_gmail_brief": CatalogToolEntry(
        tool_name="send_gmail_brief",
        auth_mode="3LO",
        required_scope="3lo:google.gmail.send",
        allowed_tenants=("tenant-finvault-alpha",),
    ),
    "schedule_calendar_postmortem": CatalogToolEntry(
        tool_name="schedule_calendar_postmortem",
        auth_mode="3LO",
        required_scope="3lo:google.calendar.events",
        allowed_tenants=("tenant-finvault-alpha",),
    ),
    "escalate_regulatory_filing": CatalogToolEntry(
        tool_name="escalate_regulatory_filing",
        auth_mode="3LO",
        required_scope="3lo:google.drive.readonly",
        allowed_tenants=("tenant-finvault-alpha",),
    ),
    "create_servicenow_incident": CatalogToolEntry(
        tool_name="create_servicenow_incident",
        auth_mode="3LO",
        required_scope="3lo:servicenow.itom.write",
        allowed_tenants=("tenant-retailstream-beta",),
    ),
    "read_sharepoint_runbook": CatalogToolEntry(
        tool_name="read_sharepoint_runbook",
        auth_mode="3LO",
        required_scope="3lo:microsoft.sharepoint.readonly",
        allowed_tenants=("tenant-retailstream-beta",),
    ),
}


def _configured_agent_bindings() -> Mapping[str, AgentBinding]:
    return bindings_from_config(get_platform_config())


_DYNAMIC_AGENT_IDS: set[str] = set()


def is_tool_tenant_allowed(tenant_id: str, tool_meta: CatalogToolEntry) -> bool:
    """Checks whether `tenant_id` is allowed to invoke `tool_meta` before scope intersection.

    Static baseline tenants (`_BASE_TENANT_DIRECTORY`) remain pinned to `tool_meta.allowed_tenants`,
    while dynamically onboarded tenants may invoke 3LO tools explicitly granted in their manifest
    `authorized_scopes`.

    Args:
        tenant_id: Verified caller tenant identifier.
        tool_meta: Tool entry from `TOOL_REGISTRY`.

    Returns:
        `True` if the tenant is eligible for `tool_meta`, `False` otherwise.
    """
    if (
        "*" in tool_meta.allowed_tenants
        or tenant_id in tool_meta.allowed_tenants
    ):
        return True
    if (
        tenant_id in TENANT_DIRECTORY
        and tenant_id not in _BASE_TENANT_DIRECTORY
    ):
        tenant_scopes = TENANT_DIRECTORY[tenant_id].get("authorized_scopes", ())
        return tool_meta.required_scope in tenant_scopes
    return False


def register_dynamic_private_agent(
    *,
    agent_id: str,
    display_name: str,
    model: str,
    owner_tenant_id: str,
    required_tier: SubscriptionTier,
    entitled_tools: tuple[str, ...] | None = None,
) -> CatalogAgentEntry:
    """Registers a tenant-owned private catalog agent for a dynamically onboarded tenant.

    Args:
        agent_id: Unique private agent identifier.
        display_name: Human-readable display name for ARD discovery.
        model: Foundation model identifier configured for the private agent.
        owner_tenant_id: Owning enterprise `tenant_id`.
        required_tier: Minimum subscription tier required.
        entitled_tools: Optional candidate tool tuple; defaults to all `TOOL_REGISTRY` keys.

    Returns:
        Registered `CatalogAgentEntry`.

    Raises:
        ValueError: If `agent_id` already belongs to another tenant (built-in or dynamic), or is
            a built-in agent. A tenant may only re-register its own dynamic agent.
    """
    existing = AGENT_CATALOG.get(agent_id)
    if existing is not None and (
        existing.owner_tenant_id != owner_tenant_id
        or agent_id not in _DYNAMIC_AGENT_IDS
    ):
        raise ValueError(
            f"Agent id '{agent_id}' is already registered and cannot be replaced."
        )
    entry = CatalogAgentEntry(
        agent_id=agent_id,
        display_name=display_name,
        model=model,
        visibility="private",
        owner_tenant_id=owner_tenant_id,
        required_tier=required_tier,
        entitled_tools=(
            entitled_tools
            if entitled_tools is not None
            else tuple(TOOL_REGISTRY)
        ),
    )
    AGENT_CATALOG[agent_id] = entry
    _DYNAMIC_AGENT_IDS.add(agent_id)
    return entry


def evict_dynamic_agents_for_tenant(tenant_id: str) -> int:
    """Removes dynamically registered private agents owned by `tenant_id`.

    Args:
        tenant_id: Offboarded tenant identifier.

    Returns:
        Count of removed dynamic private agent entries.
    """
    matching_ids = [
        agent_id
        for agent_id in list(_DYNAMIC_AGENT_IDS)
        if (entry := AGENT_CATALOG.get(agent_id)) is not None
        and entry.owner_tenant_id == tenant_id
    ]
    for agent_id in matching_ids:
        AGENT_CATALOG.pop(agent_id, None)
        _DYNAMIC_AGENT_IDS.discard(agent_id)
    return len(matching_ids)


def reset_dynamic_agents() -> None:
    """Removes all dynamically registered private agents from `AGENT_CATALOG`."""
    for agent_id in list(_DYNAMIC_AGENT_IDS):
        AGENT_CATALOG.pop(agent_id, None)
    _DYNAMIC_AGENT_IDS.clear()


class AgentRegistryPDP:
    """Hop 2 Policy Decision Point: Filters agents and tools by tenant entitlement."""

    def __init__(
        self,
        *,
        agent_bindings: Callable[[], Mapping[str, AgentBinding]] | None = None,
    ) -> None:
        self._agent_bindings = agent_bindings or _configured_agent_bindings

    def agent_identity(self, agent_id: str) -> CatalogAgentEntry:
        """The catalog entry with its ADR-0016 binding (principal, purposes) for this
        environment.
        """
        entry = (
            AGENT_CATALOG.get(agent_id) if isinstance(agent_id, str) else None
        )
        if entry is None:
            raise AgentAuthorizationError("E_AGENT_NOT_AVAILABLE")
        binding = self._agent_bindings().get(agent_id)
        if binding is None:
            return entry
        return replace(
            entry,
            workload_principal=binding.workload_principal,
            allowed_purposes=binding.allowed_purposes,
        )

    def verify_agent_caller(
        self,
        agent_id: str,
        caller_principal: CallerPrincipal | None,
        purpose: str,
    ) -> CatalogAgentEntry:
        """ADR-0016 agent layer: the calling workload IS `agent_id` and may do `purpose`.

        `agent_id` must come from a verified context token and `caller_principal` from a verified
        ID token (`agents.workload_identity`), never from request fields or headers. Fails closed:
        an unknown agent, an agent with no configured principal (in any environment), a missing or
        different caller, or a purpose the agent is not allowed is refused. For `mcp:<tool>` the
        tool must also be in the agent's catalog `entitled_tools`.
        """
        if not isinstance(agent_id, str) or not agent_id:
            raise AgentAuthorizationError("E_AGENT_ID_MISSING")
        entry = self.agent_identity(agent_id)
        bound = (
            {
                agent_id: AgentBinding(
                    agent_id=agent_id,
                    workload_principal=entry.workload_principal,
                    allowed_purposes=entry.allowed_purposes,
                )
            }
            if entry.workload_principal
            else {}
        )
        check_agent_binding(
            agent_id=agent_id,
            caller=caller_principal,
            purpose=purpose,
            bindings=bound,
        )
        if (
            purpose.startswith("mcp:")
            and purpose[4:] not in entry.entitled_tools
        ):
            raise AgentAuthorizationError("E_AGENT_TOOL_NOT_ENTITLED")
        return entry

    def discover_ai_catalog(self, tenant_id: str) -> dict[str, Any]:
        """Implements ARD `/.well-known/ai-catalog.json` filtered by calling tenant."""
        if tenant_id not in TENANT_DIRECTORY:
            raise PermissionError(
                f"403 Forbidden: Unknown tenant '{tenant_id}'."
            )

        visible_agents: list[dict[str, Any]] = []
        for entry in AGENT_CATALOG.values():
            if (
                entry.visibility == "private"
                and entry.owner_tenant_id != tenant_id
            ):
                continue
            if is_agent_suspended(entry.agent_id):
                continue
            entitled_tools = self.get_entitled_tools(
                tenant_id=tenant_id,
                agent_id=entry.agent_id,
            )
            visible_agents.append(
                {
                    "agent_id": entry.agent_id,
                    "display_name": entry.display_name,
                    "model": entry.model,
                    "visibility": entry.visibility,
                    "entitled_tools": entitled_tools,
                }
            )
        return {
            "protocol": "ARD/1.0",
            "endpoint": "/.well-known/ai-catalog.json",
            "tenant_id": tenant_id,
            "agents": visible_agents,
        }

    def verify_agent_access(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        caller_scopes: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> CatalogAgentEntry:
        """Verifies whether `tenant_id` (and optional intra-tenant user RBAC `caller_scopes`) can
        invoke `agent_id`.
        """
        if tenant_id not in TENANT_DIRECTORY:
            raise PermissionError(
                f"403 Forbidden: Unauthenticated tenant '{tenant_id}'."
            )
        entry = AGENT_CATALOG.get(agent_id)
        # Unknown and other tenants' private agents look the same (no existence oracle: agent IDs
        # can contain tenant names).
        if entry is None or (
            entry.visibility == "private" and entry.owner_tenant_id != tenant_id
        ):
            raise PermissionError(
                "403 Forbidden: E_AGENT_NOT_AVAILABLE: the agent is not available to this caller."
            )
        if is_agent_suspended(agent_id):
            raise PermissionError(
                f"403 Forbidden: E_AGENT_SUSPENDED: Agent '{agent_id}' is currently suspended."
            )
        tenant_scopes = (
            set(caller_scopes)
            if caller_scopes is not None
            else set(TENANT_DIRECTORY[tenant_id]["authorized_scopes"])
        )

        if f"agent:{agent_id}" not in tenant_scopes:
            raise PermissionError(
                "403 Forbidden: Caller in tenant '"
                f"{tenant_id}' lacks entitlement scope 'agent:{agent_id}'."
            )
        return entry

    def get_entitled_tools(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        caller_scopes: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> list[str]:
        """Returns the exact list of tool names entitled for `(tenant_id, agent_id,
        caller_scopes)`.
        """
        entry = self.verify_agent_access(
            tenant_id=tenant_id,
            agent_id=agent_id,
            caller_scopes=caller_scopes,
        )
        tenant_scopes = (
            set(caller_scopes)
            if caller_scopes is not None
            else set(TENANT_DIRECTORY[tenant_id]["authorized_scopes"])
        )

        entitled: list[str] = []
        for tool_name in entry.entitled_tools:
            tool_meta = TOOL_REGISTRY.get(tool_name)
            if not tool_meta:
                continue
            if is_tool_tenant_allowed(tenant_id, tool_meta) and (
                tool_meta.required_scope in tenant_scopes
            ):
                entitled.append(tool_name)
        return entitled
