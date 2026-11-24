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
# pylint: disable=protected-access,redefined-outer-name,unused-argument
# pylint: disable=use-implicit-booleaness-not-comparison

"""Memory envelope encryption, strict memory keys, and the Firestore v2 record format.

Closes F1 and assurance inventory rows #3, #4 and #6 (read side):

- **F1 / #3:** memory is sealed with a random per-record data key wrapped by the tenant's KMS key;
  nothing stored lets a reader (e.g. a project Viewer) derive the key.
- **#4:** USER / SESSION memory is user-partitioned, and the AAD binds the caller's user.
- **#6:** RAG returns only own tenant / own user memory (and GLOBAL), ranked before decryption.
- GLOBAL memory is read-only for agents and tenants; it is sealed with a platform key that tenant
  identities cannot use.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

import pytest
from agents import memory_crypto as mc
from agents import platform_config as pc
from agents.context import (
    TENANT_DIRECTORY,
    ContextEnvelope,
    EdgeAuthVerifier,
    MemoryScope,
)
from agents.memory_bank import MemoryBankPartitioner
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"


def _env(
    tenant_id: str,
    sub: str,
    role: str | None = "sre_admin",
    session: str = "sess-1",
) -> ContextEnvelope:
    claims: dict[str, Any] = {
        "iss": str(TENANT_DIRECTORY[tenant_id]["iss"]),
        "sub": sub,
        "tenant_id": tenant_id,
        "exp": int(time.time()) + 3600,
    }
    if role is not None:
        claims["user_role"] = role
    return EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims=claims,
        dpop_proof={"jkt": f"jkt-{sub}", "jti": f"dpop-{uuid.uuid4().hex}"},
        session_id=session,
    )


class CountingWrapper(mc.LocalKeyWrapper):
    def __init__(self) -> None:
        super().__init__(pc.resolve_project_id())
        self.unwraps = 0

    def unwrap(self, **kwargs: Any) -> bytes:
        self.unwraps += 1
        return super().unwrap(**kwargs)


@pytest.fixture
def wrapper() -> CountingWrapper:
    return CountingWrapper()


@pytest.fixture
def bank(wrapper: CountingWrapper) -> MemoryBankPartitioner:
    return MemoryBankPartitioner(crypto=mc.MemoryCrypto(wrapper))


@pytest.fixture
def alice() -> ContextEnvelope:
    return _env(FV, "alice@finvault.com")


@pytest.fixture
def charlie() -> ContextEnvelope:
    return _env(FV, "charlie@finvault.com", role="compliance_officer")


@pytest.fixture
def rs_admin() -> ContextEnvelope:
    return _env(RS, "ops@retailstream.com")


# ---------------------------------------------------------------------------------------------
# Envelope encryption (F1)
# ---------------------------------------------------------------------------------------------


def test_stored_record_has_no_derivable_key_material(
    bank: MemoryBankPartitioner, alice: ContextEnvelope
) -> None:
    key = bank.write_memory(
        envelope=alice,
        scope=MemoryScope.USER,
        actor="agent",
        content={"limit": 50_000_000},
    )
    record = bank._store[key]
    assert record["format"] == "v2"
    assert set(record) >= {
        "wrapped_dek_hex",
        "nonce_hex",
        "ciphertext_hex",
        "kms_key_name",
    }
    assert "50000000" not in str(record)
    assert "dek" not in {k for k in record if not k.endswith("_hex")}


def test_f1_viewer_with_raw_record_and_source_code_cannot_decrypt(
    bank: MemoryBankPartitioner, alice: ContextEnvelope
) -> None:
    """The old attack: derive the key from the stored KMS key name. It must now fail."""
    key = bank.write_memory(
        envelope=alice,
        scope=MemoryScope.TENANT,
        actor="agent",
        content={"secret": "wire-audit"},
    )
    record = bank._store[key]
    derived = hashlib.sha256(
        f"cymbal-cmek-dek-v1:{record['kms_key_name']}".encode()
    ).digest()
    aad = mc.record_aad(tenant_id=FV, user="", scope="tenant", key=key)
    with pytest.raises(InvalidTag):
        AESGCM(derived).decrypt(
            bytes.fromhex(record["nonce_hex"]),
            bytes.fromhex(record["ciphertext_hex"]),
            aad,
        )


def test_each_record_gets_a_fresh_data_key(
    bank: MemoryBankPartitioner, alice: ContextEnvelope
) -> None:
    k1 = bank.write_memory(
        envelope=alice, scope=MemoryScope.USER, actor="a1", content={"x": 1}
    )
    k2 = bank.write_memory(
        envelope=alice, scope=MemoryScope.USER, actor="a2", content={"x": 1}
    )
    assert (
        bank._store[k1]["wrapped_dek_hex"] != bank._store[k2]["wrapped_dek_hex"]
    )
    assert (
        bank._store[k1]["ciphertext_hex"] != bank._store[k2]["ciphertext_hex"]
    )


def test_cross_tenant_unwrap_denied_by_kms_iam_even_with_acl_bypassed(
    bank: MemoryBankPartitioner,
    alice: ContextEnvelope,
    rs_admin: ContextEnvelope,
) -> None:
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.TENANT, actor="a", content={"x": 1}
    )
    with pytest.raises(
        PermissionError, match=r"E_KMS_KEY_MISMATCH|E_KMS_IAM_DENIED"
    ):
        bank._open(rs_admin, key, bank._store[key])


@pytest.mark.parametrize("field", ["key", "scope"])
def test_moved_or_relabelled_record_fails_authentication(
    bank: MemoryBankPartitioner, alice: ContextEnvelope, field: str
) -> None:
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.TENANT, actor="a", content={"x": 1}
    )
    record = dict(bank._store[key])
    if field == "key":
        moved = key.replace("/a", "/b")
        bank._store[moved] = record
        target = moved
    else:
        record["scope"] = "strategy"
        bank._store[key] = record
        target = key
    with pytest.raises(PermissionError):
        bank.read_memory(envelope=alice, target_key=target)


def test_legacy_v1_record_is_refused(
    bank: MemoryBankPartitioner, alice: ContextEnvelope
) -> None:
    key = mc.build_memory_key(
        tenant_id=FV,
        sub=alice.security.sub,
        scope=MemoryScope.TENANT,
        session_id="s",
        actor="a",
    )
    bank._store[key] = {
        "key": key,
        "scope": "tenant",
        "nonce": b"x",
        "ciphertext": b"y",
    }
    with pytest.raises(
        mc.LegacyMemoryFormatError, match="E_MEMORY_LEGACY_FORMAT"
    ):
        bank.read_memory(envelope=alice, target_key=key)


def test_unwrapped_key_cache_avoids_repeat_kms_calls(
    bank: MemoryBankPartitioner,
    alice: ContextEnvelope,
    wrapper: CountingWrapper,
) -> None:
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.USER, actor="a", content={"x": 1}
    )
    for _ in range(3):
        bank.read_memory(envelope=alice, target_key=key)
    assert wrapper.unwraps == 1


# --- #4 data-key cache ----------------------------------------------------------------------------


def test_04_second_user_in_tenant_does_its_own_kms_unwrap(
    bank: MemoryBankPartitioner, wrapper: CountingWrapper
) -> None:
    alice, bob = _env(FV, "alice@finvault.com"), _env(FV, "bob@finvault.com")
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.TENANT, actor="a", content={"x": 1}
    )
    bank.read_memory(envelope=alice, target_key=key)
    bank.read_memory(envelope=bob, target_key=key)
    assert wrapper.unwraps == 2  # each principal is audited at KMS


def test_04_tampered_stored_key_name_is_refused_even_when_cached(
    bank: MemoryBankPartitioner,
) -> None:
    alice = _env(FV, "alice@finvault.com")
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.TENANT, actor="a", content={"x": 1}
    )
    bank.read_memory(envelope=alice, target_key=key)  # warm the cache
    bank._store[key]["kms_key_name"] = TENANT_DIRECTORY[RS]["cmek_key_name"]
    with pytest.raises(PermissionError, match="E_KMS_KEY_MISMATCH"):
        bank.read_memory(envelope=alice, target_key=key)


def test_04_clear_cache_forces_kms_again_and_cache_is_bounded(
    wrapper: CountingWrapper,
) -> None:
    crypto = mc.MemoryCrypto(wrapper, cache_max_entries=3)
    bank = MemoryBankPartitioner(crypto=crypto)
    alice = _env(FV, "alice@finvault.com")
    keys = [
        bank.write_memory(
            envelope=alice,
            scope=MemoryScope.USER,
            actor=f"a{i}",
            content={"i": i},
        )
        for i in range(5)
    ]
    for key in keys:
        bank.read_memory(envelope=alice, target_key=key)
    assert len(crypto._cache) <= 3
    crypto.clear_cache()
    bank.read_memory(envelope=alice, target_key=keys[0])
    assert wrapper.unwraps == 6


# --- #5 scope from the key, never from the stored record ----------------------------------------


def test_05_tampered_stored_scope_is_refused(
    bank: MemoryBankPartitioner,
) -> None:
    alice = _env(FV, "alice@finvault.com")
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.TENANT, actor="a", content={"x": 1}
    )
    bank._store[key]["scope"] = "global"
    with pytest.raises(mc.MemoryAccessDenied, match="does not match its key"):
        bank.read_memory(envelope=alice, target_key=key)


# --- #6 platform identity may use only the platform key ----------------------------------------


def test_06_platform_identity_cannot_use_a_tenant_key(
    wrapper: CountingWrapper,
) -> None:
    with pytest.raises(PermissionError, match="only the GLOBAL key"):
        wrapper.wrap(
            envelope=None,
            kms_key_name=TENANT_DIRECTORY[FV]["cmek_key_name"],
            dek=b"0" * 32,
            aad=b"a",
        )


def test_06_live_wrapper_enforces_the_same_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []
    live = object.__new__(mc.CloudKMSKeyWrapper)
    live._kms = type(
        "K", (), {"encrypt_for_tenant": lambda *a, **k: called.append("x")}
    )()
    with pytest.raises(PermissionError, match="only the GLOBAL key"):
        live.wrap(
            envelope=None,
            kms_key_name=TENANT_DIRECTORY[FV]["cmek_key_name"],
            dek=b"0",
            aad=b"a",
        )
    assert called == []


def test_tenant_identity_cannot_use_the_platform_global_key(
    wrapper: CountingWrapper,
) -> None:
    alice = _env(FV, "alice@finvault.com")
    with pytest.raises(PermissionError):
        wrapper.wrap(
            envelope=alice,
            kms_key_name=mc.platform_global_key_name(),
            dek=b"0" * 32,
            aad=b"a",
        )


# ---------------------------------------------------------------------------------------------
# Tenant + user qualified memory keys (#2, #3, #4, #9, #10)
# ---------------------------------------------------------------------------------------------


def test_equal_subjects_at_two_tenants_get_distinct_memory_keys() -> None:
    fv_key = mc.build_memory_key(
        tenant_id=FV,
        sub="00u123",
        scope=MemoryScope.SESSION,
        session_id="s",
        actor="a",
    )
    rs_key = mc.build_memory_key(
        tenant_id=RS,
        sub="00u123",
        scope=MemoryScope.SESSION,
        session_id="s",
        actor="a",
    )
    assert fv_key.split("/")[1] != rs_key.split("/")[1]


def test_raw_subjects_never_appear_in_memory_keys() -> None:
    key = mc.build_memory_key(
        tenant_id=FV,
        sub="alice@finvault.com",
        scope=MemoryScope.USER,
        session_id="s",
        actor="a",
    )
    assert "alice" not in key
    assert "@" not in key


@pytest.mark.parametrize(
    "key",
    [
        "global/_tenant/tenant/a",
        "global/u-0123456789abcdef/user/_/a",
        "global/tenant/a",
        "global/global",
    ],
)
def test_03_only_the_exact_global_shape_is_world_readable(key: str) -> None:
    with pytest.raises(mc.MemoryAccessDenied):
        mc.assert_can_read(_env(RS, "x@retailstream.com"), key)


def test_03_memory_key_cannot_use_the_global_namespace() -> None:
    with pytest.raises(ValueError, match=r"Invalid or reserved tenant_id"):
        mc.build_memory_key(
            tenant_id="global",
            sub="s",
            scope=MemoryScope.TENANT,
            session_id="",
            actor="a",
        )


@pytest.mark.parametrize(
    "key",
    [
        f"{FV}/_tenant/user/x",
        f"{FV}/u-0123456789abcdef/global/s/a",
        f"{FV}/u-0123456789abcdef/TENANT/s/a",
        f"{FV}/u-0123456789abcdef/user/s1/a",  # USER keys are session-independent
        f"{FV}//tenant/a",
    ],
)
def test_09_parser_rejects_shape_scope_mismatches(key: str) -> None:
    with pytest.raises(mc.MemoryAccessDenied):
        mc.parse_memory_key(key)


def test_10_empty_subject_cannot_form_a_user_partition() -> None:
    with pytest.raises(ValueError, match=r"empty subject"):
        mc.user_partition(FV, "")


def test_10_user_memory_persists_across_sessions_session_memory_does_not() -> (
    None
):
    def key(scope: MemoryScope, session: str) -> str:
        return mc.build_memory_key(
            tenant_id=FV, sub="a", scope=scope, session_id=session, actor="x"
        )

    assert key(MemoryScope.USER, "s1") == key(MemoryScope.USER, "s2")
    assert key(MemoryScope.SESSION, "s1") != key(MemoryScope.SESSION, "s2")


def test_charlie_cannot_read_alices_user_memory(
    bank: MemoryBankPartitioner,
    alice: ContextEnvelope,
    charlie: ContextEnvelope,
) -> None:
    key = bank.write_memory(
        envelope=alice,
        scope=MemoryScope.USER,
        actor="a",
        content={"pref": "private"},
    )
    with pytest.raises(
        PermissionError, match="Cross-user memory access denied"
    ):
        bank.read_memory(envelope=charlie, target_key=key)
    # Code check skipped: the AAD binds Alice, so Charlie's unwrap fails cryptographically.
    with pytest.raises(PermissionError):
        bank._open(charlie, key, bank._store[key])


def test_tenant_shared_memory_is_visible_to_every_user_in_the_tenant(
    bank: MemoryBankPartitioner,
    alice: ContextEnvelope,
    charlie: ContextEnvelope,
) -> None:
    key = bank.write_memory(
        envelope=alice,
        scope=MemoryScope.TENANT,
        actor="a",
        content={"runbook": "restart"},
    )
    assert (
        bank.read_memory(envelope=charlie, target_key=key)["runbook"]
        == "restart"
    )


def test_agents_cannot_write_global_memory(
    bank: MemoryBankPartitioner, alice: ContextEnvelope
) -> None:
    with pytest.raises(PermissionError, match="E_MEMORY_WRITE_DENIED"):
        bank.write_memory(
            envelope=alice,
            scope=MemoryScope.GLOBAL,
            actor="a",
            content={"x": 1},
        )


# ---------------------------------------------------------------------------------------------
# RAG (#6, #11)
# ---------------------------------------------------------------------------------------------


def test_rag_returns_only_own_tenant_own_user_and_global(
    bank: MemoryBankPartitioner,
    alice: ContextEnvelope,
    charlie: ContextEnvelope,
    rs_admin: ContextEnvelope,
) -> None:
    vec = [1.0, 0.0, 0.0]
    bank.write_memory(
        envelope=alice,
        scope=MemoryScope.USER,
        actor="a",
        content={"who": "alice"},
        embedding=vec,
    )
    bank.write_memory(
        envelope=alice,
        scope=MemoryScope.TENANT,
        actor="t",
        content={"who": "fv"},
        embedding=vec,
    )
    bank.write_memory(
        envelope=rs_admin,
        scope=MemoryScope.TENANT,
        actor="t",
        content={"who": "rs"},
        embedding=vec,
    )
    bank.write_global(
        operator=mc.OperatorPrincipal(
            operator="op@cymbal.example", approved_by="rev@cymbal.example"
        ),
        actor="g",
        content={"who": "global"},
        embedding=vec,
    )

    seen = {
        hit["payload"]["who"]
        for hit in bank.retrieve_similar_memories_rag(
            envelope=charlie, query_embedding=vec, top_k=10
        )
    }
    assert seen == {"fv", "global"}


def test_11_rag_survives_a_bad_record_and_decrypts_only_what_it_returns(
    bank: MemoryBankPartitioner,
    wrapper: CountingWrapper,
    rs_admin: ContextEnvelope,
) -> None:
    alice = _env(FV, "alice@finvault.com")
    vec = [1.0, 0.0]
    for i in range(5):
        bank.write_memory(
            envelope=alice,
            scope=MemoryScope.USER,
            actor=f"a{i}",
            content={"i": i},
            embedding=vec,
        )
    for i in range(3):
        bank.write_memory(
            envelope=rs_admin,
            scope=MemoryScope.TENANT,
            actor=f"rs{i}",
            content={"rs": i},
            embedding=vec,
        )
    bad = bank.write_memory(
        envelope=alice,
        scope=MemoryScope.USER,
        actor="bad",
        content={"i": -1},
        embedding=vec,
    )
    bank._store[bad]["ciphertext_hex"] = "00" * 32
    hits = bank.retrieve_similar_memories_rag(
        envelope=alice, query_embedding=vec, top_k=2
    )
    assert len(hits) == 2
    # Decrypts only Alice's 6 candidate embeddings (never RetailStream's 3), and reuses the cached
    # DEKs when opening the top-2 payload ciphertexts (0 extra unwraps).
    assert wrapper.unwraps == 6
    assert (
        bank.retrieve_similar_memories_rag(
            envelope=alice, query_embedding=vec, top_k=-1
        )
        == []
    )


# ---------------------------------------------------------------------------------------------
# Side channels, encoding and exact key checks (#12, #13, #14)
# ---------------------------------------------------------------------------------------------


def test_denials_do_not_reveal_the_owner(
    bank: MemoryBankPartitioner,
    alice: ContextEnvelope,
    rs_admin: ContextEnvelope,
) -> None:
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.TENANT, actor="a", content={"x": 1}
    )
    with pytest.raises(PermissionError) as exc:
        bank.read_memory(envelope=rs_admin, target_key=key)
    assert FV not in str(exc.value)
    assert key not in str(exc.value)


def test_12_document_ids_are_injective() -> None:
    from agents.gcp_live_bridge import LiveFirestoreMemoryBank

    assert LiveFirestoreMemoryBank.doc_id_for(
        "a/b__c"
    ) != LiveFirestoreMemoryBank.doc_id_for("a__b/c")


def test_13_aad_encoding_is_unambiguous() -> None:
    a = mc.record_aad(tenant_id="t|x", user="", scope="tenant", key="k")
    b = mc.record_aad(tenant_id="t", user="x", scope="tenant", key="k")
    assert a != b


def test_14_platform_key_check_is_exact() -> None:
    other_project = mc.platform_global_key_name().replace(
        "projects/", "projects/evil-", 1
    )
    with pytest.raises(PermissionError):
        mc.assert_platform_key(other_project)


def test_platform_and_tenant_keys_share_one_project() -> None:
    project = TENANT_DIRECTORY[FV]["cmek_key_name"].split("/")[1]
    assert mc.platform_global_key_name().split("/")[1] == project


# ---------------------------------------------------------------------------------------------
# Live Firestore bank (hermetic: fake Firestore client, LocalKMS-backed crypto)
# ---------------------------------------------------------------------------------------------


class _FakeSnap:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class _FakeDoc:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store, self._id = store, doc_id

    def set(self, data: dict[str, Any]) -> None:
        self._store[self._id] = dict(data)

    def get(self) -> _FakeSnap:
        return _FakeSnap(self._store.get(self._id))


class _FakeFirestore:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def collection(self, _name: str) -> _FakeFirestore:
        return self

    def document(self, doc_id: str) -> _FakeDoc:
        return _FakeDoc(self.docs, doc_id)


@pytest.fixture
def live_bank(wrapper: CountingWrapper) -> Any:
    from agents.gcp_live_bridge import LiveFirestoreMemoryBank

    mc.set_memory_crypto(mc.MemoryCrypto(wrapper))
    bank = object.__new__(LiveFirestoreMemoryBank)
    bank.collection_name = "cymbal_memory_bank_v1"
    bank._client = _FakeFirestore()
    yield bank
    mc.set_memory_crypto(None)


def test_live_firestore_documents_hold_only_ciphertext_and_wrapped_keys(
    live_bank: Any, alice: ContextEnvelope, rs_admin: ContextEnvelope
) -> None:
    key = live_bank.write_memory(
        envelope=alice,
        scope=MemoryScope.SESSION,
        actor="a",
        content={"prompt": "IBAN DE89"},
    )
    (doc,) = live_bank._client.docs.values()
    assert doc["format"] == "v2"
    assert "cmek_key" not in doc
    assert "DE89" not in str(doc)
    assert "alice" not in str(doc)
    assert (
        live_bank.read_memory(envelope=alice, target_composite_key=key)[
            "prompt"
        ]
        == "IBAN DE89"
    )
    with pytest.raises(PermissionError, match="Cross-tenant"):
        live_bank.read_memory(envelope=rs_admin, target_composite_key=key)


def test_live_firestore_refuses_legacy_documents(
    live_bank: Any, alice: ContextEnvelope
) -> None:
    key = mc.build_memory_key(
        tenant_id=FV,
        sub=alice.security.sub,
        scope=MemoryScope.SESSION,
        session_id="sess-1",
        actor="a",
    )
    live_bank._client.docs[live_bank.doc_id_for(key)] = {
        "composite_key": key,
        "scope": "session",
        "cmek_key": "projects/p/locations/l/keyRings/r/cryptoKeys/k",
        "nonce_hex": "00",
        "ciphertext_hex": "00",
    }
    with pytest.raises(mc.LegacyMemoryFormatError):
        live_bank.read_memory(envelope=alice, target_composite_key=key)


# --- Re-review follow-ups ---------------------------------------------------------------------


def test_kms_layer_alone_denies_cross_tenant_unwrap(
    bank: MemoryBankPartitioner,
    wrapper: CountingWrapper,
    alice: ContextEnvelope,
    rs_admin: ContextEnvelope,
) -> None:
    """Skip every code check and ask (Local)KMS directly: RetailStream's SA is still refused."""
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.TENANT, actor="a", content={"x": 1}
    )
    record = mc.SealedRecord.from_storage(bank._store[key])
    with pytest.raises(PermissionError, match="E_KMS_IAM_DENIED"):
        wrapper.unwrap(
            envelope=rs_admin,
            kms_key_name=record.kms_key_name,
            wrapped=record.wrapped_dek,
            aad=mc.caller_aad(alice, key),
        )


def test_live_kms_without_envelope_refuses_tenant_keys() -> None:
    from agents.gcp_live_bridge import LiveCloudKMSCMEKVerifier

    kms = LiveCloudKMSCMEKVerifier(project_id="cymbal-multitenancy-example")
    for call in (kms.encrypt_for_tenant, kms.decrypt_for_tenant):
        arg = "plaintext" if call == kms.encrypt_for_tenant else "ciphertext"
        with pytest.raises(PermissionError, match="only the GLOBAL key"):
            call(
                kms_key_name=TENANT_DIRECTORY[FV]["cmek_key_name"],
                tenant_id=FV,
                **{arg: b"x"},
            )


@pytest.mark.parametrize(
    "bad", [["a", "b"], [float("nan"), 1.0], [True, False], []]
)
def test_malformed_embeddings_are_rejected_on_write(
    bank: MemoryBankPartitioner, alice: ContextEnvelope, bad: list[Any]
) -> None:
    with pytest.raises(ValueError, match="embedding"):
        bank.write_memory(
            envelope=alice,
            scope=MemoryScope.USER,
            actor="a",
            content={"x": 1},
            embedding=bad,
        )


def test_a_malformed_stored_vector_does_not_break_rag(
    bank: MemoryBankPartitioner, alice: ContextEnvelope
) -> None:
    vec = [1.0, 0.0]
    good = bank.write_memory(
        envelope=alice,
        scope=MemoryScope.USER,
        actor="g",
        content={"ok": 1},
        embedding=vec,
    )
    bad = bank.write_memory(
        envelope=alice,
        scope=MemoryScope.USER,
        actor="b",
        content={"ok": 0},
        embedding=vec,
    )
    bank._store[bad]["embedding"] = ["x", "y"]
    hits = bank.retrieve_similar_memories_rag(
        envelope=alice, query_embedding=vec
    )
    assert [h["key"] for h in hits] == [good]


def test_rag_tenant_label_comes_from_the_key(
    bank: MemoryBankPartitioner, alice: ContextEnvelope
) -> None:
    vec = [1.0, 0.0]
    key = bank.write_memory(
        envelope=alice,
        scope=MemoryScope.TENANT,
        actor="t",
        content={"x": 1},
        embedding=vec,
    )
    bank._store[key]["tenant_id"] = RS  # tampered label
    (hit,) = bank.retrieve_similar_memories_rag(
        envelope=alice, query_embedding=vec
    )
    assert hit["tenant_id"] == FV


def test_write_without_a_caller_is_an_access_denial(
    bank: MemoryBankPartitioner,
) -> None:
    for scope in (MemoryScope.TENANT, MemoryScope.GLOBAL):
        with pytest.raises(
            mc.MemoryAccessDenied, match="E_MEMORY_WRITE_DENIED"
        ):
            bank.write_memory(envelope=None, scope=scope, actor="a", content={"x": 1})  # type: ignore[arg-type]


def test_cache_hit_does_not_rebuild_the_cache(
    bank: MemoryBankPartitioner, alice: ContextEnvelope
) -> None:
    key = bank.write_memory(
        envelope=alice, scope=MemoryScope.USER, actor="a", content={"x": 1}
    )
    bank.read_memory(envelope=alice, target_key=key)
    cache_before = bank.crypto._cache
    bank.read_memory(envelope=alice, target_key=key)
    assert bank.crypto._cache is cache_before
