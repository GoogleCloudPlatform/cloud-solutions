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
# pylint: disable=missing-class-docstring

"""Memory envelope encryption and memory access rules (data-plane isolation).

Why this exists: memory used to be encrypted with a key *derived* from the KMS key name
(`sha256("cymbal-cmek-dek-v1:" + key_name)`). The key name is not secret, so anyone who could read
a stored record (for example a project Viewer reading Firestore) could decrypt it, and Cloud KMS
was never involved.

Model (format `v2`):

1. **A random 256-bit data key per record** encrypts the payload with AES-256-GCM.
2. **The data key is wrapped by Cloud KMS** with the tenant's key, **as the tenant's service
   account** (tenant-scoped credential from the verified envelope). GLOBAL (platform) memory uses
   the platform key and holds no tenant data.
3. **AAD binds the record to its owner and place**: canonical JSON of
   `[format, tenant, user, scope, key]`, computed from the *caller's* identity. A moved, relabelled,
   or foreign-user record fails authentication.
4. **No derivable key material is stored.** Legacy `v1` records are refused.

Scope and namespace are always taken from the parsed key, never from the stored record.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

from agents.context import (
    PLATFORM_GLOBAL_KEY_ID,
    PLATFORM_GLOBAL_KMS_KEY_NAME,
    RESERVED_TENANT_IDS,
    ContextEnvelope,
    MemoryScope,
    tenant_qualified_user_id,
)
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT_V2 = "v2"
TENANT_MEMORY_WRITE_SCOPE = "memory:tenant.write"
USER_SCOPES = frozenset({MemoryScope.USER, MemoryScope.SESSION})
TENANT_SHARED_SCOPES = frozenset({MemoryScope.TENANT, MemoryScope.STRATEGY})
GLOBAL_NAMESPACE = "global"
# Unwrapped data keys are cached briefly to keep KMS off the hot path. Disabling a tenant's KMS key
# therefore takes effect for new reads within this window (documented crypto-shred latency).
DEK_CACHE_TTL_SECONDS = 60.0
DEK_CACHE_MAX_ENTRIES = 4096

__all__ = [
    "PLATFORM_GLOBAL_KEY_ID",
    "LegacyMemoryFormatError",
    "MemoryAccessDenied",
    "MemoryCrypto",
    "OperatorPrincipal",
    "SealedRecord",
    "tenant_qualified_user_id",
]


class MemoryAccessDenied(PermissionError):
    """A memory read or write is not allowed for the caller (no foreign identifiers included)."""


class LegacyMemoryFormatError(PermissionError):
    """A stored record uses the retired derived-key format and is refused."""


# ---------------------------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------------------------


def user_partition(tenant_id: str, sub: str) -> str:
    """Opaque per-user partition; keeps raw subjects (emails) out of keys and document IDs.

    64 bits of SHA-256 are enough here: a collision would still fail AES-GCM authentication,
    because the AAD carries the caller's own partition.
    """
    if not sub or not sub.strip():
        raise ValueError("An empty subject cannot form a user partition.")
    return "u-" + hashlib.sha256(f"{tenant_id}:{sub}".encode()).hexdigest()[:16]


def _segment(value: str, name: str) -> str:
    if not value or "/" in value or "\x00" in value:
        raise ValueError(f"Invalid {name} for a memory key segment.")
    return value


def _tenant_segment(tenant_id: str) -> str:
    _segment(tenant_id, "tenant_id")
    if ":" in tenant_id or tenant_id in RESERVED_TENANT_IDS:
        raise ValueError("Invalid or reserved tenant_id for a memory key.")
    return tenant_id


def build_memory_key(
    *, tenant_id: str, sub: str, scope: MemoryScope, session_id: str, actor: str
) -> str:
    """Composite memory key.

    - GLOBAL:            `global/global/{actor}`
    - TENANT / STRATEGY: `{tenant}/_tenant/{scope}/{actor}`
    - USER:              `{tenant}/{user}/user/_/{actor}`          (persists across sessions)
    - SESSION:           `{tenant}/{user}/session/{session}/{actor}`
    """
    actor = _segment(actor, "actor")
    if scope == MemoryScope.GLOBAL:
        return f"{GLOBAL_NAMESPACE}/{MemoryScope.GLOBAL}/{actor}"
    tenant_id = _tenant_segment(tenant_id)
    if scope == MemoryScope.USER:
        return f"{tenant_id}/{user_partition(tenant_id, sub)}/{scope}/_/{actor}"
    if scope == MemoryScope.SESSION:
        session = _segment(session_id, "session_id")
        return f"{tenant_id}/{user_partition(tenant_id, sub)}/{scope}/{session}/{actor}"
    if scope in TENANT_SHARED_SCOPES:
        return f"{tenant_id}/_tenant/{scope}/{actor}"
    raise ValueError("Unknown memory scope.")


def parse_memory_key(key: str) -> dict[str, str]:
    """Strict inverse of `build_memory_key`. Shape and scope must agree; anything else is denied."""
    denied = MemoryAccessDenied(
        "403 Forbidden: Memory access denied (malformed key)."
    )
    parts = key.split("/")
    if parts and parts[0] == GLOBAL_NAMESPACE:
        if len(parts) == 3 and parts[1] == MemoryScope.GLOBAL and parts[2]:
            return {
                "kind": "global",
                "tenant_id": "",
                "user": "",
                "scope": MemoryScope.GLOBAL,
            }
        raise denied
    if any(not p for p in parts):
        raise denied
    if (
        len(parts) == 4
        and parts[1] == "_tenant"
        and parts[2] in TENANT_SHARED_SCOPES
    ):
        return {
            "kind": "tenant",
            "tenant_id": parts[0],
            "user": "",
            "scope": parts[2],
        }
    if (
        len(parts) == 5
        and parts[1].startswith("u-")
        and parts[2] in USER_SCOPES
    ):
        if parts[2] == MemoryScope.USER and parts[3] != "_":
            raise denied
        return {
            "kind": "user",
            "tenant_id": parts[0],
            "user": parts[1],
            "scope": parts[2],
        }
    raise denied


def record_aad(*, tenant_id: str, user: str, scope: str, key: str) -> bytes:
    """Canonical, unambiguous AAD encoding (JSON array; no delimiter collisions).

    This is the v2 encoding as first released; no record with an older v2 AAD exists outside
    pre-release sandbox data, so the format tag is unchanged.
    """
    return json.dumps(
        [FORMAT_V2, tenant_id, user, scope, key], separators=(",", ":")
    ).encode()


def caller_aad(envelope: ContextEnvelope | None, key: str) -> bytes:
    """AAD from the key's parsed shape and the *caller's* identity (never from stored fields)."""
    meta = parse_memory_key(key)
    if meta["kind"] == "global":
        return record_aad(
            tenant_id=GLOBAL_NAMESPACE, user="", scope=meta["scope"], key=key
        )
    if envelope is None:
        raise MemoryAccessDenied(
            "403 Forbidden: Tenant memory requires a verified caller."
        )
    tenant_id = envelope.tenant.tenant_id
    user = (
        user_partition(tenant_id, envelope.security.sub)
        if meta["kind"] == "user"
        else ""
    )
    return record_aad(
        tenant_id=tenant_id, user=user, scope=meta["scope"], key=key
    )


def expected_kms_key(envelope: ContextEnvelope | None, key: str) -> str:
    """The only KMS key allowed for this record: platform key for GLOBAL, caller's key otherwise."""
    if parse_memory_key(key)["kind"] == "global":
        return platform_global_key_name()
    if envelope is None:
        raise MemoryAccessDenied(
            "403 Forbidden: Tenant memory requires a verified caller."
        )
    return envelope.tenant.cmek_key_name


def platform_global_key_name() -> str:
    return PLATFORM_GLOBAL_KMS_KEY_NAME


# ---------------------------------------------------------------------------------------------
# Access rules
# ---------------------------------------------------------------------------------------------


def assert_can_read(envelope: ContextEnvelope, key: str) -> dict[str, str]:
    """GLOBAL: everyone. TENANT/STRATEGY: same tenant. USER/SESSION: same tenant and same user."""
    meta = parse_memory_key(key)
    if meta["kind"] == "global":
        return meta
    tenant_id = envelope.tenant.tenant_id
    if meta["tenant_id"] != tenant_id:
        raise MemoryAccessDenied(
            "403 Forbidden: Cross-tenant memory access denied."
        )
    if meta["kind"] == "user" and meta["user"] != user_partition(
        tenant_id, envelope.security.sub
    ):
        raise MemoryAccessDenied(
            "403 Forbidden: Cross-user memory access denied."
        )
    return meta


@dataclass(frozen=True)
class OperatorPrincipal:
    """An operator writing GLOBAL memory: who wrote it and who approved it (two names).

    This is the code-level gate, and the names are self-asserted audit fields. The enforcing control
    is IAM: the serving identity may only
    *decrypt* with the platform key, and only curators may *encrypt* with it, so serving code
    cannot forge GLOBAL memory even if it constructs one of these.
    """

    operator: str
    approved_by: str

    def __post_init__(self) -> None:
        if not self.operator.strip() or not self.approved_by.strip():
            raise MemoryAccessDenied(
                "E_MEMORY_WRITE_DENIED: operator and approver are required."
            )
        if (
            self.operator.strip().casefold()
            == self.approved_by.strip().casefold()
        ):
            raise MemoryAccessDenied(
                "E_MEMORY_WRITE_DENIED: approver must differ from operator."
            )


def assert_can_write(
    envelope: ContextEnvelope | None,
    scope: MemoryScope,
    *,
    operator: OperatorPrincipal | None = None,
) -> None:
    """GLOBAL: an explicit operator principal, never a caller. TENANT/STRATEGY:
    `memory:tenant.write`.
    """
    if scope == MemoryScope.GLOBAL:
        if envelope is not None or not isinstance(operator, OperatorPrincipal):
            raise MemoryAccessDenied(
                "E_MEMORY_WRITE_DENIED: GLOBAL memory is read-only for agents and tenants."
            )
        return
    if envelope is None:
        raise MemoryAccessDenied(
            "E_MEMORY_WRITE_DENIED: Tenant memory needs a verified caller."
        )
    if scope in TENANT_SHARED_SCOPES and (
        TENANT_MEMORY_WRITE_SCOPE not in envelope.tenant.authorized_scopes
    ):
        raise MemoryAccessDenied(
            "E_MEMORY_WRITE_DENIED: Writing tenant-shared memory requires the "
            f"'{TENANT_MEMORY_WRITE_SCOPE}' scope."
        )


def assert_stored_scope_matches(record: dict[str, Any], key: str) -> None:
    """A record whose stored scope disagrees with its key is treated as tampered."""
    if str(record.get("scope")) != parse_memory_key(key)["scope"]:
        raise MemoryAccessDenied(
            "403 Forbidden: Stored record does not match its key."
        )


# ---------------------------------------------------------------------------------------------
# Key wrapping (Cloud KMS in live mode, IAM-enforcing LocalKMS offline)
# ---------------------------------------------------------------------------------------------


class KeyWrapper(Protocol):
    def wrap(
        self,
        *,
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        dek: bytes,
        aad: bytes,
    ) -> bytes: ...

    def unwrap(
        self,
        *,
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        wrapped: bytes,
        aad: bytes,
    ) -> bytes: ...


def assert_platform_key(kms_key_name: str) -> None:
    """The platform (runtime) identity may use exactly one key: the platform GLOBAL key."""
    if kms_key_name != platform_global_key_name():
        raise PermissionError(
            "E_KMS_IAM_DENIED: Platform identity may use only the GLOBAL key."
        )


class LocalKeyWrapper:
    """Hermetic wrapper: tenant keys via `LocalKMS` + tenant credentials, so IAM is still enforced.

    `envelope=None` means the platform runtime identity, which may use only the platform key.
    Key material lives in this process only; records sealed here cannot be opened elsewhere.
    """

    def __init__(self, project_id: str) -> None:
        from agents.tenant_credentials import (
            LocalKMS,
            LocalTenantCredentialBackend,
            TenantCredentialBroker,
            TenantIsolationPolicy,
        )

        self.project_id = project_id
        self.policy = TenantIsolationPolicy(project_id=project_id)
        self.kms = LocalKMS(self.policy)
        self.broker = TenantCredentialBroker(
            project_id=project_id, backend=LocalTenantCredentialBackend()
        )
        self._platform_material = os.urandom(32)

    def wrap(
        self,
        *,
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        dek: bytes,
        aad: bytes,
    ) -> bytes:
        if envelope is None:
            assert_platform_key(kms_key_name)
            nonce = os.urandom(12)
            return nonce + AESGCM(self._platform_material).encrypt(
                nonce, dek, aad
            )
        return self.kms.encrypt(
            kms_key_name=kms_key_name,
            plaintext=dek,
            aad=aad,
            credential=self.broker.credential_for(envelope),
        )

    def unwrap(
        self,
        *,
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        wrapped: bytes,
        aad: bytes,
    ) -> bytes:
        if envelope is None:
            assert_platform_key(kms_key_name)
            try:
                return AESGCM(self._platform_material).decrypt(
                    wrapped[:12], wrapped[12:], aad
                )
            except InvalidTag as exc:
                raise PermissionError(
                    "E_KMS_DECRYPT_FAILED: Wrong key or AAD."
                ) from exc
        return self.kms.decrypt(
            kms_key_name=kms_key_name,
            ciphertext=wrapped,
            aad=aad,
            credential=self.broker.credential_for(envelope),
        )


class CloudKMSKeyWrapper:
    """Live wrapper: Cloud KMS as the tenant SA, or as the runtime SA for the platform key only."""

    def __init__(self, project_id: str) -> None:
        from agents.gcp_live_bridge import LiveCloudKMSCMEKVerifier

        self.project_id = project_id
        self._kms = LiveCloudKMSCMEKVerifier(project_id=project_id)

    def wrap(
        self,
        *,
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        dek: bytes,
        aad: bytes,
    ) -> bytes:
        if envelope is None:
            assert_platform_key(kms_key_name)
        return self._kms.encrypt_for_tenant(
            kms_key_name=kms_key_name,
            tenant_id=(
                envelope.tenant.tenant_id if envelope else GLOBAL_NAMESPACE
            ),
            plaintext=dek,
            envelope=envelope,
            aad=aad,
        )

    def unwrap(
        self,
        *,
        envelope: ContextEnvelope | None,
        kms_key_name: str,
        wrapped: bytes,
        aad: bytes,
    ) -> bytes:
        if envelope is None:
            assert_platform_key(kms_key_name)
        return self._kms.decrypt_for_tenant(
            kms_key_name=kms_key_name,
            tenant_id=(
                envelope.tenant.tenant_id if envelope else GLOBAL_NAMESPACE
            ),
            ciphertext=wrapped,
            envelope=envelope,
            aad=aad,
        )


# ---------------------------------------------------------------------------------------------
# Sealing
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SealedRecord:
    """What is stored. Contains no key material that can be derived without Cloud KMS."""

    format: str
    kms_key_name: str
    wrapped_dek: bytes
    nonce: bytes
    ciphertext: bytes
    embedding_nonce: bytes = b""
    embedding_ciphertext: bytes = b""

    def to_storage(self) -> dict[str, str]:
        storage = {
            "format": self.format,
            "kms_key_name": self.kms_key_name,
            "wrapped_dek_hex": self.wrapped_dek.hex(),
            "nonce_hex": self.nonce.hex(),
            "ciphertext_hex": self.ciphertext.hex(),
        }
        if self.embedding_nonce and self.embedding_ciphertext:
            storage["embedding_nonce_hex"] = self.embedding_nonce.hex()
            storage["embedding_ciphertext_hex"] = (
                self.embedding_ciphertext.hex()
            )
        return storage

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> SealedRecord:
        if data.get("format") != FORMAT_V2:
            raise LegacyMemoryFormatError(
                "E_MEMORY_LEGACY_FORMAT: Record uses the retired derived-key format and is refused."
            )
        embedding_nonce_hex = str(data.get("embedding_nonce_hex", ""))
        embedding_ciphertext_hex = str(data.get("embedding_ciphertext_hex", ""))
        if bool(embedding_nonce_hex) != bool(embedding_ciphertext_hex):
            raise MemoryAccessDenied(
                "E_CMEK_AEAD_DECRYPTION_FAILED: Incomplete sealed embedding fields."
            )
        try:
            wrapped_dek = bytes.fromhex(str(data["wrapped_dek_hex"]))
            nonce = bytes.fromhex(str(data["nonce_hex"]))
            ciphertext = bytes.fromhex(str(data["ciphertext_hex"]))
            embedding_nonce = (
                bytes.fromhex(embedding_nonce_hex)
                if embedding_nonce_hex
                else b""
            )
            embedding_ciphertext = (
                bytes.fromhex(embedding_ciphertext_hex)
                if embedding_ciphertext_hex
                else b""
            )
        except ValueError as exc:
            raise MemoryAccessDenied(
                "E_CMEK_AEAD_DECRYPTION_FAILED: Stored hex fields are malformed."
            ) from exc
        return cls(
            format=FORMAT_V2,
            kms_key_name=str(data["kms_key_name"]),
            wrapped_dek=wrapped_dek,
            nonce=nonce,
            ciphertext=ciphertext,
            embedding_nonce=embedding_nonce,
            embedding_ciphertext=embedding_ciphertext,
        )


class MemoryCrypto:
    """Seals and opens memory payloads with per-record data keys wrapped by KMS."""

    def __init__(
        self,
        wrapper: KeyWrapper,
        cache_ttl: float = DEK_CACHE_TTL_SECONDS,
        cache_max_entries: int = DEK_CACHE_MAX_ENTRIES,
    ) -> None:
        from agents.context import register_tenant_eviction_target

        self.wrapper = wrapper
        self.cache_ttl = cache_ttl
        self.cache_max_entries = cache_max_entries
        self._cache: dict[tuple[Any, ...], tuple[float, bytes]] = {}
        self._eviction_generation: dict[str, int] = {}
        self._lock = threading.Lock()
        register_tenant_eviction_target(self)

    def seal(
        self,
        *,
        envelope: ContextEnvelope | None,
        key: str,
        payload: dict[str, Any],
        embedding: list[float] | None = None,
    ) -> SealedRecord:
        kms_key_name = expected_kms_key(envelope, key)
        aad = caller_aad(envelope, key)
        dek = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)
        plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
        embedding_nonce = b""
        embedding_ciphertext = b""
        if embedding:
            embedding_nonce = os.urandom(12)
            embedding_bytes = json.dumps(
                [float(val) for val in embedding]
            ).encode("utf-8")
            embedding_ciphertext = AESGCM(dek).encrypt(
                embedding_nonce,
                embedding_bytes,
                aad + b":embedding",
            )
        wrapped = self.wrapper.wrap(
            envelope=envelope, kms_key_name=kms_key_name, dek=dek, aad=aad
        )
        return SealedRecord(
            FORMAT_V2,
            kms_key_name,
            wrapped,
            nonce,
            ciphertext,
            embedding_nonce,
            embedding_ciphertext,
        )

    def _cached_unwrap(
        self,
        *,
        envelope: ContextEnvelope | None,
        record: SealedRecord,
        aad: bytes,
    ) -> bytes:
        tenant_id = envelope.tenant.tenant_id if envelope is not None else ""
        principal = (
            ("tenant", tenant_id, envelope.security.sub)
            if envelope is not None
            else ("platform",)
        )
        cache_key = (principal, record.kms_key_name, aad, record.wrapped_dek)
        now = time.monotonic()
        with self._lock:
            generation_before = self._eviction_generation.get(tenant_id, 0)
            cached = self._cache.get(cache_key)
            if cached is not None and now - cached[0] < self.cache_ttl:
                return cached[1]
            self._cache.pop(cache_key, None)
        dek = self.wrapper.unwrap(
            envelope=envelope,
            kms_key_name=record.kms_key_name,
            wrapped=record.wrapped_dek,
            aad=aad,
        )
        with self._lock:
            if (
                tenant_id
                and self._eviction_generation.get(tenant_id, 0)
                != generation_before
            ):
                raise MemoryAccessDenied(
                    "E_TENANT_OFFBOARDED_DURING_UNWRAP: Tenant was offboarded during DEK unwrap."
                )
            if self.cache_ttl > 0:
                if len(self._cache) >= self.cache_max_entries:
                    # Drop expired entries first, then the oldest (insertion order) if still full.
                    self._cache = {
                        k: v
                        for k, v in self._cache.items()
                        if now - v[0] < self.cache_ttl
                    }
                    while len(self._cache) >= self.cache_max_entries:
                        self._cache.pop(next(iter(self._cache)))
                self._cache[cache_key] = (now, dek)
        return dek

    def open(
        self,
        *,
        envelope: ContextEnvelope | None,
        key: str,
        record: SealedRecord,
    ) -> dict[str, Any]:
        if record.kms_key_name != expected_kms_key(envelope, key):
            raise MemoryAccessDenied(
                "E_KMS_KEY_MISMATCH: Stored key does not match the caller."
            )
        aad = caller_aad(envelope, key)
        dek = self._cached_unwrap(envelope=envelope, record=record, aad=aad)
        try:
            plaintext = AESGCM(dek).decrypt(
                record.nonce, record.ciphertext, aad
            )
        except InvalidTag as exc:
            raise MemoryAccessDenied(
                "E_CMEK_AEAD_DECRYPTION_FAILED: Record authentication failed (wrong key or AAD)."
            ) from exc
        return dict(json.loads(plaintext.decode("utf-8")))

    def open_embedding(
        self,
        *,
        envelope: ContextEnvelope | None,
        key: str,
        record: SealedRecord,
    ) -> list[float]:
        """Decrypts and authenticates the sealed RAG embedding vector for `record`."""
        if not record.embedding_nonce or not record.embedding_ciphertext:
            return []
        if record.kms_key_name != expected_kms_key(envelope, key):
            raise MemoryAccessDenied(
                "E_KMS_KEY_MISMATCH: Stored key does not match the caller."
            )
        aad = caller_aad(envelope, key)
        dek = self._cached_unwrap(envelope=envelope, record=record, aad=aad)
        try:
            plaintext = AESGCM(dek).decrypt(
                record.embedding_nonce,
                record.embedding_ciphertext,
                aad + b":embedding",
            )
        except InvalidTag as exc:
            raise MemoryAccessDenied(
                "E_CMEK_AEAD_DECRYPTION_FAILED: Embedding authentication failed (wrong key or AAD)."
            ) from exc
        parsed = json.loads(plaintext.decode("utf-8"))
        return [float(val) for val in parsed]

    def evict_tenant(self, tenant_id: str) -> int:
        """Evicts all unwrapped DEK cache entries belonging to `tenant_id` upon offboarding."""
        with self._lock:
            self._eviction_generation[tenant_id] = (
                self._eviction_generation.get(tenant_id, 0) + 1
            )
            matching_keys = [
                cache_key
                for cache_key in self._cache
                if (
                    isinstance(cache_key[0], tuple)
                    and len(cache_key[0]) >= 2
                    and cache_key[0][0] == "tenant"
                    and cache_key[0][1] == tenant_id
                )
            ]
            for cache_key in matching_keys:
                self._cache.pop(cache_key, None)
            return len(matching_keys)

    def clear_cache(self) -> None:
        """Drop all unwrapped data keys (call after disabling a key to shred immediately)."""
        with self._lock:
            self._cache.clear()


_DEFAULT_CRYPTO: MemoryCrypto | None = None
_DEFAULT_LOCK = threading.Lock()


def get_memory_crypto() -> MemoryCrypto:
    """Process-wide crypto: Cloud KMS in live mode, IAM-enforcing LocalKMS otherwise."""
    global _DEFAULT_CRYPTO
    with _DEFAULT_LOCK:
        if _DEFAULT_CRYPTO is None:
            from agents.platform_config import is_live_mode, resolve_project_id

            project_id = resolve_project_id()
            wrapper: KeyWrapper = (
                CloudKMSKeyWrapper(project_id)
                if is_live_mode()
                else LocalKeyWrapper(project_id)
            )
            _DEFAULT_CRYPTO = MemoryCrypto(wrapper)
        return _DEFAULT_CRYPTO


def set_memory_crypto(crypto: MemoryCrypto | None) -> None:
    global _DEFAULT_CRYPTO
    with _DEFAULT_LOCK:
        _DEFAULT_CRYPTO = crypto
