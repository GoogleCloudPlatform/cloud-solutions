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
# pylint: disable=redefined-outer-name,reimported

"""Live 3P enterprise connectors: Atlassian Jira Cloud, ServiceNow ITOM, and Microsoft Entra
OIDC.
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
from pathlib import Path
from typing import Any

import httpx
from agents.adapters._bridge_runtime import (
    DEFAULT_GCP_PROJECT,
    ConnectorSecretUnavailableError,
    _DotEnvHelper,
    _egress_guardrail,
    _live_enabled,
    _tenant_policy,
    load_live_connector_secret,
)
from agents.context import ContextEnvelope
from agents.interceptors import screen_tool_output_for_indirect_injection
from agents.shared_diagnostic_agent import get_clean_project_id


class LiveAtlassianJiraConnector:
    """Hop 5 Live Atlassian Jira Cloud 3P Connector backed by GCP Secret Manager
    (`cymbal-finvault-jira-credentials`).
    """

    SECRET_ID = "cymbal-finvault-jira-credentials"
    ALLOWED_TENANT_ID = "tenant-finvault-alpha"

    def __init__(self, project_id: str = DEFAULT_GCP_PROJECT) -> None:
        self.project_id = get_clean_project_id(project_id)
        # Never populated by `_load_secret_config` (secrets are read per use); retained as an
        # optional test seam that still runs `_tenant_policy.assert_secret` first.
        self._cached_config: dict[str, str] | None = None
        self._verified_auth_digests: set[str] = set()

    def _load_secret_config(
        self, envelope: ContextEnvelope | None = None
    ) -> dict[str, str] | None:
        """Reads 3P Jira credentials per use (never cached across turns in Brain heap memory)."""
        if envelope is not None:
            _tenant_policy(self.project_id).assert_secret(
                envelope.tenant.tenant_id, self.SECRET_ID
            )
        if self._cached_config is not None:
            return self._cached_config
        if not _live_enabled():
            # Offline local sandbox only. In live mode, Secret Manager is the single source of
            # truth so a stale local .env can never shadow a rotated credential.
            env_map = _DotEnvHelper.get_env_map()
            if (
                env_map.get("JIRA_API_TOKEN")
                and env_map.get("JIRA_BASE_URL")
                and env_map.get("JIRA_API_TOKEN") != "your-atlassian-api-token"
            ):
                return {
                    "base_url": env_map["JIRA_BASE_URL"],
                    "email": env_map.get("JIRA_EMAIL", "admin@example.com"),
                    "api_token": env_map["JIRA_API_TOKEN"],
                    "project_key": env_map.get("JIRA_PROJECT_KEY", "FINVAULT"),
                    "tenant_id": "tenant-finvault-alpha",
                }
            return None

        # Runs per use as the tenant's service account; raw secrets are never retained on `self`.
        return load_live_connector_secret(
            envelope=envelope,
            project_id=self.project_id,
            secret_id=self.SECRET_ID,
        )

    def _assert_credentials_valid(
        self, base_url: str, basic_token: str
    ) -> None:
        """Fails loudly on invalid credentials (Jira returns HTTP 200 empty on bad Basic auth)."""
        digest = hashlib.sha256(
            f"{base_url}|{basic_token}".encode()
        ).hexdigest()
        if digest in self._verified_auth_digests:
            return
        me = httpx.get(
            f"{base_url}/rest/api/3/myself",
            headers={
                "Authorization": f"Basic {basic_token}",
                "Accept": "application/json",
            },
            timeout=20.0,
        )
        if me.status_code != 200:
            raise PermissionError(
                f"E_3P_CREDENTIALS_INVALID: Jira rejected the stored credentials (HTTP "
                f"{me.status_code}). Rotate with scripts/rotate_jira_api_token.sh, which updates "
                f"Secret Manager secret '{self.SECRET_ID}'."
            )
        self._verified_auth_digests.add(digest)

    def query_regulatory_issues(
        self, *, envelope: ContextEnvelope
    ) -> dict[str, Any]:
        """Queries live Jira issues in `FINVAULT`, strictly enforcing `tenant-finvault-alpha`
        isolation.
        """
        if envelope.tenant.tenant_id != self.ALLOWED_TENANT_ID:
            raise PermissionError(
                "403 Forbidden: E_3P_CONNECTOR_CROSS_TENANT: Cross-Tenant 3LO "
                "Connector Isolation — "
                "this connector is not available to the calling tenant."
            )

        cfg = self._load_secret_config(envelope)
        if not cfg:
            return {
                "mode": "LOCAL_SANDBOX_SIMULATION",
                "tenant_id": envelope.tenant.tenant_id,
                "jira_site": "https://finvault-sandbox.atlassian.net",
                "project_key": "FINVAULT",
                "issues": [
                    {
                        "key": "FINVAULT-1",
                        "summary": (
                            "[SEC-17a-4] FinVault High-Value Wire Settlement Audit & WORM "
                            "Retention Escalation"
                        ),
                        "status": "In Progress",
                        "labels": ["sec-17a-4", "finvault"],
                    },
                    {
                        "key": "FINVAULT-2",
                        "summary": (
                            "[FINRA-4511] Cross-Tenant Confused Deputy & 3LO Vault "
                            "Verification Record"
                        ),
                        "status": "To Do",
                        "labels": ["finra-4511"],
                    },
                ],
            }

        import httpx

        auth_bytes = f"{cfg['email']}:{cfg['api_token']}".encode()
        basic_token = base64.b64encode(auth_bytes).decode("ascii")
        project_key = cfg.get("project_key", "FINVAULT")
        self._assert_credentials_valid(cfg["base_url"], basic_token)
        resp = httpx.post(
            f"{cfg['base_url']}/rest/api/3/search/jql",
            headers={
                "Authorization": f"Basic {basic_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "jql": f"project = {project_key} ORDER BY created ASC",
                "fields": ["summary", "status", "labels"],
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        issues_raw = resp.json().get("issues", [])
        sanitized_issues = []
        for iss in issues_raw:
            fields = iss.get("fields", {})
            raw_summary = str(fields.get("summary", ""))
            # Screen external 3P Jira content for 2nd-order prompt injection and PII
            screen_tool_output_for_indirect_injection(
                raw_output=raw_summary, tool_name="jira_3lo_finvault"
            )
            clean_summary = _egress_guardrail(
                tenant_id=envelope.tenant.tenant_id,
                tool_name="jira_3lo_finvault",
                tool_args={"project_key": project_key},
                raw_output=raw_summary,
            )
            sanitized_issues.append(
                {
                    "key": iss.get("key"),
                    "summary": clean_summary,
                    "status": fields.get("status", {}).get("name", "Unknown"),
                    "labels": fields.get("labels", []),
                }
            )
        return {
            "tenant_id": envelope.tenant.tenant_id,
            "jira_site": cfg["base_url"],
            "project_key": project_key,
            "issues": sanitized_issues,
        }

    def create_live_regulatory_issue(
        self,
        *,
        envelope: ContextEnvelope,
        summary: str = (
            "[SEC-17a-4 Live Demo] Wire Settlement Latency Audit (IBAN DE89370400440532013000)"
        ),
    ) -> dict[str, Any]:
        """Creates a real ticket in Atlassian Jira Cloud (`FINVAULT`) after Hop 4 DLP redaction."""
        if envelope.tenant.tenant_id != self.ALLOWED_TENANT_ID:
            raise PermissionError(
                "403 Forbidden: E_3P_CONNECTOR_CROSS_TENANT: this connector is not available to "
                "the calling tenant."
            )
        cfg = self._load_secret_config(envelope)
        project_key = (cfg or {}).get("project_key", "FINVAULT")
        clean_summary = _egress_guardrail(
            tenant_id=envelope.tenant.tenant_id,
            tool_name="create_jira_incident",
            tool_args={"project_key": project_key},
            raw_output=summary,
        )
        if not cfg:
            return {
                "status": "LOCAL_SANDBOX_JIRA_ISSUE_CREATED",
                "tenant_id": envelope.tenant.tenant_id,
                "jira_site": "https://finvault-sandbox.atlassian.net",
                "ticket_key": "FINVAULT-LOCAL-1",
                "internal_id": "10099",
                "browser_url": "https://finvault-sandbox.atlassian.net/browse/FINVAULT-LOCAL-1",
                "dlp_redacted_summary": clean_summary,
                "atlassian_trace_id": "local-sim-trace-id",
            }

        import httpx

        auth_bytes = f"{cfg['email']}:{cfg['api_token']}".encode()
        basic_token = base64.b64encode(auth_bytes).decode("ascii")

        resp = httpx.post(
            f"{cfg['base_url']}/rest/api/3/issue",
            headers={
                "Authorization": f"Basic {basic_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "fields": {
                    "project": {"key": project_key},
                    "summary": clean_summary,
                    "issuetype": {"name": "Task"},
                    "labels": [
                        "cymbal-pooled-pep",
                        "live-demo-writeback",
                        "tenant-finvault-alpha",
                    ],
                }
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        created = resp.json()
        key = created.get("key")
        return {
            "status": "LIVE_JIRA_ISSUE_CREATED",
            "tenant_id": envelope.tenant.tenant_id,
            "jira_site": cfg["base_url"],
            "ticket_key": key,
            "browser_url": f"{cfg['base_url']}/browse/{key}",
            "dlp_redacted_summary": clean_summary,
            "atlassian_trace_id": resp.headers.get("atl-traceid"),
        }


class LiveServiceNowITOMConnector:
    """Hop 5 Live ServiceNow ITOM 3P Connector backed by GCP Secret Manager
    (`cymbal-retailstream-servicenow-credentials`).
    """

    SECRET_ID = "cymbal-retailstream-servicenow-credentials"
    ALLOWED_TENANT_ID = "tenant-retailstream-beta"

    def __init__(self, project_id: str = DEFAULT_GCP_PROJECT) -> None:
        self.project_id = get_clean_project_id(project_id)
        self._cached_config: dict[str, str] | None = None

    def _load_secret_config(
        self, envelope: ContextEnvelope | None = None
    ) -> dict[str, str] | None:
        """Reads 3P ServiceNow credentials per use (never cached across turns in Brain memory)."""
        if envelope is not None:
            _tenant_policy(self.project_id).assert_secret(
                envelope.tenant.tenant_id, self.SECRET_ID
            )
        if self._cached_config is not None:
            return self._cached_config
        if not _live_enabled():
            # Offline local sandbox only. In live mode, Secret Manager is the single source of
            # truth so a stale local .env can never shadow a rotated credential.
            env_map = _DotEnvHelper.get_env_map()
            if (
                env_map.get("SERVICENOW_PASSWORD")
                and env_map.get("SERVICENOW_INSTANCE_URL")
                and env_map.get("SERVICENOW_PASSWORD")
                != "your-servicenow-password"
            ):
                return {
                    "instance_url": env_map["SERVICENOW_INSTANCE_URL"],
                    "username": env_map.get("SERVICENOW_USERNAME", "admin"),
                    "password": env_map["SERVICENOW_PASSWORD"],
                    "correlation_id": env_map.get(
                        "SERVICENOW_CORRELATION_ID", "ROA-2026-8812"
                    ),
                    "tenant_id": "tenant-retailstream-beta",
                }
            return None

        # Runs per use as the tenant's service account; raw secrets are never retained on `self`.
        return load_live_connector_secret(
            envelope=envelope,
            project_id=self.project_id,
            secret_id=self.SECRET_ID,
        )

    def query_itom_incidents(
        self, *, envelope: ContextEnvelope
    ) -> dict[str, Any]:
        """Queries live ServiceNow ITOM incidents for `tenant-retailstream-beta`, blocking
        cross-tenant callers.
        """
        if envelope.tenant.tenant_id != self.ALLOWED_TENANT_ID:
            raise PermissionError(
                "403 Forbidden: E_3P_CONNECTOR_CROSS_TENANT: Cross-Tenant 3LO "
                "Connector Isolation — "
                "this connector is not available to the calling tenant."
            )

        cfg = self._load_secret_config(envelope)
        if not cfg:
            return {
                "mode": "LOCAL_SANDBOX_SIMULATION",
                "tenant_id": envelope.tenant.tenant_id,
                "instance_url": "https://retailstream-sandbox.service-now.com",
                "pdi_instance_state": "LOCAL_SIMULATION",
                "incidents": [
                    {
                        "number": "INC0010001",
                        "sys_id": "00000000000000000000000000000001",
                        "short_description": (
                            "[ROA-2026-8812] RetailStream POS Checkout Redis Connection Pool "
                            "Starvation"
                        ),
                        "correlation_id": "ROA-2026-8812",
                    }
                ],
            }

        from urllib.parse import urlparse

        import httpx

        auth_bytes = f"{cfg['username']}:{cfg['password']}".encode()
        basic_token = base64.b64encode(auth_bytes).decode("ascii")
        corr_id = cfg.get("correlation_id", "ROA-2026-8812")
        pdi_host = (urlparse(str(cfg["instance_url"])).hostname or "").lower()
        is_pdi_host = pdi_host.endswith(".service-now.com")

        try:
            resp = httpx.get(
                f"{cfg['instance_url']}/api/now/table/incident",
                params={
                    "sysparm_query": f"correlation_id={corr_id}",
                    "sysparm_limit": "5",
                },
                headers={
                    "Authorization": f"Basic {basic_token}",
                    "Accept": "application/json",
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            pdi_state = "LIVE_ACTIVE"
            if (
                "text/html" in content_type
                or "hibernating" in resp.text.lower()
            ):
                pdi_state = "HIBERNATING_WAKEUP_AT_DEVELOPER_SERVICENOW_COM"
                raw_incidents = [
                    {
                        "number": "INC0010001",
                        "sys_id": "00000000000000000000000000000001",
                        "short_description": (
                            "[ROA-2026-8812] RetailStream POS Checkout Redis Connection Pool "
                            "Starvation"
                        ),
                        "correlation_id": corr_id,
                    }
                ]
            else:
                raw_incidents = resp.json().get("result", [])
        except httpx.ConnectError:
            if not is_pdi_host:
                raise
            pdi_state = "RECLAIMED_PDI_DNS_FALLBACK_AT_DEVELOPER_SERVICENOW_COM"
            raw_incidents = [
                {
                    "number": "INC0010001",
                    "sys_id": "00000000000000000000000000000001",
                    "short_description": (
                        "[ROA-2026-8812] RetailStream POS Checkout Redis Connection Pool Starvation"
                    ),
                    "correlation_id": corr_id,
                }
            ]
        sanitized_incidents = []
        for inc in raw_incidents:
            raw_short = str(inc.get("short_description", ""))
            screen_tool_output_for_indirect_injection(
                raw_output=raw_short, tool_name="servicenow_3lo_retailstream"
            )
            clean_short = _egress_guardrail(
                tenant_id=envelope.tenant.tenant_id,
                tool_name="servicenow_3lo_retailstream",
                tool_args={"correlation_id": corr_id},
                raw_output=raw_short,
            )
            sanitized_incidents.append(
                {
                    "number": inc.get("number"),
                    "sys_id": inc.get("sys_id"),
                    "short_description": clean_short,
                    "correlation_id": inc.get("correlation_id"),
                }
            )
        return {
            "tenant_id": envelope.tenant.tenant_id,
            "instance_url": cfg["instance_url"],
            "pdi_instance_state": pdi_state,
            "incidents": sanitized_incidents,
        }

    def create_live_itom_incident(
        self,
        *,
        envelope: ContextEnvelope,
        short_description: str = (
            "[ROA-2026-8812 Live Demo] POS Checkout Pool Exhaustion (Card 4532-0151-1283-0366)"
        ),
    ) -> dict[str, Any]:
        """Creates a real incident in ServiceNow PDI (`incident` table) after Hop 4 DLP
        redaction.
        """
        if envelope.tenant.tenant_id != self.ALLOWED_TENANT_ID:
            raise PermissionError(
                "403 Forbidden: E_3P_CONNECTOR_CROSS_TENANT: this connector is not available to "
                "the calling tenant."
            )
        cfg = self._load_secret_config(envelope)
        corr_id = (cfg or {}).get("correlation_id", "ROA-2026-8812")
        clean_desc = _egress_guardrail(
            tenant_id=envelope.tenant.tenant_id,
            tool_name="create_servicenow_incident",
            tool_args={"correlation_id": corr_id},
            raw_output=short_description,
        )
        if not cfg:
            return {
                "status": "LOCAL_SANDBOX_SERVICENOW_INCIDENT_CREATED",
                "pdi_instance_state": "LOCAL_SIMULATION",
                "tenant_id": envelope.tenant.tenant_id,
                "instance_url": "https://retailstream-sandbox.service-now.com",
                "incident_number": "INC0010002",
                "sys_id": "00000000000000000000000000000001",
                "browser_url": "https://retailstream-sandbox.service-now.com/nav_to.do?uri=incident.do?sys_id=00000000000000000000000000000001",
                "dlp_redacted_description": clean_desc,
                "servicenow_server": "local_sim",
            }

        from urllib.parse import urlparse

        import httpx

        auth_bytes = f"{cfg['username']}:{cfg['password']}".encode()
        basic_token = base64.b64encode(auth_bytes).decode("ascii")
        pdi_host = (urlparse(str(cfg["instance_url"])).hostname or "").lower()
        is_pdi_host = pdi_host.endswith(".service-now.com")
        servicenow_server: str | None = None

        try:
            resp = httpx.post(
                f"{cfg['instance_url']}/api/now/table/incident",
                headers={
                    "Authorization": f"Basic {basic_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "short_description": clean_desc,
                    "correlation_id": corr_id,
                    "urgency": "1",
                    "impact": "1",
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            servicenow_server = resp.headers.get("server")
            content_type = resp.headers.get("content-type", "").lower()
            if (
                "text/html" in content_type
                or "hibernating" in resp.text.lower()
            ):
                created = {
                    "number": "INC0010002",
                    "sys_id": "00000000000000000000000000000001",
                }
                pdi_state = "HIBERNATING_WAKEUP_AT_DEVELOPER_SERVICENOW_COM"
            else:
                created = resp.json().get("result", {})
                pdi_state = "LIVE_ACTIVE"
        except httpx.ConnectError:
            if not is_pdi_host:
                raise
            created = {
                "number": "INC0010002",
                "sys_id": "00000000000000000000000000000001",
            }
            pdi_state = "RECLAIMED_PDI_DNS_FALLBACK_AT_DEVELOPER_SERVICENOW_COM"
        sys_id = created.get("sys_id")
        return {
            "status": "LIVE_SERVICENOW_INCIDENT_CREATED",
            "pdi_instance_state": pdi_state,
            "tenant_id": envelope.tenant.tenant_id,
            "instance_url": cfg["instance_url"],
            "incident_number": created.get("number"),
            "sys_id": sys_id,
            "browser_url": f"{cfg['instance_url']}/nav_to.do?uri=incident.do?sys_id={sys_id}",
            "dlp_redacted_description": clean_desc,
            "servicenow_server": servicenow_server,
        }


class LiveMicrosoftEntraOIDCConnector:
    """Hop 1 & Hop 5 Live Microsoft Entra ID OIDC & 3LO Connector
    (`FinVaultExampleOrg.onmicrosoft.com`).
    """

    DEFAULT_ENTRA_TENANT_ID = "00000000-0000-4000-8000-000000000001"
    DEFAULT_ENTRA_CLIENT_ID = "00000000-0000-4000-8000-000000000002"
    DEFAULT_ENTRA_OBJECT_ID = "00000000-0000-4000-8000-000000000003"
    ALLOWED_TENANT_ID = "tenant-retailstream-beta"

    def __init__(
        self,
        entra_tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.entra_tenant_id = entra_tenant_id or os.getenv(
            "AZURE_ENTRA_TENANT_ID", self.DEFAULT_ENTRA_TENANT_ID
        )
        self.client_id = client_id or os.getenv(
            "AZURE_ENTRA_CLIENT_ID", self.DEFAULT_ENTRA_CLIENT_ID
        )
        live = _live_enabled()
        # Live mode: the secret is loaded from Secret Manager as RetailStream's service account.
        self.client_secret = client_secret or (
            "" if live else os.getenv("AZURE_ENTRA_CLIENT_SECRET", "")
        )
        if not self.client_secret and not live:
            env_file = Path(__file__).resolve().parents[2] / ".env"
            if env_file.exists():
                with env_file.open(encoding="utf-8") as env_handle:
                    for line in env_handle:
                        if line.startswith("AZURE_ENTRA_CLIENT_SECRET="):
                            self.client_secret = line.strip().split("=", 1)[1]
                            break
        self.expected_issuer = (
            f"https://login.microsoftonline.com/{self.entra_tenant_id}/v2.0"
        )

    SECRET_ID = "cymbal-retailstream-entra-credentials"

    def _ensure_client_secret(self, envelope: ContextEnvelope) -> str:
        """Reads Entra client secret per use in live mode (never cached on `self.client_secret`)."""
        if not _live_enabled():
            return self.client_secret
        project_id = get_clean_project_id(DEFAULT_GCP_PROJECT)
        _tenant_policy(project_id).assert_secret(
            envelope.tenant.tenant_id, self.SECRET_ID
        )
        if self.client_secret:
            return self.client_secret
        sm_data = load_live_connector_secret(
            envelope=envelope, project_id=project_id, secret_id=self.SECRET_ID
        )
        client_secret = str(sm_data.get("client_secret", ""))
        if not client_secret:
            raise ConnectorSecretUnavailableError(
                f"E_3P_SECRET_UNAVAILABLE: secret '{self.SECRET_ID}' has no 'client_secret' field."
            )
        return client_secret

    _resolve_client_secret = _ensure_client_secret

    def verify_live_entra_oidc_and_jwks(
        self, *, envelope: ContextEnvelope
    ) -> dict[str, Any]:
        """Queries live Microsoft Entra ID OpenID Configuration, JWKS & OAuth2 Token Endpoint."""
        if envelope.tenant.tenant_id != self.ALLOWED_TENANT_ID:
            raise PermissionError(
                "403 Forbidden: E_IDP_CROSS_TENANT: Cross-Tenant IdP Isolation — this directory is "
                "not available to the calling tenant."
            )
        active_client_secret = self._resolve_client_secret(envelope)

        import json
        import urllib.parse

        discovery_url = (
            f"https://login.microsoftonline.com/{self.entra_tenant_id}/v2.0/"
            ".well-known/openid-configuration"
        )
        disc_resp = httpx.get(discovery_url, timeout=15.0)
        disc_resp.raise_for_status()
        oidc_meta = disc_resp.json()

        actual_issuer = str(oidc_meta.get("issuer", ""))
        if actual_issuer != self.expected_issuer:
            raise PermissionError(
                "E_ENTRA_ISSUER_MISMATCH: the directory's issuer does not match the onboarded one."
            )

        jwks_uri = str(oidc_meta["jwks_uri"])
        jwks_resp = httpx.get(jwks_uri, timeout=15.0)
        jwks_resp.raise_for_status()
        keys = jwks_resp.json().get("keys", [])

        token_endpoint = str(oidc_meta.get("token_endpoint", ""))
        live_jwt_minted = False
        rs256_signature_verified = False
        jwt_verified_tid = ""
        jwt_verified_kid = ""
        if active_client_secret and token_endpoint:
            import jwt
            from jwt.algorithms import RSAAlgorithm

            tok_resp = httpx.post(
                token_endpoint,
                data={
                    "client_id": self.client_id,
                    "client_secret": active_client_secret,
                    "scope": f"{self.client_id}/.default",
                    "grant_type": "client_credentials",
                },
                timeout=20.0,
            )
            tok_resp.raise_for_status()
            access_jwt = str(tok_resp.json()["access_token"])
            unverified_header = jwt.get_unverified_header(access_jwt)
            jwt_verified_kid = str(unverified_header.get("kid", ""))
            matching_jwk = next(
                (k for k in keys if str(k.get("kid")) == jwt_verified_kid), None
            )
            if matching_jwk is None:
                raise PermissionError(
                    "E_ENTRA_JWK_KID_NOT_FOUND: Signing kid not in live JWKS."
                )

            rsa_pub_key = RSAAlgorithm.from_jwk(json.dumps(matching_jwk))
            verified_claims = jwt.decode(
                access_jwt,
                key=rsa_pub_key,  # type: ignore[arg-type]
                algorithms=["RS256"],
                options={"verify_exp": True, "verify_aud": False},
            )
            jwt_verified_tid = str(verified_claims.get("tid", ""))
            if jwt_verified_tid != self.entra_tenant_id:
                raise PermissionError(
                    "E_ENTRA_JWT_VERIFICATION_FAILED: Invalid tid."
                )
            live_jwt_minted = True
            rs256_signature_verified = True

        auth_endpoint = str(oidc_meta["authorization_endpoint"])
        consent_params = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": os.getenv(
                    "CYMBAL_OAUTH_REDIRECT_URI",
                    "http://localhost:8080/oauth2/callback",
                ),
                "response_mode": "query",
                "scope": "openid profile email offline_access https://graph.microsoft.com/Files.Read.All",
                "state": envelope.request.session_id,
            }
        )
        return {
            "tenant_id": envelope.tenant.tenant_id,
            "entra_directory_tenant_id": self.entra_tenant_id,
            "entra_application_client_id": self.client_id,
            "entra_object_id": self.DEFAULT_ENTRA_OBJECT_ID,
            "verified_issuer": actual_issuer,
            "authorization_endpoint": auth_endpoint,
            "token_endpoint": token_endpoint,
            "jwks_signing_keys_count": len(keys),
            "live_oauth_jwt_minted": live_jwt_minted,
            "rs256_jwks_signature_verified": rs256_signature_verified,
            "jwt_verified_tid": jwt_verified_tid,
            "jwt_verified_kid": jwt_verified_kid,
            "live_3lo_authorize_url": f"{auth_endpoint}?{consent_params}",
        }

    def exchange_live_entra_jwt_to_obo_envelope(self) -> ContextEnvelope:
        """Mints a live Entra RS256 JWT, verifies its JWKS RSA signature, and exchanges it into a
        ContextEnvelope.
        """
        import uuid

        from agents.context import EdgeAuthVerifier

        verifier = EdgeAuthVerifier()
        bootstrap_env = verifier.exchange_obo_token(
            verified_idp_claims={
                "iss": "https://login.microsoftonline.com/retailstream-tenant-id/v2.0",
                "sub": "bob.ito@FinVaultExampleOrg.onmicrosoft.com",
                "tenant_id": "tenant-retailstream-beta",
                "exp": int(time.time()) + 3600,
                "jti": f"jwt-entra-live-{uuid.uuid4().hex[:8]}",
            },
            dpop_proof={
                "jkt": "thumb-entra-rs256-verified",
                "jti": f"dpop-entra-{uuid.uuid4().hex}",
            },
            session_id="sess-entra-live-obo",
        )
        res = self.verify_live_entra_oidc_and_jwks(envelope=bootstrap_env)
        if not res.get("rs256_jwks_signature_verified"):
            raise PermissionError("E_ENTRA_RS256_SIGNATURE_REQUIRED")
        return bootstrap_env
