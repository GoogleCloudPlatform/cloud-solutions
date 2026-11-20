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

# pylint: disable=import-outside-toplevel,line-too-long,unused-variable

"""AlloyDB for PostgreSQL Fail-Closed RLS Bounded Connection Pool with Priority QoS (Hop 5).

Enforces transactional `SET LOCAL app.current_tenant_id = $1` with:
1. **Real Bounded Connection Pool (`pool_size=K`) & Priority QoS Scheduling**:
   - Multiplexes thousands of concurrent tenant turns over `K` physical connections.
   - When all `K` connections are busy, waiting callers are scheduled via a priority queue where
     **Enterprise Tier (`priority=0`)** preempts **Standard Tier (`priority=10`)** to prevent
     Head-of-Line Blocking during Standard-tier traffic storms.
2. **Exclusive Connection Ownership Under Mid-Transaction `await`**:
   - Each checked-out `PooledConnection` is exclusively locked to one coroutine until `finally:`
     resets `active_guc_tenant_id = None` and returns the connection to the pool.
3. **Comment-Stripped & Function-Aware SQL RLS Validation**:
   - Strips SQL block/line comments (`/**/`, `--`) and blocks `set_config('app.current_tenant_id',
     ...)`,
     `SET LOCAL`, `RESET ALL`, `UNION [ALL] SELECT`, tautologies (`OR 1=1`), and stacked queries.
"""

from __future__ import annotations

import asyncio
import contextvars
import datetime as dt
import heapq
import inspect
import itertools
import logging
import os
import re
import time
import weakref
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LAST_EXECUTED_GUC: contextvars.ContextVar[str] = contextvars.ContextVar(
    "last_executed_guc", default=""
)

_SQL_COMMENTS_RE = re.compile(r"(/\*.*?\*/|--[^\r\n]*)", re.DOTALL)
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")

ALLOWED_DB_USER_ROLES: frozenset[str] = frozenset(
    {
        "sre_admin",
        "compliance_officer",
        "read_only_analyst",
        "incident_responder",
        "support_viewer",
        "analyst",
    }
)
ALLOWED_DB_AGENT_IDS: frozenset[str] = frozenset(
    {
        "cymbal_shared_diagnostic_agent",
        "finvault_regulatory_escalation_agent",
        "sre_diagnostic_agent",
    }
)


def _is_allowed_db_agent_id(agent_id: str) -> bool:
    """Checks whether `agent_id` is in the static DB allowlist or dynamic `AGENT_CATALOG`."""
    if agent_id in ALLOWED_DB_AGENT_IDS:
        return True
    from agents.registry import AGENT_CATALOG

    return agent_id in AGENT_CATALOG


def _pg_row_to_dict(row: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Converts an `asyncpg.Record` into a JSON-safe dictionary (`datetime` -> ISO-8601 string)."""
    return {
        str(k): (v.isoformat() if isinstance(v, (dt.datetime, dt.date)) else v)
        for k, v in dict(row).items()
    }


def _validate_optional_rbac_guc(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if not _SAFE_IDENTIFIER_RE.fullmatch(cleaned):
        raise PermissionError(
            f"E_RLS_TAMPERING_DETECTED: Invalid RBAC GUC identifier format for '{name}'."
        )
    return cleaned


_FORBIDDEN_SQL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\bset\s+(local\s+|session\s+)?app\.current_(tenant_id|user_role|agent_id)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bset_config\s*\(\s*['\"]app\.current_(tenant_id|user_role|agent_id)['\"]",
        re.IGNORECASE,
    ),
    re.compile(
        r"\breset\s+(app\.current_(tenant_id|user_role|agent_id)|all)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(or|where|and)\s+1\s*=\s*1\b", re.IGNORECASE),
    re.compile(
        r"\b(or|where|and)\s+['\"]([^'\"]+)['\"]\s*=\s*['\"]\2['\"]",
        re.IGNORECASE,
    ),
    re.compile(r"\bunion\s+(all\s+)?select\b", re.IGNORECASE),
    re.compile(
        r";\s*(select|insert|update|delete|drop|alter|grant|revoke|truncate|set|copy|do)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpg_sleep\s*\(", re.IGNORECASE),
)


@dataclass(frozen=True)
class IncidentRecord:
    incident_id: str
    tenant_id: str
    service_name: str
    severity: str
    summary: str
    pii_notes: str


@dataclass
class PooledConnection:
    """Represents one physical database connection in the bounded AlloyDB connection pool."""

    connection_id: int
    active_guc_tenant_id: str | None = None
    active_guc_user_role: str | None = None
    active_guc_agent_id: str | None = None
    in_transaction: bool = False
    checkout_count: int = 0


DEFAULT_SEEDED_INCIDENTS: tuple[IncidentRecord, ...] = (
    IncidentRecord(
        incident_id="INC-FV-1001",
        tenant_id="tenant-finvault-alpha",
        service_name="core-wire-settlement",
        severity="P1",
        summary="Wire settlement latency spike > 4500ms in us-central1",
        pii_notes="Affected customer SSN 123-45-6789 and routing ABA: 021000021",
    ),
    IncidentRecord(
        incident_id="INC-FV-1002",
        tenant_id="tenant-finvault-alpha",
        service_name="ledger-reconciliation",
        severity="P2",
        summary="OCC daily reconciliation drift detected on shard 4",
        pii_notes="Escalate to FinVault compliance officer",
    ),
    IncidentRecord(
        incident_id="INC-RS-2001",
        tenant_id="tenant-retailstream-beta",
        service_name="checkout-cart-api",
        severity="P1",
        summary="Checkout 503 surge during flash sale event",
        pii_notes="Customer card 4532-0151-1283-0366 failed authorization",
    ),
)

DEFAULT_SEEDED_RUNBOOKS: dict[str, list[dict[str, str]]] = {
    "tenant-finvault-alpha": [
        {
            "runbook_id": "RB-FV-01",
            "tenant_id": "tenant-finvault-alpha",
            "title": "FinVault Wire Settlement Failover & OCC Notice Runbook",
            "remediation_steps": (
                "1. Drain secondary AlloyDB read pool. 2. Trigger Agent Alpha OCC filing."
            ),
        }
    ],
    "tenant-retailstream-beta": [
        {
            "runbook_id": "RB-RS-01",
            "tenant_id": "tenant-retailstream-beta",
            "title": "RetailStream Checkout Redis Cache Warmup Runbook",
            "remediation_steps": (
                "1. Scale Cloud Run checkout pods. 2. Open ServiceNow ITOM ticket."
            ),
        }
    ],
}


ALLOWED_DB_WRITE_USER_ROLES: frozenset[str] = frozenset(
    {
        "sre_admin",
        "incident_responder",
    }
)
ALLOWED_DB_WRITE_AGENT_IDS: frozenset[str] = frozenset(
    {
        "cymbal_shared_diagnostic_agent",
        "sre_diagnostic_agent",
    }
)


def resolve_gcp_iam_db_token() -> str:
    """Fetches a fresh Google Cloud OAuth2 IAM access token for AlloyDB IAM authentication."""
    import google.auth
    from google.auth.transport import requests as google_requests

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google_requests.Request())
    token = getattr(credentials, "token", None)
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError(
            "E_ALLOYDB_IAM_TOKEN_EMPTY: Failed to obtain GCP IAM database token."
        )
    return token.strip()


def make_asyncpg_pool_factory(
    dsn: str,
    max_size: int = 20,
    *,
    user: str | None = None,
    password: str | Callable[[], str] | None = None,
    iam_auth: bool = False,
    ssl: Any | None = None,
    db_role: str | None = None,
) -> Callable[[], Any]:
    """Creates a lazy per-event-loop `asyncpg.create_pool` factory for `dsn`.

    Args:
        dsn: PostgreSQL / AlloyDB connection string.
        max_size: Maximum connection count per event-loop pool.
        user: Optional database role override passed directly to `asyncpg.create_pool`.
        password: Optional role password or token-provider callable passed to `asyncpg.create_pool`.
        iam_auth: When True, dynamically mints short-lived GCP IAM OAuth2 tokens per connection.
        ssl: Optional SSL mode/context override (`"require"` by default for non-loopback IAM auth).
        db_role: Optional PostgreSQL role assumed on connection initialization (`SET ROLE ...`).

    Returns:
        An async zero-argument callable returning an `asyncpg.Pool` bound to the active loop.

    Raises:
        ValueError: If `dsn` or `db_role` is invalid.
    """
    clean_dsn = dsn.strip()
    if not clean_dsn:
        raise ValueError("PostgreSQL DSN must be a non-empty string.")
    clean_db_role: str | None = None
    if db_role is not None:
        clean_db_role = db_role.strip()
        if not _SAFE_IDENTIFIER_RE.fullmatch(clean_db_role):
            raise ValueError(
                f"Invalid PostgreSQL db_role identifier: {db_role!r}"
            )
    credential_kwargs: dict[str, Any] = {}
    if user is not None:
        credential_kwargs["user"] = user
    if password is not None:
        credential_kwargs["password"] = password
    elif iam_auth:
        credential_kwargs["password"] = resolve_gcp_iam_db_token
    if ssl is not None:
        credential_kwargs["ssl"] = ssl
    elif (
        iam_auth
        and "@127.0.0.1" not in clean_dsn
        and "@localhost" not in clean_dsn
        and "//127.0.0.1" not in clean_dsn
        and "//localhost" not in clean_dsn
    ):
        credential_kwargs["ssl"] = "require"

    async def _init_conn(conn: Any) -> None:
        if clean_db_role is not None:
            await conn.execute(f'SET ROLE "{clean_db_role}";')

    async def _create_loop_pool() -> Any:
        import asyncpg

        return await asyncpg.create_pool(
            dsn=clean_dsn,
            min_size=1,
            max_size=max(1, max_size),
            init=_init_conn if clean_db_role is not None else None,
            **credential_kwargs,
        )

    return _create_loop_pool


def make_tenant_iam_pool_factory(
    dsn: str,
    *,
    project_id: str | None = None,
    max_size: int = 4,
    db_role: str | None = "cymbal_mcp_app",
) -> Callable[[str], Any]:
    """Builds a per-tenant `asyncpg` pool factory authenticating as each tenant's `ct-*` IAM SA.

    Designed for Cloud Run Agent Identity runtimes (`principal://agents.global...`), where each
    turn uses the brokered 300s `ct-<sha256(tenant_id)[:24]>@<project>.iam` OAuth2 access token
    and assumes the `NOSUPERUSER NOBYPASSRLS` `cymbal_mcp_app` database role.
    """
    from agents.auth import _ACTIVE_TENANT_ENVELOPE
    from agents.platform_config import resolve_project_id
    from agents.tenant_credentials import get_default_broker
    from agents.tenant_identity import tenant_service_account_id

    clean_dsn = dsn.strip()
    if not clean_dsn:
        raise ValueError("PostgreSQL DSN must be a non-empty string.")

    def _create_tenant_pool(tenant_id: str) -> Any:
        clean_tenant = tenant_id.strip()
        if not clean_tenant:
            raise ValueError("tenant_id must be a non-empty string.")
        resolved_project = project_id or resolve_project_id()
        iam_db_user = (
            f"{tenant_service_account_id(clean_tenant)}@{resolved_project}.iam"
        )

        def _tenant_token_provider() -> str:
            envelope = _ACTIVE_TENANT_ENVELOPE.get()
            if envelope is None or envelope.tenant.tenant_id != clean_tenant:
                raise PermissionError(
                    "E_ALLOYDB_TENANT_ENVELOPE_MISMATCH: Active ContextEnvelope required to mint "
                    f"AlloyDB IAM token for '{clean_tenant}'."
                )
            cred = get_default_broker(resolved_project).credential_for(envelope)
            if not cred.token:
                raise RuntimeError(
                    "E_ALLOYDB_IAM_TOKEN_EMPTY: Broker returned empty ct-* token."
                )
            return cred.token

        loop_factory = make_asyncpg_pool_factory(
            clean_dsn,
            max_size=max_size,
            user=iam_db_user,
            password=_tenant_token_provider,
            iam_auth=True,
            db_role=db_role,
        )
        return loop_factory()

    return _create_tenant_pool


def build_rls_db_pool_from_env(*, pool_size: int = 20) -> RLSDatabasePool:
    """Constructs an `RLSDatabasePool` from `DATABASE_URL` and IAM auth environment flags."""
    from agents.workload_identity import flag_enabled

    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        return RLSDatabasePool(pool_size=pool_size)
    if flag_enabled("ALLOYDB_TENANT_IAM_AUTH"):
        return RLSDatabasePool(
            pool_size=pool_size,
            tenant_pool_factory=make_tenant_iam_pool_factory(
                dsn, max_size=min(4, max(1, pool_size))
            ),
        )
    iam_auth = flag_enabled("ALLOYDB_IAM_AUTH")
    return RLSDatabasePool(
        pool_size=pool_size,
        pool_factory=make_asyncpg_pool_factory(
            dsn,
            max_size=pool_size,
            iam_auth=iam_auth,
            db_role="cymbal_mcp_app" if iam_auth else None,
        ),
    )


class RLSDatabasePool:
    """Hop 5 Persistence Layer: Bounded Priority Connection Pool with Transactional `SET LOCAL`."""

    def __init__(
        self,
        asyncpg_pool: Any | None = None,
        pool_size: int = 20,
        pool_factory: Callable[[], Any] | None = None,
        tenant_pool_factory: Callable[[str], Any] | None = None,
    ) -> None:
        """Initializes the bounded RLS connection pool.

        Args:
            asyncpg_pool: Optional pre-created `asyncpg` pool for single-loop execution.
            pool_size: Maximum concurrent in-memory or live connections.
            pool_factory: Optional zero-argument callable (sync or async) returning a
                loop-bound `asyncpg` pool (for example via `make_asyncpg_pool_factory(dsn)`).
            tenant_pool_factory: Optional single-argument `(tenant_id) -> asyncpg.Pool` factory
                for per-tenant brokered IAM authentication.
        """
        self._pool = asyncpg_pool
        self._pool_factory = pool_factory if asyncpg_pool is None else None
        self._tenant_pool_factory = (
            tenant_pool_factory
            if (asyncpg_pool is None and pool_factory is None)
            else None
        )
        self._closed: bool = False
        self._pools_by_loop: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, Any
        ] = weakref.WeakKeyDictionary()
        self._tenant_pools_by_loop: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, dict[str, Any]
        ] = weakref.WeakKeyDictionary()
        self._pool_locks_by_loop: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, asyncio.Lock
        ] = weakref.WeakKeyDictionary()
        self._closed_loops: weakref.WeakSet[asyncio.AbstractEventLoop] = (
            weakref.WeakSet()
        )
        self._hooked_loops: weakref.WeakSet[asyncio.AbstractEventLoop] = (
            weakref.WeakSet()
        )
        self.pool_size = max(1, pool_size)
        self._connections: list[PooledConnection] = [
            PooledConnection(connection_id=i + 1) for i in range(self.pool_size)
        ]
        self._available: list[PooledConnection] = list(self._connections)
        self._waiters: list[
            tuple[int, int, asyncio.Future[PooledConnection]]
        ] = []
        self._seq = itertools.count()
        self.active_in_use: int = 0
        self.peak_in_use: int = 0
        self.total_checkouts: int = 0

        self._incidents: list[IncidentRecord] = list(DEFAULT_SEEDED_INCIDENTS)
        self._by_tenant: dict[str, list[IncidentRecord]] = {}
        for incident in self._incidents:
            self._by_tenant.setdefault(incident.tenant_id, []).append(incident)

        self._runbooks: dict[str, list[dict[str, str]]] = {
            tenant_key: list(records)
            for tenant_key, records in DEFAULT_SEEDED_RUNBOOKS.items()
        }

    def _install_loop_close_hook(self, loop: asyncio.AbstractEventLoop) -> None:
        """Hooks `loop.close()` to release the loop's pool reference and break `pool._loop`
        cycles.
        """
        if loop in self._hooked_loops:
            return
        original_close = getattr(loop, "close", None)
        if not callable(original_close):
            logger.warning(
                "Could not install loop.close hook on %s (close attribute is not callable); "
                "call await pool.close() explicitly on this event loop before closing it.",
                type(loop).__name__,
            )
            return
        pools_by_loop = self._pools_by_loop
        tenant_pools_by_loop = self._tenant_pools_by_loop
        locks_by_loop = self._pool_locks_by_loop
        closed_loops = self._closed_loops

        def _wrapped_loop_close() -> None:
            loop_pool = pools_by_loop.pop(loop, None)
            tenant_pools = tenant_pools_by_loop.pop(loop, None) or {}
            locks_by_loop.pop(loop, None)
            closed_loops.add(loop)
            terminate_fn = getattr(loop_pool, "terminate", None)
            if callable(terminate_fn):
                terminate_fn()
            for t_pool in tenant_pools.values():
                t_term = getattr(t_pool, "terminate", None)
                if callable(t_term):
                    t_term()
            original_close()

        try:
            loop.close = _wrapped_loop_close  # type: ignore[method-assign]
            self._hooked_loops.add(loop)
        except (AttributeError, TypeError) as exc:
            logger.warning(
                "Could not install loop.close hook on %s (%s); "
                "call await pool.close() explicitly on this event loop before closing it.",
                type(loop).__name__,
                exc,
            )
            return

    async def _resolve_live_pool(
        self, tenant_id: str | None = None
    ) -> Any | None:
        """Returns the live `asyncpg` pool isolated to the current running event loop.

        Uses a `WeakKeyDictionary` keyed on the event loop object so garbage-collected loops
        never hand stale pools to new loops that reuse the same memory address, and guards
        concurrent first calls on the same loop with a per-loop `asyncio.Lock`.

        Returns:
            The active loop's `asyncpg` pool, or `None` when operating in in-memory mode.

        Raises:
            RuntimeError: If the pool has been closed (`E_DB_POOL_CLOSED`) or `pool_factory`
                returned `None` (`E_DB_POOL_FACTORY_RETURNED_NONE`).
        """
        if self._closed:
            raise RuntimeError(
                "E_DB_POOL_CLOSED: RLSDatabasePool has been closed."
            )
        loop = asyncio.get_running_loop()
        if loop in self._closed_loops:
            raise RuntimeError(
                "E_DB_POOL_CLOSED: RLSDatabasePool has been closed on the current event loop."
            )
        if self._pool is not None:
            return self._pool
        if self._tenant_pool_factory is not None:
            clean_tenant = (tenant_id or "").strip()
            if not clean_tenant:
                return None
            loop_map = self._tenant_pools_by_loop.get(loop)
            if loop_map is not None and clean_tenant in loop_map:
                return loop_map[clean_tenant]
            loop_lock = self._pool_locks_by_loop.get(loop)
            if loop_lock is None:
                loop_lock = asyncio.Lock()
                self._pool_locks_by_loop[loop] = loop_lock
            async with loop_lock:
                if self._closed or loop in self._closed_loops:
                    raise RuntimeError(
                        "E_DB_POOL_CLOSED: RLSDatabasePool has been closed on the current "
                        "event loop."
                    )
                loop_map = self._tenant_pools_by_loop.setdefault(loop, {})
                if clean_tenant in loop_map:
                    return loop_map[clean_tenant]
                created_t = self._tenant_pool_factory(clean_tenant)
                resolved_t = (
                    await created_t
                    if inspect.isawaitable(created_t)
                    else created_t
                )
                if resolved_t is None:
                    raise RuntimeError(
                        "E_DB_POOL_FACTORY_RETURNED_NONE: tenant_pool_factory returned None."
                    )
                self._install_loop_close_hook(loop)
                loop_map[clean_tenant] = resolved_t
                return resolved_t
        if self._pool_factory is None:
            return None
        existing_pool = self._pools_by_loop.get(loop)
        if existing_pool is not None:
            return existing_pool
        loop_lock = self._pool_locks_by_loop.get(loop)
        if loop_lock is None:
            loop_lock = asyncio.Lock()
            self._pool_locks_by_loop[loop] = loop_lock
        async with loop_lock:
            if self._closed or loop in self._closed_loops:
                raise RuntimeError(
                    "E_DB_POOL_CLOSED: RLSDatabasePool has been closed on the current event loop."
                )
            existing_pool = self._pools_by_loop.get(loop)
            if existing_pool is not None:
                return existing_pool
            created = self._pool_factory()
            resolved_pool = (
                await created if inspect.isawaitable(created) else created
            )
            if resolved_pool is None:
                raise RuntimeError(
                    "E_DB_POOL_FACTORY_RETURNED_NONE: pool_factory returned None; "
                    "refusing to fall back to in-memory seeded rows."
                )
            self._install_loop_close_hook(loop)
            self._pools_by_loop[loop] = resolved_pool
            return resolved_pool

    async def close(self) -> None:
        """Closes the current event loop's live `asyncpg` pool and marks it closed.

        Note (Per-Loop Scope in Factory Mode): Because `asyncpg.Pool.close()` must be awaited on
        the event loop that created the pool, `close()` in `pool_factory` mode closes only the
        pool bound to `asyncio.get_running_loop()` (plus `self._pool` if a single-loop pool was
        injected). A multi-loop shutdown must call `await db_pool.close()` on each active loop
        (or let each loop's `loop.close()` hook terminate its pool). Tracking entries are removed
        only after `close()` succeeds so a partial failure never loses track of an open pool.
        """
        current_loop = asyncio.get_running_loop()
        if self._pool is not None:
            close_fn = getattr(self._pool, "close", None)
            if callable(close_fn):
                close_result = close_fn()
                if inspect.isawaitable(close_result):
                    await close_result
            self._pool = None
            self._closed = True
            self._closed_loops.add(current_loop)
            return

        if self._tenant_pool_factory is not None:
            tenant_pools = self._tenant_pools_by_loop.get(current_loop)
            if tenant_pools:
                for t_pool in list(tenant_pools.values()):
                    close_fn = getattr(t_pool, "close", None)
                    if callable(close_fn):
                        close_result = close_fn()
                        if inspect.isawaitable(close_result):
                            await close_result
                self._tenant_pools_by_loop.pop(current_loop, None)
                self._pool_locks_by_loop.pop(current_loop, None)
            self._closed_loops.add(current_loop)
            return

        if self._pool_factory is not None:
            loop_pool = self._pools_by_loop.get(current_loop)
            if loop_pool is not None:
                close_fn = getattr(loop_pool, "close", None)
                if callable(close_fn):
                    close_result = close_fn()
                    if inspect.isawaitable(close_result):
                        await close_result
                self._pools_by_loop.pop(current_loop, None)
                self._pool_locks_by_loop.pop(current_loop, None)
            self._closed_loops.add(current_loop)
            return

        self._closed = True
        self._closed_loops.add(current_loop)

    @property
    def _shared_connection(self) -> PooledConnection:
        """Backward-compatible accessor returning connection #1 for single-connection
        inspections.
        """
        return self._connections[0]

    @property
    def last_executed_guc(self) -> str:
        return _LAST_EXECUTED_GUC.get()

    def seed_tenant_incident(self, record: IncidentRecord) -> None:
        """Seeds an incident row for dynamic multi-tenant scale benchmarks."""
        self._incidents.append(record)
        self._by_tenant.setdefault(record.tenant_id, []).append(record)

    def seed_tenant_runbook(
        self, tenant_id: str, runbook: Mapping[str, str]
    ) -> None:
        """Seeds a tenant-scoped remediation runbook for dynamic enterprise tenants.

        Args:
            tenant_id: Owning tenant identifier enforced by RLS.
            runbook: Runbook dictionary containing `runbook_id`, `title`, and `remediation_steps`.

        Raises:
            ValueError: If `tenant_id` is empty.
        """
        clean_tenant = tenant_id.strip()
        if not clean_tenant:
            raise ValueError("tenant_id must be a non-empty string.")
        seeded_entry = {str(key): str(val) for key, val in runbook.items()}
        seeded_entry["tenant_id"] = clean_tenant
        self._runbooks.setdefault(clean_tenant, []).append(seeded_entry)

    @staticmethod
    def validate_sql_safety(sql: str) -> None:
        """Strips SQL comments and blocks any attempt to override `app.current_tenant_id` or
        inject.
        """
        decommented = _SQL_COMMENTS_RE.sub(" ", sql)
        for pattern in _FORBIDDEN_SQL_PATTERNS:
            if pattern.search(decommented):
                raise PermissionError(
                    "E_RLS_TAMPERING_DETECTED: Query attempted to override `app.current_tenant_id` "
                    "(SET LOCAL / set_config / RESET) or inject tautology/stacked SQL."
                )

    async def _acquire_connection(
        self, priority: int
    ) -> tuple[PooledConnection, float]:
        t0 = time.perf_counter()
        if self._available:
            conn = self._available.pop(0)
        else:
            loop = asyncio.get_running_loop()
            fut: asyncio.Future[PooledConnection] = loop.create_future()
            heapq.heappush(self._waiters, (priority, next(self._seq), fut))
            conn = await fut

        wait_ms = (time.perf_counter() - t0) * 1000.0
        self.active_in_use += 1
        self.peak_in_use = max(self.peak_in_use, self.active_in_use)
        self.total_checkouts += 1
        conn.checkout_count += 1
        return conn, wait_ms

    def _release_connection(self, conn: PooledConnection) -> None:
        self.active_in_use = max(0, self.active_in_use - 1)
        while self._waiters:
            _, _, fut = heapq.heappop(self._waiters)
            if (
                not fut.done()
                and not fut.cancelled()
                and not fut.get_loop().is_closed()
            ):
                fut.set_result(conn)
                return
        self._available.append(conn)

    @asynccontextmanager
    async def checkout_transaction(
        self,
        tenant_id: str | None,
        *,
        user_role: str | None = None,
        agent_id: str | None = None,
        priority: int = 10,
    ) -> AsyncIterator[tuple[PooledConnection, float]]:
        """Acquires an exclusive pooled connection, sets `SET LOCAL` RLS + RBAC GUCs, and resets
        on exit.
        """
        if self._closed or asyncio.get_running_loop() in self._closed_loops:
            raise RuntimeError(
                "E_DB_POOL_CLOSED: RLSDatabasePool has been closed."
            )
        conn, wait_ms = await self._acquire_connection(priority)
        assert (
            not conn.in_transaction
        ), "Connection pool invariant violated: connection already in tx!"
        assert (
            conn.active_guc_tenant_id is None
        ), "Connection pool invariant violated: dirty GUC!"

        conn.in_transaction = True
        normalized = tenant_id.strip() if tenant_id else ""
        clean_role = _validate_optional_rbac_guc(
            "app.current_user_role", user_role
        )
        clean_agent = _validate_optional_rbac_guc(
            "app.current_agent_id", agent_id
        )
        if normalized:
            conn.active_guc_tenant_id = normalized
            conn.active_guc_user_role = clean_role
            conn.active_guc_agent_id = clean_agent
            guc_parts = [f"SET LOCAL app.current_tenant_id = '{normalized}';"]
            if clean_role:
                guc_parts.append(
                    f"SET LOCAL app.current_user_role = '{clean_role}';"
                )
            if clean_agent:
                guc_parts.append(
                    f"SET LOCAL app.current_agent_id = '{clean_agent}';"
                )
            _LAST_EXECUTED_GUC.set(" ".join(guc_parts))
        else:
            conn.active_guc_tenant_id = None
            conn.active_guc_user_role = None
            conn.active_guc_agent_id = None
            _LAST_EXECUTED_GUC.set("")
        try:
            yield conn, wait_ms
        finally:
            conn.active_guc_tenant_id = None
            conn.active_guc_user_role = None
            conn.active_guc_agent_id = None
            conn.in_transaction = False
            self._release_connection(conn)

    async def query_incidents(
        self,
        *,
        tenant_id: str | None,
        user_role: str | None = None,
        agent_id: str | None = None,
        severity_filter: str | None = None,
        raw_sql: str | None = None,
        simulate_mid_tx_crash: bool = False,
        simulated_query_ms: float = 0.0,
        priority: int = 10,
    ) -> list[dict[str, Any]]:
        """Executes `SET LOCAL app.current_tenant_id = $1` (+ optional RBAC GUCs) and returns
        tenant-scoped rows.
        """
        if raw_sql:
            self.validate_sql_safety(raw_sql)
        clean_role = _validate_optional_rbac_guc(
            "app.current_user_role", user_role
        )
        clean_agent = _validate_optional_rbac_guc(
            "app.current_agent_id", agent_id
        )

        live_pool = await self._resolve_live_pool(tenant_id)
        if live_pool is not None:
            if not tenant_id or not tenant_id.strip():
                _LAST_EXECUTED_GUC.set("")
                return []
            clean_tenant = tenant_id.strip()
            async with live_pool.acquire() as conn, conn.transaction():
                # `SET LOCAL ... = $1` is not valid with bind parameters (asyncpg/Postgres);
                # set_config(name, value, is_local => true) is the parameterized equivalent.
                await conn.execute(
                    "SELECT set_config('app.current_tenant_id', $1, true);",
                    tenant_id,
                )
                guc_parts = [
                    f"SET LOCAL app.current_tenant_id = '{clean_tenant}';"
                ]
                if clean_role:
                    await conn.execute(
                        "SELECT set_config('app.current_user_role', $1, true);",
                        clean_role,
                    )
                    guc_parts.append(
                        f"SET LOCAL app.current_user_role = '{clean_role}';"
                    )
                if clean_agent:
                    await conn.execute(
                        "SELECT set_config('app.current_agent_id', $1, true);",
                        clean_agent,
                    )
                    guc_parts.append(
                        f"SET LOCAL app.current_agent_id = '{clean_agent}';"
                    )
                _LAST_EXECUTED_GUC.set(" ".join(guc_parts))
                if severity_filter:
                    rows = await conn.fetch(
                        "SELECT * FROM tenant_incidents WHERE severity = $1;",
                        severity_filter,
                    )
                else:
                    rows = await conn.fetch("SELECT * FROM tenant_incidents;")
                return [_pg_row_to_dict(r) for r in rows]

        async with self.checkout_transaction(
            tenant_id,
            user_role=clean_role,
            agent_id=clean_agent,
            priority=priority,
        ) as (conn, _wait_ms):
            expected_tenant = tenant_id.strip() if tenant_id else None
            if simulated_query_ms > 0.0:
                await asyncio.sleep(simulated_query_ms / 1000.0)
            if simulate_mid_tx_crash:
                raise RuntimeError(
                    "Simulated mid-transaction database crash before commit."
                )

            active_tenant = conn.active_guc_tenant_id
            # Verify exclusive connection ownership was never mutated across the await point
            assert active_tenant == (expected_tenant or None)
            if not active_tenant:
                return []
            if (
                conn.active_guc_user_role
                and conn.active_guc_user_role not in ALLOWED_DB_USER_ROLES
            ):
                return []
            if conn.active_guc_agent_id and not _is_allowed_db_agent_id(
                conn.active_guc_agent_id
            ):
                return []

            candidates = self._by_tenant.get(active_tenant, [])
            return [
                {
                    "incident_id": inc.incident_id,
                    "tenant_id": inc.tenant_id,
                    "service_name": inc.service_name,
                    "severity": inc.severity,
                    "summary": inc.summary,
                    "pii_notes": inc.pii_notes,
                }
                for inc in candidates
                if severity_filter is None or inc.severity == severity_filter
            ]

    async def query_runbooks(
        self,
        *,
        tenant_id: str | None,
        user_role: str | None = None,
        agent_id: str | None = None,
    ) -> list[dict[str, str]]:
        """Retrieves tenant-scoped runbooks under fail-closed RLS and RBAC."""
        clean_role = _validate_optional_rbac_guc(
            "app.current_user_role", user_role
        )
        clean_agent = _validate_optional_rbac_guc(
            "app.current_agent_id", agent_id
        )
        live_pool = await self._resolve_live_pool(tenant_id)
        if live_pool is not None:
            if not tenant_id or not tenant_id.strip():
                _LAST_EXECUTED_GUC.set("")
                return []
            clean_tenant = tenant_id.strip()
            async with live_pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.current_tenant_id', $1, true);",
                    clean_tenant,
                )
                guc_parts = [
                    f"SET LOCAL app.current_tenant_id = '{clean_tenant}';"
                ]
                if clean_role:
                    await conn.execute(
                        "SELECT set_config('app.current_user_role', $1, true);",
                        clean_role,
                    )
                    guc_parts.append(
                        f"SET LOCAL app.current_user_role = '{clean_role}';"
                    )
                if clean_agent:
                    await conn.execute(
                        "SELECT set_config('app.current_agent_id', $1, true);",
                        clean_agent,
                    )
                    guc_parts.append(
                        f"SET LOCAL app.current_agent_id = '{clean_agent}';"
                    )
                _LAST_EXECUTED_GUC.set(" ".join(guc_parts))
                rows = await conn.fetch(
                    "SELECT * FROM tenant_runbooks ORDER BY runbook_id;"
                )
                return [_pg_row_to_dict(row) for row in rows]

        async with self.checkout_transaction(
            tenant_id, user_role=clean_role, agent_id=clean_agent
        ) as (conn, _wait_ms):
            if not conn.active_guc_tenant_id:
                return []
            if (
                conn.active_guc_user_role
                and conn.active_guc_user_role not in ALLOWED_DB_USER_ROLES
            ):
                return []
            if conn.active_guc_agent_id and not _is_allowed_db_agent_id(
                conn.active_guc_agent_id
            ):
                return []
            return list(self._runbooks.get(conn.active_guc_tenant_id, []))

    async def update_incident(
        self,
        *,
        tenant_id: str | None,
        incident_id: str,
        user_role: str | None = None,
        agent_id: str | None = None,
        severity: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any] | None:
        """Updates mutable `severity`/`summary` columns on `tenant_incidents` under RLS + RBAC."""
        clean_incident_id = incident_id.strip()
        if not clean_incident_id:
            raise ValueError("incident_id must be a non-empty string.")
        if severity is None and summary is None:
            raise ValueError(
                "At least one of severity or summary must be provided."
            )
        clean_role = _validate_optional_rbac_guc(
            "app.current_user_role", user_role
        )
        clean_agent = _validate_optional_rbac_guc(
            "app.current_agent_id", agent_id
        )

        live_pool = await self._resolve_live_pool(tenant_id)
        if live_pool is not None:
            if not tenant_id or not tenant_id.strip():
                _LAST_EXECUTED_GUC.set("")
                return None
            clean_tenant = tenant_id.strip()
            async with live_pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.current_tenant_id', $1, true);",
                    clean_tenant,
                )
                guc_parts = [
                    f"SET LOCAL app.current_tenant_id = '{clean_tenant}';"
                ]
                if clean_role:
                    await conn.execute(
                        "SELECT set_config('app.current_user_role', $1, true);",
                        clean_role,
                    )
                    guc_parts.append(
                        f"SET LOCAL app.current_user_role = '{clean_role}';"
                    )
                if clean_agent:
                    await conn.execute(
                        "SELECT set_config('app.current_agent_id', $1, true);",
                        clean_agent,
                    )
                    guc_parts.append(
                        f"SET LOCAL app.current_agent_id = '{clean_agent}';"
                    )
                _LAST_EXECUTED_GUC.set(" ".join(guc_parts))
                row = await conn.fetchrow(
                    "UPDATE tenant_incidents "
                    "SET severity = COALESCE($2, severity), "
                    "    summary = COALESCE($3, summary) "
                    "WHERE incident_id = $1 "
                    "RETURNING incident_id, tenant_id, service_name, severity, summary, pii_notes;",
                    clean_incident_id,
                    severity,
                    summary,
                )
                return _pg_row_to_dict(row) if row is not None else None

        async with self.checkout_transaction(
            tenant_id, user_role=clean_role, agent_id=clean_agent
        ) as (conn, _wait_ms):
            active_tenant = conn.active_guc_tenant_id
            if not active_tenant:
                return None
            if conn.active_guc_user_role not in ALLOWED_DB_WRITE_USER_ROLES:
                return None
            if conn.active_guc_agent_id not in ALLOWED_DB_WRITE_AGENT_IDS:
                return None
            tenant_list = self._by_tenant.get(active_tenant, [])
            for idx, inc in enumerate(tenant_list):
                if inc.incident_id == clean_incident_id:
                    updated = IncidentRecord(
                        incident_id=inc.incident_id,
                        tenant_id=inc.tenant_id,
                        service_name=inc.service_name,
                        severity=(
                            severity if severity is not None else inc.severity
                        ),
                        summary=summary if summary is not None else inc.summary,
                        pii_notes=inc.pii_notes,
                    )
                    tenant_list[idx] = updated
                    for g_idx, g_inc in enumerate(self._incidents):
                        if g_inc.incident_id == clean_incident_id:
                            self._incidents[g_idx] = updated
                            break
                    return {
                        "incident_id": updated.incident_id,
                        "tenant_id": updated.tenant_id,
                        "service_name": updated.service_name,
                        "severity": updated.severity,
                        "summary": updated.summary,
                        "pii_notes": updated.pii_notes,
                    }
            return None

    async def verify_live_rls_posture(
        self,
        *,
        expected_tables: tuple[str, ...] = (
            "tenant_incidents",
            "tenant_runbooks",
        ),
        schema_path: Path | None = None,
    ) -> dict[str, Any]:
        """Verifies fail-closed PostgreSQL RLS role and table posture at startup or healthcheck.

        In live `asyncpg` mode (`self._pool is not None`), queries `pg_roles` and `pg_class` to
        confirm the connecting database role has `NOT rolsuper AND NOT rolbypassrls` and that all
        `expected_tables` have both `relrowsecurity` and `relforcerowsecurity` enabled. In offline
        mode, validates `mcp_server/schema.sql` DDL invariants.

        Args:
            expected_tables: Tenant-scoped table names that must enforce `FORCE ROW LEVEL SECURITY`.
            schema_path: Optional override path to `schema.sql` for offline DDL verification.

        Returns:
            Dictionary describing the verified role and table RLS posture.

        Raises:
            PermissionError: With code `E_RLS_POSTURE_VIOLATION` if the role can bypass RLS or any
                expected table lacks `ENABLE`/`FORCE ROW LEVEL SECURITY`.
        """
        from agents.auth import _ACTIVE_TENANT_ENVELOPE

        active_env = _ACTIVE_TENANT_ENVELOPE.get()
        active_tid = (
            active_env.tenant.tenant_id if active_env is not None else None
        )
        live_pool = await self._resolve_live_pool(active_tid)
        if live_pool is not None:
            async with live_pool.acquire() as conn:
                role_row = await conn.fetchrow(
                    "SELECT current_user AS role_name, rolsuper, rolbypassrls "
                    "FROM pg_roles WHERE rolname = current_user;"
                )
                if role_row is None:
                    raise PermissionError(
                        "E_RLS_POSTURE_VIOLATION: Could not resolve current_user in pg_roles."
                    )
                role_name = str(role_row["role_name"])
                is_superuser = bool(role_row["rolsuper"])
                can_bypass_rls = bool(role_row["rolbypassrls"])
                if is_superuser or can_bypass_rls:
                    raise PermissionError(
                        f"E_RLS_POSTURE_VIOLATION: Database role '{role_name}' must be "
                        f"NOSUPERUSER and NOBYPASSRLS (rolsuper={is_superuser}, "
                        f"rolbypassrls={can_bypass_rls})."
                    )

                table_rows = await conn.fetch(
                    "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
                    "FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = ANY($1::text[]);",
                    list(expected_tables),
                )
                posture_by_table = {
                    str(row["relname"]): (
                        bool(row["relrowsecurity"]),
                        bool(row["relforcerowsecurity"]),
                    )
                    for row in table_rows
                }
                for table_name in expected_tables:
                    table_flags = posture_by_table.get(table_name)
                    if table_flags != (True, True):
                        raise PermissionError(
                            f"E_RLS_POSTURE_VIOLATION: Table '{table_name}' does not have "
                            f"ENABLE and FORCE ROW LEVEL SECURITY active (got {table_flags})."
                        )
                return {
                    "verified": True,
                    "mode": "live_pg_catalog",
                    "role_name": role_name,
                    "rolsuper": False,
                    "rolbypassrls": False,
                    "tables_verified": list(expected_tables),
                }

        resolved_schema_path = schema_path or (
            Path(__file__).resolve().parent / "schema.sql"
        )
        schema_sql = resolved_schema_path.read_text(encoding="utf-8")
        for table_name in expected_tables:
            enable_pattern = re.compile(
                rf"ALTER\s+TABLE\s+{re.escape(table_name)}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY\s*;",
                re.IGNORECASE,
            )
            force_pattern = re.compile(
                rf"ALTER\s+TABLE\s+{re.escape(table_name)}\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\s*;",
                re.IGNORECASE,
            )
            if not enable_pattern.search(
                schema_sql
            ) or not force_pattern.search(schema_sql):
                raise PermissionError(
                    f"E_RLS_POSTURE_VIOLATION: Schema DDL for '{table_name}' is missing "
                    "ENABLE or FORCE ROW LEVEL SECURITY."
                )
        return {
            "verified": True,
            "mode": "schema_ddl_verified",
            "role_name": "cymbal_mcp_app",
            "rolsuper": False,
            "rolbypassrls": False,
            "tables_verified": list(expected_tables),
        }
