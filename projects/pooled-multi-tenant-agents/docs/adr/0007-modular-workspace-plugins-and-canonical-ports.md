# ADR-0007: Modular Multi-Workspace Plugin Architecture & Canonical Capability Ports in Pattern A (Pooled)

- **Status**: Accepted
- **Date**: 2026-10-12
- **Applies To**: `agents/workspace_plugins.py`,
  `tests/unit/test_modular_workspace_customization.py` (Pattern A: High-Density
  Pooled Architecture)

## Context

In **Pattern A (High-Density Pooled Architecture)**, all tenants share a single
agent runtime in Gemini fleet and a single AlloyDB RLS persistence cluster, but
each enterprise customer brings its own heterogeneous identity provider,
collaboration workspace, ticketing system, and model preferences:

- **FinVault Bank (`tenant-finvault-alpha`, Enterprise Default)**: Google
  Workspace OIDC + Google Drive/Calendar/Gmail (3LO) + Jira Cloud (3LO) +
  Private Agent Alpha on Claude Sonnet (`8,000` thinking budget).
- **RetailStream Corp (`tenant-retailstream-beta`, Standard Default)**:
  Microsoft Entra ID + SharePoint Online (3LO) + ServiceNow ITOM (3LO with
  inline OAuth consent) + Shared Diagnostic Agent (`4,000` thinking cap).
- **Additional Pooled Enterprise Tenants (e.g., `tenant-healthcore-gamma`)**:
  May mix **Okta OIDC + Google Workspace + ServiceNow ITOM**, or hot-swap
  **Jira** for **PagerDuty** and **Claude Sonnet** for **Gemma 3** without
  redeploying the shared runtime.

## Decision

1.  **Preserve Strict Default Alignment (`DEFAULT_FINVAULT_MANIFEST` &
    `DEFAULT_RETAILSTREAM_MANIFEST`)**:
    - Out of the box, `WorkspacePluginRegistry` pre-registers
      `tenant-finvault-alpha` and `tenant-retailstream-beta` with their exact
      canonical defaults from the Cymbal SaaS Pattern A specification.
1.  **Decouple Pooled Agent Reasoning from Vendor Implementations via 4
    Pluggable Workspace Ports**:
    - **Port 1 — Identity Federation (`IdPAdapterType`)**:
      `google_workspace_oidc`, `microsoft_entra_oidc`, `okta_enterprise_oidc`.
    - **Port 2 — Collaboration & Knowledge (`WorkspaceAdapterType`)**:
      `google_workspace_3lo`, `microsoft_365_sharepoint_3lo`,
      `slack_notion_3lo`.
    - **Port 3 — ITSM Incident Ticketing (`ITSMAdapterType`)**:
      `jira_cloud_3lo`, `servicenow_itom_3lo`, `pagerduty_linear_3lo`.
    - **Port 4 — Model, Skill & NLC Overlay (`custom_skills_uris`,
      `custom_nlc_rules`, `private_agent_model`)**: Hot-swappable per pooled
      tenant via `TenantWorkspaceManifest`.
1.  **Support Canonical Polymorphic Tools + Inline 3LO Consent**:
    - Canonical tools (`invoke_canonical_itsm_ticket`,
      `invoke_canonical_workspace_runbook`) present one invariant schema to the
      LLM (maximizing global prompt prefix cache hit rates across the pool) and
      dispatch to the tenant's configured adapter after verifying
      `AuthManager3LOVault` 3LO tokens or returning an
      `E_3LO_INLINE_CONSENT_REQUIRED` challenge URL.

## Consequences

- **Positive**: Any enterprise customer with any combination of IdP,
  collaboration workspace, and ITSM ticketing can onboard onto the shared
  **Pattern A Pooled Runtime** via a declarative manifest with zero agent code
  changes.
- **Negative**: Requires maintaining workspace adapter scope mappings in
  `WorkspacePluginRegistry`.
