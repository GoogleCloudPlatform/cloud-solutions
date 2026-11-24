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

"""IAM Credentials REST backend for the broker (generateAccessToken / generateIdToken).

Runs as the broker's own service account (ADC). No ADK or agent imports.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from datetime import datetime
from typing import Any

from agents.kms_rest import run_with_deadline
from broker_service.core import (
    BrokerRefused,
    BrokerUnavailable,
    MintedCredential,
)

IAM_CREDENTIALS_API = "https://iamcredentials.googleapis.com/v1"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class IamCredentialsBackend:
    def __init__(self, *, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds
        self._creds: Any = None
        self._lock = threading.Lock()

    def _headers(self) -> dict[str, str]:
        import functools

        import google.auth
        import google.auth.transport.requests

        with self._lock:
            if self._creds is None:
                self._creds, _ = google.auth.default(
                    scopes=[CLOUD_PLATFORM_SCOPE]
                )
            if not self._creds.valid:
                request = functools.partial(
                    google.auth.transport.requests.Request(),
                    timeout=self._timeout,
                )
                self._creds.refresh(request)
            return {"Authorization": f"Bearer {self._creds.token}"}

    def _post(
        self, principal: str, method: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        import httpx

        def call() -> dict[str, Any]:
            resp = httpx.post(
                f"{IAM_CREDENTIALS_API}/projects/-/serviceAccounts/{principal}:{method}",
                headers=self._headers(),
                json=body,
                timeout=self._timeout,
            )
            if resp.status_code in (403, 404):
                # The broker SA lacks TokenCreator on this tenant SA, or the SA doesn't exist:
                # a deployment problem, never something the caller can fix.
                raise BrokerUnavailable(f"E_BROKER_IAM_{resp.status_code}")
            if resp.status_code != 200:
                raise BrokerUnavailable(f"E_BROKER_IAM_HTTP_{resp.status_code}")
            return dict(resp.json())

        try:
            return run_with_deadline(call, self._timeout)
        except BrokerUnavailable:
            raise
        except Exception as exc:
            cause = exc.__cause__
            if isinstance(cause, (BrokerUnavailable, BrokerRefused)):
                raise cause from exc
            raise BrokerUnavailable(
                f"E_BROKER_IAM_UNAVAILABLE_{type(exc).__name__}"
            ) from exc

    def access_token(
        self, *, principal: str, lifetime_seconds: int
    ) -> MintedCredential:
        data = self._post(
            principal,
            "generateAccessToken",
            {
                "scope": [CLOUD_PLATFORM_SCOPE],
                "lifetime": f"{int(lifetime_seconds)}s",
            },
        )
        expires = datetime.fromisoformat(str(data["expireTime"]))
        return MintedCredential(
            kind="access_token",
            token=str(data["accessToken"]),
            expires_at=expires.timestamp(),
            principal=principal,
        )

    def id_token(self, *, principal: str, audience: str) -> MintedCredential:
        data = self._post(
            principal,
            "generateIdToken",
            {"audience": audience, "includeEmail": True},
        )
        token = str(data["token"])
        try:
            payload = token.split(".")[1]
            exp = float(
                json.loads(
                    base64.urlsafe_b64decode(
                        payload + "=" * (-len(payload) % 4)
                    )
                )["exp"]
            )
        except (IndexError, KeyError, ValueError):
            exp = time.time() + 3600
        return MintedCredential(
            kind="id_token", token=token, expires_at=exp, principal=principal
        )
