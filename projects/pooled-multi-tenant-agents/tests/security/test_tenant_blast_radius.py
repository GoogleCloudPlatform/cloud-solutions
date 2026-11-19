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
# pylint: disable=missing-class-docstring,redefined-outer-name,unused-argument

"""Blast-radius containment tests (ADR-0010).

Proves, without cloud access, that a compromised tenant identity or credential reaches at most
its own tenant:
- the per-tenant service account formula matches Terraform;
- the policy grants each tenant only its own key, secrets, and runbook prefix (blast radius = 1);
- an IAM-enforcing KMS stand-in denies every cross-tenant use of a key;
- credentials are minted only from a verified envelope and cached per tenant;
- live connectors reject cross-tenant resources before any network call, and use the tenant's
  credential when allowed;
- Terraform removes the shared identity's project-wide KMS/Secret Manager/Storage roles and mirrors
  the Python policy.
"""

from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from agents import gcp_live_bridge as bridge
from agents.context import (
    TENANT_DIRECTORY,
    ContextEnvelope,
    EdgeAuthVerifier,
    register_tenant,
    reset_dynamic_tenants,
)
from agents.tenant_credentials import (
    TENANT_SECRET_IDS,
    LocalKMS,
    LocalTenantCredentialBackend,
    TenantCredentialBroker,
    TenantIsolationPolicy,
    TenantScopedCredential,
    describe_blast_radius,
    set_default_broker,
    tenant_service_account_email,
    tenant_service_account_id,
)

PROJECT = bridge.get_clean_project_id(bridge.DEFAULT_GCP_PROJECT)
FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
TF_DIR = Path(__file__).resolve().parents[2] / "terraform"


def _envelope(tenant_id: str, sub: str = "user@example.com") -> ContextEnvelope:
    return EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims={
            "iss": str(TENANT_DIRECTORY[tenant_id]["iss"]),
            "sub": sub,
            "tenant_id": tenant_id,
            "exp": int(time.time()) + 3600,
        },
        dpop_proof={"jkt": f"jkt-{tenant_id}", "jti": f"dpop-{time.time_ns()}"},
    )


@pytest.fixture
def policy() -> TenantIsolationPolicy:
    return TenantIsolationPolicy(project_id=PROJECT)


@pytest.fixture
def broker() -> Iterator[TenantCredentialBroker]:
    b = TenantCredentialBroker(
        project_id=PROJECT, backend=LocalTenantCredentialBackend()
    )
    set_default_broker(b)
    yield b
    set_default_broker(None)


@pytest.fixture
def many_tenants() -> Iterator[list[str]]:
    ids = [f"tenant-pooled-{i:03d}" for i in range(25)]
    for t in ids:
        register_tenant(tenant_id=t, display_name=t)
    yield ids
    reset_dynamic_tenants()


# ---------------------------------------------------------------------------------------------
# Identity naming
# ---------------------------------------------------------------------------------------------


def test_tenant_service_account_ids_match_terraform_formula() -> None:
    # Values produced by `terraform console`: substr(sha256(t), 0, 24)
    assert tenant_service_account_id(FV) == "ct-0d87c6dd05045f2ced242032"
    assert tenant_service_account_id(RS) == "ct-3e6202600efbbf0fd09338de"


def test_tenant_service_account_ids_are_valid_and_unique(
    many_tenants: list[str],
) -> None:
    ids = {tenant_service_account_id(t) for t in TENANT_DIRECTORY}
    assert len(ids) == len(TENANT_DIRECTORY)
    for sa_id in ids:
        assert re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", sa_id)
    assert tenant_service_account_email(FV, PROJECT).endswith(
        f"@{PROJECT}.iam.gserviceaccount.com"
    )


@pytest.mark.parametrize("bad", ["", " tenant-x", "tenant-x ", "tenant\x00x"])
def test_tenant_service_account_id_rejects_malformed_tenant(bad: str) -> None:
    with pytest.raises(ValueError, match="E_INVALID_TENANT_ID"):
        tenant_service_account_id(bad)


# ---------------------------------------------------------------------------------------------
# Policy: blast radius = exactly one tenant
# ---------------------------------------------------------------------------------------------


def test_each_tenant_is_granted_only_its_own_resources(
    policy: TenantIsolationPolicy,
) -> None:
    fv = policy.grants_for(FV)
    rs = policy.grants_for(RS)
    assert fv.kms_keys == {TENANT_DIRECTORY[FV]["cmek_key_name"]}
    assert fv.secret_ids == set(TENANT_SECRET_IDS[FV])
    assert fv.object_prefixes == {(policy.runbook_bucket, f"{FV}/")}
    assert not (fv.kms_keys & rs.kms_keys)
    assert not (fv.secret_ids & rs.secret_ids)
    assert not (fv.object_prefixes & rs.object_prefixes)


def test_blast_radius_is_one_tenant_for_every_tenant(
    policy: TenantIsolationPolicy, many_tenants: list[str]
) -> None:
    report = describe_blast_radius(policy)
    assert len(report) == len(TENANT_DIRECTORY) >= 27
    for tenant_id, reached in report.items():
        assert reached == [tenant_id], f"{tenant_id} can reach {reached}"


def test_each_kms_key_is_usable_by_exactly_its_owner(
    policy: TenantIsolationPolicy, many_tenants: list[str]
) -> None:
    for tenant_id, meta in TENANT_DIRECTORY.items():
        assert policy.tenants_with_kms_access(str(meta["cmek_key_name"])) == {
            tenant_id
        }


@pytest.mark.parametrize(("caller", "owner"), [(FV, RS), (RS, FV)])
def test_policy_denies_cross_tenant_key_secret_and_object(
    policy: TenantIsolationPolicy, caller: str, owner: str
) -> None:
    with pytest.raises(
        PermissionError, match="E_TENANT_RESOURCE_SCOPE_VIOLATION"
    ):
        policy.assert_kms_key(
            caller, str(TENANT_DIRECTORY[owner]["cmek_key_name"])
        )
    for secret_id in TENANT_SECRET_IDS[owner]:
        with pytest.raises(
            PermissionError, match="E_TENANT_RESOURCE_SCOPE_VIOLATION"
        ):
            policy.assert_secret(caller, secret_id)
    with pytest.raises(
        PermissionError, match="E_TENANT_RESOURCE_SCOPE_VIOLATION"
    ):
        policy.assert_object(
            caller, policy.runbook_bucket, f"{owner}/runbook.md"
        )


def test_policy_allows_key_versions_but_rejects_path_traversal(
    policy: TenantIsolationPolicy,
) -> None:
    key = str(TENANT_DIRECTORY[FV]["cmek_key_name"])
    policy.assert_kms_key(FV, f"{key}/cryptoKeyVersions/3")
    with pytest.raises(PermissionError):
        policy.assert_kms_key(FV, f"{key}-evil")
    with pytest.raises(PermissionError, match="Path traversal"):
        policy.assert_object(
            FV, policy.runbook_bucket, f"{FV}/../{RS}/runbook.md"
        )
    with pytest.raises(PermissionError):
        policy.assert_object(FV, "some-other-bucket", f"{FV}/runbook.md")


def test_policy_rejects_unknown_tenant(policy: TenantIsolationPolicy) -> None:
    with pytest.raises(PermissionError, match="E_TENANT_NOT_ONBOARDED"):
        policy.grants_for("tenant-does-not-exist")


# ---------------------------------------------------------------------------------------------
# IAM-enforcing KMS: a compromised credential cannot use another tenant's key
# ---------------------------------------------------------------------------------------------


def test_kms_cross_tenant_matrix(
    policy: TenantIsolationPolicy,
    broker: TenantCredentialBroker,
    many_tenants: list[str],
) -> None:
    kms = LocalKMS(policy)
    sample = [FV, RS, *many_tenants[:4]]
    creds = {t: broker.credential_for(_envelope(t)) for t in sample}
    sealed = {
        t: kms.encrypt(
            kms_key_name=str(TENANT_DIRECTORY[t]["cmek_key_name"]),
            plaintext=f"CANARY-{t}".encode(),
            aad=t.encode(),
            credential=creds[t],
        )
        for t in sample
    }
    for owner in sample:
        key = str(TENANT_DIRECTORY[owner]["cmek_key_name"])
        assert (
            kms.decrypt(
                kms_key_name=key,
                ciphertext=sealed[owner],
                aad=owner.encode(),
                credential=creds[owner],
            )
            == f"CANARY-{owner}".encode()
        )
        for attacker in sample:
            if attacker == owner:
                continue
            with pytest.raises(PermissionError, match="E_KMS_IAM_DENIED"):
                kms.decrypt(
                    kms_key_name=key,
                    ciphertext=sealed[owner],
                    aad=owner.encode(),
                    credential=creds[attacker],
                )


def test_kms_denies_shared_identity_without_tenant_credential(
    policy: TenantIsolationPolicy,
) -> None:
    kms = LocalKMS(policy)
    with pytest.raises(PermissionError, match="E_KMS_IAM_DENIED"):
        kms.encrypt(
            kms_key_name=str(TENANT_DIRECTORY[FV]["cmek_key_name"]),
            plaintext=b"x",
            aad=b"x",
            credential=None,
        )


def test_kms_denies_forged_credential_claiming_another_tenant(
    policy: TenantIsolationPolicy,
) -> None:
    kms = LocalKMS(policy)
    forged = TenantScopedCredential(
        tenant_id=FV,
        principal=tenant_service_account_email(RS, PROJECT),
        token="stolen",
        expires_at=time.time() + 60,
    )
    with pytest.raises(PermissionError, match="E_KMS_IAM_DENIED"):
        kms.encrypt(
            kms_key_name=str(TENANT_DIRECTORY[FV]["cmek_key_name"]),
            plaintext=b"x",
            aad=b"x",
            credential=forged,
        )


def test_kms_rejects_aad_mismatch(
    policy: TenantIsolationPolicy, broker: TenantCredentialBroker
) -> None:
    kms = LocalKMS(policy)
    cred = broker.credential_for(_envelope(FV))
    key = str(TENANT_DIRECTORY[FV]["cmek_key_name"])
    ct = kms.encrypt(
        kms_key_name=key, plaintext=b"secret", aad=FV.encode(), credential=cred
    )
    with pytest.raises(PermissionError, match="E_KMS_DECRYPT_FAILED"):
        kms.decrypt(
            kms_key_name=key, ciphertext=ct, aad=RS.encode(), credential=cred
        )


# ---------------------------------------------------------------------------------------------
# Credential broker
# ---------------------------------------------------------------------------------------------


def test_broker_mints_tenant_principal_from_envelope_and_caches(
    broker: TenantCredentialBroker,
) -> None:
    fv_env, rs_env = _envelope(FV), _envelope(RS)
    fv1 = broker.credential_for(fv_env)
    fv2 = broker.credential_for(_envelope(FV, sub="other-user@finvault.com"))
    rs1 = broker.credential_for(rs_env)
    assert fv1.principal == tenant_service_account_email(FV, PROJECT)
    assert rs1.principal == tenant_service_account_email(RS, PROJECT)
    assert fv1 is fv2
    assert fv1.token != rs1.token
    assert broker.headers_for(rs_env)["Authorization"] == f"Bearer {rs1.token}"


def test_broker_refreshes_before_expiry() -> None:
    now = [1_000.0]
    backend = LocalTenantCredentialBackend(clock=lambda: now[0])
    b = TenantCredentialBroker(
        project_id=PROJECT,
        backend=backend,
        lifetime_seconds=300,
        clock=lambda: now[0],
    )
    first = b.credential_for(_envelope(FV))
    now[0] += 200  # inside the 60s refresh margin
    assert b.credential_for(_envelope(FV)) is first
    now[0] += 50
    assert b.credential_for(_envelope(FV)) is not first
    assert len(backend.minted) == 2


def test_broker_requires_verified_envelope(
    broker: TenantCredentialBroker,
) -> None:
    with pytest.raises(PermissionError, match="E_UNVERIFIED_ENVELOPE"):
        broker.credential_for({"tenant_id": FV})  # type: ignore[arg-type]


def test_broker_rejects_offboarded_tenant(
    broker: TenantCredentialBroker,
) -> None:
    register_tenant(tenant_id="tenant-offboarded", display_name="gone")
    env = _envelope("tenant-offboarded")
    reset_dynamic_tenants()
    with pytest.raises(PermissionError, match="E_TENANT_NOT_ONBOARDED"):
        broker.credential_for(env)


def test_broker_rejects_backend_that_mints_wrong_principal() -> None:
    class EvilBackend:
        def mint(
            self, *, tenant_id: str, principal: str, lifetime_seconds: int
        ) -> TenantScopedCredential:
            return TenantScopedCredential(
                tenant_id=RS,
                principal=principal,
                token="x",
                expires_at=time.time() + 300,
            )

    b = TenantCredentialBroker(project_id=PROJECT, backend=EvilBackend())
    with pytest.raises(PermissionError, match="E_CREDENTIAL_TENANT_MISMATCH"):
        b.credential_for(_envelope(FV))


@pytest.mark.parametrize("lifetime", [10, 7200])
def test_broker_enforces_short_lifetime(lifetime: int) -> None:
    with pytest.raises(ValueError, match="E_CREDENTIAL_LIFETIME"):
        TenantCredentialBroker(
            project_id=PROJECT,
            backend=LocalTenantCredentialBackend(),
            lifetime_seconds=lifetime,
        )


# ---------------------------------------------------------------------------------------------
# Live connectors: policy check before network, tenant credential on the wire
# ---------------------------------------------------------------------------------------------


class _Resp:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        text: str = "",
        status: int = 200,
    ):
        self._payload = payload or {}
        self.text = text
        self.status_code = status

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


@pytest.fixture
def http_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    import httpx

    calls: list[dict[str, Any]] = []

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, Any], timeout: float
    ) -> _Resp:
        calls.append({"method": "POST", "url": url, "headers": headers})
        return _Resp({"ciphertext": base64.b64encode(b"ct").decode()})

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> _Resp:
        calls.append({"method": "GET", "url": url, "headers": headers})
        if "secretmanager" in url:
            data = base64.b64encode(
                json_module.dumps({"api_token": "t"}).encode()
            ).decode()
            return _Resp({"payload": {"data": data}})
        if url.endswith("?alt=media"):
            return _Resp(text="Runbook: restart the settlement worker.")
        return _Resp(
            {
                "name": "obj",
                "kmsKeyName": f"{TENANT_DIRECTORY[FV]['cmek_key_name']}/cryptoKeyVersions/1",
            }
        )

    json_module = json
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.delenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", raising=False)
    return calls


def test_kms_verifier_blocks_other_tenants_key_before_network(
    broker: TenantCredentialBroker, http_calls: list[dict[str, Any]]
) -> None:
    kms = bridge.LiveCloudKMSCMEKVerifier(project_id=PROJECT)
    with pytest.raises(
        PermissionError, match="E_TENANT_RESOURCE_SCOPE_VIOLATION"
    ):
        kms.encrypt_for_tenant(
            kms_key_name=str(TENANT_DIRECTORY[RS]["cmek_key_name"]),
            tenant_id=FV,
            plaintext=b"x",
            envelope=_envelope(FV),
        )
    with pytest.raises(
        PermissionError, match="E_TENANT_RESOURCE_SCOPE_VIOLATION"
    ):
        kms.encrypt_for_tenant(
            kms_key_name=str(TENANT_DIRECTORY[FV]["cmek_key_name"]),
            tenant_id=RS,
            plaintext=b"x",
            envelope=_envelope(FV),
        )
    assert http_calls == []


def test_kms_verifier_uses_tenant_credential(
    broker: TenantCredentialBroker, http_calls: list[dict[str, Any]]
) -> None:
    env = _envelope(FV)
    bridge.LiveCloudKMSCMEKVerifier(project_id=PROJECT).encrypt_for_tenant(
        kms_key_name=str(TENANT_DIRECTORY[FV]["cmek_key_name"]),
        tenant_id=FV,
        plaintext=b"x",
        envelope=env,
    )
    assert len(http_calls) == 1
    assert (
        http_calls[0]["headers"]["Authorization"]
        == f"Bearer {broker.credential_for(env).token}"
    )
    assert (
        tenant_service_account_id(FV)
        in http_calls[0]["headers"]["Authorization"]
    )


def test_secret_access_is_tenant_scoped(
    broker: TenantCredentialBroker, http_calls: list[dict[str, Any]]
) -> None:
    with pytest.raises(
        PermissionError, match="E_TENANT_RESOURCE_SCOPE_VIOLATION"
    ):
        bridge.access_tenant_secret(
            envelope=_envelope(RS),
            project_id=PROJECT,
            secret_id=TENANT_SECRET_IDS[FV][0],
        )
    assert http_calls == []

    env = _envelope(FV)
    cfg = bridge.access_tenant_secret(
        envelope=env, project_id=PROJECT, secret_id=TENANT_SECRET_IDS[FV][0]
    )
    assert cfg == {"api_token": "t"}
    assert (
        http_calls[0]["headers"]["Authorization"]
        == f"Bearer {broker.credential_for(env).token}"
    )


def test_runbook_vault_blocks_traversal_and_uses_tenant_credential(
    broker: TenantCredentialBroker, http_calls: list[dict[str, Any]]
) -> None:
    vault = bridge.LiveGCSCMEKRunbookVault(project_id=PROJECT)
    env = _envelope(FV)
    with pytest.raises(PermissionError, match="Path traversal"):
        vault.read_tenant_runbook(
            envelope=env, target_object_path=f"{FV}/../{RS}/secret.md"
        )
    assert http_calls == []

    result = vault.read_tenant_runbook(
        envelope=env, target_object_path=f"{FV}/runbook.md"
    )
    assert result["tenant_id"] == FV
    token = broker.credential_for(env).token
    assert {c["headers"]["Authorization"] for c in http_calls} == {
        f"Bearer {token}"
    }


def test_escape_hatch_falls_back_to_shared_identity_only_when_disabled(
    broker: TenantCredentialBroker,
    http_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CYMBAL_TENANT_SCOPED_CREDENTIALS", "0")
    monkeypatch.setattr(
        bridge,
        "_legacy_adc_headers",
        lambda project_id: {"Authorization": "Bearer shared-adc"},
    )
    bridge.LiveCloudKMSCMEKVerifier(project_id=PROJECT).encrypt_for_tenant(
        kms_key_name=str(TENANT_DIRECTORY[FV]["cmek_key_name"]),
        tenant_id=FV,
        plaintext=b"x",
        envelope=_envelope(FV),
    )
    assert http_calls[0]["headers"]["Authorization"] == "Bearer shared-adc"


# ---------------------------------------------------------------------------------------------
# Terraform mirrors the policy and removes project-wide data roles from the shared identity
# ---------------------------------------------------------------------------------------------

_DATA_ROLES = (
    "roles/cloudkms.cryptoKeyEncrypterDecrypter",
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin",
)


def _tf(name: str) -> str:
    return (TF_DIR / name).read_text(encoding="utf-8")


def _block(text: str, start_marker: str) -> str:
    start = text.index(start_marker)
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"unterminated block {start_marker}")


def test_shared_gateway_identity_has_no_project_wide_data_roles() -> None:
    roles_block = _block(
        _tf("modules/platform_core/iap_gateway.tf"),
        "runtime_project_roles = setunion(",
    )
    for role in _DATA_ROLES:
        assert role not in roles_block


def test_no_project_level_binding_grants_tenant_data_roles() -> None:
    for tf in (p for p in TF_DIR.rglob("*.tf") if ".terraform" not in p.parts):
        text = tf.read_text(encoding="utf-8")
        for match in re.finditer(
            r'resource "google_project_iam_member" "[^"]+"', text
        ):
            block = _block(text, match.group(0))
            for role in _DATA_ROLES:
                assert role not in block, f"{tf.name}: project-level {role}"


def test_bigquery_row_access_policies_include_tenant_identities() -> None:
    bq = _block(
        _tf("modules/tenant/main.tf"),
        'resource "google_bigquery_row_access_policy" "tenant"',
    )
    assert "filter_predicate = \"tenant_id = '${var.tenant_id}'\"" in bq
    assert "google_service_account.tenant.email" in bq
    # One tenant module instance per tenant: the policy can only ever name its own tenant.
    assert "for_each = local.tenants" in _tf("main.tf")
    assert "tenant_id               = each.key" in _tf("main.tf")


def test_pooled_runbook_bucket_has_no_single_tenant_default_key() -> None:
    bucket = _block(
        _tf("modules/platform_core/alloydb.tf"),
        'resource "google_storage_bucket" "pooled_cmek_runbooks"',
    )
    assert "default_kms_key_name" not in bucket


def test_terraform_tenant_identities_mirror_python_policy() -> None:
    tf = _tf("modules/tenant/main.tf")
    assert 'account_id   = "ct-${substr(sha256(var.tenant_id), 0, 24)}"' in tf
    for resource in (
        'resource "google_kms_crypto_key_iam_member" "tenant_key_user"',
        'resource "google_secret_manager_secret_iam_member" "tenant_secret_accessor"',
        'resource "google_storage_managed_folder_iam_member" "tenant_runbooks_reader"',
        'resource "google_service_account_iam_member" "gateway_impersonates_tenant"',
        'resource "google_bigquery_table_iam_member" "tenant_spans_reader"',
    ):
        assert resource in tf

    # Tenants and their secrets come from the same YAML the Python policy loads.
    tenants_tf = _tf("tenants.tf")
    assert "yamldecode(file(" in tenants_tf
    assert "secret_ids    = try(cfg.secret_ids, [])" in tenants_tf
    assert (
        "secret_ids              = var.enable_3p_connectors ? each.value.secret_ids : []"
        in _tf("main.tf")
    )
    for tenant_id, expected_secret_ids in TENANT_SECRET_IDS.items():
        cfg = (
            TF_DIR.parent
            / "config"
            / "tenants"
            / "sandbox"
            / f"{tenant_id}.yaml"
        ).read_text()
        for secret_id in expected_secret_ids:
            assert secret_id in cfg
