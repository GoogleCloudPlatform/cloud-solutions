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

"""Gateway side of the B5 split: forward admitted turns to each agent's own runtime service.

`AGENT_RUNTIME_URLS` (JSON map agent_id -> https URL) turns it on; unset (the default) keeps every
turn in process, as before. Per forwarded turn the gateway:

1. has already bound the routed `agent_id` into the context token (always, when forwarding);
2. pre-mints one broker-audience derived token (the existing ADR-0014 B3 exchange), so the agent
   service never needs a signer;
3. calls `POST /internal/v1/turn` on that agent's service with its own Google ID token
   (audience = the service URL; Cloud Run IAM `run.invoker` = gateway SA only);
4. maps the answer back to exactly the response the in-process path gives.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import Callable, Mapping
from typing import Any, Literal

from agents.context import ContextEnvelope
from agents.registry import AGENT_CATALOG
from agents.runtime_protocol import (
    SANDBOX_PAUSE_PATH,
    SANDBOX_RELEASE_PATH,
    TURN_PATH,
    turn_payload,
)
from fastapi import HTTPException

AGENT_RUNTIME_URLS_ENV = "AGENT_RUNTIME_URLS"
logger = logging.getLogger(__name__)


def _fetch_id_token(audience: str) -> str:
    from agents.tenant_credentials import _fetch_cloud_run_id_token

    return _fetch_cloud_run_id_token(audience)


def _broker_backend_in_use() -> bool:
    """Tenant credentials come from the credential broker only in live mode with a broker URL
    (`agents.tenant_credentials.get_default_broker`); otherwise no broker token is minted.
    """
    from agents.platform_config import is_live_mode

    return is_live_mode() and bool(
        (os.getenv("CREDENTIAL_BROKER_URL") or "").strip()
    )


class RemoteRuntimeClient:
    def __init__(
        self,
        urls: Mapping[str, str],
        *,
        id_token_provider: Callable[[str], str] = _fetch_id_token,
        http_post: Callable[..., Any] | None = None,
        exchange: Any | None = None,
        timeout_seconds: float = 180.0,
        broker_token_needed: Callable[[], bool] | None = None,
    ) -> None:
        """`broker_token_needed()` decides per turn whether to pre-mint a broker token: only when
        the turn can mint tenant credentials (live mode with the credential broker).
        """
        if not urls:
            raise ValueError(
                "E_RUNTIME_URLS: at least one agent runtime URL is required"
            )
        for agent_id, url in urls.items():
            if agent_id not in AGENT_CATALOG:
                raise ValueError(
                    f"E_RUNTIME_URLS: {agent_id!r} is not a catalog agent"
                )
            # Plain http only for the in-process test server with an injected transport.
            if not (
                isinstance(url, str)
                and (
                    url.startswith("https://")
                    or (http_post is not None and url == "http://testserver")
                )
            ):
                raise ValueError(
                    f"E_RUNTIME_URLS: the URL for {agent_id!r} must be https://"
                )
        self._urls = {k: v.rstrip("/") for k, v in urls.items()}
        self._id_token_provider = id_token_provider
        self._http_post = http_post
        self._exchange = exchange
        self._timeout = timeout_seconds
        self._broker_token_needed = (
            broker_token_needed or _broker_backend_in_use
        )

    @classmethod
    def from_env(cls) -> RemoteRuntimeClient | None:
        raw = (os.getenv(AGENT_RUNTIME_URLS_ENV) or "").strip()
        if not raw:
            return None
        try:
            urls = json.loads(raw)
        except ValueError as exc:
            raise RuntimeError(
                "E_RUNTIME_URLS: AGENT_RUNTIME_URLS must be a JSON object"
            ) from exc
        if not isinstance(urls, dict):
            raise TypeError(
                "E_RUNTIME_URLS: AGENT_RUNTIME_URLS must be a JSON object"
            )
        try:
            return cls(urls)
        except ValueError as exc:  # fail closed at startup on a wrong map
            raise RuntimeError(str(exc)) from exc

    def handles(self, agent_id: str) -> bool:
        return agent_id in self._urls

    def _broker_token(self, envelope: ContextEnvelope) -> str:
        from agents.context_exchange import get_context_token_exchange

        exchange = self._exchange or get_context_token_exchange()
        token, _ = exchange.exchange(envelope.context_token, audience="broker")
        return token

    def _post(
        self, url: str, body: dict[str, Any], *, path: str = TURN_PATH
    ) -> Any:
        post = self._http_post
        if post is None:
            import httpx

            post = httpx.post
        id_token = self._id_token_provider(url)
        return post(
            url + path,
            headers={"X-Serverless-Authorization": f"Bearer {id_token}"},
            json=body,
            timeout=self._timeout,
        )

    async def _post_internal(
        self,
        *,
        url: str,
        path: str,
        body: dict[str, Any],
        hops: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Posts a B5 internal request and decodes `outcome` (`ok` | `blocked` | `http_error`)."""
        try:
            resp = await asyncio.to_thread(self._post, url, body, path=path)
        except (
            Exception
        ) as exc:  # transport or metadata server: an outage, not a denial
            raise HTTPException(
                status_code=503,
                detail={"error": "E_RUNTIME_UNAVAILABLE"},
                headers={"Retry-After": "10"},
            ) from exc
        if resp.status_code == 503:
            raise HTTPException(
                status_code=503,
                detail={"error": "E_RUNTIME_UNAVAILABLE"},
                headers={"Retry-After": "10"},
            )
        if resp.status_code != 200:
            # The runtime refused the gateway itself (identity, token, agent): a deployment or
            # integrity fault, never the end user's; no detail leaks to the caller.
            code = "E_RUNTIME_REFUSED"
            with contextlib.suppress(
                Exception
            ):  # keep the generic code if the body is odd
                code = str(resp.json()["detail"]["error"])
            logger.warning("agent runtime refused the gateway: %s", code)
            raise HTTPException(
                status_code=502,
                detail={"error": "E_RUNTIME_REFUSED", "runtime": code},
            )
        try:
            data = resp.json()
            outcome = data["outcome"]
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail={"error": "E_RUNTIME_MALFORMED"}
            ) from exc
        if outcome == "ok":
            return dict(data["result"])
        if outcome == "blocked":
            if hops is not None:
                hops[:] = list(data.get("hops") or [])
            raise PermissionError(str(data.get("message", "E_REQUEST_BLOCKED")))
        if outcome == "http_error":
            try:
                status = int(data["status_code"])
            except (KeyError, TypeError, ValueError):
                status = 502
            if (
                not 400 <= status <= 599
            ):  # a runtime can't turn an error into a success code
                status = 502
            detail_obj = data.get("detail")
            response_headers: dict[str, str] | None = None
            if (
                status == 503
                and isinstance(detail_obj, Mapping)
                and detail_obj.get("error") == "E_SANDBOX_UNAVAILABLE"
            ):
                response_headers = {
                    "Retry-After": "15",
                    "Cache-Control": "no-store",
                }
            raise HTTPException(
                status_code=status,
                detail=detail_obj,
                headers=response_headers,
            )
        raise HTTPException(
            status_code=502, detail={"error": "E_RUNTIME_MALFORMED"}
        )

    async def run_turn(
        self,
        req: Any,
        envelope: ContextEnvelope,
        *,
        hops: list[dict[str, Any]],
        finops: dict[str, Any],
        estimated_tokens: int,
        prompt_cache_hit: bool,
        identity_source: str,
    ) -> dict[str, Any]:
        """The turn's result, or the same `PermissionError` / `HTTPException` the in-process path
        raises. `hops` is updated in place with the runtime's hops when the turn is blocked.
        """
        url = self._urls[req.agent_id]
        # ExchangeRefused is a PermissionError. No broker token when nothing in the turn can use it.
        broker_token = (
            self._broker_token(envelope)
            if self._broker_token_needed()
            else None
        )
        body = {
            "context_token": envelope.context_token,
            "broker_token": broker_token,
            "turn": turn_payload(req),
            "admission": {
                "hops": hops,
                "finops": finops,
                "estimated_tokens": estimated_tokens,
                "prompt_cache_hit": prompt_cache_hit,
                "identity_source": identity_source,
                "trace_id": envelope.request.trace_id,
                "correlation_id": envelope.request.correlation_id,
            },
        }
        return await self._post_internal(
            url=url, path=TURN_PATH, body=body, hops=hops
        )

    async def _sandbox_action(
        self,
        *,
        path: str,
        envelope: ContextEnvelope,
        agent_id: str,
        language: Literal["python", "javascript", "bash"] | None = None,
    ) -> dict[str, Any]:
        """Forwards a session sandbox lifecycle call (`pause` or `release`) to the B5 runtime."""
        url = self._urls[agent_id]
        body: dict[str, Any] = {
            "context_token": envelope.context_token,
            "agent_id": agent_id,
            "trace_id": envelope.request.trace_id,
            "correlation_id": envelope.request.correlation_id,
        }
        if language is not None:
            body["language"] = language
        return await self._post_internal(url=url, path=path, body=body)

    async def pause_sandbox(
        self,
        *,
        envelope: ContextEnvelope,
        agent_id: str,
        language: Literal["python", "javascript", "bash"] | None = None,
    ) -> dict[str, Any]:
        """Pauses the caller session's tainted agent sandbox in Gemini in the agent's B5 runtime."""
        return await self._sandbox_action(
            path=SANDBOX_PAUSE_PATH,
            envelope=envelope,
            agent_id=agent_id,
            language=language,
        )

    async def release_sandbox(
        self,
        *,
        envelope: ContextEnvelope,
        agent_id: str,
        language: Literal["python", "javascript", "bash"] | None = None,
    ) -> dict[str, Any]:
        """Destroys the caller session's tainted agent sandbox in the agent's B5 runtime."""
        return await self._sandbox_action(
            path=SANDBOX_RELEASE_PATH,
            envelope=envelope,
            agent_id=agent_id,
            language=language,
        )
