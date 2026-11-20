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
# pylint: disable=missing-class-docstring,wrong-import-position

"""Client helper for calling the gateway as a synthetic sandbox user (scripts, CI, tests).

    caller = SandboxCaller(client_or_base_url, tenant_id="tenant-finvault-alpha",
                           sub="alice@finvault.com", role="sre_admin")
    headers = caller.headers("POST", f"{base_url}/api/v1/invoke-agent")

1. The ID token comes from the gateway's sandbox-only `POST /api/v1/sandbox/token`, in the
   tenant's own IdP format, so it goes through the same Hop 0 checks as a real IdP token.
2. It is exchanged once at `POST /api/v1/auth/token` for a short-lived gateway token bound to
   this caller's own ES256 key (RFC 9449 `cnf.jkt`).
3. Every request sends `Authorization: DPoP <gateway token>` and a fresh proof for that method
   and URL, carrying the token hash (`ath`) and a new `jti`.

Works against a live gateway (base URL) or a FastAPI `TestClient` (anything with `.post`).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.context import AsymmetricDPoPProvider
from cryptography.hazmat.primitives.asymmetric import ec

SANDBOX_TOKEN_PATH = "/api/v1/sandbox/token"
TOKEN_EXCHANGE_PATH = "/api/v1/auth/token"
TESTCLIENT_BASE = "http://testserver"


class SandboxCaller:
    def __init__(
        self,
        client: Any,
        *,
        tenant_id: str,
        sub: str,
        role: str = "read_only_analyst",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """`extra_headers` go on every call, e.g. Cloud Run's IAM token in
        `X-Serverless-Authorization` (the app's own token uses `Authorization`).
        """
        self._client = client
        self._extra = dict(extra_headers or {})
        self.tenant_id = tenant_id
        self.sub = sub
        self.role = role
        self._dpop_key = ec.generate_private_key(ec.SECP256R1())
        self._id_token: str | None = None
        self._access_token: str | None = None

    @property
    def base_url(self) -> str:
        return (
            self._client.rstrip("/")
            if isinstance(self._client, str)
            else TESTCLIENT_BASE
        )

    def url(self, path: str) -> str:
        return self.base_url + path

    def _post(
        self,
        path: str,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        headers = {**self._extra, **(headers or {})}
        if isinstance(self._client, str):
            import httpx

            return httpx.post(
                self.url(path), json=json, headers=headers, timeout=30
            )
        return self._client.post(path, json=json, headers=headers)

    @property
    def id_token(self) -> str:
        """Sandbox IdP-format ID token (Hop 0 input)."""
        if self._id_token is None:
            resp = self._post(
                SANDBOX_TOKEN_PATH,
                {
                    "tenant_id": self.tenant_id,
                    "sub": self.sub,
                    "role": self.role,
                },
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"sandbox token request failed: HTTP {resp.status_code}"
                )
            self._id_token = str(resp.json()["id_token"])
        return self._id_token

    @property
    def access_token(self) -> str:
        """Gateway token bound to this caller's DPoP key (exchanged once, then cached)."""
        if self._access_token is None:
            resp = self._post(
                TOKEN_EXCHANGE_PATH,
                {"subject_token": self.id_token},
                headers={
                    "DPoP": self.dpop_proof(
                        "POST", self.url(TOKEN_EXCHANGE_PATH)
                    )
                },
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"token exchange failed: HTTP {resp.status_code}"
                )
            self._access_token = str(resp.json()["access_token"])
        return self._access_token

    def dpop_proof(
        self, method: str, url: str, *, access_token: str | None = None
    ) -> str:
        from app.gateway_tokens import access_token_hash

        return AsymmetricDPoPProvider.mint_dpop_proof_jwt(
            client_private_key=self._dpop_key,
            htm=method.upper(),
            htu=url,
            ath=access_token_hash(access_token) if access_token else None,
        )

    def headers(self, method: str, url: str) -> dict[str, str]:
        """`Authorization: DPoP` + a fresh proof bound to this request and the gateway token."""
        token = self.access_token
        return {
            **self._extra,
            "Authorization": f"DPoP {token}",
            "DPoP": self.dpop_proof(method, url, access_token=token),
        }
