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

"""Multi-Tenant Model Routing Policy Decision Point (Shared Map and First Move).

Implements the two-track model routing architecture and four multi-tenant primitives:
1. Track 1 (Shared First Move): Task-aware routing and FastSearch harness trimming
   that routes read-only lookup queries to `gemini-4-hydrogen` while trimming active
   tool schemas to a read-only allowlist and disabling sub-agent delegation.
2. Mid-Task Escalation (`AskPro` Advisor Pattern): Keeps `gemini-4-hydrogen` as the
   primary session executor and allows at most one bounded consultation per turn to
   `gemini-4-carbon` when complexity or tool errors exceed threshold.
3. Cross-Family Session Sanitizer: Strips incompatible `<thought>` and `<thinking>`
   blocks when switching between Claude and Gemini model families in multi-turn
   sessions while preserving signed `agent_id` attribution.
4. Glass-Box Routing Savings Ledger: Tenant-isolated FinOps ledger tracking tokens
   and USD saved by model routing and harness trimming per tenant.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agents.context import (
    TENANT_DIRECTORY,
    ContextEnvelope,
    SubscriptionTier,
    register_tenant_eviction_target,
)
from agents.platform_config import get_platform_config

FAST_SEARCH_READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "query_telemetry_rls",
        "read_runbook",
        "read_sharepoint_runbook",
    }
)

_FAST_SEARCH_PROMPT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:lookup|search|list|fetch|read|show|status|check|summarize)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:runbook|incident|latency|logs|telemetry)\b", re.IGNORECASE
    ),
)

_MUTATING_OR_COMPLEX_PROMPT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:create|open|file|escalate|remediate|patch|mutat|schedule|postmortem|occ|sec\s+17a-4|finra)\b",
        re.IGNORECASE,
    ),
)

_THOUGHT_TAG_PATTERN: re.Pattern[str] = re.compile(
    r"<(?:thought|thinking)>.*?</(?:thought|thinking)>",
    re.IGNORECASE | re.DOTALL,
)

DEFAULT_FLASH_MODEL: str = get_platform_config().models.default_executor_model
DEFAULT_PRO_MODEL: str = get_platform_config().models.default_frontier_model
FALLBACK_FLASH_MODEL: str = get_platform_config().models.fallback_fast_model
FALLBACK_PRO_MODEL: str = get_platform_config().models.fallback_frontier_model

# Published Vertex AI / Anthropic token rates (USD per 1,000,000 input tokens) for modeled savings.
MODEL_INPUT_COST_PER_1M_USD: Mapping[str, float] = {
    "gemini-4-hydrogen": 1.50,
    "gemini-4-carbon": 2.00,
    "gemini-4-argon": 2.00,
    "gemini-3.8-flash": 0.15,
    "gemini-2.5-flash": 0.15,
    "gemini-2.5-pro": 1.25,
    "claude-3-7-sonnet@20250219": 3.00,
}

FULL_HARNESS_TOOL_SCHEMA_TOKENS: int = 2200
FAST_SEARCH_TRIMMED_SCHEMA_TOKENS: int = 800
FAST_SEARCH_THINKING_BUDGET_TOKENS: int = 2048


class ModelRoutingMode(StrEnum):
    """Supported model routing modes across Track 1 (Harness) and Track 2 (Router)."""

    DETERMINISTIC = "deterministic"
    TRACK1_FAST_SEARCH = "track1_fast_search"
    ASKPRO_MID_TASK_ADVISOR = "askpro_mid_task_advisor"
    ADAPTIVE_BANDIT_GUARDED = "adaptive_bandit_guarded"


class TaskComplexityClass(StrEnum):
    """Task complexity classification used by the Hop 3 model router."""

    FAST_SEARCH_LOOKUP = "fast_search_lookup"
    STANDARD_DIAGNOSTIC = "standard_diagnostic"
    REGULATORY_ESCALATION = "regulatory_escalation"


@dataclass(frozen=True)
class TenantModelRoutingPolicy:
    """Immutable per-tenant model routing policy contract."""

    tenant_id: str
    routing_mode: ModelRoutingMode
    allowed_models: tuple[str, ...]
    default_executor_model: str
    advisor_model: str
    max_advisor_consultations_per_turn: int = 1
    semantic_cache_partitioned_by_tenant: bool = True


@dataclass(frozen=True)
class ModelRoutingDecision:
    """Verifiable Hop 3 model routing and harness trimming decision receipt."""

    tenant_id: str
    agent_id: str
    routing_mode: ModelRoutingMode
    task_complexity: TaskComplexityClass
    selected_model: str
    advisor_model: str | None
    effective_thinking_budget: int
    pruned_active_tools: tuple[str, ...]
    trimmed_write_tools_count: int
    allow_subagent_delegation: bool
    schema_tokens_saved: int
    estimated_turn_usd_saved: float
    cross_family_thoughts_stripped: int
    sanitized_session_history: tuple[str, ...]


def _model_family(model_id: str) -> str:
    """Returns the canonical model family identifier ('claude' or 'gemini')."""
    lowered = model_id.strip().lower()
    if lowered.startswith("claude"):
        return "claude"
    if lowered.startswith(("gemini", "gemma")):
        return "gemini"
    return "other"


class CrossFamilySessionSanitizer:
    """Sanitizes session history when routing across distinct model families."""

    @staticmethod
    def sanitize_history_for_target_model(
        *,
        previous_model_id: str | None,
        target_model_id: str,
        session_history: Sequence[str],
        envelope: ContextEnvelope,
        expected_agent_id: str,
        session_state: Mapping[str, Any] | None = None,
    ) -> tuple[tuple[str, ...], int]:
        """Strips raw thought blocks across model families and verifies agent identity.

        Args:
            previous_model_id: Model identifier used in the preceding session turn, if any.
            target_model_id: Model identifier selected for the current turn.
            session_history: Sequence of prior assistant/user transcript messages.
            envelope: Verified caller ContextEnvelope for this turn.
            expected_agent_id: Canonical agent identifier invoked for this turn.
            session_state: Optional ADK session state dictionary to verify agent attribution.

        Returns:
            A tuple of `(sanitized_messages, stripped_thought_blocks_count)`.

        Raises:
            PermissionError: If `session_state` attempts to spoof `temp:tenant_id` or
                `temp:agent_id`.
        """
        if not isinstance(envelope, ContextEnvelope):
            raise PermissionError(
                "E_UNVERIFIED_ENVELOPE: Verified ContextEnvelope required."
            )
        if session_state is not None:
            state_tenant = session_state.get("temp:tenant_id")
            if (
                state_tenant is not None
                and str(state_tenant) != envelope.tenant.tenant_id
            ):
                raise PermissionError(
                    "E_CROSS_TENANT_SESSION_STATE: Session state tenant_id does not match envelope."
                )
            state_agent = session_state.get("temp:agent_id")
            if (
                state_agent is not None
                and str(state_agent) != expected_agent_id
            ):
                raise PermissionError(
                    "E_AGENT_IDENTITY_DRIFT: Session state agent_id drifted across model switch."
                )

        if not previous_model_id:
            return tuple(session_history), 0

        previous_family = _model_family(previous_model_id)
        target_family = _model_family(target_model_id)
        if previous_family == target_family:
            return tuple(session_history), 0

        sanitized_messages: list[str] = []
        stripped_count = 0
        for message in session_history:
            matches = _THOUGHT_TAG_PATTERN.findall(message)
            if matches:
                stripped_count += len(matches)
                cleaned = _THOUGHT_TAG_PATTERN.sub("", message).strip()
                sanitized_messages.append(cleaned)
            else:
                sanitized_messages.append(message)
        return tuple(sanitized_messages), stripped_count


class FastSearchHarnessTrimmer:
    """Implements Track 1 task-aware routing and read-only harness trimming."""

    @staticmethod
    def classify_task_complexity(
        *,
        agent_id: str,
        tool_name: str,
        prompt: str,
    ) -> TaskComplexityClass:
        """Classifies a turn into FastSearch lookup, Standard diagnostic, or Regulatory escalation.

        Args:
            agent_id: Target agent identifier.
            tool_name: Requested MCP tool name.
            prompt: User prompt text.

        Returns:
            The resolved `TaskComplexityClass`.
        """
        if agent_id == "finvault_regulatory_escalation_agent":
            return TaskComplexityClass.REGULATORY_ESCALATION
        if tool_name not in FAST_SEARCH_READ_ONLY_TOOLS:
            return TaskComplexityClass.STANDARD_DIAGNOSTIC
        for mutating_pattern in _MUTATING_OR_COMPLEX_PROMPT_PATTERNS:
            if mutating_pattern.search(prompt):
                return TaskComplexityClass.STANDARD_DIAGNOSTIC
        if all(
            pattern.search(prompt) for pattern in _FAST_SEARCH_PROMPT_PATTERNS
        ):
            return TaskComplexityClass.FAST_SEARCH_LOOKUP
        return TaskComplexityClass.STANDARD_DIAGNOSTIC

    @staticmethod
    def trim_harness_for_fast_search(
        entitled_tools: Sequence[str],
    ) -> tuple[tuple[str, ...], int, int]:
        """Trims active tools to the read-only search allowlist for FastSearch turns.

        Args:
            entitled_tools: Tools entitled by Hop 2 RBAC intersection.

        Returns:
            Tuple of `(trimmed_tools, removed_write_tools_count, schema_tokens_saved)`.
        """
        trimmed = tuple(
            tool
            for tool in entitled_tools
            if tool in FAST_SEARCH_READ_ONLY_TOOLS
        )
        removed_count = max(0, len(entitled_tools) - len(trimmed))
        tokens_saved = (
            FULL_HARNESS_TOOL_SCHEMA_TOKENS - FAST_SEARCH_TRIMMED_SCHEMA_TOKENS
            if removed_count > 0
            or len(trimmed) <= len(FAST_SEARCH_READ_ONLY_TOOLS)
            else 0
        )
        return trimmed, removed_count, tokens_saved


class GlassBoxRoutingSavingsLedger:
    """Tenant-isolated ledger recording customer-visible token and USD routing savings."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_tenant: dict[str, dict[str, Any]] = {}
        register_tenant_eviction_target(self)

    def evict_tenant(self, tenant_id: str) -> bool:
        """Evicts a tenant's routing ledger upon tenant offboarding."""
        with self._lock:
            return self._by_tenant.pop(tenant_id, None) is not None

    def record_decision(self, decision: ModelRoutingDecision) -> None:
        """Records a verified routing decision in the tenant's glass-box savings ledger."""
        with self._lock:
            bucket = self._by_tenant.setdefault(
                decision.tenant_id,
                {
                    "tenant_id": decision.tenant_id,
                    "turns_routed": 0,
                    "fast_search_turns": 0,
                    "askpro_escalations": 0,
                    "schema_tokens_saved": 0,
                    "estimated_usd_saved": 0.0,
                    "cross_family_thoughts_stripped": 0,
                    "last_selected_model": decision.selected_model,
                },
            )
            bucket["turns_routed"] += 1
            if (
                decision.task_complexity
                == TaskComplexityClass.FAST_SEARCH_LOOKUP
            ):
                bucket["fast_search_turns"] += 1
            bucket["schema_tokens_saved"] += decision.schema_tokens_saved
            bucket["estimated_usd_saved"] = round(
                float(bucket["estimated_usd_saved"])
                + decision.estimated_turn_usd_saved,
                6,
            )
            bucket[
                "cross_family_thoughts_stripped"
            ] += decision.cross_family_thoughts_stripped
            bucket["last_selected_model"] = decision.selected_model

    def record_askpro_escalation(
        self, *, tenant_id: str, incremental_usd_saved: float
    ) -> None:
        """Records a bounded AskPro mid-task escalation in the tenant's ledger."""
        with self._lock:
            bucket = self._by_tenant.setdefault(
                tenant_id,
                {
                    "tenant_id": tenant_id,
                    "turns_routed": 0,
                    "fast_search_turns": 0,
                    "askpro_escalations": 0,
                    "schema_tokens_saved": 0,
                    "estimated_usd_saved": 0.0,
                    "cross_family_thoughts_stripped": 0,
                    "last_selected_model": DEFAULT_FLASH_MODEL,
                },
            )
            bucket["askpro_escalations"] += 1
            bucket["estimated_usd_saved"] = round(
                float(bucket["estimated_usd_saved"]) + incremental_usd_saved,
                6,
            )

    def get_tenant_summary(self, envelope: ContextEnvelope) -> dict[str, Any]:
        """Returns the glass-box routing savings summary exclusively for the authenticated tenant.

        Args:
            envelope: Verified caller ContextEnvelope.

        Returns:
            Dictionary containing the caller tenant's cumulative routing metrics.

        Raises:
            PermissionError: If the envelope is unverified or the tenant has been offboarded.
        """
        if not isinstance(envelope, ContextEnvelope):
            raise PermissionError(
                "E_UNVERIFIED_ENVELOPE: Verified ContextEnvelope required."
            )
        tenant_id = envelope.tenant.tenant_id
        if tenant_id not in TENANT_DIRECTORY:
            raise PermissionError(
                f"403 E_TENANT_OFFBOARDED: Tenant '{tenant_id}' is not active in TENANT_DIRECTORY."
            )
        with self._lock:
            existing = self._by_tenant.get(tenant_id)
            if existing is None:
                return {
                    "tenant_id": tenant_id,
                    "turns_routed": 0,
                    "fast_search_turns": 0,
                    "askpro_escalations": 0,
                    "schema_tokens_saved": 0,
                    "estimated_usd_saved": 0.0,
                    "cross_family_thoughts_stripped": 0,
                    "last_selected_model": None,
                }
            return dict(existing)


class SharedModelRoutingPDP:
    """Multi-tenant Model Routing Policy Decision Point (Hop 3)."""

    def __init__(
        self,
        *,
        policy_ttl_seconds: float = 60.0,
        live_advisor_fn: Any | None = None,
    ) -> None:
        self._policy_ttl_seconds = policy_ttl_seconds
        self._live_advisor_fn = live_advisor_fn
        self._lock = threading.Lock()
        self._policy_cache: dict[
            str, tuple[float, TenantModelRoutingPolicy]
        ] = {}
        self._advisor_consultations: dict[tuple[str, str], int] = {}
        self.ledger = GlassBoxRoutingSavingsLedger()
        register_tenant_eviction_target(self)

    def evict_tenant(self, tenant_id: str) -> bool:
        """Purges cached routing policies, advisor turn counters, and ledger for `tenant_id`."""
        with self._lock:
            removed_policy = self._policy_cache.pop(tenant_id, None) is not None
            trace_keys = [
                key
                for key in self._advisor_consultations
                if key[0] == tenant_id
            ]
            for trace_key in trace_keys:
                self._advisor_consultations.pop(trace_key, None)
        removed_ledger = self.ledger.evict_tenant(tenant_id)
        return removed_policy or bool(trace_keys) or removed_ledger

    def resolve_tenant_policy(
        self,
        envelope: ContextEnvelope,
        *,
        requested_mode: ModelRoutingMode | None = None,
        now: float | None = None,
    ) -> TenantModelRoutingPolicy:
        """Resolves the tenant's model routing policy after synchronous entitlement verification.

        Args:
            envelope: Verified caller ContextEnvelope.
            requested_mode: Optional explicit routing mode override requested for this turn.
            now: Optional monotonic timestamp override for deterministic TTL testing.

        Returns:
            The resolved `TenantModelRoutingPolicy`.

        Raises:
            PermissionError: If the tenant is not onboarded or requests an unentitled routing mode.
        """
        if not isinstance(envelope, ContextEnvelope):
            raise PermissionError(
                "E_UNVERIFIED_ENVELOPE: Verified ContextEnvelope required."
            )
        tenant_id = envelope.tenant.tenant_id
        # Synchronous policy/onboarding check MUST run before any TTL cache lookup.
        if tenant_id not in TENANT_DIRECTORY:
            raise PermissionError(
                f"403 E_TENANT_OFFBOARDED: Tenant '{tenant_id}' is not active in TENANT_DIRECTORY."
            )

        current_time = time.monotonic() if now is None else now
        is_enterprise = (
            envelope.tenant.subscription_tier == SubscriptionTier.ENTERPRISE
        )

        if requested_mode is None:
            with self._lock:
                cached_entry = self._policy_cache.get(tenant_id)
                if cached_entry is not None:
                    expires_at, cached_policy = cached_entry
                    if current_time < expires_at:
                        return cached_policy
                    self._policy_cache.pop(tenant_id, None)

        effective_mode = requested_mode or (
            ModelRoutingMode.ASKPRO_MID_TASK_ADVISOR
            if is_enterprise
            else ModelRoutingMode.TRACK1_FAST_SEARCH
        )

        if (
            effective_mode == ModelRoutingMode.ADAPTIVE_BANDIT_GUARDED
            and not is_enterprise
        ):
            raise PermissionError(
                "403 E_ROUTING_MODE_FORBIDDEN: Adaptive bandit routing requires Enterprise tier."
            )

        model_cfg = get_platform_config().models
        allowed_models = (
            model_cfg.enterprise_allowed_models
            if is_enterprise
            else model_cfg.standard_allowed_models
        )
        policy = TenantModelRoutingPolicy(
            tenant_id=tenant_id,
            routing_mode=effective_mode,
            allowed_models=allowed_models,
            default_executor_model=model_cfg.default_executor_model,
            advisor_model=model_cfg.default_frontier_model,
            max_advisor_consultations_per_turn=1,
            semantic_cache_partitioned_by_tenant=True,
        )
        if requested_mode is None:
            with self._lock:
                self._policy_cache[tenant_id] = (
                    current_time + self._policy_ttl_seconds,
                    policy,
                )
        return policy

    def decide_route(
        self,
        *,
        envelope: ContextEnvelope,
        agent_id: str,
        tool_name: str,
        prompt: str,
        entitled_tools: Sequence[str],
        requested_thinking_budget: int,
        requested_mode: ModelRoutingMode | None = None,
        previous_model_id: str | None = None,
        session_history: Sequence[str] = (),
        session_state: Mapping[str, Any] | None = None,
    ) -> ModelRoutingDecision:
        """Computes the Hop 3 model routing and harness-trimming decision for a verified turn.

        Args:
            envelope: Verified caller ContextEnvelope.
            agent_id: Target agent identifier.
            tool_name: Requested MCP tool name.
            prompt: User prompt text.
            entitled_tools: Tools entitled at Hop 2.
            requested_thinking_budget: Thinking token budget clamped by Hop 3 bulkhead.
            requested_mode: Optional explicit `ModelRoutingMode`.
            previous_model_id: Optional prior turn model ID for cross-family sanitization.
            session_history: Optional prior turn messages to sanitize across model families.
            session_state: Optional ADK session state dictionary.

        Returns:
            A verified `ModelRoutingDecision` instance.

        Raises:
            PermissionError: If tenant or agent access violates multi-tenant routing invariants.
        """
        policy = self.resolve_tenant_policy(
            envelope, requested_mode=requested_mode
        )
        complexity = FastSearchHarnessTrimmer.classify_task_complexity(
            agent_id=agent_id,
            tool_name=tool_name,
            prompt=prompt,
        )

        is_enterprise = (
            envelope.tenant.subscription_tier == SubscriptionTier.ENTERPRISE
        )
        if complexity == TaskComplexityClass.REGULATORY_ESCALATION:
            if not is_enterprise:
                raise PermissionError(
                    "403 E_REGULATORY_ESCALATION_FORBIDDEN: Regulatory escalation "
                    "requires Enterprise tier."
                )
            selected_model = "claude-3-7-sonnet@20250219"
            pruned_tools = tuple(entitled_tools)
            removed_write_tools = 0
            schema_tokens_saved = 0
            effective_budget = min(
                requested_thinking_budget, envelope.tenant.thinking_token_budget
            )
            allow_subagents = True
        elif (
            complexity == TaskComplexityClass.FAST_SEARCH_LOOKUP
            and policy.routing_mode
            in (
                ModelRoutingMode.TRACK1_FAST_SEARCH,
                ModelRoutingMode.ASKPRO_MID_TASK_ADVISOR,
                ModelRoutingMode.ADAPTIVE_BANDIT_GUARDED,
            )
        ):
            selected_model = DEFAULT_FLASH_MODEL
            pruned_tools, removed_write_tools, schema_tokens_saved = (
                FastSearchHarnessTrimmer.trim_harness_for_fast_search(
                    entitled_tools
                )
            )
            effective_budget = min(
                requested_thinking_budget,
                FAST_SEARCH_THINKING_BUDGET_TOKENS,
                envelope.tenant.thinking_token_budget,
            )
            allow_subagents = False
        else:
            model_cfg = get_platform_config().models
            selected_model = (
                model_cfg.default_shared_model
                if policy.routing_mode == ModelRoutingMode.DETERMINISTIC
                and is_enterprise
                else policy.default_executor_model
            )
            pruned_tools = tuple(entitled_tools)
            removed_write_tools = 0
            schema_tokens_saved = 0
            effective_budget = min(
                requested_thinking_budget, envelope.tenant.thinking_token_budget
            )
            allow_subagents = is_enterprise

        sanitized_history, stripped_thoughts = (
            CrossFamilySessionSanitizer.sanitize_history_for_target_model(
                previous_model_id=previous_model_id,
                target_model_id=selected_model,
                session_history=session_history,
                envelope=envelope,
                expected_agent_id=agent_id,
                session_state=session_state,
            )
        )

        pro_rate = MODEL_INPUT_COST_PER_1M_USD[DEFAULT_PRO_MODEL]
        selected_rate = MODEL_INPUT_COST_PER_1M_USD.get(
            selected_model, pro_rate
        )
        base_turn_tokens = 6000
        rate_delta_savings = max(
            0.0, (pro_rate - selected_rate) * (base_turn_tokens / 1_000_000.0)
        )
        schema_savings = selected_rate * (schema_tokens_saved / 1_000_000.0)
        estimated_usd_saved = round(rate_delta_savings + schema_savings, 6)

        decision = ModelRoutingDecision(
            tenant_id=envelope.tenant.tenant_id,
            agent_id=agent_id,
            routing_mode=policy.routing_mode,
            task_complexity=complexity,
            selected_model=selected_model,
            advisor_model=(
                policy.advisor_model
                if policy.routing_mode
                == ModelRoutingMode.ASKPRO_MID_TASK_ADVISOR
                else None
            ),
            effective_thinking_budget=effective_budget,
            pruned_active_tools=pruned_tools,
            trimmed_write_tools_count=removed_write_tools,
            allow_subagent_delegation=allow_subagents,
            schema_tokens_saved=schema_tokens_saved,
            estimated_turn_usd_saved=estimated_usd_saved,
            cross_family_thoughts_stripped=stripped_thoughts,
            sanitized_session_history=sanitized_history,
        )
        self.ledger.record_decision(decision)
        return decision

    def escalate_to_advisor(
        self,
        *,
        envelope: ContextEnvelope,
        trace_id: str,
        escalation_reason: str,
        compact_evidence_digest: str,
    ) -> dict[str, Any]:
        """Executes a bounded mid-task escalation from `gemini-4-hydrogen` to `gemini-4-carbon`.

        Args:
            envelope: Verified caller ContextEnvelope.
            trace_id: Active turn trace identifier used to cap consultations at 1 per turn.
            escalation_reason: Reason trigger ('tool_error_retry', 'ambiguous_evidence',
                'complex_synthesis').
            compact_evidence_digest: Sanitized digest of tool outputs for the advisor.

        Returns:
            Structured receipt containing the advisor guidance and modeled cost savings.

        Raises:
            PermissionError: If the tenant is offboarded or exceeds
                `max_advisor_consultations_per_turn`.
            ValueError: If `trace_id` or `compact_evidence_digest` is empty.
        """
        policy = self.resolve_tenant_policy(
            envelope, requested_mode=ModelRoutingMode.ASKPRO_MID_TASK_ADVISOR
        )
        cleaned_trace_id = trace_id.strip()
        cleaned_digest = compact_evidence_digest.strip()
        if not cleaned_trace_id or not cleaned_digest:
            raise ValueError(
                "trace_id and compact_evidence_digest must be non-empty."
            )

        consultation_key = (envelope.tenant.tenant_id, cleaned_trace_id)
        with self._lock:
            used_count = self._advisor_consultations.get(consultation_key, 0)
            if used_count >= policy.max_advisor_consultations_per_turn:
                raise PermissionError(
                    "429 E_ASKPRO_CONSULTATION_CAP_EXCEEDED: Maximum 1 advisor "
                    "consultation per turn."
                )
            self._advisor_consultations[consultation_key] = used_count + 1

        # Compare 4-step tool loop on Pro (4 * 8,000 tokens) vs 3 steps on fast executor + 1 compact
        # AskPro call (2,500 tokens).
        advisor_rate = MODEL_INPUT_COST_PER_1M_USD.get(
            policy.advisor_model, MODEL_INPUT_COST_PER_1M_USD[DEFAULT_PRO_MODEL]
        )
        executor_rate = MODEL_INPUT_COST_PER_1M_USD.get(
            policy.default_executor_model,
            MODEL_INPUT_COST_PER_1M_USD[DEFAULT_FLASH_MODEL],
        )
        full_pro_loop_usd = (32_000 / 1_000_000.0) * advisor_rate
        hybrid_askpro_usd = (24_000 / 1_000_000.0) * executor_rate + (
            2_500 / 1_000_000.0
        ) * advisor_rate
        incremental_savings_usd = round(
            max(0.0, full_pro_loop_usd - hybrid_askpro_usd), 6
        )
        self.ledger.record_askpro_escalation(
            tenant_id=envelope.tenant.tenant_id,
            incremental_usd_saved=incremental_savings_usd,
        )
        advisor_guidance = (
            f"[{policy.advisor_model} Advisor Synthesis] Verified evidence digest "
            f"({len(cleaned_digest)} chars) for tenant={envelope.tenant.tenant_id}."
        )
        live_vertex_call = False
        if self._live_advisor_fn is not None:
            advisor_guidance = str(
                self._live_advisor_fn(
                    advisor_model=policy.advisor_model,
                    escalation_reason=escalation_reason,
                    compact_evidence_digest=cleaned_digest,
                    tenant_id=envelope.tenant.tenant_id,
                )
            )
            live_vertex_call = True
        else:
            from agents import platform_config
            from agents.shared_diagnostic_agent import (
                build_thinking_config,
                get_model_location,
            )

            if platform_config.is_live_mode():
                from google import genai
                from google.genai import types as genai_types

                advisor_location = get_model_location(policy.advisor_model)
                thinking_cfg = build_thinking_config(
                    model_name=policy.advisor_model,
                    thinking_level="MEDIUM",
                )
                gen_cfg_kwargs: dict[str, Any] = {
                    "system_instruction": (
                        "Provide a concise, tenant-isolated SRE root-cause advisor synthesis."
                    ),
                    "max_output_tokens": 2048,
                }
                if thinking_cfg is not None:
                    gen_cfg_kwargs["thinking_config"] = (
                        genai_types.ThinkingConfig(**thinking_cfg)
                    )
                client = genai.Client(
                    vertexai=True,
                    project=platform_config.resolve_project_id(),
                    location=advisor_location,
                )
                resp = client.models.generate_content(
                    model=policy.advisor_model,
                    contents=(
                        f"Escalation reason: {escalation_reason}\n"
                        f"Compact evidence digest:\n{cleaned_digest}"
                    ),
                    config=genai_types.GenerateContentConfig(**gen_cfg_kwargs),
                )
                raw_text = (getattr(resp, "text", None) or "").strip()
                if raw_text:
                    advisor_guidance = raw_text
                    live_vertex_call = True
        return {
            "status": "ASKPRO_ADVISOR_COMPLETED",
            "tenant_id": envelope.tenant.tenant_id,
            "trace_id": cleaned_trace_id,
            "executor_model": policy.default_executor_model,
            "advisor_model": policy.advisor_model,
            "consultation_index": used_count + 1,
            "max_consultations_per_turn": policy.max_advisor_consultations_per_turn,
            "escalation_reason": escalation_reason,
            "advisor_guidance": advisor_guidance,
            "live_vertex_call": live_vertex_call,
            "incremental_usd_saved_vs_full_pro_loop": incremental_savings_usd,
        }
