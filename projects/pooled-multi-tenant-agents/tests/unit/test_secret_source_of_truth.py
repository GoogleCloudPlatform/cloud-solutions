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
# pylint: disable=missing-class-docstring,protected-access
# pylint: disable=redefined-outer-name,unused-argument
# pylint: disable=use-implicit-booleaness-not-comparison

"""Secrets have a single source of truth, and 3P connectors fail loudly on bad credentials.

- Live mode: connector secrets come only from Secret Manager (as the tenant's service account).
  A local `.env` can never shadow a rotated credential.
- Offline mode: `.env` remains available for the local sandbox.
- Jira Cloud answers bad Basic auth as an anonymous user (HTTP 200, zero issues), so the connector
  verifies `/myself` and raises `E_3P_CREDENTIALS_INVALID` instead of returning an empty result.
- If Secret Manager is unreachable in live mode, connectors raise `E_3P_SECRET_UNAVAILABLE`
  instead of silently falling back to simulated demo data.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from agents import gcp_live_bridge as bridge
from agents.context import TENANT_DIRECTORY, ContextEnvelope, EdgeAuthVerifier
from agents.tenant_credentials import TENANT_SECRET_IDS

FV = "tenant-finvault-alpha"
STALE = {
    "JIRA_API_TOKEN": "stale-local-token",
    "JIRA_BASE_URL": "https://example.atlassian.net",
}
FROM_SECRET_MANAGER = {
    "base_url": "https://example.atlassian.net",
    "email": "svc@example.com",
    "api_token": "rotated-token",
    "project_key": "FINVAULT",
    "tenant_id": FV,
}


def _secret_owner(secret_id: str) -> str:
    return next(t for t, ids in TENANT_SECRET_IDS.items() if secret_id in ids)


def _envelope(tenant_id: str = FV) -> ContextEnvelope:
    return EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims={
            "iss": str(TENANT_DIRECTORY[tenant_id]["iss"]),
            "sub": "alice@finvault.com",
            "tenant_id": tenant_id,
            "exp": int(time.time()) + 3600,
        },
        dpop_proof={"jkt": "jkt", "jti": f"dpop-{time.time_ns()}"},
    )


@pytest.fixture
def stale_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bridge._DotEnvHelper, "get_env_map", staticmethod(lambda: dict(STALE))
    )


def test_live_mode_ignores_dotenv_and_reads_secret_manager(
    monkeypatch: pytest.MonkeyPatch, stale_dotenv: None
) -> None:
    monkeypatch.setattr(bridge, "is_live_gcp_enabled", lambda: True)
    calls: list[str] = []

    def fake_access(
        *, envelope: ContextEnvelope, project_id: str, secret_id: str
    ) -> dict[str, str]:
        calls.append(secret_id)
        return dict(FROM_SECRET_MANAGER)

    monkeypatch.setattr(bridge, "access_tenant_secret", fake_access)
    cfg = bridge.LiveAtlassianJiraConnector()._load_secret_config(_envelope())
    assert cfg is not None
    assert cfg["api_token"] == "rotated-token"
    assert calls == ["cymbal-finvault-jira-credentials"]


def test_offline_mode_still_uses_dotenv_for_local_sandbox(
    monkeypatch: pytest.MonkeyPatch, stale_dotenv: None
) -> None:
    monkeypatch.setattr(bridge, "is_live_gcp_enabled", lambda: False)
    cfg = bridge.LiveAtlassianJiraConnector()._load_secret_config(_envelope())
    assert cfg is not None
    assert cfg["api_token"] == "stale-local-token"


def test_entra_live_mode_ignores_env_client_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "is_live_gcp_enabled", lambda: True)
    monkeypatch.setenv("AZURE_ENTRA_CLIENT_SECRET", "stale-local-secret")
    assert bridge.LiveMicrosoftEntraOIDCConnector().client_secret == ""


class _Resp:
    def __init__(
        self, status: int, payload: dict[str, Any] | None = None
    ) -> None:
        self.status_code = status
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def _jira_with_config() -> bridge.LiveAtlassianJiraConnector:
    jira = bridge.LiveAtlassianJiraConnector()
    jira._cached_config = dict(FROM_SECRET_MANAGER)
    return jira


def test_jira_raises_on_invalid_credentials_instead_of_empty_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    searched: list[str] = []
    monkeypatch.setattr(httpx, "get", lambda url, headers, timeout: _Resp(401))
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: searched.append(url) or _Resp(200, {"issues": []}),
    )
    with pytest.raises(PermissionError, match="E_3P_CREDENTIALS_INVALID"):
        _jira_with_config().query_regulatory_issues(envelope=_envelope())
    assert searched == []


def test_jira_verifies_credentials_once_then_searches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    gets: list[str] = []

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> _Resp:
        gets.append(url)
        return _Resp(200, {"accountId": "x"})

    issue = {
        "key": "FINVAULT-1",
        "fields": {"summary": "Audit", "status": {"name": "To Do"}},
    }
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _Resp(200, {"issues": [issue]})
    )
    jira = _jira_with_config()
    env = _envelope()
    first = jira.query_regulatory_issues(envelope=env)
    jira.query_regulatory_issues(envelope=env)
    assert [i["key"] for i in first["issues"]] == ["FINVAULT-1"]
    assert gets == ["https://example.atlassian.net/rest/api/3/myself"]


def _secret_manager_outage(
    *, envelope: ContextEnvelope, project_id: str, secret_id: str
) -> dict:
    raise ConnectionError("secretmanager.googleapis.com unreachable")


@pytest.mark.parametrize(
    "connector_cls",
    [bridge.LiveAtlassianJiraConnector, bridge.LiveServiceNowITOMConnector],
)
def test_live_mode_secret_outage_fails_loudly_instead_of_simulating(
    monkeypatch: pytest.MonkeyPatch, connector_cls: type
) -> None:
    """A Secret Manager outage must not silently degrade a live connector to demo data."""
    monkeypatch.setattr(bridge, "is_live_gcp_enabled", lambda: True)
    monkeypatch.setattr(bridge, "access_tenant_secret", _secret_manager_outage)
    connector = connector_cls()
    owner = _secret_owner(connector.SECRET_ID)
    with pytest.raises(
        bridge.ConnectorSecretUnavailableError, match="E_3P_SECRET_UNAVAILABLE"
    ):
        connector._load_secret_config(_envelope(owner))


def test_live_mode_isolation_denial_still_raises_permission_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny(
        *, envelope: ContextEnvelope, project_id: str, secret_id: str
    ) -> dict:
        raise PermissionError("403 Forbidden: cross-tenant secret")

    monkeypatch.setattr(bridge, "is_live_gcp_enabled", lambda: True)
    monkeypatch.setattr(bridge, "access_tenant_secret", deny)
    with pytest.raises(PermissionError, match="403 Forbidden"):
        bridge.LiveAtlassianJiraConnector()._load_secret_config(_envelope())


def test_entra_live_mode_secret_outage_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "is_live_gcp_enabled", lambda: True)
    monkeypatch.setattr(bridge, "access_tenant_secret", _secret_manager_outage)
    entra = bridge.LiveMicrosoftEntraOIDCConnector()
    with pytest.raises(bridge.ConnectorSecretUnavailableError):
        entra._ensure_client_secret(_envelope("tenant-retailstream-beta"))


def test_entra_live_mode_rejects_secret_without_client_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "is_live_gcp_enabled", lambda: True)
    monkeypatch.setattr(
        bridge, "access_tenant_secret", lambda **_: {"client_id": "x"}
    )
    entra = bridge.LiveMicrosoftEntraOIDCConnector()
    with pytest.raises(
        bridge.ConnectorSecretUnavailableError, match="client_secret"
    ):
        entra._ensure_client_secret(_envelope("tenant-retailstream-beta"))


@pytest.mark.parametrize(
    "connector_cls",
    [bridge.LiveAtlassianJiraConnector, bridge.LiveServiceNowITOMConnector],
)
def test_warm_secret_cache_is_never_returned_to_another_tenant(
    connector_cls: type,
) -> None:
    """Review follow-up: the tenant policy runs before the cache, not only in public methods."""
    connector = connector_cls()
    connector._cached_config = {
        "api_token": "warm-cache",
        "password": "warm-cache",
    }
    owner = (
        "tenant-finvault-alpha"
        if connector_cls is bridge.LiveAtlassianJiraConnector
        else ("tenant-retailstream-beta")
    )
    other = (
        "tenant-retailstream-beta"
        if owner == "tenant-finvault-alpha"
        else "tenant-finvault-alpha"
    )
    assert connector._load_secret_config(_envelope(owner)) is not None
    with pytest.raises(PermissionError):
        connector._load_secret_config(_envelope(other))


def test_loaded_entra_secret_is_not_reused_for_another_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "is_live_gcp_enabled", lambda: True)
    entra = bridge.LiveMicrosoftEntraOIDCConnector()
    entra.client_secret = "already-loaded"
    with pytest.raises(PermissionError):
        entra._ensure_client_secret(_envelope("tenant-finvault-alpha"))
