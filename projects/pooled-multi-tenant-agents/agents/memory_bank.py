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

"""In-process Memory Bank (5 scopes) with tenant + user isolation and KMS envelope encryption.

Isolation per path:

| Path | Lock 1 (code) | Lock 2 (crypto / IAM) |
| :--- | :--- | :--- |
| Cross-tenant read | `assert_can_read` (tenant in key) | Data key wrapped by the tenant's KMS key;
only that tenant's SA can unwrap |
| Cross-user read (same tenant) | `assert_can_read` (user partition in key) | AAD carries the
caller's user partition |
| Moved / relabelled record | Strict key parsing; stored scope must match the key | AAD carries the
full key and scope |
| Poisoning shared memory | `assert_can_write` (GLOBAL needs an `OperatorPrincipal`; TENANT needs
`memory:tenant.write`) | Platform key: serving identity may only decrypt; only curators may encrypt
|
| Poisoned record | Injection screen on every string leaf, on every read path (direct read and RAG)
| Flagged records are marked quarantined in the store and refused from then on |

TENANT / STRATEGY memory is one entry per agent (`actor`): the latest write by an authorized
admin replaces the previous one. USER memory persists across sessions; SESSION memory does not.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import math
from typing import Any

from agents.context import ContextEnvelope, MemoryScope
from agents.memory_crypto import (
    MemoryAccessDenied,
    MemoryCrypto,
    OperatorPrincipal,
    SealedRecord,
    assert_can_read,
    assert_can_write,
    assert_stored_scope_matches,
    build_memory_key,
    get_memory_crypto,
    parse_memory_key,
)

logger = logging.getLogger(__name__)


_MAX_PAYLOAD_DEPTH = 32


class _Unscreenable(Exception):
    """Payload shape the screen cannot inspect faithfully; treated as unsafe (fail closed)."""


def _string_leaves(value: Any, depth: int = 0) -> list[str]:
    """Every string in a JSON-like payload (keys included), so nothing is screened as `repr`."""
    if depth > _MAX_PAYLOAD_DEPTH:
        raise _Unscreenable("payload nested too deeply")
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for k, v in value.items():
            if not isinstance(k, str):
                raise _Unscreenable("non-string key")
            out.append(k)
            out.extend(_string_leaves(v, depth + 1))
        return out
    if isinstance(value, list | tuple):
        return [
            leaf for item in value for leaf in _string_leaves(item, depth + 1)
        ]
    if value is None or isinstance(value, bool | int | float):
        return []
    raise _Unscreenable(f"unsupported type {type(value).__name__}")


def screen_retrieved_chunk(payload: dict[str, Any]) -> bool:
    """True if a decrypted memory is safe to hand to the model (indirect-injection screen).

    Screens each string leaf on its own and all leaves joined, on the real characters (not
    `str(dict)`, which escapes newlines and zero-width characters past the patterns). Anything
    the screen cannot inspect (too deep, non-JSON types) fails closed.
    """
    from agents.interceptors import screen_tool_output_for_indirect_injection

    try:
        leaves = _string_leaves(payload)
        for text in (*leaves, " ".join(leaves)):
            screen_tool_output_for_indirect_injection(
                raw_output=text, tool_name="memory"
            )
    except (PermissionError, _Unscreenable):
        return False
    return True


def key_fingerprint(key: str) -> str:
    """Short, non-reversible handle for logs (memory keys contain tenant and user partitions)."""
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _valid_vector(vec: Any) -> list[float] | None:
    """A finite numeric vector, or None. Malformed stored vectors must never break RAG."""
    if not isinstance(vec, list) or not vec:
        return None
    if not all(
        isinstance(x, int | float) and not isinstance(x, bool) for x in vec
    ):
        return None
    if not all(math.isfinite(x) for x in vec):
        return None
    return [float(x) for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def global_write_metadata(
    operator: OperatorPrincipal, content: dict[str, Any]
) -> dict[str, Any]:
    """Plaintext audit fields stored with a GLOBAL record (no tenant data by construction)."""
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return {
        "curated_by": operator.operator,
        "approved_by": operator.approved_by,
        "content_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def log_quarantine(key: str, record: dict[str, Any]) -> None:
    """Security event without content: key fingerprint, owning tenant, scope."""
    logger.warning(
        "SECURITY memory_quarantined key=%s tenant=%s scope=%s",
        key_fingerprint(key),
        record.get("tenant_id", "?"),
        record.get("scope", "?"),
    )


class MemoryBankPartitioner:
    """Subsystem 4: 5-scope Memory Bank with per-record KMS-wrapped data keys."""

    def __init__(self, crypto: MemoryCrypto | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._crypto = crypto

    @property
    def crypto(self) -> MemoryCrypto:
        return self._crypto or get_memory_crypto()

    @staticmethod
    def build_composite_key(
        *,
        tenant_id: str,
        scope: MemoryScope,
        session_id: str,
        actor: str,
        sub: str,
    ) -> str:
        return build_memory_key(
            tenant_id=tenant_id,
            sub=sub,
            scope=scope,
            session_id=session_id,
            actor=actor,
        )

    def _put(
        self,
        *,
        envelope: ContextEnvelope | None,
        key: str,
        content: dict[str, Any],
        embedding: list[float] | None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if embedding is not None and _valid_vector(embedding) is None:
            raise ValueError(
                "embedding must be a non-empty list of finite numbers"
            )
        sealed = self.crypto.seal(
            envelope=envelope,
            key=key,
            payload=content,
            embedding=embedding,
        )
        self._store[key] = {
            "key": key,
            "tenant_id": envelope.tenant.tenant_id if envelope else "global",
            "scope": parse_memory_key(key)["scope"],
            **sealed.to_storage(),
            **(metadata or {}),
        }
        return key

    def write_memory(
        self,
        *,
        envelope: ContextEnvelope,
        scope: MemoryScope,
        actor: str,
        content: dict[str, Any],
        embedding: list[float] | None = None,
    ) -> str:
        """Writes tenant / user memory as the caller. GLOBAL is refused (operator-only)."""
        if envelope is None:
            raise MemoryAccessDenied(
                "E_MEMORY_WRITE_DENIED: Memory writes need a verified caller."
            )
        assert_can_write(envelope, scope)
        key = build_memory_key(
            tenant_id=envelope.tenant.tenant_id,
            sub=envelope.security.sub,
            scope=scope,
            session_id=envelope.request.session_id,
            actor=actor,
        )
        return self._put(
            envelope=envelope, key=key, content=content, embedding=embedding
        )

    def exists(self, key: str) -> bool:
        return key in self._store

    def write_global(
        self,
        *,
        operator: OperatorPrincipal,
        actor: str,
        content: dict[str, Any],
        embedding: list[float] | None = None,
        replace: bool = False,
    ) -> str:
        """Operator tooling only (`scripts/curate_global_memory.py`): platform-wide memory.

        Needs an `OperatorPrincipal` (operator + a different approver). In live mode the real
        control is IAM: only curators can encrypt with the platform key.
        """
        assert_can_write(None, MemoryScope.GLOBAL, operator=operator)
        key = build_memory_key(
            tenant_id="",
            sub="",
            scope=MemoryScope.GLOBAL,
            session_id="",
            actor=actor,
        )
        if self.exists(key) and not replace:
            raise MemoryAccessDenied(
                "E_GLOBAL_EXISTS: GLOBAL entry exists; pass replace=True."
            )
        return self._put(
            envelope=None,
            key=key,
            content=content,
            embedding=embedding,
            metadata=global_write_metadata(operator, content),
        )

    def _quarantine(self, key: str, record: dict[str, Any]) -> None:
        record["quarantined"] = True
        record["quarantined_at"] = dt.datetime.now(dt.UTC).isoformat()
        log_quarantine(key, record)

    def _open(
        self, envelope: ContextEnvelope, key: str, record: dict[str, Any]
    ) -> dict[str, Any]:
        """Decrypts and screens a record for the caller. Namespace and scope come from the key."""
        if record.get("quarantined"):
            raise MemoryAccessDenied(
                "E_MEMORY_QUARANTINED: record is quarantined."
            )
        assert_stored_scope_matches(record, key)
        if "embedding" in record:
            raise MemoryAccessDenied(
                "E_CMEK_AEAD_DECRYPTION_FAILED: Unsealed plaintext embedding field is refused."
            )
        is_global = parse_memory_key(key)["kind"] == "global"
        sealed_record = SealedRecord.from_storage(record)
        payload = self.crypto.open(
            envelope=None if is_global else envelope,
            key=key,
            record=sealed_record,
        )
        if sealed_record.embedding_nonce or sealed_record.embedding_ciphertext:
            sealed_embedding = self.crypto.open_embedding(
                envelope=None if is_global else envelope,
                key=key,
                record=sealed_record,
            )
            if _valid_vector(sealed_embedding) is None:
                raise MemoryAccessDenied(
                    "E_CMEK_AEAD_DECRYPTION_FAILED: Sealed embedding decrypted to invalid vector."
                )
        if not screen_retrieved_chunk(payload):
            self._quarantine(key, record)
            raise MemoryAccessDenied(
                "E_MEMORY_QUARANTINED: record failed the injection screen."
            )
        return payload

    def read_memory(
        self, *, envelope: ContextEnvelope, target_key: str
    ) -> dict[str, Any]:
        """Code check, KMS unwrap as the caller, AES-GCM with the caller's AAD, injection screen."""
        assert_can_read(envelope, target_key)
        record = self._store.get(target_key)
        if record is None:
            raise KeyError("Memory key not found.")
        return self._open(envelope, target_key, record)

    def reseal_legacy_embeddings(
        self,
        *,
        envelope: ContextEnvelope | None,
        operator: OperatorPrincipal | None = None,
    ) -> int:
        """Re-seals legacy records carrying plaintext `embedding` into ciphertext-only storage.

        Args:
            envelope: Caller's `ContextEnvelope` for tenant/user records, or `None` for `GLOBAL`.
            operator: Required `OperatorPrincipal` when migrating `GLOBAL` records.

        Returns:
            Count of legacy records migrated to ciphertext-only embeddings.
        """
        migrated_count = 0
        for key, record in list(self._store.items()):
            if "embedding" not in record:
                continue
            parsed = parse_memory_key(key)
            is_global = parsed["kind"] == "global"
            if is_global:
                assert_can_write(None, MemoryScope.GLOBAL, operator=operator)
            else:
                if envelope is None:
                    continue
                try:
                    assert_can_read(envelope, key)
                    assert_can_write(envelope, MemoryScope(parsed["scope"]))
                except MemoryAccessDenied:
                    continue
            legacy_vector = _valid_vector(record.get("embedding"))
            if legacy_vector is None:
                raise ValueError(
                    f"Legacy record {key_fingerprint(key)} has malformed embedding."
                )
            sealed_record = SealedRecord.from_storage(record)
            payload = self.crypto.open(
                envelope=None if is_global else envelope,
                key=key,
                record=sealed_record,
            )
            resealed = self.crypto.seal(
                envelope=None if is_global else envelope,
                key=key,
                payload=payload,
                embedding=legacy_vector,
            )
            updated_record = dict(record)
            updated_record.pop("embedding", None)
            updated_record.update(resealed.to_storage())
            self._store[key] = updated_record
            migrated_count += 1
        return migrated_count

    def retrieve_similar_memories_rag(
        self,
        *,
        envelope: ContextEnvelope,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Similarity search over own tenant's shared memory, own user's memory, and GLOBAL.

        Candidates are filtered by `assert_can_read`, then their AEAD-sealed embeddings are
        decrypted per tenant at search time (cached in `MemoryCrypto` so opening the top-k
        winning payloads performs zero extra KMS unwraps). Any record with an unsealed plaintext
        `embedding` field or failed AEAD authentication is skipped and logged without content.
        """
        if top_k <= 0:
            return []
        candidates: list[tuple[float, str, dict[str, Any]]] = []
        for key, record in self._store.items():
            try:
                assert_can_read(envelope, key)
            except MemoryAccessDenied:
                continue
            if record.get("quarantined"):
                continue
            if "embedding" in record:
                logger.warning(
                    "RAG: skipping memory record %s (unsealed plaintext embedding refused)",
                    key_fingerprint(key),
                )
                continue
            if not record.get("embedding_nonce_hex") and not record.get(
                "embedding_ciphertext_hex"
            ):
                continue
            is_global = parse_memory_key(key)["kind"] == "global"
            try:
                sealed_record = SealedRecord.from_storage(record)
                decrypted_vector = self.crypto.open_embedding(
                    envelope=None if is_global else envelope,
                    key=key,
                    record=sealed_record,
                )
            except (PermissionError, ValueError, KeyError):
                logger.warning(
                    "RAG: skipping memory record %s (failed to open embedding)",
                    key_fingerprint(key),
                )
                continue
            vec = _valid_vector(decrypted_vector)
            if vec is not None and len(vec) == len(query_embedding):
                candidates.append((_cosine(query_embedding, vec), key, record))
        candidates.sort(key=lambda c: (-c[0], c[1]))

        hits: list[dict[str, Any]] = []
        for similarity, key, record in candidates:
            if len(hits) >= top_k:
                break
            try:
                payload = self._open(envelope, key, record)
            except (PermissionError, ValueError, KeyError):
                logger.warning(
                    "RAG: skipping memory record %s (failed to open)",
                    key_fingerprint(key),
                )
                continue
            hits.append(
                {
                    "key": key,
                    "tenant_id": parse_memory_key(key)["tenant_id"] or "global",
                    "similarity": round(similarity, 4),
                    "payload": payload,
                }
            )
        return hits
