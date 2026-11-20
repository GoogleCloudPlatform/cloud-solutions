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

"""Tests for Gemini platform Memory Bank Scopes, ADK Schema Hiding, IAM CEL & GDPR Residency."""

from __future__ import annotations

import pytest
from agents.memory_bank_iam_and_residency import (
    ADKToolSchemaInspector,
    MemoryBankScopeStore,
    MemoryBankTopologyRouter,
)
from mcp_server.server import (
    create_jira_incident,
    create_servicenow_incident,
    query_telemetry_rls,
    read_runbook,
    schedule_calendar_postmortem,
)

US_RETAIL_SA = (
    "us-retail-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
)
US_WEALTH_SA = (
    "us-wealth-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
)
EU_RETAIL_SA = (
    "eu-retail-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
)


def test_adk_tool_schema_hides_tool_context_and_identity_keys() -> None:
    """Act 1A: Verifies ADK hides `tool_context` so LLM cannot pass forged `user_id`/`tenant_id`."""
    for tool_fn in (
        query_telemetry_rls,
        read_runbook,
        create_jira_incident,
        create_servicenow_incident,
        schedule_calendar_postmortem,
    ):
        report = (
            ADKToolSchemaInspector.verify_tool_safe_against_scope_injection(
                tool_fn
            )
        )
        assert report["has_hidden_tool_context"] is True
        assert report["leaked_identity_parameters"] == []
        assert report["safe_against_prompt_scope_injection"] is True


def test_5_key_exact_case_sensitive_scope_dictionary_isolation() -> None:
    """Act 1B: Verifies exact case-sensitive match on <= 5 key-value scope dictionary."""
    store = MemoryBankScopeStore()
    alice_scope = {
        "tenant_id": "tenant-finvault-alpha",
        "line_of_business": "retail_banking",
        "user_id": "alice",
    }
    store.create_or_consolidate_memory(
        service_account_email=US_RETAIL_SA,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope=alice_scope,
        extracted_fact="Alice wire transfers are capped at $50k.",
    )

    # 1. Exact match -> returns 1 memory
    exact = store.retrieve_memories(
        service_account_email=US_RETAIL_SA,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope=alice_scope,
    )
    assert len(exact) == 1
    assert "50k" in exact[0].extracted_fact

    # 2. Different user_id ('charlie') in same LoB -> returns 0 memories
    charlie = store.retrieve_memories(
        service_account_email=US_RETAIL_SA,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope={
            "tenant_id": "tenant-finvault-alpha",
            "line_of_business": "retail_banking",
            "user_id": "charlie",
        },
    )
    assert len(charlie) == 0

    # 3. Case-sensitive mismatch ('Alice' vs 'alice') -> returns 0 memories
    case_mismatch = store.retrieve_memories(
        service_account_email=US_RETAIL_SA,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope={
            "tenant_id": "tenant-finvault-alpha",
            "line_of_business": "retail_banking",
            "user_id": "Alice",
        },
    )
    assert len(case_mismatch) == 0

    # 4. Subset scope (missing 'user_id') -> returns 0 memories
    subset = store.retrieve_memories(
        service_account_email=US_RETAIL_SA,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope={
            "tenant_id": "tenant-finvault-alpha",
            "line_of_business": "retail_banking",
        },
    )
    assert len(subset) == 0

    # 5. > 5 keys in scope dictionary -> rejected with ValueError
    with pytest.raises(ValueError, match="E_MEMORY_SCOPE_TOO_LARGE"):
        store.validate_and_canonicalize_scope(
            {
                "k1": "v1",
                "k2": "v2",
                "k3": "v3",
                "k4": "v4",
                "k5": "v5",
                "k6": "v6",
            }
        )


def test_cloud_iam_cel_conditions_block_cross_lob_and_cross_tenant_at_perimeter() -> (
    None
):
    """Act 2: Wealth Management SA cannot read or write Retail Banking memories (403 IAM CEL)."""
    store = MemoryBankScopeStore()
    alice_retail_scope = {
        "tenant_id": "tenant-finvault-alpha",
        "line_of_business": "retail_banking",
        "user_id": "alice",
    }
    store.create_or_consolidate_memory(
        service_account_email=US_RETAIL_SA,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope=alice_retail_scope,
        extracted_fact="Alice retail checking preference.",
    )

    # Wealth Management SA writes to its own LoB -> succeeds
    wealth_scope = {
        "tenant_id": "tenant-finvault-alpha",
        "line_of_business": "wealth_management",
        "user_id": "bob",
    }
    w_rec = store.create_or_consolidate_memory(
        service_account_email=US_WEALTH_SA,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope=wealth_scope,
        extracted_fact="Bob wealth portfolio rebalance schedule.",
    )
    assert w_rec.memory_bank_id == "cymbal-us-memory-bank"

    # Wealth Management SA tries to READ Alice's retail_banking scope -> 403 PERMISSION_DENIED (IAM
    # CEL)
    with pytest.raises(
        PermissionError, match=r"403 PERMISSION_DENIED.*IAM CEL Scope Lock"
    ) as exc:
        store.retrieve_memories(
            service_account_email=US_WEALTH_SA,
            region="us-central1",
            memory_bank_id="cymbal-us-memory-bank",
            scope=alice_retail_scope,
        )
    # Code only: no bound scope values, requested values, or service accounts in the message.
    assert "E_MEMORY_IAM_CEL_SCOPE_LOCK" in str(exc.value)
    for leak in ("wealth_management", "retail_banking", US_WEALTH_SA, "alice"):
        assert leak not in str(exc.value)

    # Wealth Management SA tries to WRITE to Alice's retail_banking scope -> 403 PERMISSION_DENIED
    # (IAM CEL)
    with pytest.raises(
        PermissionError, match=r"403 PERMISSION_DENIED.*IAM CEL Scope Lock"
    ):
        store.create_or_consolidate_memory(
            service_account_email=US_WEALTH_SA,
            region="us-central1",
            memory_bank_id="cymbal-us-memory-bank",
            scope=alice_retail_scope,
            extracted_fact="Unauthorized cross-LoB injection.",
        )


def test_gdpr_regional_residency_blocks_global_and_cross_border_us_eu_access() -> (
    None
):
    """Act 3: GDPR `europe-west3` vs `us-central1` regional lock + Org Policy `global` block."""
    store = MemoryBankScopeStore()

    # 1. Org Policy `constraints/gcp.resourceLocations` blocks `global` Memory Bank
    with pytest.raises(
        PermissionError, match="E_ORG_POLICY_LOCATION_VIOLATION"
    ):
        store.create_or_consolidate_memory(
            service_account_email=EU_RETAIL_SA,
            region="global",
            memory_bank_id="cymbal-eu-memory-bank",
            scope={
                "tenant_id": "tenant-finvault-alpha",
                "line_of_business": "retail_banking",
                "user_id": "eva",
            },
            extracted_fact="Eva GDPR protected fact.",
        )

    # 2. EU Retail SA writes Eva's memory to `europe-west3` -> succeeds
    eva_scope = {
        "tenant_id": "tenant-finvault-alpha",
        "line_of_business": "retail_banking",
        "user_id": "eva",
    }
    eva_rec = store.create_or_consolidate_memory(
        service_account_email=EU_RETAIL_SA,
        region="europe-west3",
        memory_bank_id="cymbal-eu-memory-bank",
        scope=eva_scope,
        extracted_fact="Eva SEPA transfer preference in Frankfurt.",
    )
    assert eva_rec.region == "europe-west3"

    # 3. US Retail SA tries to read Eva's EU memory in `europe-west3` -> 403 PERMISSION_DENIED
    # (Regional Lock)
    with pytest.raises(
        PermissionError, match=r"403 PERMISSION_DENIED.*IAM CEL Regional Lock"
    ):
        store.retrieve_memories(
            service_account_email=US_RETAIL_SA,
            region="europe-west3",
            memory_bank_id="cymbal-eu-memory-bank",
            scope=eva_scope,
        )

    # 4. EU Retail SA tries to read Alice's US memory in `us-central1` -> 403 PERMISSION_DENIED
    # (Regional Lock)
    with pytest.raises(
        PermissionError, match=r"403 PERMISSION_DENIED.*IAM CEL Regional Lock"
    ):
        store.retrieve_memories(
            service_account_email=EU_RETAIL_SA,
            region="us-central1",
            memory_bank_id="cymbal-us-memory-bank",
            scope=eva_scope,
        )


def test_1_shared_vs_n_dedicated_memory_bank_4_trigger_router() -> None:
    """Verifies the 4-trigger decision rule for 1 Shared vs N Dedicated Memory Banks."""
    shared = MemoryBankTopologyRouter.recommend_memory_bank_topology()
    assert (
        shared["memory_bank_topology"]
        == "SINGLE_SHARED_REGIONAL_MEMORY_BANK_WITH_SCOPES_AND_IAM_CEL"
    )

    dedicated = MemoryBankTopologyRouter.recommend_memory_bank_topology(
        requires_per_tenant_cmek=True,
        requires_separate_region_or_vpc_sc=True,
        region="europe-west3",
        tenant_id="tenant-finvault-alpha",
    )
    assert (
        dedicated["memory_bank_topology"]
        == "DEDICATED_MEMORY_BANK_INSTANCE_PER_TENANT"
    )
    assert (
        "1_PER_TENANT_CMEK_KEY"
        in dedicated["triggered_enterprise_requirements"]
    )
    assert (
        "2_REGIONAL_DATA_RESIDENCY_OR_VPC_SC"
        in dedicated["triggered_enterprise_requirements"]
    )


def test_agent_id_in_memory_scope_and_iam_cel_blocks_cross_agent_pollution() -> (
    None
):
    """Verifies (tenant_id, lob, user_id, agent_id) scope and IAM CEL isolation across catalog
    agents.
    """
    store = MemoryBankScopeStore()
    sre_sa = "finvault-sre-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
    compliance_sa = "finvault-compliance-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"

    priya_sre_scope = MemoryBankScopeStore.build_verified_memory_scope(
        tenant_id="tenant-finvault-alpha",
        lob="retail_banking",
        user_id="priya@finvault.com",
        agent_id="sre_diagnostic_agent",
    )
    assert priya_sre_scope["agent_id"] == "sre_diagnostic_agent"

    store.create_or_consolidate_memory(
        service_account_email=sre_sa,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope=priya_sre_scope,
        extracted_fact="Priya prefers p99 wire latency alerts grouped by cluster.",
    )

    # Same user + tenant, but different agent_id -> 0 exact scope matches & blocked by IAM CEL if
    # impersonated
    priya_compliance_scope = MemoryBankScopeStore.build_verified_memory_scope(
        tenant_id="tenant-finvault-alpha",
        lob="retail_banking",
        user_id="priya@finvault.com",
        agent_id="finvault_regulatory_escalation_agent",
    )
    with pytest.raises(
        PermissionError, match=r"403 PERMISSION_DENIED.*IAM CEL Scope Lock"
    ):
        store.retrieve_memories(
            service_account_email=compliance_sa,
            region="us-central1",
            memory_bank_id="cymbal-us-memory-bank",
            scope=priya_sre_scope,
        )

    compliance_hits = store.retrieve_memories(
        service_account_email=compliance_sa,
        region="us-central1",
        memory_bank_id="cymbal-us-memory-bank",
        scope=priya_compliance_scope,
    )
    assert len(compliance_hits) == 0
