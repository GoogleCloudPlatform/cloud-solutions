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

# pylint: disable=import-outside-toplevel,line-too-long

"""Modular Multi-Workspace Plugin Architecture for Pattern A (High-Density Pooled Architecture).

Enables enterprise tenants with different corporate workspaces (Google Workspace, Microsoft 365,
Okta, Jira Cloud, ServiceNow ITOM, PagerDuty, Slack/Notion) to run on a **single shared Gemini
Pooled Agent Runtime fleet** (`Pattern A`) with zero code changes:
1. **Strict Default Alignment with Anchor Scenario (Slides 7, 8 & 10)**:
   - **Tenant Alpha (`tenant-finvault-alpha` — FinVault Bank, Enterprise Tier)**:
     Defaults to `google_workspace_oidc`, `google_workspace_3lo` (Drive/Calendar/Gmail),
     `jira_cloud_3lo`, `8,000` thinking-token budget, and private `Agent Alpha` on
     `claude-3-7-sonnet@20250219`.
   - **Tenant Beta (`tenant-retailstream-beta` — RetailStream Corp, Standard Tier)**:
     Defaults to `microsoft_entra_oidc`, `microsoft_365_sharepoint_3lo`,
     `servicenow_itom_3lo` (with inline 3LO OAuth consent flow), and `4,000` thinking-token cap.
2. **Pluggable Workspace Ports on the Shared Pooled Runtime**:
   - Decouples pooled agent reasoning from customer workspace vendors across 4 Pluggable Ports:
     (1) Identity Provider Port (`google_workspace_oidc`, `microsoft_entra_oidc`,
     `okta_enterprise_oidc`),
     (2) Collaboration & Runbook Workspace Port (`google_workspace_3lo`,
     `microsoft_365_sharepoint_3lo`, `slack_notion_3lo`),
     (3) ITSM Ticketing Port (`jira_cloud_3lo`, `servicenow_itom_3lo`, `pagerduty_linear_3lo`), and
     (4) Model, Skill & NLC Overlay Port (`gemini-4-carbon`, `gemini-4-hydrogen`,
     `claude-3-7-sonnet@20250219`, `gemma-3-27b-it`).
   - All tenants share the same **Pattern A Pooled Runtime** and **AlloyDB Fail-Closed RLS (`SET
     LOCAL`)**
     while dynamically binding their workspace adapters per turn.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from agents.auth.vault_and_bulkhead import get_default_3lo_vault
from agents.context import (
    TENANT_DIRECTORY,
    AuthManager3LOVault,
    ContextEnvelope,
    SubscriptionTier,
    register_tenant,
    register_tenant_eviction_target,
)
from agents.interceptors import egress_dlp_and_nlc_guardrail
from agents.registry import register_dynamic_private_agent

_PINNED_SECRET_VERSION_RE = re.compile(
    r"^projects/[a-zA-Z0-9_-]+/secrets/[a-zA-Z0-9_-]+/versions/[1-9][0-9]*$"
)
_OAUTH_STATE_KEY = secrets.token_bytes(32)


def resolve_oauth_state_signing_key(
    *,
    secret_fetcher: Any | None = None,
) -> bytes:
    """Resolves the 3LO OAuth `state` HMAC key from pinned Secret Manager (`Gap 14`).

    Order of precedence:
    1. `OAUTH_3LO_CSRF_SECRET_VERSION`: pinned Secret Manager resource version
       (`projects/<p>/secrets/<s>/versions/<N>`; `/versions/latest` is rejected).
    2. When `OAUTH_REQUIRE_SHARED_CSRF_KEY=1` (multi-instance OAuth callback mode), fails closed
       with `RuntimeError("E_OAUTH_CSRF_SECRET_REQUIRED")` if `OAUTH_3LO_CSRF_SECRET_VERSION` is
       unset.
    3. Single-instance / offline sandbox mode: per-process 32-byte random `_OAUTH_STATE_KEY`.
    """
    pinned_version = os.getenv("OAUTH_3LO_CSRF_SECRET_VERSION", "").strip()
    if pinned_version:
        if pinned_version.endswith(
            "/latest"
        ) or not _PINNED_SECRET_VERSION_RE.fullmatch(pinned_version):
            raise ValueError(
                "E_OAUTH_CSRF_SECRET_UNPINNED: OAUTH_3LO_CSRF_SECRET_VERSION must reference a "
                "pinned numeric Secret Manager version (never 'latest')."
            )
        if secret_fetcher is not None:
            raw_bytes = secret_fetcher(pinned_version)
        else:
            import google.auth
            import google.auth.transport.requests
            import httpx

            creds, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            creds.refresh(google.auth.transport.requests.Request())
            resp = httpx.get(
                f"https://secretmanager.googleapis.com/v1/{pinned_version}:access",
                headers={"Authorization": f"Bearer {creds.token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            raw_bytes = base64.b64decode(resp.json()["payload"]["data"])
        key_bytes = (
            raw_bytes
            if isinstance(raw_bytes, bytes)
            else str(raw_bytes).encode("utf-8")
        )
        if len(key_bytes) < 32:
            raise ValueError(
                "E_OAUTH_CSRF_SECRET_TOO_SHORT: OAuth CSRF secret must be at least 32 bytes."
            )
        return key_bytes

    if os.getenv("OAUTH_REQUIRE_SHARED_CSRF_KEY", "").strip() == "1":
        raise RuntimeError(
            "E_OAUTH_CSRF_SECRET_REQUIRED: Set OAUTH_3LO_CSRF_SECRET_VERSION (pinned Secret "
            "Manager version) when OAUTH_REQUIRE_SHARED_CSRF_KEY=1."
        )
    return _OAUTH_STATE_KEY


class IdPAdapterType(StrEnum):
    """Pluggable Inbound OIDC Identity Provider Adapters for Pooled Tenants (Port 1)."""

    GOOGLE_WORKSPACE_OIDC = "google_workspace_oidc"
    MICROSOFT_ENTRA_OIDC = "microsoft_entra_oidc"
    OKTA_ENTERPRISE_OIDC = "okta_enterprise_oidc"


class WorkspaceAdapterType(StrEnum):
    """Pluggable 3LO Collaboration & Knowledge Workspace Adapters for Pooled Tenants (Port 2)."""

    GOOGLE_WORKSPACE_3LO = (
        "google_workspace_3lo"  # Drive, Docs, Gmail, Calendar
    )
    MICROSOFT_365_SHAREPOINT_3LO = (
        "microsoft_365_sharepoint_3lo"  # SharePoint, Outlook, Teams
    )
    SLACK_NOTION_3LO = "slack_notion_3lo"  # Slack channels + Notion runbooks


class ITSMAdapterType(StrEnum):
    """Pluggable 3LO ITSM Incident Ticketing Adapters for Pooled Tenants (Port 3)."""

    JIRA_CLOUD_3LO = "jira_cloud_3lo"
    SERVICENOW_ITOM_3LO = "servicenow_itom_3lo"
    PAGERDUTY_LINEAR_3LO = "pagerduty_linear_3lo"


@dataclass(frozen=True)
class TenantWorkspaceManifest:
    """Declarative Tenant Workspace Manifest for Pattern A (High-Density Pooled Architecture).

    Allows onboarding or reconfiguring any enterprise customer with a different workspace stack
    onto the shared pooled runtime without modifying agent or MCP tool code.
    """

    tenant_id: str
    display_name: str
    subscription_tier: SubscriptionTier = SubscriptionTier.STANDARD
    idp_adapter: IdPAdapterType = IdPAdapterType.GOOGLE_WORKSPACE_OIDC
    idp_issuer: str = "https://accounts.google.com"
    workspace_adapter: WorkspaceAdapterType = (
        WorkspaceAdapterType.GOOGLE_WORKSPACE_3LO
    )
    itsm_adapter: ITSMAdapterType = ITSMAdapterType.JIRA_CLOUD_3LO
    shared_agent_model: str = "gemini-4-hydrogen"
    private_agent_id: str | None = None
    private_agent_model: str | None = None
    thinking_token_budget: int = 4000
    require_inline_3lo_consent: bool = False
    enforce_gateway_3lo_vault: bool = False
    custom_skills_uris: tuple[str, ...] = ()
    custom_nlc_rules: tuple[str, ...] = ()
    authorized_scopes: tuple[str, ...] = field(default_factory=tuple)


# ============================================================================
# Canonical Default Tenant Manifests (100% Aligned with Pattern A Slides 7 & 8)
# ============================================================================

DEFAULT_FINVAULT_MANIFEST = TenantWorkspaceManifest(
    tenant_id="tenant-finvault-alpha",
    display_name="FinVault Bank",
    subscription_tier=SubscriptionTier.ENTERPRISE,
    idp_adapter=IdPAdapterType.GOOGLE_WORKSPACE_OIDC,
    idp_issuer="https://accounts.google.com",
    workspace_adapter=WorkspaceAdapterType.GOOGLE_WORKSPACE_3LO,
    itsm_adapter=ITSMAdapterType.JIRA_CLOUD_3LO,
    shared_agent_model="gemini-4-hydrogen",
    private_agent_id="finvault_regulatory_escalation_agent",
    private_agent_model="claude-3-7-sonnet@20250219",
    thinking_token_budget=8000,
    require_inline_3lo_consent=False,
    custom_skills_uris=(
        "gs://cymbal-skills-prod/finvault/occ_regulatory_escalation_skill.md",
    ),
    custom_nlc_rules=(
        "Redact all banking SSNs and ABA routing numbers before egress",
        "Escalate P1 core-wire-settlement outages exceeding 4 hours to OCC",
    ),
    authorized_scopes=tuple(
        TENANT_DIRECTORY["tenant-finvault-alpha"]["authorized_scopes"]
    ),
)

DEFAULT_RETAILSTREAM_MANIFEST = TenantWorkspaceManifest(
    tenant_id="tenant-retailstream-beta",
    display_name="RetailStream Corp",
    subscription_tier=SubscriptionTier.STANDARD,
    idp_adapter=IdPAdapterType.MICROSOFT_ENTRA_OIDC,
    idp_issuer="https://login.microsoftonline.com/retailstream-tenant-id/v2.0",
    workspace_adapter=WorkspaceAdapterType.MICROSOFT_365_SHAREPOINT_3LO,
    itsm_adapter=ITSMAdapterType.SERVICENOW_ITOM_3LO,
    shared_agent_model="gemini-4-hydrogen",
    private_agent_id=None,
    private_agent_model=None,
    thinking_token_budget=4000,
    require_inline_3lo_consent=True,
    custom_skills_uris=(
        "gs://cymbal-skills-prod/retailstream/flash_sale_checkout_skill.md",
    ),
    custom_nlc_rules=(
        "Redact all payment credit card PANs before egress",
        "Deny any retention discount modification exceeding 15% without VP approval",
    ),
    authorized_scopes=tuple(
        TENANT_DIRECTORY["tenant-retailstream-beta"]["authorized_scopes"]
    ),
)

_DEFAULT_MANIFESTS: dict[str, TenantWorkspaceManifest] = {
    "tenant-finvault-alpha": DEFAULT_FINVAULT_MANIFEST,
    "tenant-retailstream-beta": DEFAULT_RETAILSTREAM_MANIFEST,
}

ITSM_REQUIRED_SCOPE: dict[ITSMAdapterType, str] = {
    ITSMAdapterType.JIRA_CLOUD_3LO: "3lo:jira.incidents.write",
    ITSMAdapterType.SERVICENOW_ITOM_3LO: "3lo:servicenow.itom.write",
    ITSMAdapterType.PAGERDUTY_LINEAR_3LO: "3lo:pagerduty.incidents.write",
}

WORKSPACE_REQUIRED_SCOPE: dict[WorkspaceAdapterType, str] = {
    WorkspaceAdapterType.GOOGLE_WORKSPACE_3LO: "3lo:google.drive.readonly",
    WorkspaceAdapterType.MICROSOFT_365_SHAREPOINT_3LO: "3lo:microsoft.sharepoint.readonly",
    WorkspaceAdapterType.SLACK_NOTION_3LO: "3lo:notion.runbooks.readonly",
}


class WorkspacePluginRegistry:
    """Manages Declarative Tenant Workspace Manifests & Dispatches Canonical Capability Ports in
    Pattern A.
    """

    def __init__(self, vault_3lo: AuthManager3LOVault | None = None) -> None:
        self._manifests: dict[str, TenantWorkspaceManifest] = dict(
            _DEFAULT_MANIFESTS
        )
        self.vault_3lo = vault_3lo or get_default_3lo_vault()
        register_tenant_eviction_target(self)

    def has_manifest(self, tenant_id: str) -> bool:
        """Returns whether `tenant_id` has a registered workspace manifest."""
        return tenant_id in self._manifests

    def evict_tenant(self, tenant_id: str) -> int:
        """Removes a dynamically onboarded tenant manifest and purges its 3LO vault tokens.

        Args:
            tenant_id: Offboarded tenant identifier.

        Returns:
            Count of evicted manifest and 3LO token entries.
        """
        removed_manifest = 0
        if (
            tenant_id not in _DEFAULT_MANIFESTS
            and self._manifests.pop(tenant_id, None) is not None
        ):
            removed_manifest = 1
        return removed_manifest + int(self.vault_3lo.evict_tenant(tenant_id))

    def reset_dynamic_manifests(self) -> None:
        """Restores `_manifests` to the canonical anchor tenant manifests."""
        self._manifests.clear()
        self._manifests.update(_DEFAULT_MANIFESTS)

    def get_manifest(self, tenant_id: str) -> TenantWorkspaceManifest:
        if tenant_id not in self._manifests:
            raise PermissionError(
                f"403 Forbidden: No workspace manifest registered for '{tenant_id}'."
            )
        return self._manifests[tenant_id]

    def register_or_update_manifest(
        self, manifest: TenantWorkspaceManifest
    ) -> TenantWorkspaceManifest:
        """Registers a new tenant manifest or hot-swaps an existing tenant's workspace
        adapters/models.
        """
        scopes = list(manifest.authorized_scopes)
        itsm_scope = ITSM_REQUIRED_SCOPE[manifest.itsm_adapter]
        ws_scope = WORKSPACE_REQUIRED_SCOPE[manifest.workspace_adapter]
        for required in (itsm_scope, ws_scope):
            if required not in scopes:
                scopes.append(required)
        if manifest.private_agent_id:
            private_agent_scope = f"agent:{manifest.private_agent_id}"
            if private_agent_scope not in scopes:
                scopes.append(private_agent_scope)

        updated = replace(manifest, authorized_scopes=tuple(scopes))
        self._manifests[updated.tenant_id] = updated

        register_tenant(
            tenant_id=updated.tenant_id,
            display_name=updated.display_name,
            tier=updated.subscription_tier,
            iss=updated.idp_issuer,
            org_unit="pattern-a-pooled",
            extra_scopes=tuple(
                s
                for s in updated.authorized_scopes
                if s
                not in (
                    "2lo:cymbal.telemetry.read",
                    "2lo:cymbal.runbooks.read",
                    "agent:cymbal_shared_diagnostic_agent",
                )
            ),
        )
        if updated.private_agent_id and updated.private_agent_id not in (
            "cymbal_shared_diagnostic_agent",
            "finvault_regulatory_escalation_agent",
        ):
            register_dynamic_private_agent(
                agent_id=updated.private_agent_id,
                display_name=f"{updated.display_name} Private Enterprise Agent",
                model=updated.private_agent_model or updated.shared_agent_model,
                owner_tenant_id=updated.tenant_id,
                required_tier=updated.subscription_tier,
            )
        return updated

    def hot_swap_tenant_config(
        self,
        tenant_id: str,
        *,
        itsm_adapter: ITSMAdapterType | None = None,
        workspace_adapter: WorkspaceAdapterType | None = None,
        private_agent_model: str | None = None,
        shared_agent_model: str | None = None,
    ) -> TenantWorkspaceManifest:
        """Hot-swaps a pooled tenant's workspace adapter or foundation model with zero downtime."""
        current = self.get_manifest(tenant_id)
        updated = replace(
            current,
            itsm_adapter=itsm_adapter or current.itsm_adapter,
            workspace_adapter=workspace_adapter or current.workspace_adapter,
            private_agent_model=private_agent_model
            or current.private_agent_model,
            shared_agent_model=shared_agent_model or current.shared_agent_model,
        )
        return self.register_or_update_manifest(updated)

    async def invoke_canonical_itsm_ticket(
        self,
        *,
        envelope: ContextEnvelope,
        summary: str,
        priority: str = "P1",
        token_handle_3lo: str | None = None,
    ) -> dict[str, Any]:
        """Canonical Port 3 (`create_incident_ticket`): Dispatches to Jira, ServiceNow, or
        PagerDuty.
        """
        manifest = self.get_manifest(envelope.tenant.tenant_id)
        required_scope = ITSM_REQUIRED_SCOPE[manifest.itsm_adapter]

        if required_scope not in envelope.tenant.authorized_scopes:
            raise PermissionError(
                f"403 Forbidden: Tenant '{manifest.tenant_id}' lacks scope '{required_scope}' "
                f"for adapter '{manifest.itsm_adapter}'."
            )

        if manifest.require_inline_3lo_consent and not token_handle_3lo:
            return {
                "status": "OAUTH_CONSENT_REQUIRED",
                "error_code": "E_3LO_INLINE_CONSENT_REQUIRED",
                "tenant_id": manifest.tenant_id,
                "adapter": str(manifest.itsm_adapter),
                "idp_issuer": manifest.idp_issuer,
                "required_scope": required_scope,
                "consent_url": (
                    f"{manifest.idp_issuer}/authorize?client_id=cymbal-agent-pep"
                    f"&scope={required_scope}&state={envelope.request.session_id}"
                ),
            }

        if token_handle_3lo:
            self.vault_3lo.checkout_3lo_token(
                token_handle=token_handle_3lo,
                envelope=envelope,
                required_scope=required_scope,
            )

        clean_summary = egress_dlp_and_nlc_guardrail(
            tenant_id=manifest.tenant_id,
            tool_name="create_incident_ticket",
            tool_args={"summary": summary, "priority": priority},
            raw_output=summary,
        )

        for nlc_rule in manifest.custom_nlc_rules:
            if "PHI" in nlc_rule and "MRN-" in clean_summary:
                raise PermissionError(
                    "E_CUSTOM_NLC_VIOLATION: Tenant '"
                    f"{manifest.tenant_id}' NLC blocked MRN/PHI in ticket."
                )

        if manifest.itsm_adapter == ITSMAdapterType.JIRA_CLOUD_3LO:
            return {
                "status": "created",
                "canonical_port": "create_incident_ticket",
                "dispatched_adapter": "jira_cloud_3lo",
                "tenant_id": manifest.tenant_id,
                "ticket_id": "FINVAULT-901",
                "summary": clean_summary,
            }
        if manifest.itsm_adapter == ITSMAdapterType.SERVICENOW_ITOM_3LO:
            return {
                "status": "created",
                "canonical_port": "create_incident_ticket",
                "dispatched_adapter": "servicenow_itom_3lo",
                "tenant_id": manifest.tenant_id,
                "ticket_id": "INC0049281",
                "summary": clean_summary,
            }
        return {
            "status": "created",
            "canonical_port": "create_incident_ticket",
            "dispatched_adapter": "pagerduty_linear_3lo",
            "tenant_id": manifest.tenant_id,
            "ticket_id": "PD-INC-7741",
            "summary": clean_summary,
        }

    async def invoke_canonical_workspace_runbook(
        self,
        *,
        envelope: ContextEnvelope,
        runbook_query: str,
        token_handle_3lo: str | None = None,
    ) -> dict[str, Any]:
        """Canonical Port 2 (`fetch_workspace_runbook`): Dispatches to Google Drive, SharePoint,
        or Notion.
        """
        manifest = self.get_manifest(envelope.tenant.tenant_id)
        required_scope = WORKSPACE_REQUIRED_SCOPE[manifest.workspace_adapter]

        if required_scope not in envelope.tenant.authorized_scopes:
            raise PermissionError(
                f"403 Forbidden: Tenant '{manifest.tenant_id}' lacks scope '{required_scope}'."
            )

        if manifest.require_inline_3lo_consent and not token_handle_3lo:
            return {
                "status": "OAUTH_CONSENT_REQUIRED",
                "error_code": "E_3LO_INLINE_CONSENT_REQUIRED",
                "tenant_id": manifest.tenant_id,
                "adapter": str(manifest.workspace_adapter),
                "required_scope": required_scope,
                "consent_url": (
                    f"{manifest.idp_issuer}/authorize?client_id=cymbal-agent-pep"
                    f"&scope={required_scope}&state={envelope.request.session_id}"
                ),
            }

        if token_handle_3lo:
            self.vault_3lo.checkout_3lo_token(
                token_handle=token_handle_3lo,
                envelope=envelope,
                required_scope=required_scope,
            )

        return {
            "status": "success",
            "canonical_port": "fetch_workspace_runbook",
            "dispatched_adapter": str(manifest.workspace_adapter),
            "tenant_id": manifest.tenant_id,
            "rls_isolation": f"SET LOCAL app.current_tenant_id = '{manifest.tenant_id}';",
            "loaded_skills": list(manifest.custom_skills_uris),
            "query": runbook_query,
        }

    @staticmethod
    def mint_csrf_bound_oauth_state(
        *, envelope: ContextEnvelope, required_scope: str
    ) -> str:
        """Mints a tenant-bound OAuth 2.0 `state` token preventing Cross-Tenant OAuth Login CSRF."""
        import hashlib
        import hmac

        key_bytes = resolve_oauth_state_signing_key()
        payload = (
            f"{envelope.tenant.tenant_id}:{envelope.security.sub}:{envelope.request.session_id}:"
            f"{required_scope}"
        )
        mac = hmac.new(
            key_bytes, payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()[:24]
        return (
            f"{envelope.tenant.tenant_id}.{envelope.request.session_id}.{mac}"
        )

    @classmethod
    def verify_oauth_callback_state(
        cls,
        *,
        callback_state: str,
        active_envelope: ContextEnvelope,
        required_scope: str,
    ) -> bool:
        """Rejects Cross-Tenant 3LO OAuth CSRF where an attacker replays another tenant's
        `state`.
        """
        import hmac

        expected = cls.mint_csrf_bound_oauth_state(
            envelope=active_envelope,
            required_scope=required_scope,
        )
        if not hmac.compare_digest(callback_state, expected):
            raise PermissionError(
                "403 E_OAUTH_3LO_CSRF_STATE_MISMATCH: OAuth callback `state` does not match "
                f"authenticated tenant '{active_envelope.tenant.tenant_id}' session."
            )
        return True


_DEFAULT_WORKSPACE_PLUGIN_REGISTRY: WorkspacePluginRegistry | None = None


def get_default_workspace_plugin_registry() -> WorkspacePluginRegistry:
    """Returns the shared in-process `WorkspacePluginRegistry` singleton."""
    global _DEFAULT_WORKSPACE_PLUGIN_REGISTRY
    if _DEFAULT_WORKSPACE_PLUGIN_REGISTRY is None:
        _DEFAULT_WORKSPACE_PLUGIN_REGISTRY = WorkspacePluginRegistry()
    return _DEFAULT_WORKSPACE_PLUGIN_REGISTRY
