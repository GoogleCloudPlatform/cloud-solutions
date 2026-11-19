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

# pylint: disable=broad-exception-caught,import-outside-toplevel
# pylint: disable=inconsistent-quotes,line-too-long

"""Auth Manager 3LO token vault, continuous-refill token-bucket bulkheads, and cache simulator."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import inspect
import json
import os
import re
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import redis
from agents import platform_config
from agents.auth.envelope import ContextEnvelope
from agents.auth.tenant_directory import (
    TENANT_DIRECTORY,
    register_tenant_eviction_target,
)
from agents.platform_config import resolve_project_id
from redis.exceptions import RedisError


@dataclass(frozen=True)
class Delegated3LOToken:
    """3LO OAuth credential stored in Auth Manager Vault bound to a specific tenant & user."""

    token_handle: str
    tenant_id: str
    user_sub: str
    provider: str
    scopes: tuple[str, ...]
    access_token: str
    expires_at: int


class AuthManager3LOVault:
    """Edge Case #7: GCP Agent Identity Auth Manager 3LO Token Vault with Confused-Deputy Guard."""

    def __init__(self) -> None:
        self._tokens: dict[str, Delegated3LOToken] = {}
        self._lock = threading.Lock()
        register_tenant_eviction_target(self)

    @staticmethod
    def handle_for_caller(
        *,
        tenant_id: str,
        user_sub: str,
        required_scope: str,
    ) -> str:
        """Derives a deterministic vault handle scoped to `(tenant_id, user_sub, required_scope)`.

        Args:
            tenant_id: Verified tenant identifier.
            user_sub: Verified user subject identifier.
            required_scope: Required 3LO OAuth scope string.

        Returns:
            Opaque `3lo-<24-hex>` handle bound to the exact caller and scope.
        """
        digest = hashlib.sha256(
            f"{tenant_id}:{user_sub}:{required_scope}".encode()
        ).hexdigest()[:24]
        return f"3lo-{digest}"

    def store_3lo_token(self, token: Delegated3LOToken) -> str:
        with self._lock:
            self._tokens[token.token_handle] = token
        return token.token_handle

    def evict_tenant(self, tenant_id: str) -> int:
        """Evicts all delegated 3LO OAuth tokens belonging to `tenant_id`."""
        with self._lock:
            matching_handles = [
                handle
                for handle, tok in self._tokens.items()
                if tok.tenant_id == tenant_id
            ]
            for handle in matching_handles:
                self._tokens.pop(handle, None)
            return len(matching_handles)

    def checkout_3lo_token(
        self,
        *,
        token_handle: str,
        envelope: ContextEnvelope,
        required_scope: str,
    ) -> Delegated3LOToken:
        """Verifies the 3LO token belongs to the exact calling `(tenant_id, user_sub)`."""
        if envelope.tenant.tenant_id not in TENANT_DIRECTORY:
            raise PermissionError(
                f"E_TENANT_NOT_ONBOARDED: Tenant '{envelope.tenant.tenant_id}' is not onboarded."
            )
        with self._lock:
            tok = self._tokens.get(token_handle)
        if tok is None:
            raise PermissionError(
                f"E_3LO_TOKEN_NOT_FOUND: Unknown 3LO handle '{token_handle}'."
            )

        if (
            tok.tenant_id != envelope.tenant.tenant_id
            or tok.user_sub != envelope.security.sub
        ):
            raise PermissionError(
                "E_3LO_CONFUSED_DEPUTY_BLOCKED: the 3LO token is not bound to the calling tenant "
                "and user."
            )
        if tok.expires_at <= int(time.time()):
            raise PermissionError(
                "E_3LO_TOKEN_EXPIRED: Delegated 3LO OAuth token has expired."
            )
        if required_scope not in tok.scopes:
            raise PermissionError(
                f"E_3LO_INSUFFICIENT_SCOPE: 3LO token lacks required scope '{required_scope}'."
            )
        return tok


class RemoteBroker3LOVault(AuthManager3LOVault):
    """Out-of-process 3LO consent vault delegating storage & checkout to `broker_service` (`C6`).

    Keeps zero standing 3LO user tokens in Brain process memory (`self._tokens` stays empty).
    Every store, checkout, and tenant eviction uses a fresh `aud='broker'` KMS-signed `ctx+jwt`
    plus a Cloud Run caller ID token (`X-Serverless-Authorization`).
    """

    STORE_PATH = "/internal/v1/3lo-credential/store"
    CHECKOUT_PATH = "/internal/v1/3lo-credential/checkout"
    EVICT_PATH = "/internal/v1/3lo-credential/evict"

    def __init__(
        self,
        broker_url: str,
        *,
        exchange: Any | None = None,
        id_token_provider: Callable[[str], str] | None = None,
        http_post: Callable[..., Any] | None = None,
        timeout_seconds: float = 10.0,
        allow_exchange: bool = True,
    ) -> None:
        super().__init__()
        if not (
            broker_url.startswith("https://")
            or broker_url == "http://testserver"
            or http_post is not None
        ):
            raise ValueError(
                "E_BROKER_URL: the credential broker URL must be https://"
            )
        self.broker_url = broker_url.rstrip("/")
        self._exchange = exchange
        self._id_token_provider = id_token_provider
        self._http_post = http_post
        self._timeout = timeout_seconds
        self._allow_exchange = allow_exchange

    def _mint_broker_headers(self, envelope: ContextEnvelope) -> dict[str, str]:
        from agents.context_exchange import get_context_token_exchange
        from agents.tenant_credentials import (
            _TURN_BROKER_TOKEN,
            BROKER_CONTEXT_TOKEN_HEADER,
            _fetch_cloud_run_id_token,
        )

        if not envelope.context_token:
            raise PermissionError(
                "E_BROKER_NO_CONTEXT_TOKEN: a signed context token is required."
            )
        pre_minted = _TURN_BROKER_TOKEN.get()
        if pre_minted:
            broker_token = pre_minted
        elif self._allow_exchange:
            exch = self._exchange or get_context_token_exchange()
            broker_token, _ = exch.exchange(
                envelope.context_token, audience="broker"
            )
        else:
            raise PermissionError(
                "E_BROKER_NO_BROKER_TOKEN: this turn carries no pre-minted broker token."
            )
        provider = self._id_token_provider or _fetch_cloud_run_id_token
        caller_id_token = provider(self.broker_url)
        return {
            "X-Serverless-Authorization": f"Bearer {caller_id_token}",
            BROKER_CONTEXT_TOKEN_HEADER: broker_token,
        }

    def _post(
        self, path: str, *, headers: dict[str, str], payload: dict[str, Any]
    ) -> Any:
        post = self._http_post
        if post is None:
            import httpx

            post = httpx.post
        try:
            resp = post(
                self.broker_url + path,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except Exception as exc:
            raise RuntimeError(
                f"E_BROKER_UNAVAILABLE: {type(exc).__name__}"
            ) from exc
        if resp.status_code in (400, 401, 403, 404, 409, 422, 429):
            code = "E_BROKER_REFUSED"
            with contextlib.suppress(Exception):
                code = str(resp.json().get("detail", {}).get("error", code))
            raise PermissionError(
                f"403 Forbidden: {code}: broker 3LO vault refused operation."
            )
        if resp.status_code != 200:
            raise RuntimeError(f"E_BROKER_UNAVAILABLE: HTTP {resp.status_code}")
        return resp.json()

    def store_3lo_token_for_caller(
        self,
        *,
        envelope: ContextEnvelope,
        token: Delegated3LOToken,
    ) -> str:
        """Stores `token` out-of-process in `broker_service` bound to `envelope`."""
        if (
            token.tenant_id != envelope.tenant.tenant_id
            or token.user_sub != envelope.security.sub
        ):
            raise PermissionError(
                "E_3LO_CONFUSED_DEPUTY_BLOCKED: 3LO token owner does not match caller envelope."
            )
        headers = self._mint_broker_headers(envelope)
        body = self._post(
            self.STORE_PATH,
            headers=headers,
            payload={
                "token_handle": token.token_handle,
                "provider": token.provider,
                "scopes": list(token.scopes),
                "access_token": token.access_token,
                "expires_at": int(token.expires_at),
            },
        )
        return str(body["token_handle"])

    def checkout_3lo_token(
        self,
        *,
        token_handle: str,
        envelope: ContextEnvelope,
        required_scope: str,
    ) -> Delegated3LOToken:
        """Checks out a 3LO token from `broker_service` without retaining it in Brain memory."""
        if envelope.tenant.tenant_id not in TENANT_DIRECTORY:
            raise PermissionError(
                f"E_TENANT_NOT_ONBOARDED: Tenant '{envelope.tenant.tenant_id}' is not onboarded."
            )
        headers = self._mint_broker_headers(envelope)
        body = self._post(
            self.CHECKOUT_PATH,
            headers=headers,
            payload={
                "token_handle": token_handle,
                "required_scope": required_scope,
            },
        )
        if (
            body.get("tenant_id") != envelope.tenant.tenant_id
            or body.get("user_sub") != envelope.security.sub
        ):
            raise PermissionError(
                "E_3LO_CONFUSED_DEPUTY_BLOCKED: broker returned mismatched 3LO owner."
            )
        return Delegated3LOToken(
            token_handle=str(body["token_handle"]),
            tenant_id=str(body["tenant_id"]),
            user_sub=str(body["user_sub"]),
            provider=str(body["provider"]),
            scopes=tuple(str(s) for s in body.get("scopes", ())),
            access_token=str(body["access_token"]),
            expires_at=int(body["expires_at"]),
        )


def get_default_3lo_vault() -> AuthManager3LOVault:
    """Returns `RemoteBroker3LOVault` when broker 3LO URL is set, else `AuthManager3LOVault`."""
    explicit_3lo_url = os.getenv("BROKER_3LO_VAULT_URL", "").strip()
    if explicit_3lo_url:
        return RemoteBroker3LOVault(explicit_3lo_url)
    broker_url = os.getenv("CREDENTIAL_BROKER_URL", "").strip()
    if broker_url and platform_config.is_live_mode():
        return RemoteBroker3LOVault(broker_url)
    return AuthManager3LOVault()


@dataclass
class _BucketState:
    requests_used: float = 0.0
    tokens_used: float = 0.0
    session_turns: dict[str, int] = field(default_factory=dict)
    last_refill_ts: float = 0.0


_REDIS_STORE_ERRORS: tuple[type[BaseException], ...] = (
    RedisError,
    OSError,
    TimeoutError,
)

_REDIS_CONSUME_LUA = """
local bucket_key = KEYS[1]
local turns_key = KEYS[2]
local order_key = KEYS[3]

local now_arg = ARGV[1]
local rpm_limit = tonumber(ARGV[2])
local tpm_limit = tonumber(ARGV[3])
local billable_tokens = tonumber(ARGV[4])
local session_id = ARGV[5]
local max_turns = tonumber(ARGV[6])
local max_tracked_sessions = tonumber(ARGV[7])
local ttl_seconds = tonumber(ARGV[8])

local now_ts
if now_arg == "SERVER_TIME" then
  local server_time = redis.call("TIME")
  now_ts = tonumber(server_time[1]) + (tonumber(server_time[2]) / 1000000.0)
else
  now_ts = tonumber(now_arg)
end

local fields = redis.call("HMGET", bucket_key, "requests_used", "tokens_used", "last_refill_ts")
local requests_used = tonumber(fields[1])
local tokens_used = tonumber(fields[2])
local last_refill_ts = tonumber(fields[3])

if last_refill_ts == nil then
  requests_used = 0.0
  tokens_used = 0.0
  last_refill_ts = now_ts
else
  local elapsed = now_ts - last_refill_ts
  if elapsed > 0.0 then
    local rpm_refill = (elapsed / 60.0) * rpm_limit
    local tpm_refill = (elapsed / 60.0) * tpm_limit
    requests_used = math.max(0.0, requests_used - rpm_refill)
    tokens_used = math.max(0.0, tokens_used - tpm_refill)
    last_refill_ts = now_ts
  end
end

if session_id ~= "" then
  local current_turns = tonumber(redis.call("HGET", turns_key, session_id) or "0")
  if (current_turns + 1) > max_turns then
    return {"ERR_SESSION_TURNS", tostring(current_turns), "0", "0"}
  end
end

if (requests_used + 1.0) > rpm_limit then
  return {"ERR_RPM", "0", "0", "0"}
end

if (tokens_used + billable_tokens) > tpm_limit then
  return {"ERR_TPM", "0", "0", "0"}
end

requests_used = requests_used + 1.0
tokens_used = tokens_used + billable_tokens
redis.call(
  "HSET",
  bucket_key,
  "requests_used", tostring(requests_used),
  "tokens_used", tostring(tokens_used),
  "last_refill_ts", tostring(last_refill_ts)
)
redis.call("EXPIRE", bucket_key, ttl_seconds)

local turns_used = 1
if session_id ~= "" then
  if redis.call("HEXISTS", turns_key, session_id) == 0 then
    while redis.call("LLEN", order_key) >= max_tracked_sessions do
      local oldest_session = redis.call("LPOP", order_key)
      if not oldest_session then
        break
      end
      redis.call("HDEL", turns_key, oldest_session)
    end
    redis.call("RPUSH", order_key, session_id)
  end
  turns_used = redis.call("HINCRBY", turns_key, session_id, 1)
  redis.call("EXPIRE", turns_key, ttl_seconds)
  redis.call("EXPIRE", order_key, ttl_seconds)
end

local remaining_rpm = math.floor(rpm_limit - requests_used)
local remaining_tpm = math.floor(tpm_limit - tokens_used)
return {"OK", tostring(turns_used), tostring(remaining_rpm), tostring(remaining_tpm)}
"""


def _decode_redis_text(raw_item: object) -> str:
    """Converts a Redis string/bytes reply item to `str` or raises `OSError` on unexpected types."""
    if isinstance(raw_item, bytes):
        return raw_item.decode("utf-8")
    if isinstance(raw_item, str):
        return raw_item
    raise OSError("Unexpected Redis bulkhead response element type")


_REDIS_TLS_LOCK = threading.Lock()
_REDIS_TLS_CACHE: dict[str, tuple[str, str | None]] = {}
_PINNED_REDIS_SECRET_RE = re.compile(
    r"^(?:projects/[A-Za-z0-9_-]+/secrets/)?[A-Za-z0-9_-]+/versions/[1-9][0-9]*$"
)


def _fetch_secret_version_bytes(resource_name: str) -> bytes:
    """Fetches raw secret payload bytes from Secret Manager using ADC or SPIFFE mTLS."""
    from agents.kms_rest import (
        build_spiffe_mtls_session,
        configure_client_certificate_env,
        workload_spiffe_mtls_active,
    )

    if workload_spiffe_mtls_active():
        session = build_spiffe_mtls_session()
        resp = session.get(
            f"https://secretmanager.mtls.googleapis.com/v1/{resource_name}:access",
            timeout=10.0,
        )
    else:
        import google.auth
        import google.auth.transport.requests
        import httpx

        configure_client_certificate_env()
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        resp = httpx.get(
            f"https://secretmanager.googleapis.com/v1/{resource_name}:access",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=10.0,
        )
    resp.raise_for_status()
    return base64.b64decode(resp.json()["payload"]["data"])


def _load_redis_tls_bundle(secret_version: str) -> tuple[str, str | None]:
    """Resolves a pinned `REDIS_TLS_SECRET_VERSION` JSON payload to `(rediss_url, ca_file_path)`."""
    cleaned = secret_version.strip()
    if cleaned.endswith("/latest") or not _PINNED_REDIS_SECRET_RE.fullmatch(
        cleaned
    ):
        raise ValueError(
            "E_REDIS_TLS_SECRET_UNPINNED: REDIS_TLS_SECRET_VERSION must reference a pinned "
            "numeric Secret Manager version."
        )
    resource_name = (
        cleaned
        if cleaned.startswith("projects/")
        else f"projects/{resolve_project_id()}/secrets/{cleaned}"
    )
    with _REDIS_TLS_LOCK:
        cached = _REDIS_TLS_CACHE.get(resource_name)
        if cached is not None:
            return cached
        raw = _fetch_secret_version_bytes(resource_name)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "E_REDIS_TLS_SECRET_INVALID: invalid JSON payload"
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError(
                "E_REDIS_TLS_SECRET_INVALID: expected JSON object"
            )
        url = str(payload.get("url") or "").strip()
        if not url.startswith(("rediss://", "redis://")):
            raise RuntimeError(
                "E_REDIS_TLS_SECRET_INVALID: missing redis/rediss url"
            )
        ca_pem = str(payload.get("ca_pem") or "").strip()
        ca_path: str | None = None
        if ca_pem:
            fd, ca_path = tempfile.mkstemp(
                prefix="cymbal-redis-ca-", suffix=".pem"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(ca_pem if ca_pem.endswith("\n") else ca_pem + "\n")
            os.chmod(ca_path, 0o600)
        result = (url, ca_path)
        _REDIS_TLS_CACHE[resource_name] = result
        return result


def build_redis_client_from_env() -> Any | None:
    """Builds a synchronous Redis client from `REDIS_TLS_SECRET_VERSION` or `REDIS_URL`.

    Returns:
        Configured synchronous `redis.Redis` client if configured; None otherwise.
    """
    secret_version = os.getenv("REDIS_TLS_SECRET_VERSION", "").strip()
    if secret_version:
        redis_url, ca_path = _load_redis_tls_bundle(secret_version)
        kwargs: dict[str, Any] = {
            "socket_connect_timeout": 2.0,
            "socket_timeout": 2.0,
            "decode_responses": False,
        }
        if ca_path is not None:
            kwargs["ssl_cert_reqs"] = "required"
            kwargs["ssl_ca_certs"] = ca_path
            kwargs["ssl_check_hostname"] = False
        return redis.Redis.from_url(redis_url, **kwargs)
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    return redis.Redis.from_url(
        redis_url,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
        decode_responses=False,
    )


class SharedBulkheadStore:
    """Thread-safe shared token-bucket and session-turn store for multi-instance deployments.

    Allows multiple `TokenBucketBulkhead` instances (or `RedisBulkheadStore`) to share atomic
    per-tenant RPM, TPM, and `session_turns` state. If `healthy` is False or an underlying backend
    raises `OSError` / `RuntimeError`, callers fail closed with `E_BULKHEAD_BACKEND_UNAVAILABLE`.
    """

    def __init__(self) -> None:
        self.buckets: dict[str, _BucketState] = {}
        self.lock = threading.Lock()
        self.healthy: bool = True

    def ensure_healthy(self) -> None:
        if not self.healthy:
            raise OSError("Shared bulkhead store connection lost")


class RedisBulkheadStore(SharedBulkheadStore):
    """Atomic Redis Lua-backed token-bucket and session-turn store for multi-replica gateways."""

    def __init__(
        self,
        redis_client: Any,
        *,
        key_prefix: str = "cymbal:bulkhead:v1",
        ttl_seconds: int = 3600,
    ) -> None:
        """Initializes an atomic Redis bulkhead store and rejects async/coroutine clients.

        Args:
            redis_client: Synchronous Redis client implementing `eval` and `delete`.
            key_prefix: Namespace prefix for per-tenant bucket and session-turn keys.
            ttl_seconds: Expiration window in seconds (>= 60) applied on active tenant buckets.

        Raises:
            ValueError: If `redis_client` is None, async/coroutine-based, or `ttl_seconds < 60`.
        """
        super().__init__()
        if redis_client is None:
            raise ValueError(
                "RedisBulkheadStore requires a synchronous Redis client"
            )
        client_module = type(redis_client).__module__
        eval_method = getattr(redis_client, "eval", None)
        delete_method = getattr(redis_client, "delete", None)
        if (
            client_module.startswith("redis.asyncio")
            or not callable(eval_method)
            or not callable(delete_method)
            or inspect.iscoroutinefunction(eval_method)
            or inspect.iscoroutinefunction(delete_method)
        ):
            raise ValueError(
                "RedisBulkheadStore requires a synchronous Redis client with eval and delete"
            )
        if ttl_seconds < 60:
            raise ValueError("ttl_seconds must be at least 60 seconds")
        self._redis = redis_client
        self._key_prefix = key_prefix
        self._ttl_seconds = int(ttl_seconds)

    def _keys_for_tenant(self, tenant_id: str) -> tuple[str, str, str]:
        return (
            f"{self._key_prefix}:bucket:{tenant_id}",
            f"{self._key_prefix}:turns:{tenant_id}",
            f"{self._key_prefix}:order:{tenant_id}",
        )

    def evict_tenant(self, tenant_id: str) -> bool:
        """Deletes all Redis token-bucket and session-turn keys for `tenant_id`.

        Args:
            tenant_id: Tenant identifier to purge from Redis.

        Returns:
            True if at least one Redis key was deleted; False otherwise.

        Raises:
            OSError: If Redis is unreachable or returns a malformed response.
        """
        self.ensure_healthy()
        bucket_key, turns_key, order_key = self._keys_for_tenant(tenant_id)
        try:
            deleted_key_count = self._redis.delete(
                bucket_key, turns_key, order_key
            )
        except _REDIS_STORE_ERRORS as exc:
            raise OSError(
                "Redis bulkhead store unavailable during tenant eviction"
            ) from exc
        if not isinstance(deleted_key_count, int) or isinstance(
            deleted_key_count, bool
        ):
            raise OSError("Unexpected Redis bulkhead delete response")
        return deleted_key_count > 0

    def consume_atomic(
        self,
        *,
        tenant_id: str,
        clock_value: float | None,
        rpm_limit: int,
        tpm_limit: int,
        billable_tokens: int,
        session_id: str | None,
        max_turns: int,
        max_tracked_sessions: int,
    ) -> dict[str, int]:
        """Executes continuous refill, quota checks, and consumption atomically via Redis Lua.

        Args:
            tenant_id: Verified tenant identifier.
            clock_value: Optional explicit timestamp for deterministic tests; None uses Redis TIME.
            rpm_limit: Requests-per-minute ceiling for the tenant.
            tpm_limit: Tokens-per-minute ceiling for the tenant.
            billable_tokens: Post-cache-discount tokens charged on this turn.
            session_id: Optional `sess-{jti}` session key for autonomous loop breaking.
            max_turns: Maximum autonomous calls permitted per gateway session token.
            max_tracked_sessions: Maximum concurrent sessions tracked per tenant (`FIFO` eviction).

        Returns:
            Dictionary with `session_turns_used`, `remaining_rpm`, and `remaining_tpm`.

        Raises:
            PermissionError: On `429` session-turn, RPM, or TPM quota exhaustion.
            OSError: On Redis transport error or malformed script reply (mapped to `503`).
        """
        self.ensure_healthy()
        bucket_key, turns_key, order_key = self._keys_for_tenant(tenant_id)
        clock_argument = (
            "SERVER_TIME" if clock_value is None else f"{clock_value:.6f}"
        )
        try:
            raw_eval_result = self._redis.eval(
                _REDIS_CONSUME_LUA,
                3,
                bucket_key,
                turns_key,
                order_key,
                clock_argument,
                str(int(rpm_limit)),
                str(int(tpm_limit)),
                str(int(billable_tokens)),
                session_id or "",
                str(int(max_turns)),
                str(int(max_tracked_sessions)),
                str(self._ttl_seconds),
            )
        except _REDIS_STORE_ERRORS as exc:
            raise OSError("Redis bulkhead store unavailable") from exc

        if (
            not isinstance(raw_eval_result, (list, tuple))
            or len(raw_eval_result) != 4
        ):
            raise OSError("Unexpected Redis bulkhead eval response")
        status_label = _decode_redis_text(raw_eval_result[0])
        turns_used_text = _decode_redis_text(raw_eval_result[1])
        remaining_rpm_text = _decode_redis_text(raw_eval_result[2])
        remaining_tpm_text = _decode_redis_text(raw_eval_result[3])

        if status_label == "ERR_SESSION_TURNS":
            raise PermissionError(
                "429 Too Many Requests: "
                "E_SESSION_LOOP_CIRCUIT_BREAKER: Tenant '"
                f"{tenant_id}' exceeded max autonomous turns per session "
                f"({max_turns}) in '{session_id}'."
            )
        if status_label == "ERR_RPM":
            raise PermissionError(
                f"429 Too Many Requests: Tenant '{tenant_id}' exceeded RPM limit ({rpm_limit})."
            )
        if status_label == "ERR_TPM":
            raise PermissionError(
                f"429 Too Many Requests: Tenant '{tenant_id}' exceeded TPM bulkhead ({tpm_limit})."
            )
        if status_label != "OK":
            raise OSError(f"Unexpected Redis bulkhead status: {status_label!r}")

        try:
            return {
                "session_turns_used": int(turns_used_text),
                "remaining_rpm": int(remaining_rpm_text),
                "remaining_tpm": int(remaining_tpm_text),
            }
        except ValueError as exc:
            raise OSError(
                "Non-integer counters in Redis bulkhead response"
            ) from exc


class TokenBucketBulkhead:
    """Subsystem 5: Continuous-Refill Token-Bucket Bulkhead, Thinking Cap & Session Loop Breaker."""

    MAX_TRACKED_SESSIONS: int = 4096

    def __init__(
        self,
        clock_fn: Callable[[], float] = time.monotonic,
        shared_store: SharedBulkheadStore | None = None,
    ) -> None:
        self._clock = clock_fn
        self._has_custom_clock = clock_fn is not time.monotonic
        self._shared_store = shared_store
        self._buckets: dict[str, _BucketState] = (
            shared_store.buckets if shared_store is not None else {}
        )
        self._lock = (
            shared_store.lock if shared_store is not None else threading.Lock()
        )
        register_tenant_eviction_target(self)

    def evict_tenant(self, tenant_id: str) -> bool:
        """Removes cached token-bucket and session-turn state for `tenant_id`.

        Args:
            tenant_id: Tenant identifier to evict.

        Returns:
            True if a bucket entry existed and was removed; False otherwise.
        """
        with self._lock:
            evicted_local = self._buckets.pop(tenant_id, None) is not None
        if isinstance(self._shared_store, RedisBulkheadStore):
            try:
                evicted_remote = self._shared_store.evict_tenant(tenant_id)
            except OSError as exc:
                raise PermissionError(
                    "503 Service Unavailable: E_BULKHEAD_BACKEND_UNAVAILABLE: "
                    "Shared rate-limit bulkhead store unreachable during tenant eviction."
                ) from exc
            return evicted_local or evicted_remote
        return evicted_local

    def _refill(
        self, state: _BucketState, rpm_limit: int, tpm_limit: int, now: float
    ) -> None:
        if state.last_refill_ts == 0.0:
            state.last_refill_ts = now
            return
        elapsed = max(0.0, now - state.last_refill_ts)
        if elapsed <= 0.0:
            return
        rpm_refill = (elapsed / 60.0) * float(rpm_limit)
        tpm_refill = (elapsed / 60.0) * float(tpm_limit)
        state.requests_used = max(0.0, state.requests_used - rpm_refill)
        state.tokens_used = max(0.0, state.tokens_used - tpm_refill)
        state.last_refill_ts = now

    def check_and_consume(
        self,
        *,
        tenant_id: str,
        requested_thinking_tokens: int,
        estimated_total_tokens: int,
        prompt_cache_hit: bool = True,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Enforces thinking budget caps, continuous-refill RPM/TPM bulkheads, and session loop
        limits.
        """
        if tenant_id not in TENANT_DIRECTORY:
            raise PermissionError(f"Unknown tenant_id: {tenant_id}")

        if requested_thinking_tokens < 0 or estimated_total_tokens < 0:
            raise PermissionError(
                "400 Bad Request: E_NEGATIVE_TOKEN_QUOTA_EXPLOIT_BLOCKED: Token counts "
                "cannot be negative."
            )

        cfg = TENANT_DIRECTORY[tenant_id]
        max_thinking = int(cfg["thinking_budget"])
        if requested_thinking_tokens > max_thinking:
            raise PermissionError(
                f"429 Too Many Requests: Requested thinking budget ({requested_thinking_tokens}) "
                f"exceeds tier cap ({max_thinking}) for tenant '{tenant_id}'."
            )

        billable_tokens = (
            int(estimated_total_tokens * 0.10)
            if prompt_cache_hit
            else estimated_total_tokens
        )

        if isinstance(self._shared_store, RedisBulkheadStore):
            max_turns = int(cfg.get("max_turns_per_session", 5))
            clock_value = self._clock() if self._has_custom_clock else None
            try:
                redis_counters = self._shared_store.consume_atomic(
                    tenant_id=tenant_id,
                    clock_value=clock_value,
                    rpm_limit=int(cfg["rpm_limit"]),
                    tpm_limit=int(cfg["tpm_limit"]),
                    billable_tokens=billable_tokens,
                    session_id=session_id,
                    max_turns=max_turns,
                    max_tracked_sessions=int(self.MAX_TRACKED_SESSIONS),
                )
            except PermissionError:
                raise
            except (OSError, RuntimeError) as exc:
                raise PermissionError(
                    "503 Service Unavailable: E_BULKHEAD_BACKEND_UNAVAILABLE: "
                    "Shared rate-limit bulkhead store unreachable; failing closed."
                ) from exc
            return {
                "tenant_id": tenant_id,
                "effective_thinking_tokens": requested_thinking_tokens,
                "billable_tokens": billable_tokens,
                "raw_tokens": estimated_total_tokens,
                "prompt_cache_hit": prompt_cache_hit,
                "remaining_tpm": redis_counters["remaining_tpm"],
                "remaining_rpm": redis_counters["remaining_rpm"],
                "session_turns_used": redis_counters["session_turns_used"],
            }

        with self._lock:
            if self._shared_store is not None:
                try:
                    self._shared_store.ensure_healthy()
                except (OSError, RuntimeError) as exc:
                    raise PermissionError(
                        "503 Service Unavailable: E_BULKHEAD_BACKEND_UNAVAILABLE: "
                        "Shared rate-limit bulkhead store unreachable; failing closed."
                    ) from exc
            now = self._clock()
            fs_doc_ref: Any = None
            if self._shared_store is None and platform_config.is_live_mode():
                try:
                    from google.cloud import firestore

                    if "pytest" not in sys.modules:
                        fs_client = firestore.Client(
                            project=resolve_project_id(),
                            database=os.getenv(
                                "FIRESTORE_DATABASE", "cymbal-memory-bank-prod"
                            ),
                        )
                        fs_doc_ref = fs_client.collection(
                            "cymbal_token_buckets_v1"
                        ).document(tenant_id)
                        snap = fs_doc_ref.get()
                        if snap.exists:
                            doc = snap.to_dict() or {}
                            state = _BucketState(
                                requests_used=float(
                                    doc.get("requests_used", 0.0)
                                ),
                                tokens_used=float(doc.get("tokens_used", 0.0)),
                                session_turns={
                                    str(k): int(v)
                                    for k, v in (
                                        doc.get("session_turns") or {}
                                    ).items()
                                },
                                last_refill_ts=now,
                            )
                            self._buckets[tenant_id] = state
                except Exception:
                    fs_doc_ref = None
            state = self._buckets.setdefault(
                tenant_id, _BucketState(last_refill_ts=now)
            )
            self._refill(
                state, int(cfg["rpm_limit"]), int(cfg["tpm_limit"]), now
            )

            if session_id:
                max_turns = int(cfg.get("max_turns_per_session", 5))
                current_turns = state.session_turns.get(session_id, 0)
                if current_turns + 1 > max_turns:
                    raise PermissionError(
                        "429 Too Many Requests: "
                        "E_SESSION_LOOP_CIRCUIT_BREAKER: Tenant '"
                        f"{tenant_id}"
                        "' "
                        "exceeded max autonomous turns per session ("
                        f"{max_turns}"
                        ") in '"
                        f"{session_id}"
                        "'."
                    )

            if state.requests_used + 1.0 > float(cfg["rpm_limit"]):
                raise PermissionError(
                    "429 Too Many Requests: Tenant '"
                    f"{tenant_id}' exceeded RPM limit ({cfg['rpm_limit']})."
                )
            if state.tokens_used + float(billable_tokens) > float(
                cfg["tpm_limit"]
            ):
                raise PermissionError(
                    "429 Too Many Requests: Tenant '"
                    f"{tenant_id}' exceeded TPM bulkhead ({cfg['tpm_limit']})."
                )

            state.requests_used += 1.0
            state.tokens_used += float(billable_tokens)
            if session_id:
                if (
                    session_id not in state.session_turns
                    and len(state.session_turns) >= self.MAX_TRACKED_SESSIONS
                ):
                    oldest_session = next(iter(state.session_turns))
                    state.session_turns.pop(oldest_session, None)
                state.session_turns[session_id] = (
                    state.session_turns.get(session_id, 0) + 1
                )
            turns_used = (
                state.session_turns.get(session_id, 1) if session_id else 1
            )
            remaining_tpm = int(float(cfg["tpm_limit"]) - state.tokens_used)
            remaining_rpm = int(float(cfg["rpm_limit"]) - state.requests_used)
            if fs_doc_ref is not None:
                with contextlib.suppress(Exception):
                    fs_doc_ref.set(
                        {
                            "tenant_id": tenant_id,
                            "requests_used": state.requests_used,
                            "tokens_used": state.tokens_used,
                            "session_turns": state.session_turns,
                            "updated_at": time.time(),
                        }
                    )

        return {
            "tenant_id": tenant_id,
            "effective_thinking_tokens": requested_thinking_tokens,  # within the tier cap here
            "billable_tokens": billable_tokens,
            "raw_tokens": estimated_total_tokens,
            "prompt_cache_hit": prompt_cache_hit,
            "remaining_tpm": remaining_tpm,
            "remaining_rpm": remaining_rpm,
            "session_turns_used": turns_used,
        }


def build_bulkhead_from_env() -> TokenBucketBulkhead:
    """Constructs a `TokenBucketBulkhead` wired to `RedisBulkheadStore` when `REDIS_URL` is set.

    Returns:
        `TokenBucketBulkhead` backed by `RedisBulkheadStore` if `REDIS_URL` is configured, else an
        in-process `TokenBucketBulkhead`.
    """
    redis_client = build_redis_client_from_env()
    if redis_client is not None:
        return TokenBucketBulkhead(
            shared_store=RedisBulkheadStore(redis_client)
        )
    return TokenBucketBulkhead()


class PrefixCacheSimulator:
    """Quantifies the FinOps benefit of Pooled Shared Prompt Prefix Caching vs. Siloed Caches."""

    def __init__(
        self,
        *,
        shared_prefix_tokens: int = 16_384,
        dynamic_turn_tokens: int = 1_616,
        cache_ttl_seconds: float = 3600.0,
        price_per_million_tokens_usd: float = 1.25,
    ) -> None:
        self.shared_prefix_tokens = shared_prefix_tokens
        self.dynamic_turn_tokens = dynamic_turn_tokens
        self.cache_ttl_seconds = cache_ttl_seconds
        self.price_per_m = price_per_million_tokens_usd

    def compare_pooled_vs_siloed(
        self,
        *,
        num_tenants: int,
        turns_per_tenant_per_day: int = 6,
        hours_simulated: int = 24,
    ) -> dict[str, Any]:
        """Simulates 24h of multi-tenant agent traffic and returns Pooled vs. Siloed COGS
        metrics.
        """
        total_turns = num_tenants * turns_per_tenant_per_day
        raw_tokens_per_turn = (
            self.shared_prefix_tokens + self.dynamic_turn_tokens
        )
        cached_turn_billable = (
            int(self.shared_prefix_tokens * 0.10) + self.dynamic_turn_tokens
        )

        ttl_windows = max(
            1, int((hours_simulated * 3600) / self.cache_ttl_seconds)
        )
        pooled_cold_misses = min(total_turns, ttl_windows)
        pooled_cache_hits = total_turns - pooled_cold_misses
        pooled_billable_tokens = (
            pooled_cold_misses * raw_tokens_per_turn
            + pooled_cache_hits * cached_turn_billable
        )

        windows_active_per_tenant = min(turns_per_tenant_per_day, ttl_windows)
        siloed_cold_misses = num_tenants * windows_active_per_tenant
        siloed_cache_hits = total_turns - siloed_cold_misses
        siloed_billable_tokens = (
            siloed_cold_misses * raw_tokens_per_turn
            + siloed_cache_hits * cached_turn_billable
        )

        unoptimized_tokens = total_turns * raw_tokens_per_turn
        pooled_cost_usd = (
            pooled_billable_tokens / 1_000_000
        ) * self.price_per_m
        siloed_cost_usd = (
            siloed_billable_tokens / 1_000_000
        ) * self.price_per_m
        unoptimized_cost_usd = (
            unoptimized_tokens / 1_000_000
        ) * self.price_per_m

        return {
            "num_tenants": num_tenants,
            "total_turns": total_turns,
            "pooled_cache_hit_rate_pct": round(
                (pooled_cache_hits / total_turns) * 100.0, 2
            ),
            "siloed_cache_hit_rate_pct": round(
                (siloed_cache_hits / total_turns) * 100.0, 2
            ),
            "pooled_billable_tokens": pooled_billable_tokens,
            "siloed_billable_tokens": siloed_billable_tokens,
            "pooled_cost_usd": round(pooled_cost_usd, 4),
            "siloed_cost_usd": round(siloed_cost_usd, 4),
            "unoptimized_cost_usd": round(unoptimized_cost_usd, 4),
            "pooled_vs_siloed_cogs_reduction_pct": round(
                (
                    (siloed_billable_tokens - pooled_billable_tokens)
                    / siloed_billable_tokens
                )
                * 100.0,
                2,
            ),
            "pooled_vs_unoptimized_savings_pct": round(
                (
                    (unoptimized_tokens - pooled_billable_tokens)
                    / unoptimized_tokens
                )
                * 100.0,
                2,
            ),
        }
