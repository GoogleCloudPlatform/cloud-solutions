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

"""Tests for Modular Multi-Workspace Customization in Pattern A (Pooled Architecture).

Verifies:
1. **Default Alignment**: `FinVault Bank` and `RetailStream Corp` default manifests match Slides 7 &
   8
   (`google_workspace_oidc` + `jira_cloud_3lo` + `claude-3-7-sonnet` vs. `microsoft_entra_oidc` +
   `servicenow_itom_3lo` + inline 3LO consent).
2. **Inline 3LO OAuth Consent Flow**: RetailStream prompts mid-session with an interactive Entra ID
   OAuth consent URL when a 3LO token handle is missing, then succeeds once authorized.
3. **Heterogeneous Workspace Composability on the Shared Pool**: Onboarding a 3rd enterprise
   customer (`tenant-healthcore-gamma` using **Okta OIDC + Google Workspace + ServiceNow ITOM +
   HIPAA custom NLCs**) onto the Pooled runtime works purely via `TenantWorkspaceManifest`.
4. **Live Hot-Swapping of Workspace Adapters & Models**: Switching a pooled tenant's ticketing
   provider (`Jira` -> `PagerDuty`), collaboration suite (`Google` -> `Slack/Notion`), or model
   (`Claude Sonnet` -> `Gemma 3`) at runtime with zero code edits.
"""

from __future__ import annotations

import time

import pytest
from agents.context import (
    ContextEnvelope,
    Delegated3LOToken,
    EdgeAuthVerifier,
    SubscriptionTier,
    reset_dynamic_tenants,
)
from agents.workspace_plugins import (
    DEFAULT_FINVAULT_MANIFEST,
    DEFAULT_RETAILSTREAM_MANIFEST,
    IdPAdapterType,
    ITSMAdapterType,
    TenantWorkspaceManifest,
    WorkspaceAdapterType,
    WorkspacePluginRegistry,
)


def test_anchor_tenant_defaults_are_strictly_aligned_with_scoping_docs() -> (
    None
):
    """Verifies FinVault Bank and RetailStream Corp defaults match Slides 7 & 8."""
    registry = WorkspacePluginRegistry()

    fv = registry.get_manifest("tenant-finvault-alpha")
    assert fv == DEFAULT_FINVAULT_MANIFEST
    assert fv.subscription_tier == SubscriptionTier.ENTERPRISE
    assert fv.idp_adapter == IdPAdapterType.GOOGLE_WORKSPACE_OIDC
    assert fv.workspace_adapter == WorkspaceAdapterType.GOOGLE_WORKSPACE_3LO
    assert fv.itsm_adapter == ITSMAdapterType.JIRA_CLOUD_3LO
    assert fv.private_agent_id == "finvault_regulatory_escalation_agent"
    assert fv.private_agent_model == "claude-3-7-sonnet@20250219"
    assert fv.thinking_token_budget == 8000

    rs = registry.get_manifest("tenant-retailstream-beta")
    assert rs == DEFAULT_RETAILSTREAM_MANIFEST
    assert rs.subscription_tier == SubscriptionTier.STANDARD
    assert rs.idp_adapter == IdPAdapterType.MICROSOFT_ENTRA_OIDC
    assert (
        rs.workspace_adapter
        == WorkspaceAdapterType.MICROSOFT_365_SHAREPOINT_3LO
    )
    assert rs.itsm_adapter == ITSMAdapterType.SERVICENOW_ITOM_3LO
    assert rs.private_agent_id is None
    assert rs.thinking_token_budget == 4000
    assert rs.require_inline_3lo_consent is True


async def test_retailstream_inline_3lo_oauth_consent_challenge_and_completion(
    retailstream_envelope: ContextEnvelope,
) -> None:
    """Slide 7 Requirement: Prompts RetailStream engineer with inline OAuth consent when 3LO token
    missing.
    """
    registry = WorkspacePluginRegistry()

    challenge = await registry.invoke_canonical_itsm_ticket(
        envelope=retailstream_envelope,
        summary="Checkout 503 surge during flash sale",
        token_handle_3lo=None,
    )
    assert challenge["status"] == "OAUTH_CONSENT_REQUIRED"
    assert challenge["error_code"] == "E_3LO_INLINE_CONSENT_REQUIRED"
    assert "login.microsoftonline.com" in challenge["consent_url"]
    assert "3lo:servicenow.itom.write" in challenge["consent_url"]

    handle = registry.vault_3lo.store_3lo_token(
        Delegated3LOToken(
            token_handle="3lo-rs-snow-001",
            tenant_id="tenant-retailstream-beta",
            user_sub="bob@retailstream.com",
            provider="servicenow-entra-3lo",
            scopes=("3lo:servicenow.itom.write",),
            access_token="entra-snow-token",
            expires_at=int(time.time()) + 3600,
        )
    )

    ticket = await registry.invoke_canonical_itsm_ticket(
        envelope=retailstream_envelope,
        summary="Checkout 503 surge for card 4532-0151-1283-0366",
        token_handle_3lo=handle,
    )
    assert ticket["status"] == "created"
    assert ticket["dispatched_adapter"] == "servicenow_itom_3lo"
    assert ticket["ticket_id"] == "INC0049281"
    assert "[REDACTED_PAYMENT_PAN]" in ticket["summary"]


async def test_heterogeneous_workspace_mix_and_match_onboarding_zero_code_changes() -> (
    None
):
    """Onboards Tenant Gamma (HealthCore) mixing Okta + Google Workspace + ServiceNow + HIPAA NLCs
    onto the Pool.
    """
    registry = WorkspacePluginRegistry()
    verifier = EdgeAuthVerifier()

    try:
        healthcore_manifest = TenantWorkspaceManifest(
            tenant_id="tenant-healthcore-gamma",
            display_name="HealthCore Medical Group",
            subscription_tier=SubscriptionTier.ENTERPRISE,
            idp_adapter=IdPAdapterType.OKTA_ENTERPRISE_OIDC,
            idp_issuer="https://healthcore.okta.com/oauth2/default",
            workspace_adapter=WorkspaceAdapterType.GOOGLE_WORKSPACE_3LO,
            itsm_adapter=ITSMAdapterType.SERVICENOW_ITOM_3LO,
            thinking_token_budget=8000,
            custom_skills_uris=(
                "gs://cymbal-skills-prod/healthcore/hipaa_triage_skill.md",
            ),
            custom_nlc_rules=(
                "Never include patient MRN or PHI in external ticket summaries",
            ),
        )
        registry.register_or_update_manifest(healthcore_manifest)

        hc_envelope = verifier.exchange_obo_token(
            verified_idp_claims={
                "iss": "https://healthcore.okta.com/oauth2/default",
                "sub": "dr.smith@healthcore.org",
                "tenant_id": "tenant-healthcore-gamma",
                "exp": int(time.time()) + 3600,
                "jti": "jwt-hc-001",
            },
            dpop_proof={"jkt": "thumb-hc", "jti": "dpop-hc-001"},
            session_id="sess-hc-001",
        )

        rb = await registry.invoke_canonical_workspace_runbook(
            envelope=hc_envelope,
            runbook_query="PHR database failover runbook",
        )
        assert rb["dispatched_adapter"] == "google_workspace_3lo"
        assert "hipaa_triage_skill.md" in rb["loaded_skills"][0]

        ticket = await registry.invoke_canonical_itsm_ticket(
            envelope=hc_envelope,
            summary="PHR cluster latency spike in us-central1",
        )
        assert ticket["dispatched_adapter"] == "servicenow_itom_3lo"

        with pytest.raises(PermissionError, match="E_CUSTOM_NLC_VIOLATION"):
            await registry.invoke_canonical_itsm_ticket(
                envelope=hc_envelope,
                summary="Patient record MRN-994821 failed sync",
            )
    finally:
        reset_dynamic_tenants()


async def test_live_hot_swap_of_workspace_adapters_and_models_in_pooled_runtime(
    finvault_envelope: ContextEnvelope,
) -> None:
    """Proves FinVault can hot-swap Jira -> PagerDuty, Google -> Slack/Notion, and Claude -> Gemma
    3 in Pool.
    """
    registry = WorkspacePluginRegistry()
    verifier = EdgeAuthVerifier()

    try:
        t1 = await registry.invoke_canonical_itsm_ticket(
            envelope=finvault_envelope,
            summary="Wire latency alert",
        )
        assert t1["dispatched_adapter"] == "jira_cloud_3lo"

        swapped = registry.hot_swap_tenant_config(
            "tenant-finvault-alpha",
            itsm_adapter=ITSMAdapterType.PAGERDUTY_LINEAR_3LO,
            workspace_adapter=WorkspaceAdapterType.SLACK_NOTION_3LO,
            private_agent_model="gemma-3-27b-it",
        )
        assert swapped.private_agent_model == "gemma-3-27b-it"

        fv_env_v2 = verifier.exchange_obo_token(
            verified_idp_claims={
                "iss": "https://accounts.google.com",
                "sub": "alice@finvault.com",
                "tenant_id": "tenant-finvault-alpha",
                "exp": int(time.time()) + 3600,
                "jti": "jwt-fv-swapped",
            },
            dpop_proof={"jkt": "thumb-fv-2", "jti": "dpop-fv-swapped"},
        )
        t2 = await registry.invoke_canonical_itsm_ticket(
            envelope=fv_env_v2,
            summary="Wire latency escalated to PagerDuty",
        )
        assert t2["dispatched_adapter"] == "pagerduty_linear_3lo"

        rb2 = await registry.invoke_canonical_workspace_runbook(
            envelope=fv_env_v2,
            runbook_query="Wire settlement Notion runbook",
        )
        assert rb2["dispatched_adapter"] == "slack_notion_3lo"
    finally:
        reset_dynamic_tenants()
