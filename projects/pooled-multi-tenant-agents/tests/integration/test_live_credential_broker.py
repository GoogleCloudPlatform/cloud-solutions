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

"""Live checks for the credential broker IAM move (ADR-0014 B4, rollout step 5).

Requires `RUN_LIVE_GCP_TESTS=1` and ADC for an operator who may impersonate both
`cymbal-pooled-runtime-sa` and `cymbal-broker-sa` (roles/iam.serviceAccountTokenCreator on them).
`CREDENTIAL_BROKER_URL` enables the service checks. `B4_STAGE4_DONE=1` enables the check that the
runtime SA can no longer mint tenant tokens (only true after step 4).

Each check calls Google APIs directly as the impersonated identity, so results are enforced by
Cloud IAM / Cloud Run IAM alone, not by application code.
"""

from __future__ import annotations

import base64
import os

import httpx
import pytest
from agents.context import TENANT_DIRECTORY
from agents.tenant_identity import tenant_service_account_email

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_GCP_TESTS") != "1",
    reason="Set RUN_LIVE_GCP_TESTS=1 to run against live GCP resources.",
)

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "cymbal-multitenancy-example")
RUNTIME_SA = f"cymbal-pooled-runtime-sa@{PROJECT}.iam.gserviceaccount.com"
BROKER_SA = f"cymbal-broker-sa@{PROJECT}.iam.gserviceaccount.com"
BROKER_URL = os.getenv("CREDENTIAL_BROKER_URL", "").rstrip("/")
FV, RS = "tenant-finvault-alpha", "tenant-retailstream-beta"
SCOPE = "https://www.googleapis.com/auth/cloud-platform"
IAM = "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts"


def _as(principal: str) -> str:
    """Access token for `principal`, impersonated from the operator's ADC."""
    import google.auth
    import google.auth.transport.requests
    from google.auth import impersonated_credentials

    source, _ = google.auth.default(scopes=[SCOPE])
    creds = impersonated_credentials.Credentials(
        source_credentials=source,
        target_principal=principal,
        target_scopes=[SCOPE],
        lifetime=300,
    )
    creds.refresh(google.auth.transport.requests.Request())
    return str(creds.token)


def _id_token_as(principal: str, audience: str) -> str:
    resp = httpx.post(
        f"{IAM}/{principal}:generateIdToken",
        headers={"Authorization": f"Bearer {_as_operator()}"},
        json={"audience": audience, "includeEmail": True},
        timeout=30,
    )
    resp.raise_for_status()
    return str(resp.json()["token"])


def _as_operator() -> str:
    import google.auth
    import google.auth.transport.requests

    creds, _ = google.auth.default(scopes=[SCOPE])
    creds.refresh(google.auth.transport.requests.Request())
    return str(creds.token)


def _mint_tenant_token(caller_token: str, tenant_id: str) -> httpx.Response:
    return httpx.post(
        f"{IAM}/{tenant_service_account_email(tenant_id, PROJECT)}:generateAccessToken",
        headers={"Authorization": f"Bearer {caller_token}"},
        json={"scope": [SCOPE], "lifetime": "300s"},
        timeout=30,
    )


@pytest.mark.skipif(
    os.getenv("B4_STAGE4_DONE") != "1", reason="only after step 4"
)
@pytest.mark.parametrize("tenant", [FV, RS])
def test_runtime_sa_can_no_longer_mint_tenant_tokens(tenant: str) -> None:
    assert _mint_tenant_token(_as(RUNTIME_SA), tenant).status_code == 403


@pytest.mark.parametrize("tenant", [FV, RS])
def test_broker_sa_can_mint_tenant_tokens(tenant: str) -> None:
    resp = _mint_tenant_token(_as(BROKER_SA), tenant)
    assert resp.status_code == 200, resp.text[:300]


@pytest.mark.parametrize(("own", "other"), [(FV, RS), (RS, FV)])
def test_broker_minted_tenant_token_still_cannot_cross_tenants(
    own: str, other: str
) -> None:
    tenant_token = _mint_tenant_token(_as(BROKER_SA), own).json()["accessToken"]
    key = str(TENANT_DIRECTORY[other]["cmek_key_name"])
    resp = httpx.post(
        f"https://cloudkms.googleapis.com/v1/{key}:encrypt",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={"plaintext": base64.b64encode(b"x").decode()},
        timeout=30,
    )
    assert resp.status_code == 403


@pytest.mark.skipif(not BROKER_URL, reason="set CREDENTIAL_BROKER_URL")
def test_broker_service_refuses_unauthenticated_and_non_runtime_callers() -> (
    None
):
    url = BROKER_URL + "/internal/v1/tenant-credential"
    assert httpx.post(
        url, json={"kind": "access_token"}, timeout=30
    ).status_code in (401, 403)
    broker_self = _id_token_as(
        BROKER_SA, BROKER_URL
    )  # a valid Google ID token, wrong identity
    resp = httpx.post(
        url,
        headers={"X-Serverless-Authorization": f"Bearer {broker_self}"},
        json={"kind": "access_token"},
        timeout=30,
    )
    assert (
        resp.status_code == 403
    )  # Cloud Run IAM: only the runtime SA has run.invoker


@pytest.mark.skipif(not BROKER_URL, reason="set CREDENTIAL_BROKER_URL")
def test_broker_service_refuses_runtime_sa_after_b5_or_missing_broker_token_pre_b5() -> (
    None
):
    runtime_id = _id_token_as(RUNTIME_SA, BROKER_URL)
    resp = httpx.post(
        BROKER_URL + "/internal/v1/tenant-credential",
        headers={"X-Serverless-Authorization": f"Bearer {runtime_id}"},
        json={"kind": "access_token"},
        timeout=30,
    )
    if os.getenv("B5_STAGE6_DONE", "1") == "1":
        # After B5 Stage 6 (broker_keep_runtime_caller = false), the gateway/runtime SA has neither
        # roles/run.invoker nor BROKER_ALLOWED_CALLERS on the credential broker; only per-agent
        # Cloud Run Agent Identity principals may invoke it.
        assert resp.status_code == 403
    else:
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"] == "E_BROKER_TOKEN_MISSING"
