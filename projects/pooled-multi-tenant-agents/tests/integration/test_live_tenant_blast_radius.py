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
# pylint: disable=redefined-outer-name

"""Live blast-radius verification (ADR-0010) against `cymbal-multitenancy-example`.

Requires `RUN_LIVE_GCP_TESTS=1`, ADC for a principal holding `roles/iam.serviceAccountTokenCreator`
on the tenant service accounts, and the per-tenant grants from `terraform/tenant_isolation.tf`.

Each check impersonates a tenant service account and calls Google APIs **directly**, bypassing the
application's policy check, so the denials below are enforced by Cloud IAM alone.
"""

from __future__ import annotations

import base64
import os
import time
from collections.abc import Callable

import httpx
import pytest
from agents.context import TENANT_DIRECTORY
from agents.tenant_credentials import (
    TENANT_SECRET_IDS,
    ImpersonatedTenantCredentialBackend,
    TenantScopedCredential,
    tenant_service_account_email,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_GCP_TESTS") != "1",
    reason="Set RUN_LIVE_GCP_TESTS=1 to run against live GCP resources.",
)

# Same as agents/gcp_live_bridge.py: use sandbox ADC without workstation mTLS client certs.
os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "cymbal-multitenancy-example")
BUCKET = os.getenv("RUNBOOK_BUCKET_NAME", f"{PROJECT}-runbooks")
FV, RS = "tenant-finvault-alpha", "tenant-retailstream-beta"
RUNBOOK = {
    FV: f"{FV}/DOC-FV-SEC-17A4-2026.md",
    RS: f"{RS}/ROA-2026-8812.md",
}


def _key(tenant_id: str) -> str:
    return str(TENANT_DIRECTORY[tenant_id]["cmek_key_name"])


@pytest.fixture(scope="module")
def creds() -> dict[str, TenantScopedCredential]:
    backend = ImpersonatedTenantCredentialBackend()
    return {
        t: backend.mint(
            tenant_id=t,
            principal=tenant_service_account_email(t, PROJECT),
            lifetime_seconds=600,
        )
        for t in (FV, RS)
    }


def _retry_status(
    call: Callable[[], httpx.Response], want: int, attempts: int = 12
) -> int:
    """IAM grants can take a few minutes to propagate; retry until the expected status appears."""
    status = 0
    for _ in range(attempts):
        status = call().status_code
        if status == want:
            return status
        time.sleep(10)
    return status


def _kms_encrypt(
    cred: TenantScopedCredential, key: str, aad: str
) -> httpx.Response:
    return httpx.post(
        f"https://cloudkms.googleapis.com/v1/{key}:encrypt",
        headers=cred.bearer_headers(PROJECT),
        json={
            "plaintext": base64.b64encode(b"CANARY").decode(),
            "additionalAuthenticatedData": base64.b64encode(
                aad.encode()
            ).decode(),
        },
        timeout=20.0,
    )


def _secret(cred: TenantScopedCredential, secret_id: str) -> httpx.Response:
    return httpx.get(
        f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/{secret_id}"
        "/versions/latest:access",
        headers=cred.bearer_headers(PROJECT),
        timeout=20.0,
    )


def _object(cred: TenantScopedCredential, path: str) -> httpx.Response:
    from urllib.parse import quote

    return httpx.get(
        f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{quote(path, safe='')}",
        headers=cred.bearer_headers(PROJECT),
        timeout=20.0,
    )


def test_impersonated_credentials_are_tenant_service_accounts(
    creds: dict[str, TenantScopedCredential],
) -> None:
    """The minted token belongs to the tenant service account (matched by its numeric uniqueId)."""
    import google.auth
    import google.auth.transport.requests

    admin, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    admin.refresh(google.auth.transport.requests.Request())
    for tenant_id, cred in creds.items():
        email = tenant_service_account_email(tenant_id, PROJECT)
        sa = httpx.get(
            f"https://iam.googleapis.com/v1/projects/-/serviceAccounts/{email}",
            headers={"Authorization": f"Bearer {admin.token}"},
            timeout=20.0,
        ).json()
        info = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": cred.token},
            timeout=20.0,
        ).json()
        assert info.get("azp") == sa["uniqueId"]


@pytest.mark.parametrize("owner", [FV, RS])
def test_tenant_can_use_its_own_key_secret_and_runbook(
    creds: dict[str, TenantScopedCredential], owner: str
) -> None:
    cred = creds[owner]
    assert (
        _retry_status(lambda: _kms_encrypt(cred, _key(owner), owner), 200)
        == 200
    )
    for secret_id in TENANT_SECRET_IDS[owner]:
        assert _retry_status(lambda s=secret_id: _secret(cred, s), 200) == 200
    assert _retry_status(lambda: _object(cred, RUNBOOK[owner]), 200) == 200


@pytest.mark.parametrize(("attacker", "victim"), [(FV, RS), (RS, FV)])
def test_iam_denies_cross_tenant_key_secret_and_runbook(
    creds: dict[str, TenantScopedCredential], attacker: str, victim: str
) -> None:
    cred = creds[attacker]
    assert _kms_encrypt(cred, _key(victim), victim).status_code == 403
    for secret_id in TENANT_SECRET_IDS[victim]:
        assert _secret(cred, secret_id).status_code == 403
    assert _object(cred, RUNBOOK[victim]).status_code == 403
