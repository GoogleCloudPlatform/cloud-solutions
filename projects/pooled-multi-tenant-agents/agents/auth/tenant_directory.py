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

"""Tenant directory registry, intra-tenant RBAC role scopes, and eviction target tracking."""

from __future__ import annotations

import re
import threading
import weakref
from typing import Any

from agents import platform_config
from agents.auth.envelope import SubscriptionTier
from agents.platform_config import (
    PLATFORM_SCOPES,
    RESERVED_TENANT_IDS,
    get_platform_config,
    resolve_project_id,
)


def _load_base_tenant_directory() -> dict[str, dict[str, Any]]:
    """Tenants come from the layered platform config (config/ + CYMBAL_ENV), not from code."""
    cfg = get_platform_config()
    entries = cfg.tenant_directory_entries(project_id=resolve_project_id())
    for meta in entries.values():
        meta["tier"] = SubscriptionTier(meta["tier"])
    return entries


_BASE_TENANT_DIRECTORY: dict[str, dict[str, Any]] = (
    _load_base_tenant_directory()
)

TENANT_DIRECTORY: dict[str, dict[str, Any]] = dict(_BASE_TENANT_DIRECTORY)

# Platform key for GLOBAL (non-tenant) memory. Resolved at the same moment and from the same
# project as the tenant keys above, so tenant and platform keys can never drift apart.
PLATFORM_GLOBAL_KEY_ID = "cymbal-platform-global"
PLATFORM_GLOBAL_KMS_KEY_NAME: str = get_platform_config().kms_key_name(
    PLATFORM_GLOBAL_KEY_ID, project_id=resolve_project_id()
)

# Platform capabilities granted by role, independent of tenant entitlements.
# `memory:tenant.write` = may write tenant-shared (TENANT / STRATEGY) memory (poisoning guard).
ROLE_PLATFORM_SCOPES: dict[str, tuple[str, ...]] = {
    "sre_admin": ("memory:tenant.write",),
}

# Intra-Tenant User RBAC Roles (Level 2: Individual User Role / AD Group inside a Tenant)
# Effective Session Scopes = Tenant Entitled Scopes (Level 1) ∩ User Role Scopes (Level 2)
USER_ROLE_ALLOWED_SCOPES: dict[str, frozenset[str]] = {
    "sre_admin": frozenset({"*"}),
    "compliance_officer": frozenset(
        {
            "2lo:cymbal.telemetry.read",
            "2lo:cymbal.runbooks.read",
            "3lo:google.drive.readonly",
            "agent:cymbal_shared_diagnostic_agent",
            "agent:finvault_regulatory_escalation_agent",
        }
    ),
    "read_only_analyst": frozenset(
        {
            "2lo:cymbal.telemetry.read",
            "2lo:cymbal.runbooks.read",
            "3lo:google.drive.readonly",
            "3lo:microsoft.sharepoint.readonly",
            "agent:cymbal_shared_diagnostic_agent",
        }
    ),
}


_TENANT_ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{2,62}")


def register_tenant(
    *,
    tenant_id: str,
    display_name: str,
    tier: SubscriptionTier = SubscriptionTier.STANDARD,
    iss: str = "https://accounts.google.com",
    org_unit: str = "pooled-saas-tenant",
    extra_scopes: tuple[str, ...] = (),
    secret_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Zero-touch O(1) control-plane onboarding of a new tenant into the Pooled runtime fleet."""
    if tenant_id in RESERVED_TENANT_IDS or not _TENANT_ID_PATTERN.fullmatch(
        tenant_id
    ):
        raise ValueError(f"Invalid or reserved tenant_id: {tenant_id!r}")
    if set(extra_scopes) & PLATFORM_SCOPES:
        raise ValueError(
            "Platform scopes are granted by role, not as tenant entitlements."
        )
    owned_elsewhere = {
        s
        for other, meta in TENANT_DIRECTORY.items()
        if other != tenant_id
        for s in meta.get("secret_ids", ())
    } & set(secret_ids)
    if owned_elsewhere:
        raise ValueError(
            f"secret_ids already owned by another tenant: {sorted(owned_elsewhere)}"
        )
    is_ent = tier == SubscriptionTier.ENTERPRISE
    active_config = get_platform_config()
    effective_limits = platform_config.resolve_effective_tier_limits(
        active_config, "enterprise" if is_ent else "standard"
    )
    base_scopes = tuple(active_config.default_scopes)
    combined_scopes = tuple(dict.fromkeys((*base_scopes, *extra_scopes)))
    meta = {
        "display_name": display_name,
        "tier": tier,
        "iss": iss,
        "org_unit": org_unit,
        "thinking_budget": effective_limits.thinking_budget,
        "rpm_limit": effective_limits.rpm_limit,
        "tpm_limit": effective_limits.tpm_limit,
        "max_turns_per_session": effective_limits.max_turns_per_session,
        "cmek_key_name": active_config.kms_key_name(
            f"{tenant_id}-cmek", project_id=resolve_project_id()
        ),
        "authorized_scopes": combined_scopes,
        "secret_ids": tuple(secret_ids),
        "external_mcp_audiences": (),
        "topology": {"pattern": "pool"},
    }
    from agents.workload_identity import clear_tenant_revoked

    clear_tenant_revoked(tenant_id)
    TENANT_DIRECTORY[tenant_id] = meta
    return meta


_TENANT_EVICTION_TARGETS: weakref.WeakSet[Any] = weakref.WeakSet()
_TENANT_EVICTION_LOCK = threading.Lock()


def register_tenant_eviction_target(target: Any) -> None:
    """Registers an in-process cache or vault instance for automatic tenant eviction on
    offboarding.
    """
    with _TENANT_EVICTION_LOCK:
        _TENANT_EVICTION_TARGETS.add(target)


def reset_dynamic_tenants() -> None:
    """Resets TENANT_DIRECTORY to the configured tenants, re-reading config (honors CYMBAL_ENV)."""
    from agents.registry import reset_dynamic_agents
    from agents.workload_identity import reset_control_plane_revocations
    from agents.workspace_plugins import _DEFAULT_WORKSPACE_PLUGIN_REGISTRY

    reset_control_plane_revocations()
    reset_dynamic_agents()
    if _DEFAULT_WORKSPACE_PLUGIN_REGISTRY is not None:
        _DEFAULT_WORKSPACE_PLUGIN_REGISTRY.reset_dynamic_manifests()
    reloaded = _load_base_tenant_directory()
    _BASE_TENANT_DIRECTORY.clear()
    _BASE_TENANT_DIRECTORY.update(reloaded)
    TENANT_DIRECTORY.clear()
    TENANT_DIRECTORY.update(_BASE_TENANT_DIRECTORY)
