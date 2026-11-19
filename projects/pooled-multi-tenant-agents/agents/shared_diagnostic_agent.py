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

# pylint: disable=import-outside-toplevel,inconsistent-quotes,line-too-long

"""Cymbal SaaS Pooled Shared Diagnostic Agent (ADK 2.0).

Serves both Tenant Alpha (FinVault Bank — Enterprise Tier) and Tenant Beta (RetailStream Corp —
Standard Tier) on a single shared agent runtime in Gemini fleet.
- Uses Gemini Prompt Prefix Context Caching (`ContextCacheConfig`) for up to 90% COGS savings
- Validates cache prefix invariance (`compute_shared_prefix_cache_key`) so tenant-specific data
  or private tool schemas never poison the shared global prompt cache (Edge Case #4)
- Dynamically prunes unentitled 3LO tools per tenant in `before_agent_callback`
- Enforces 8,000 thinking-token budget for FinVault Bank and 4,000 cap for RetailStream Corp
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any

from agents.context import TENANT_DIRECTORY
from agents.interceptors import enforce_tenant_isolation_interceptor
from agents.kms_rest import configure_client_certificate_env
from agents.platform_config import get_platform_config
from agents.registry import TOOL_REGISTRY
from agents.skill_loader import load_shared_baseline_skills_text
from mcp_server import server as mcp_tools

# Prevent corporate workstation certificate collision with sandbox sandbox locally, while preserving
# workload SPIFFE mTLS on Cloud Run Agent Identity (--identity-certificate).
configure_client_certificate_env()


def get_clean_project_id(raw_project_id: str | None = None) -> str:
    """Resolves the GCP project from arg > GOOGLE_CLOUD_PROJECT > environment config.

    No hard-coded project fallback: in live mode an unset/placeholder project fails closed
    (see `agents.platform_config.resolve_project_id`).
    """
    from agents.platform_config import resolve_project_id

    return resolve_project_id(raw_project_id)


DEFAULT_SHARED_DIAGNOSTIC_MODEL = (
    get_platform_config().models.default_shared_model
)
DEFAULT_FLASH_EXECUTOR_MODEL = (
    get_platform_config().models.default_executor_model
)
DEFAULT_FRONTIER_ADVISOR_MODEL = (
    get_platform_config().models.default_frontier_model
)
FALLBACK_FRONTIER_MODEL = get_platform_config().models.fallback_frontier_model
FALLBACK_FLASH_MODEL = get_platform_config().models.fallback_fast_model
MIN_CONTEXT_CACHE_TOKENS_GEMINI_3_4 = 4096
MIN_CONTEXT_CACHE_TOKENS_GEMINI_2 = 2048
DEFAULT_CONTEXT_CACHE_TTL_SECONDS = 3600


def get_model_location(model_name: str) -> str:
    """Resolves `global` endpoint for Gemini 3.X and Gemini 4 models vs regional for legacy 2.5."""
    lowered = model_name.lower()
    if "gemini-3" in lowered or "gemini-4" in lowered:
        return "global"
    return os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")


def min_cacheable_tokens(model_name: str) -> int:
    """Returns documented minimum token threshold for prefix context caching on `model_name`."""
    lowered = model_name.lower()
    if "gemini-3" in lowered or "gemini-4" in lowered:
        return MIN_CONTEXT_CACHE_TOKENS_GEMINI_3_4
    return MIN_CONTEXT_CACHE_TOKENS_GEMINI_2


def supports_explicit_context_caching(model_name: str) -> bool:
    """Returns whether `model_name` supports explicit `CachedContent` objects vs implicit-only.

    Gemini 4 models (`gemini-4-hydrogen`, `gemini-4-carbon`, `gemini-4-argon`) use automatic
    4,096-token durable implicit caching by default and do not use explicit `CachedContent`.
    """
    lowered = model_name.lower()
    if "gemini-4" in lowered:
        return False
    return "gemini-2" in lowered or "gemini-3" in lowered


def build_thinking_config(
    *,
    model_name: str,
    thinking_budget: int | None = None,
    thinking_level: str | None = None,
) -> dict[str, Any] | None:
    """Enforces mutual exclusivity between `thinking_level` (Gemini 3/4) and `thinking_budget`."""
    lowered = model_name.lower()
    is_hydrogen = "gemini-4-hydrogen" in lowered
    if "gemini-3" in lowered or "gemini-4" in lowered:
        if thinking_level is not None:
            lvl = thinking_level.upper()
            if (
                "3.7" in lowered or "3.8" in lowered or "gemini-4" in lowered
            ) and lvl in (
                "MINIMAL",
                "THINKINGLEVEL.MINIMAL",
            ):
                lvl = "LOW"
            if lvl in ("XHIGH", "THINKINGLEVEL.XHIGH") and not is_hydrogen:
                lvl = "HIGH"
            return {"thinking_level": lvl}
        if thinking_budget is not None:
            budget_val = int(thinking_budget)
            if budget_val <= 2048:
                return {"thinking_level": "LOW"}
            if budget_val <= 4096:
                return {"thinking_level": "MEDIUM"}
            if budget_val > 12000 and is_hydrogen:
                return {"thinking_level": "XHIGH"}
            return {"thinking_level": "HIGH"}
        return {"thinking_level": "LOW"}

    budget = 4000 if thinking_budget is None else int(thinking_budget)
    if "pro" in lowered and budget == 0:
        return None
    return {"thinking_budget": budget}


_CORE_SYSTEM_PROMPT_HEADER = (
    "You are the Cymbal SaaS Shared Diagnostic Agent.\n"
    "You correlate production telemetry, inspect incident runbooks, and propose "
    "remediation steps.\n"
    "CRITICAL MULTI-TENANT GOVERNANCE RULES:\n"
    "1. You operate strictly within the authenticated tenant scope bound in the ADK session state "
    "(`temp:tenant_id`).\n"
    "2. Never access, infer, or reference telemetry, incidents, or runbooks belonging to any "
    "other tenant.\n"
    "3. Use only the dynamically entitled MCP tools present in your active toolset.\n"
)
_BASELINE_PLUGIN_SKILLS_TEXT = load_shared_baseline_skills_text()
SHARED_SYSTEM_PROMPT_PREFIX = (
    f"{_CORE_SYSTEM_PROMPT_HEADER}\n{_BASELINE_PLUGIN_SKILLS_TEXT}\n"
    if _BASELINE_PLUGIN_SKILLS_TEXT
    else _CORE_SYSTEM_PROMPT_HEADER
)

SHARED_2LO_BASE_TOOLS: tuple[str, ...] = (
    "query_telemetry_rls",
    "read_runbook",
)


def compute_shared_prefix_cache_key(
    *,
    system_prefix: str = SHARED_SYSTEM_PROMPT_PREFIX,
    cached_tool_names: tuple[str, ...] = SHARED_2LO_BASE_TOOLS,
) -> str:
    """Edge Case #4: Validates and computes the invariant global prompt prefix cache digest.

    Raises `PermissionError("E_CACHE_POISONING_DETECTED")` if:
    1. Concrete tenant identifiers (`tenant-finvault-alpha`, `tenant-retailstream-beta`) or
       tenant-specific secrets are interpolated into the shared global prefix.
    2. Dynamic ADK state template placeholders (`{temp:...}` or `{user:...}`) are embedded in the
       static prefix, which would mutate early prefix tokens per tenant and bust KV caching.
    3. A tenant-exclusive 3LO or private tool (`escalate_regulatory_filing`, `create_jira_incident`,
       `create_servicenow_incident`) is injected into the shared global prefix cache.
    """
    lowered = system_prefix.lower()
    if "{temp:" in lowered or "{user:" in lowered:
        raise PermissionError(
            "E_CACHE_POISONING_DETECTED: Dynamic ADK template placeholder ('{temp:...}' or "
            "'{user:...}') found in shared global prompt prefix cache; dynamic tenant state "
            "must be placed in the uncached turn suffix."
        )

    for tenant_id in TENANT_DIRECTORY:
        if tenant_id.lower() in lowered:
            raise PermissionError(
                f"E_CACHE_POISONING_DETECTED: Concrete tenant_id '{tenant_id}' found in shared "
                "global prompt prefix cache."
            )

    for tool_name in cached_tool_names:
        meta = TOOL_REGISTRY.get(tool_name)
        is_shared = meta is not None and (
            "*" in meta.allowed_tenants or len(meta.allowed_tenants) >= 2
        )
        if meta is None or meta.auth_mode != "2LO" or not is_shared:
            raise PermissionError(
                f"E_CACHE_POISONING_DETECTED: Tenant-exclusive or 3LO tool '{tool_name}' "
                "cannot be placed in the shared global prompt prefix cache."
            )

    canonical = f"{system_prefix.strip()}|tools={','.join(sorted(cached_tool_names))}".encode()
    return hashlib.sha256(canonical).hexdigest()


def build_cache_aligned_turn_payload(
    *,
    tenant_id: str,
    user_prompt: str,
    dynamic_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Constructs a cache-aligned LLM request separating static cached prefix from dynamic suffix.

    Guarantees that the cached prefix (`SHARED_SYSTEM_PROMPT_PREFIX` + `SHARED_2LO_BASE_TOOLS`)
    is 100% byte-identical across all tenants while binding `tenant_id` and per-turn context
    strictly in the uncached suffix.
    """
    if tenant_id not in TENANT_DIRECTORY:
        raise PermissionError(
            f"E_UNKNOWN_TENANT: Unknown tenant_id '{tenant_id}'."
        )
    prefix_digest = compute_shared_prefix_cache_key()
    return {
        "cached_static_prefix": {
            "system_instruction": SHARED_SYSTEM_PROMPT_PREFIX,
            "shared_2lo_tools": list(SHARED_2LO_BASE_TOOLS),
            "cache_key_sha256": prefix_digest,
        },
        "uncached_dynamic_suffix": {
            "authenticated_tenant_id": tenant_id,
            "dynamic_context": dict(dynamic_context or {}),
            "user_prompt": user_prompt,
        },
    }


def compute_per_model_prefix_cache_key(
    *,
    model_name: str,
    system_prefix: str = SHARED_SYSTEM_PROMPT_PREFIX,
    cached_tool_names: tuple[str, ...] = SHARED_2LO_BASE_TOOLS,
) -> str:
    """Computes a model-scoped prefix cache digest so distinct models never share one cache key."""
    clean_model = model_name.strip().lower()
    if not clean_model:
        raise ValueError(
            "model_name must be non-empty for per-model context cache isolation."
        )
    base_digest = compute_shared_prefix_cache_key(
        system_prefix=system_prefix,
        cached_tool_names=cached_tool_names,
    )
    return hashlib.sha256(
        f"model={clean_model}|prefix={base_digest}".encode()
    ).hexdigest()


def build_per_model_context_cache_config(
    *,
    model_name: str,
    ttl_seconds: int | None = None,
    cache_intervals: int = 10,
    system_prefix: str = SHARED_SYSTEM_PROMPT_PREFIX,
    cached_tool_names: tuple[str, ...] = SHARED_2LO_BASE_TOOLS,
) -> dict[str, Any]:
    """Builds a validated ADK `ContextCacheConfig` + metadata bound to a single `model_name`.

    Enforces:
    1. Zero tenant data or 3LO tool schemas in cached prefix (`compute_shared_prefix_cache_key`).
    2. Strict per-model cache key isolation (`compute_per_model_prefix_cache_key`).
    3. Documented minimum token floor (`4,096` for Gemini 3/4, `2,048` for Gemini 2) and >=60s TTL.
    """
    resolved_ttl = int(
        ttl_seconds
        if ttl_seconds is not None
        else os.getenv(
            "CONTEXT_CACHE_TTL_SECONDS", str(DEFAULT_CONTEXT_CACHE_TTL_SECONDS)
        )
    )
    if resolved_ttl < 60:
        raise ValueError(
            "E_CONTEXT_CACHE_TTL: explicit context cache ttl_seconds must be >= 60."
        )
    required_min_tokens = min_cacheable_tokens(model_name)
    per_model_key = compute_per_model_prefix_cache_key(
        model_name=model_name,
        system_prefix=system_prefix,
        cached_tool_names=cached_tool_names,
    )
    shared_prefix_key = compute_shared_prefix_cache_key(
        system_prefix=system_prefix,
        cached_tool_names=cached_tool_names,
    )
    estimated_prefix_tokens = max(1, len(system_prefix.encode("utf-8")) // 4)
    explicit_supported = supports_explicit_context_caching(model_name)
    adk_cache_cfg: Any = None
    try:
        from google.adk.agents.context_cache_config import (
            ContextCacheConfig,  # type: ignore[import-untyped]
        )

        adk_cache_cfg = ContextCacheConfig(
            cache_intervals=cache_intervals,
            ttl_seconds=resolved_ttl,
            min_tokens=required_min_tokens,
        )
    except ImportError:
        adk_cache_cfg = None

    return {
        "enabled": True,
        "model_name": model_name,
        "caching_mode": (
            "explicit_and_implicit"
            if explicit_supported
            else "implicit_durable"
        ),
        "supports_explicit_caching": explicit_supported,
        "ttl_seconds": resolved_ttl,
        "min_tokens": required_min_tokens,
        "estimated_prefix_tokens": estimated_prefix_tokens,
        "meets_min_token_floor": estimated_prefix_tokens >= required_min_tokens,
        "shared_prefix_sha256": shared_prefix_key,
        "cache_key_sha256": per_model_key,
        "adk_context_cache_config": adk_cache_cfg,
    }


@dataclass(frozen=True)
class SharedDiagnosticAgentSpec:
    """Declarative ADK 2.0 specification for the Pooled Shared Diagnostic Agent."""

    name: str
    model: str
    instruction: str
    tools: list[Any]
    before_agent_callback: Any
    context_cache_config: dict[str, Any]
    thinking_config: dict[str, Any] | None = None


def build_shared_diagnostic_agent(
    *,
    model_name: str | None = None,
    thinking_budget: int | None = None,
) -> Any:
    """Builds the ADK 2.0 `Agent` with `GenerateContentConfig(thinking_config=...)`."""
    all_candidate_tools = [
        mcp_tools.query_telemetry_rls,
        mcp_tools.read_runbook,
        mcp_tools.execute_diagnostic_sandbox,
        mcp_tools.create_jira_incident,
        mcp_tools.send_gmail_brief,
        mcp_tools.create_servicenow_incident,
        mcp_tools.read_sharepoint_runbook,
    ]
    resolved_model = (
        model_name
        if model_name is not None
        else os.getenv(
            "SHARED_DIAGNOSTIC_MODEL", DEFAULT_SHARED_DIAGNOSTIC_MODEL
        )
    )
    thinking_cfg = build_thinking_config(
        model_name=resolved_model,
        thinking_budget=thinking_budget,
    )
    per_model_cache = build_per_model_context_cache_config(
        model_name=resolved_model
    )
    cache_cfg = {
        k: v
        for k, v in per_model_cache.items()
        if k != "adk_context_cache_config"
    }
    try:
        from google.adk.agents import Agent  # type: ignore[import-untyped]
        from google.genai import types as genai_types

        gen_cfg = (
            genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(**thinking_cfg)
            )
            if thinking_cfg is not None
            else None
        )
        return Agent(
            name="cymbal_shared_diagnostic_agent",
            model=resolved_model,
            static_instruction=SHARED_SYSTEM_PROMPT_PREFIX,
            instruction="Operate strictly within the verified tenant, role, and tool scope.",
            tools=all_candidate_tools,
            before_agent_callback=enforce_tenant_isolation_interceptor,
            generate_content_config=gen_cfg,
        )
    except (ImportError, TypeError, ValueError, AttributeError):
        return SharedDiagnosticAgentSpec(
            name="cymbal_shared_diagnostic_agent",
            model=resolved_model,
            instruction=SHARED_SYSTEM_PROMPT_PREFIX,
            tools=all_candidate_tools,
            before_agent_callback=enforce_tenant_isolation_interceptor,
            context_cache_config=cache_cfg,
            thinking_config=thinking_cfg,
        )


def build_shared_diagnostic_app(
    *,
    model_name: str | None = None,
    thinking_budget: int | None = None,
) -> Any:
    """Builds the ADK 2.0 `App` wiring `ContextCacheConfig` onto the shared diagnostic agent."""
    resolved_model = (
        model_name
        if model_name is not None
        else os.getenv(
            "SHARED_DIAGNOSTIC_MODEL", DEFAULT_SHARED_DIAGNOSTIC_MODEL
        )
    )
    agent = build_shared_diagnostic_agent(
        model_name=resolved_model,
        thinking_budget=thinking_budget,
    )
    per_model_cache = build_per_model_context_cache_config(
        model_name=resolved_model
    )
    adk_cache_cfg = per_model_cache["adk_context_cache_config"]
    try:
        from google.adk.apps import App  # type: ignore[import-untyped]

        if adk_cache_cfg is not None and not isinstance(
            agent, SharedDiagnosticAgentSpec
        ):
            return App(
                name="cymbal_pooled_app",
                root_agent=agent,
                context_cache_config=adk_cache_cfg,
            )
    except (ImportError, TypeError, ValueError):
        pass
    return agent


shared_diagnostic_agent = build_shared_diagnostic_agent()
