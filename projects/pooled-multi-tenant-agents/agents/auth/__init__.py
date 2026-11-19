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

"""Cryptographic identity, tenant directory, OBO/DPoP verifier, 3LO vault, and QoS bulkheads."""

from __future__ import annotations

from typing import Any

from agents.auth.dpop import AsymmetricDPoPProvider, _b64url_uint
from agents.auth.edge_verifier import (
    _STATE_CLAIM_BINDINGS,
    EdgeAuthVerifier,
    _claim,
    _context_verifier,
    _delegation_tag,
    _normalize_state_value,
    averify_signed_adk_state,
    get_active_envelope,
    propagate_to_subagent,
    verify_signed_adk_state,
)
from agents.auth.envelope import (
    _ACTIVE_TENANT_ENVELOPE,
    _DELEGATION_DEPTH_KEY,
    ContextEnvelope,
    MemoryScope,
    RequestContext,
    SecurityContext,
    SubscriptionTier,
    TenantContext,
    tenant_qualified_user_id,
)
from agents.auth.offboarding import offboard_tenant
from agents.auth.tenant_directory import (
    _BASE_TENANT_DIRECTORY,
    _TENANT_EVICTION_LOCK,
    _TENANT_EVICTION_TARGETS,
    _TENANT_ID_PATTERN,
    PLATFORM_GLOBAL_KEY_ID,
    PLATFORM_GLOBAL_KMS_KEY_NAME,
    ROLE_PLATFORM_SCOPES,
    TENANT_DIRECTORY,
    USER_ROLE_ALLOWED_SCOPES,
    _load_base_tenant_directory,
    register_tenant,
    register_tenant_eviction_target,
    reset_dynamic_tenants,
)
from agents.auth.vault_and_bulkhead import (
    AuthManager3LOVault,
    Delegated3LOToken,
    PrefixCacheSimulator,
    RedisBulkheadStore,
    RemoteBroker3LOVault,
    SharedBulkheadStore,
    TokenBucketBulkhead,
    _BucketState,
    build_bulkhead_from_env,
    build_redis_client_from_env,
    get_default_3lo_vault,
)
from agents.platform_config import PLATFORM_SCOPES, RESERVED_TENANT_IDS


def __getattr__(name: str) -> Any:
    """Lazy re-export of `MemoryBankPartitioner` to avoid circular imports with `memory_crypto`."""
    if name == "MemoryBankPartitioner":
        from agents.memory_bank import MemoryBankPartitioner

        return MemoryBankPartitioner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
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
