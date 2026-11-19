# ADR-0003: Dynamic Catalog Visibility via ARD (`/.well-known/ai-catalog.json`) & ADK `before_agent_callback` Tool Pruning

- **Status**: Accepted
- **Date**: 2026-10-08
- **Applies To**: Subsystem 2 (Agent Registry PDP), Subsystem 3 (ADK 2.0
  Runtime), Subsystem 7 (MCP Tool Fabric)

## Context

In Cymbal SaaS's pooled deployment:

- **FinVault Bank (`tenant-finvault-alpha`, Enterprise Tier)** owns a private
  self-service Regulatory Escalation Agent (**Agent Alpha**) and uses 3LO Google
  Workspace + Jira tools.
- **RetailStream Corp (`tenant-retailstream-beta`, Standard Tier)** is
  restricted to the **Shared Diagnostic Agent** and uses 3LO Microsoft
  SharePoint + ServiceNow tools.

If all registered tools are injected into the shared agent's system prompt, the
LLM may hallucinate calls to unentitled tools (e.g., RetailStream attempting to
invoke `create_jira_incident`) or leak proprietary tool schemas across tenants.

## Decision

1.  **Agent Resource Discovery (ARD) Filtering**:
    `AgentRegistryPDP.discover_ai_catalog(tenant_id)` filters
    `/.well-known/ai-catalog.json` at query time so private tenant agents
    (`finvault_regulatory_escalation_agent`) are completely invisible to other
    tenants, and direct invocation by an unauthorized tenant raises
    `403 Forbidden`.
1.  **Pre-Inference Tool Pruning (`before_agent_callback`)**: Before model
    inference begins on any turn, `enforce_tenant_isolation_interceptor` queries
    `AgentRegistryPDP.get_entitled_tools(tenant_id, agent_id)` and prunes
    `callback_context.active_tools` to only the tools matching the tenant's
    verified subscription tier and 2LO/3LO scopes.
1.  **Defense-in-Depth at the MCP Server**: Even if a tool name is guessed,
    `_verify_tool_authorization` inside `mcp_server/server.py` independently
    verifies `temp:tenant_id` and `temp:authorized_scopes` before executing any
    tool logic.

## Consequences

- **Positive**: Zero schema leakage in prompts, lower input token consumption,
  and dual-layer (`before_agent_callback` + MCP server) authorization
  enforcement.
- **Negative**: Requires maintaining explicit tenant and scope metadata in
  `TOOL_REGISTRY` and `AGENT_CATALOG`.
