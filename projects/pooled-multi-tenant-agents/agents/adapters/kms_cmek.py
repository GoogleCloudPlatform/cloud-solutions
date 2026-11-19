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

"""Live Cloud KMS per-tenant CMEK envelope verification and cache eviction (Hop 3)."""

from __future__ import annotations

import base64
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx
from agents.adapters._bridge_runtime import (
    DEFAULT_GCP_PROJECT,
    _adc_headers,
    _tenant_headers,
    _tenant_policy,
)
from agents.context import ContextEnvelope
from agents.memory_crypto import assert_platform_key
from agents.shared_diagnostic_agent import get_clean_project_id

# Positive Cloud KMS probe receipts are cached for up to 60s (`KMS_VERIFY_TTL_SECONDS`).
# Note on offboarding / key rotation: disabling a key directly in Cloud KMS can still report
# `verified: True` from this cache for up to 60s unless evicted via
# `evict_kms_verify_cache_for_tenant(tenant_id)` or `clear_kms_verify_cache()`.
KMS_VERIFY_TTL_SECONDS = 60.0
_KMS_VERIFY_CACHE: dict[tuple[str, str, str], tuple[dict[str, Any], float]] = {}
_KMS_VERIFY_LOCK = threading.Lock()


def clear_kms_verify_cache() -> None:
    """Clears all entries from the 60s Cloud KMS key-access verification cache."""
    with _KMS_VERIFY_LOCK:
        _KMS_VERIFY_CACHE.clear()


def evict_kms_verify_cache_for_tenant(tenant_id: str) -> int:
    """Evicts all cached Cloud KMS verification receipts for `tenant_id` during offboarding.

    Args:
        tenant_id: Tenant identifier whose cached KMS probe receipts must be purged.

    Returns:
        Number of cache entries removed.
    """
    with _KMS_VERIFY_LOCK:
        matching_keys = [
            cache_key
            for cache_key in _KMS_VERIFY_CACHE
            if cache_key[0] == tenant_id
        ]
        for cache_key in matching_keys:
            _KMS_VERIFY_CACHE.pop(cache_key, None)
        return len(matching_keys)


class LiveCloudKMSCMEKVerifier:
    """Hop 3 Per-Tenant Cloud KMS Cryptographic Envelope Verification (`cloudkms.googleapis.com`).

    When called with an `envelope`, the request runs as that tenant's service account
    (tenant-scoped credential) after a code-level check that the key and AAD belong to the
    envelope's tenant. Without an envelope it runs as the runtime identity and may use only the
    platform GLOBAL key.
    """

    def __init__(
        self,
        project_id: str = DEFAULT_GCP_PROJECT,
        verify_ttl_seconds: float = KMS_VERIFY_TTL_SECONDS,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initializes the Cloud KMS CMEK verifier.

        Args:
            project_id: Target GCP project ID hosting the Cloud KMS key rings.
            verify_ttl_seconds: TTL in seconds for cached positive probe receipts.
            clock_fn: Monotonic clock callable returning current timestamp in seconds.
        """
        self.project_id = get_clean_project_id(project_id)
        self._verify_ttl = verify_ttl_seconds
        self._clock = clock_fn

    @staticmethod
    def evict_tenant(tenant_id: str) -> int:
        """Purges cached KMS probe entries for `tenant_id` on tenant offboarding or key disable."""
        return evict_kms_verify_cache_for_tenant(tenant_id)

    def _assert_key_policy(
        self,
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        tenant_id: str,
    ) -> None:
        """Verifies synchronously that `envelope` and `tenant_id` are authorized for
        `kms_key_name`.
        """
        if envelope is None:
            assert_platform_key(kms_key_name)
            return
        if tenant_id != envelope.tenant.tenant_id:
            raise PermissionError(
                "E_TENANT_RESOURCE_SCOPE_VIOLATION: KMS AAD tenant does not match the caller."
            )
        _tenant_policy(self.project_id).assert_kms_key(
            envelope.tenant.tenant_id, kms_key_name
        )

    def verify_key_access(
        self,
        *,
        kms_key_name: str,
        tenant_id: str,
        envelope: ContextEnvelope | None = None,
    ) -> dict[str, Any]:
        """Verifies tenant Cloud KMS key access with a bounded 60s TTL cache.

        Runs `_assert_key_policy` synchronously before consulting `_KMS_VERIFY_CACHE`, and looks
        up the cache before minting a tenant SA token so cache hits avoid both IAM token minting
        and the Cloud KMS `:encrypt` probe RPC. Note: a key disabled directly in Cloud KMS can
        still return `verified: True` for up to `verify_ttl_seconds` (60s) unless cleared via
        `evict_tenant(tenant_id)` or `clear_kms_verify_cache()`.

        Args:
            kms_key_name: Full Cloud KMS cryptoKey resource name.
            tenant_id: Expected tenant owner identifier bound into AAD.
            envelope: Optional verified `ContextEnvelope` for tenant-scoped execution.

        Returns:
            Dictionary containing `kms_key_name`, `tenant_id`, `ciphertext_bytes`,
            `verified`, and `cache_hit`.

        Raises:
            PermissionError: If the tenant is not onboarded or does not own `kms_key_name`.
        """
        self._assert_key_policy(envelope, kms_key_name, tenant_id)
        principal_sub = (
            envelope.security.sub if envelope is not None else "_platform"
        )
        cache_key = (tenant_id, principal_sub, kms_key_name)
        now = float(self._clock())
        with _KMS_VERIFY_LOCK:
            cached = _KMS_VERIFY_CACHE.get(cache_key)
            if cached is not None and cached[1] > now:
                return {**cached[0], "cache_hit": True}

        probe_ciphertext = self.encrypt_for_tenant(
            kms_key_name=kms_key_name,
            tenant_id=tenant_id,
            plaintext=b"kms-access-probe",
            envelope=envelope,
        )
        receipt = {
            "kms_key_name": kms_key_name,
            "tenant_id": tenant_id,
            "ciphertext_bytes": len(probe_ciphertext),
            "verified": True,
            "cache_hit": False,
        }
        with _KMS_VERIFY_LOCK:
            if len(_KMS_VERIFY_CACHE) >= 1024:
                oldest_key = next(iter(_KMS_VERIFY_CACHE))
                _KMS_VERIFY_CACHE.pop(oldest_key, None)
            _KMS_VERIFY_CACHE[cache_key] = (receipt, now + self._verify_ttl)
        return receipt

    def _headers(
        self,
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        tenant_id: str,
    ) -> dict[str, str]:
        self._assert_key_policy(envelope, kms_key_name, tenant_id)
        if envelope is None:
            headers = _adc_headers(self.project_id)
        else:
            headers = _tenant_headers(envelope, self.project_id)
        return {**headers, "Content-Type": "application/json"}

    def encrypt_for_tenant(
        self,
        *,
        kms_key_name: str,
        tenant_id: str,
        plaintext: bytes,
        envelope: ContextEnvelope | None = None,
        aad: bytes | None = None,
    ) -> bytes:
        headers = self._headers(envelope, kms_key_name, tenant_id)
        aad_bytes = tenant_id.encode("utf-8") if aad is None else aad
        url = f"https://cloudkms.googleapis.com/v1/{kms_key_name}:encrypt"
        body = {
            "plaintext": base64.b64encode(plaintext).decode("ascii"),
            "additionalAuthenticatedData": base64.b64encode(aad_bytes).decode(
                "ascii"
            ),
        }
        response = httpx.post(url, headers=headers, json=body, timeout=15.0)
        if response.status_code in (401, 403):
            raise PermissionError(
                f"E_KMS_IAM_DENIED: Cloud KMS refused encrypt (HTTP {response.status_code})."
            )
        response.raise_for_status()  # 5xx / other errors stay availability errors, not denials
        return base64.b64decode(response.json()["ciphertext"])

    def decrypt_for_tenant(
        self,
        *,
        kms_key_name: str,
        tenant_id: str,
        ciphertext: bytes,
        envelope: ContextEnvelope | None = None,
        aad: bytes | None = None,
    ) -> bytes:
        headers = self._headers(envelope, kms_key_name, tenant_id)
        aad_bytes = tenant_id.encode("utf-8") if aad is None else aad
        url = f"https://cloudkms.googleapis.com/v1/{kms_key_name}:decrypt"
        body = {
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "additionalAuthenticatedData": base64.b64encode(aad_bytes).decode(
                "ascii"
            ),
        }
        resp = httpx.post(url, headers=headers, json=body, timeout=15.0)
        # 400 = wrong key or AAD for this ciphertext; 401/403 = IAM. Both are isolation denials.
        if resp.status_code in (400, 401, 403):
            raise PermissionError(
                f"E_CLOUD_KMS_CMEK_DECRYPT_DENIED: Cloud KMS rejected the decrypt "
                f"(HTTP {resp.status_code})."
            )
        resp.raise_for_status()  # 5xx stays an availability error
        return base64.b64decode(resp.json()["plaintext"])
