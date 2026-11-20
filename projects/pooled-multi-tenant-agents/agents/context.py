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

"""Backward-compatible facade for multi-tenant auth, context envelopes, and QoS (`agents.auth`)."""

from __future__ import annotations

from typing import Any

from agents.auth import (
    _ACTIVE_TENANT_ENVELOPE,
    _BASE_TENANT_DIRECTORY,
    _DELEGATION_DEPTH_KEY,
    _STATE_CLAIM_BINDINGS,
    _TENANT_EVICTION_LOCK,
    _TENANT_EVICTION_TARGETS,
    _TENANT_ID_PATTERN,
    PLATFORM_GLOBAL_KEY_ID,
    PLATFORM_GLOBAL_KMS_KEY_NAME,
    PLATFORM_SCOPES,
    RESERVED_TENANT_IDS,
    ROLE_PLATFORM_SCOPES,
    TENANT_DIRECTORY,
    USER_ROLE_ALLOWED_SCOPES,
    AsymmetricDPoPProvider,
    AuthManager3LOVault,
    ContextEnvelope,
    Delegated3LOToken,
    EdgeAuthVerifier,
    MemoryScope,
    PrefixCacheSimulator,
    RedisBulkheadStore,
    RemoteBroker3LOVault,
    RequestContext,
    SecurityContext,
    SharedBulkheadStore,
    SubscriptionTier,
    TenantContext,
    TokenBucketBulkhead,
    _b64url_uint,
    _BucketState,
    _claim,
    _context_verifier,
    _delegation_tag,
    _load_base_tenant_directory,
    _normalize_state_value,
    averify_signed_adk_state,
    build_bulkhead_from_env,
    build_redis_client_from_env,
    get_active_envelope,
    get_default_3lo_vault,
    offboard_tenant,
    propagate_to_subagent,
    register_tenant,
    register_tenant_eviction_target,
    reset_dynamic_tenants,
    tenant_qualified_user_id,
    verify_signed_adk_state,
)
from agents.context_token import DEFAULT_MAX_DELEGATION_DEPTH


def __getattr__(name: str) -> Any:
    """Lazy re-export of `MemoryBankPartitioner` to avoid circular imports with `memory_crypto`."""
    if name == "MemoryBankPartitioner":
        from agents.memory_bank import MemoryBankPartitioner

        return MemoryBankPartitioner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_MAX_DELEGATION_DEPTH",
    "PLATFORM_GLOBAL_KEY_ID",
    "PLATFORM_GLOBAL_KMS_KEY_NAME",
    "PLATFORM_SCOPES",
    "RESERVED_TENANT_IDS",
    "ROLE_PLATFORM_SCOPES",
    "TENANT_DIRECTORY",
    "USER_ROLE_ALLOWED_SCOPES",
    "_ACTIVE_TENANT_ENVELOPE",
    "_BASE_TENANT_DIRECTORY",
    "_DELEGATION_DEPTH_KEY",
    "_STATE_CLAIM_BINDINGS",
    "_TENANT_EVICTION_LOCK",
    "_TENANT_EVICTION_TARGETS",
    "_TENANT_ID_PATTERN",
    "AsymmetricDPoPProvider",
    "AuthManager3LOVault",
    "ContextEnvelope",
    "Delegated3LOToken",
    "EdgeAuthVerifier",
    "MemoryScope",
    "PrefixCacheSimulator",
    "RedisBulkheadStore",
    "RemoteBroker3LOVault",
    "RequestContext",
    "SecurityContext",
    "SharedBulkheadStore",
    "SubscriptionTier",
    "TenantContext",
    "TokenBucketBulkhead",
    "_BucketState",
    "_b64url_uint",
    "_claim",
    "_context_verifier",
    "_delegation_tag",
    "_load_base_tenant_directory",
    "_normalize_state_value",
    "averify_signed_adk_state",
    "build_bulkhead_from_env",
    "build_redis_client_from_env",
    "get_active_envelope",
    "get_default_3lo_vault",
    "offboard_tenant",
    "propagate_to_subagent",
    "register_tenant",
    "register_tenant_eviction_target",
    "reset_dynamic_tenants",
    "tenant_qualified_user_id",
    "verify_signed_adk_state",
]
