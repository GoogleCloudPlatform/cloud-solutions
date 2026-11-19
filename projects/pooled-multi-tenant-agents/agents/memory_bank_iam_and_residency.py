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

"""Gemini platform Memory Bank Isolation, IAM CEL Conditions & GDPR Regional Residency.

Implements the 5 core enterprise Memory Bank controls from Google Cloud FDE guidance
("Memory Isolation and Regional Compliance in Gemini platform Memory Bank"):

1. **Immutable 5-Key Exact-Match `scope` Dictionary (`MemoryBankScopeStore`)**:
   - Enforces a flat `dict[str, str]` of at most 5 keys (e.g., `tenant_id`, `line_of_business`,
     `user_id`, `agent_id`, `region`).
   - Both consolidation (`generate_or_create_memory`) and retrieval (`retrieve_memories`)
     require an **exact, case-sensitive match on the entire `scope` dictionary**—subset
     scopes, superset scopes, and case mismatches (`"Alice"` vs `"alice"`) return `0` memories.
2. **ADK Tool Schema Inspector (`ADKToolSchemaInspector`)**:
   - Verifies that `tool_context` (and identity keys like `tenant_id` / `user_id`) are hidden
     from the Gemini LLM function-calling declaration schema so a prompt injection cannot
     pass a forged `user_id` or `tenant_id` into a Memory Bank tool call.
3. **Token Broker + Per-Tenant Service Account + Cloud IAM CEL Conditions
   (`MemoryBankIAMCELGuard`)**:
   - Moves the security boundary from application code to Google Cloud IAM using least-privilege
     roles (`roles/aiplatform.memoryViewer`, `roles/aiplatform.memoryEditor`,
     `roles/aiplatform.memoryUser`) paired with Common Expression Language (CEL) conditions on
     `resource.name` (region/instance lock) and `scope` attributes (`tenant_id` /
     `line_of_business`).
4. **GDPR Regional Data Residency & Org Policy Guardrail (`RegionalMemoryBankResidencyGuard`)**:
   - Prohibits `global` Memory Bank provisioning (`constraints/gcp.resourceLocations`), pins
     US workloads (`Alice`) to `us-central1` and EU GDPR workloads (`Eva`) to `europe-west3`,
     and blocks cross-border US <-> EU queries with `403 PERMISSION_DENIED`.
5. **1-Shared vs. N-Dedicated Memory Bank Decision Router (`MemoryBankTopologyRouter`)**:
   - Routes a Shared Pooled Agent to either `1` Shared Memory Bank (with scopes + IAM CEL)
     or `N` Separate Memory Bank instances when any of the 4 enterprise triggers apply:
     (a) Per-instance CMEK, (b) Regional residency / VPC-SC, (c) Custom TTL / extraction LLM /
     embedding model / revision settings, or (d) Quota, billing & `PurgeMemories` blast radius.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

MAX_MEMORY_SCOPE_KEYS = 5
ALLOWED_MEMORY_BANK_ROLES = frozenset(
    {
        "roles/aiplatform.memoryViewer",
        "roles/aiplatform.memoryEditor",
        "roles/aiplatform.memoryUser",
    }
)
APPROVED_REGIONS = frozenset({"us-central1", "europe-west3"})


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    memory_bank_id: str
    region: str
    scope: tuple[tuple[str, str], ...]
    extracted_fact: str
    embedding_model: str = "text-embedding-005"


@dataclass(frozen=True)
class ServiceAccountIAMBinding:
    service_account_email: str
    role: str
    allowed_region: str
    allowed_memory_bank_id: str
    required_scope_kv: dict[str, str]
    cel_expression: str


class ADKToolSchemaInspector:
    """Proves ADK hides `tool_context` and identity keys from the LLM function declaration
    schema.
    """

    FORBIDDEN_LLM_IDENTITY_PARAMS = frozenset(
        {"tenant_id", "user_id", "line_of_business", "agent_id", "scope"}
    )

    @classmethod
    def extract_llm_visible_parameters(
        cls, tool_fn: Callable[..., Any]
    ) -> list[str]:
        """Emulates Google ADK's function schema generator, which strips `tool_context`."""
        sig = inspect.signature(tool_fn)
        visible: list[str] = []
        for name in sig.parameters:
            if name in ("tool_context", "db_pool"):
                continue
            visible.append(name)
        return visible

    @classmethod
    def verify_tool_safe_against_scope_injection(
        cls, tool_fn: Callable[..., Any]
    ) -> dict[str, Any]:
        sig = inspect.signature(tool_fn)
        has_tool_context = "tool_context" in sig.parameters
        llm_params = cls.extract_llm_visible_parameters(tool_fn)
        leaked_identity_params = [
            p for p in llm_params if p in cls.FORBIDDEN_LLM_IDENTITY_PARAMS
        ]
        if not has_tool_context or leaked_identity_params:
            raise PermissionError(
                f"E_ADK_SCHEMA_UNSAFE: Tool '{tool_fn.__name__}' exposes identity parameters "
                f"{leaked_identity_params} to the LLM or omits `tool_context`."
            )
        return {
            "tool_name": tool_fn.__name__,
            "has_hidden_tool_context": has_tool_context,
            "llm_visible_parameters": llm_params,
            "leaked_identity_parameters": leaked_identity_params,
            "safe_against_prompt_scope_injection": True,
        }


class MemoryBankIAMCELGuard:
    """Enforces Google Cloud IAM roles and CEL conditions on Memory Bank reads and writes."""

    def __init__(self) -> None:
        self._bindings: dict[str, ServiceAccountIAMBinding] = {
            (
                "us-retail-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
            ): ServiceAccountIAMBinding(
                service_account_email="us-retail-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com",
                role="roles/aiplatform.memoryUser",
                allowed_region="us-central1",
                allowed_memory_bank_id="cymbal-us-memory-bank",
                required_scope_kv={
                    "tenant_id": "tenant-finvault-alpha",
                    "line_of_business": "retail_banking",
                },
                cel_expression=(
                    "resource.name.startsWith('projects/cymbal-multitenancy-example/locations/us-central1/"
                    "reasoningEngines/cymbal-us-memory-bank') && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['tenant_id'] == 'tenant-finvault-alpha' && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['line_of_business'] == 'retail_banking'"
                ),
            ),
            (
                "us-wealth-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
            ): ServiceAccountIAMBinding(
                service_account_email="us-wealth-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com",
                role="roles/aiplatform.memoryUser",
                allowed_region="us-central1",
                allowed_memory_bank_id="cymbal-us-memory-bank",
                required_scope_kv={
                    "tenant_id": "tenant-finvault-alpha",
                    "line_of_business": "wealth_management",
                },
                cel_expression=(
                    "resource.name.startsWith('projects/cymbal-multitenancy-example/locations/us-central1/"
                    "reasoningEngines/cymbal-us-memory-bank') && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['tenant_id'] == 'tenant-finvault-alpha' && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['line_of_business'] == 'wealth_management'"
                ),
            ),
            (
                "eu-retail-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
            ): ServiceAccountIAMBinding(
                service_account_email="eu-retail-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com",
                role="roles/aiplatform.memoryUser",
                allowed_region="europe-west3",
                allowed_memory_bank_id="cymbal-eu-memory-bank",
                required_scope_kv={
                    "tenant_id": "tenant-finvault-alpha",
                    "line_of_business": "retail_banking",
                },
                cel_expression=(
                    "resource.name.startsWith('projects/cymbal-multitenancy-example/locations/europe-west3/"
                    "reasoningEngines/cymbal-eu-memory-bank') && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['tenant_id'] == 'tenant-finvault-alpha' && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['line_of_business'] == 'retail_banking'"
                ),
            ),
            (
                "retailstream-us-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
            ): ServiceAccountIAMBinding(
                service_account_email="retailstream-us-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com",
                role="roles/aiplatform.memoryUser",
                allowed_region="us-central1",
                allowed_memory_bank_id="cymbal-us-memory-bank",
                required_scope_kv={
                    "tenant_id": "tenant-retailstream-beta",
                    "line_of_business": "ecommerce_ops",
                },
                cel_expression=(
                    "resource.name.startsWith('projects/cymbal-multitenancy-example/locations/us-central1/"
                    "reasoningEngines/cymbal-us-memory-bank') && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['tenant_id'] == 'tenant-retailstream-beta'"
                ),
            ),
            (
                "finvault-sre-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
            ): ServiceAccountIAMBinding(
                service_account_email="finvault-sre-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com",
                role="roles/aiplatform.memoryUser",
                allowed_region="us-central1",
                allowed_memory_bank_id="cymbal-us-memory-bank",
                required_scope_kv={
                    "tenant_id": "tenant-finvault-alpha",
                    "agent_id": "sre_diagnostic_agent",
                },
                cel_expression=(
                    "resource.name.startsWith('projects/cymbal-multitenancy-example/locations/us-central1/"
                    "reasoningEngines/cymbal-us-memory-bank') && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['tenant_id'] == 'tenant-finvault-alpha' && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['agent_id'] == 'sre_diagnostic_agent'"
                ),
            ),
            (
                "finvault-compliance-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com"
            ): ServiceAccountIAMBinding(
                service_account_email="finvault-compliance-agent-sa@cymbal-multitenancy-example.iam.gserviceaccount.com",
                role="roles/aiplatform.memoryUser",
                allowed_region="us-central1",
                allowed_memory_bank_id="cymbal-us-memory-bank",
                required_scope_kv={
                    "tenant_id": "tenant-finvault-alpha",
                    "agent_id": "finvault_regulatory_escalation_agent",
                },
                cel_expression=(
                    "resource.name.startsWith('projects/cymbal-multitenancy-example/locations/us-central1/"
                    "reasoningEngines/cymbal-us-memory-bank') && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['tenant_id'] == 'tenant-finvault-alpha' && "
                    "api.getAttribute('aiplatform.googleapis.com/memoryScope', "
                    "{})['agent_id'] == 'finvault_regulatory_escalation_agent'"
                ),
            ),
        }

    def authorize_memory_operation(
        self,
        *,
        service_account_email: str,
        operation: str,  # "read" or "write"
        target_region: str,
        target_memory_bank_id: str,
        scope: dict[str, str],
    ) -> ServiceAccountIAMBinding:
        """Evaluates Cloud IAM role + CEL condition before any Memory Bank RPC hits storage."""
        binding = self._bindings.get(service_account_email)
        if binding is None:
            raise PermissionError(
                "403 PERMISSION_DENIED: Service account '"
                f"{service_account_email}' has no Memory Bank IAM binding."
            )

        if binding.role not in ALLOWED_MEMORY_BANK_ROLES:
            raise PermissionError(
                f"403 PERMISSION_DENIED: Invalid role '{binding.role}'."
            )
        if (
            operation == "write"
            and binding.role == "roles/aiplatform.memoryViewer"
        ):
            raise PermissionError(
                "403 PERMISSION_DENIED: memoryViewer cannot write to Memory Bank."
            )
        if (
            operation == "read"
            and binding.role == "roles/aiplatform.memoryEditor"
        ):
            raise PermissionError(
                "403 PERMISSION_DENIED: memoryEditor cannot read from Memory Bank."
            )

        # Evaluate Regional & Resource Path CEL Lock
        if (
            target_region != binding.allowed_region
            or target_memory_bank_id != binding.allowed_memory_bank_id
        ):
            raise PermissionError(
                "403 PERMISSION_DENIED (IAM CEL Regional Lock): "
                "E_MEMORY_IAM_CEL_REGIONAL_LOCK: the "
                "service account is not bound to the requested region or Memory Bank."
            )

        # Evaluate Scope Key-Value CEL Condition
        for req_k, req_v in binding.required_scope_kv.items():
            actual_v = scope.get(req_k)
            if actual_v != req_v:
                raise PermissionError(
                    "403 PERMISSION_DENIED (IAM CEL Scope Lock): E_MEMORY_IAM_CEL_SCOPE_LOCK: the "
                    "requested scope is outside the service account's binding."
                )

        return binding


class MemoryBankScopeStore:
    """Models Gemini platform Memory Bank's 5-key flat scope dictionary and regional residency."""

    def __init__(self, iam_guard: MemoryBankIAMCELGuard | None = None) -> None:
        self.iam_guard = iam_guard or MemoryBankIAMCELGuard()
        self._memories: list[MemoryRecord] = []
        self._seq = 0

    @staticmethod
    def build_verified_memory_scope(
        *,
        tenant_id: str,
        lob: str,
        user_id: str,
        agent_id: str,
    ) -> dict[str, str]:
        """Builds the verified 4-key (tenant, lob, user, agent) Memory Bank scope dictionary."""
        scope = {
            "tenant_id": tenant_id,
            "lob": lob,
            "user_id": user_id,
            "agent_id": agent_id,
        }
        MemoryBankScopeStore.validate_and_canonicalize_scope(scope)
        return scope

    @staticmethod
    def validate_and_canonicalize_scope(
        scope: dict[str, Any],
    ) -> tuple[tuple[str, str], ...]:
        """Enforces an immutable flat dictionary of 1..5 string key-value pairs."""
        if not scope:
            raise ValueError(
                "E_EMPTY_MEMORY_SCOPE: Memory scope dictionary cannot be empty."
            )
        if len(scope) > MAX_MEMORY_SCOPE_KEYS:
            raise ValueError(
                "E_MEMORY_SCOPE_TOO_LARGE: Memory Bank scope "
                "allows at most "
                f"{MAX_MEMORY_SCOPE_KEYS}"
                " "
                f"keys; got {len(scope)}."
            )
        for k, v in scope.items():
            if (
                not isinstance(k, str)
                or not isinstance(v, str)
                or not k
                or not v
            ):
                raise ValueError(
                    "E_INVALID_MEMORY_SCOPE_TYPE: Scope keys and values must be "
                    "non-empty strings; got "
                    f"{k!r}={v!r}."
                )
        return tuple(sorted(scope.items()))

    @staticmethod
    def enforce_regional_org_policy(region: str) -> None:
        """Enforces `constraints/gcp.resourceLocations`: blocks `global` or unapproved regions."""
        if region not in APPROVED_REGIONS:
            raise PermissionError(
                f"400 E_ORG_POLICY_LOCATION_VIOLATION: Region '{region}' is blocked by "
                f"constraints/gcp.resourceLocations (approved: {sorted(APPROVED_REGIONS)})."
            )

    def create_or_consolidate_memory(
        self,
        *,
        service_account_email: str,
        region: str,
        memory_bank_id: str,
        scope: dict[str, str],
        extracted_fact: str,
    ) -> MemoryRecord:
        """Step 1 (Generation & Consolidation): Validates org policy, IAM CEL, and 5-key scope."""
        self.enforce_regional_org_policy(region)
        canonical_scope = self.validate_and_canonicalize_scope(scope)
        self.iam_guard.authorize_memory_operation(
            service_account_email=service_account_email,
            operation="write",
            target_region=region,
            target_memory_bank_id=memory_bank_id,
            scope=scope,
        )
        self._seq += 1
        rec = MemoryRecord(
            memory_id=f"mem-{region}-{self._seq:04d}",
            memory_bank_id=memory_bank_id,
            region=region,
            scope=canonical_scope,
            extracted_fact=extracted_fact,
        )
        self._memories.append(rec)
        return rec

    def retrieve_memories(
        self,
        *,
        service_account_email: str,
        region: str,
        memory_bank_id: str,
        scope: dict[str, str],
    ) -> list[MemoryRecord]:
        """Step 2 (Scoped Similarity Retrieval): Requires exact case-sensitive match on entire
        scope.
        """
        self.enforce_regional_org_policy(region)
        canonical_scope = self.validate_and_canonicalize_scope(scope)
        self.iam_guard.authorize_memory_operation(
            service_account_email=service_account_email,
            operation="read",
            target_region=region,
            target_memory_bank_id=memory_bank_id,
            scope=scope,
        )
        return [
            m
            for m in self._memories
            if m.region == region
            and m.memory_bank_id == memory_bank_id
            and m.scope == canonical_scope
        ]


class MemoryBankTopologyRouter:
    """Implements the 4-Trigger Decision Matrix for 1-Shared vs. N-Dedicated Memory Banks."""

    @staticmethod
    def recommend_memory_bank_topology(
        *,
        requires_per_tenant_cmek: bool = False,
        requires_separate_region_or_vpc_sc: bool = False,
        requires_custom_ttl_or_embedding_model: bool = False,
        requires_isolated_quota_or_purge_blast_radius: bool = False,
        region: str = "us-central1",
        tenant_id: str = "tenant-finvault-alpha",
    ) -> dict[str, Any]:
        triggers: list[str] = []
        if requires_per_tenant_cmek:
            triggers.append("1_PER_TENANT_CMEK_KEY")
        if requires_separate_region_or_vpc_sc:
            triggers.append("2_REGIONAL_DATA_RESIDENCY_OR_VPC_SC")
        if requires_custom_ttl_or_embedding_model:
            triggers.append("3_CUSTOM_INSTANCE_TTL_OR_EXTRACTION_MODEL")
        if requires_isolated_quota_or_purge_blast_radius:
            triggers.append("4_ISOLATED_QUOTA_BILLING_OR_PURGE_BLAST_RADIUS")

        if triggers:
            return {
                "agent_runtime_topology": "SHARED_POOLED_AGENT_WITH_PER_TENANT_SA_TOKEN_BROKER",
                "memory_bank_topology": "DEDICATED_MEMORY_BANK_INSTANCE_PER_TENANT",
                "target_memory_bank_id": f"mb-{tenant_id}-{region}",
                "triggered_enterprise_requirements": triggers,
            }
        return {
            "agent_runtime_topology": "SHARED_POOLED_AGENT_WITH_PER_TENANT_SA_TOKEN_BROKER",
            "memory_bank_topology": "SINGLE_SHARED_REGIONAL_MEMORY_BANK_WITH_SCOPES_AND_IAM_CEL",
            "target_memory_bank_id": f"cymbal-shared-mb-{region}",
            "triggered_enterprise_requirements": [],
        }
