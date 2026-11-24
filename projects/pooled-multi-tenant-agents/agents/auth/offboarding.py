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

"""Immediate single-instance tenant offboarding across directory, KMS/DEK caches, and bulkheads."""

from __future__ import annotations

from typing import Any

from agents.auth.tenant_directory import (
    _TENANT_EVICTION_LOCK,
    _TENANT_EVICTION_TARGETS,
    TENANT_DIRECTORY,
)
from agents.auth.vault_and_bulkhead import (
    AuthManager3LOVault,
    TokenBucketBulkhead,
)
from agents.platform_config import RESERVED_TENANT_IDS


def offboard_tenant(
    tenant_id: str,
    *,
    bulkhead: TokenBucketBulkhead | None = None,
    memory_crypto: Any | None = None,
    credential_broker: Any | None = None,
    auth_vault: AuthManager3LOVault | None = None,
) -> dict[str, Any]:
    """Revokes a tenant across directory, DEK cache, SA credential cache, 3LO vault, and bulkhead.

    Closes the 5-minute DEK cache, 55-minute SA token cache, 60-second Cloud KMS verify cache,
    3LO token vault, and rate-limit bulkhead windows immediately (`< 1ms`) on the current gateway
    instance upon tenant offboarding or emergency suspension.

    Note (Single-Instance Scope): This helper mutates in-process `TENANT_DIRECTORY` and registered
    instance caches. In a multi-replica deployment, pair this with a shared control-plane
    revocation flag (Redis/Firestore) and disable the tenant's Cloud KMS CMEK key version or IAM
    service account.

    Args:
        tenant_id: Identifier of the tenant to offboard.
        bulkhead: Optional `TokenBucketBulkhead` instance to purge alongside registered bulkheads.
        memory_crypto: Optional `MemoryCrypto` instance to purge alongside registered instances.
        credential_broker: Optional `TenantCredentialBroker` to purge alongside registered brokers.
        auth_vault: Optional `AuthManager3LOVault` to purge alongside registered 3LO vaults.

    Returns:
        Summary dictionary of purged control-plane and runtime cache entries.

    Raises:
        ValueError: If `tenant_id` is empty or in `RESERVED_TENANT_IDS`.
    """
    from agents.gcp_live_bridge import evict_kms_verify_cache_for_tenant
    from agents.memory_crypto import MemoryCrypto, get_memory_crypto
    from agents.registry import evict_dynamic_agents_for_tenant
    from agents.tenant_credentials import (
        TenantCredentialBroker,
        evict_tenant_credentials,
    )
    from agents.workload_identity import mark_tenant_revoked

    if (
        not tenant_id
        or not isinstance(tenant_id, str)
        or tenant_id in RESERVED_TENANT_IDS
    ):
        raise ValueError(
            f"Cannot offboard invalid or reserved tenant_id: {tenant_id!r}"
        )

    mark_tenant_revoked(tenant_id)
    evict_dynamic_agents_for_tenant(tenant_id)
    removed_from_directory = TENANT_DIRECTORY.pop(tenant_id, None) is not None

    with _TENANT_EVICTION_LOCK:
        registered_targets = list(_TENANT_EVICTION_TARGETS)

    default_crypto = get_memory_crypto()
    crypto_targets: list[Any] = [default_crypto]
    if memory_crypto is not None and memory_crypto not in crypto_targets:
        crypto_targets.append(memory_crypto)
    for target in registered_targets:
        if isinstance(target, MemoryCrypto) and target not in crypto_targets:
            crypto_targets.append(target)
    evicted_deks = sum(
        int(crypto_obj.evict_tenant(tenant_id)) for crypto_obj in crypto_targets
    )

    evicted_cred = evict_tenant_credentials(tenant_id)
    broker_targets: list[Any] = []
    if credential_broker is not None:
        broker_targets.append(credential_broker)
    for target in registered_targets:
        if (
            isinstance(target, TenantCredentialBroker)
            and target not in broker_targets
        ):
            broker_targets.append(target)
    for broker_obj in broker_targets:
        evicted_cred = bool(broker_obj.evict_tenant(tenant_id)) or evicted_cred

    evicted_kms_verify = evict_kms_verify_cache_for_tenant(tenant_id)

    bulkhead_targets: list[TokenBucketBulkhead] = []
    if bulkhead is not None:
        bulkhead_targets.append(bulkhead)
    for target in registered_targets:
        if (
            isinstance(target, TokenBucketBulkhead)
            and target not in bulkhead_targets
        ):
            bulkhead_targets.append(target)
    evicted_bucket = False
    for bulkhead_obj in bulkhead_targets:
        evicted_bucket = (
            bool(bulkhead_obj.evict_tenant(tenant_id)) or evicted_bucket
        )

    vault_targets: list[AuthManager3LOVault] = []
    if auth_vault is not None:
        vault_targets.append(auth_vault)
    for target in registered_targets:
        if (
            isinstance(target, AuthManager3LOVault)
            and target not in vault_targets
        ):
            vault_targets.append(target)
    evicted_3lo = sum(
        int(vault_obj.evict_tenant(tenant_id)) for vault_obj in vault_targets
    )

    handled_targets = {
        id(item)
        for item in (
            *crypto_targets,
            *broker_targets,
            *bulkhead_targets,
            *vault_targets,
        )
    }
    for extra_target in registered_targets:
        if id(extra_target) not in handled_targets and hasattr(
            extra_target, "evict_tenant"
        ):
            extra_target.evict_tenant(tenant_id)

    return {
        "tenant_id": tenant_id,
        "removed_from_directory": removed_from_directory,
        "evicted_dek_entries": evicted_deks,
        "evicted_sa_credential": evicted_cred,
        "evicted_kms_verify_entries": evicted_kms_verify,
        "evicted_bulkhead_bucket": evicted_bucket,
        "evicted_3lo_tokens": evicted_3lo,
    }
