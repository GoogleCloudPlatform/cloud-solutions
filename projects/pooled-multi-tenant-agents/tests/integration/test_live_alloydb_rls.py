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
# pylint: disable=protected-access,redefined-outer-name

"""Live End-to-End PostgreSQL 18 Row-Level Security & Column/Action RBAC Tests on AlloyDB.

Requires `RUN_LIVE_GCP_TESTS=1`. Connects to the live `cymbal-pooled-rls-primary-prod` AlloyDB
for PostgreSQL 18 instance (either via `ALLOYDB_LIVE_DSN` or by spawning an ephemeral local
`alloydb-auth-proxy --public-ip --auto-iam-authn` tunnel) as the non-superuser `cymbal_mcp_app`
role (`NOSUPERUSER NOBYPASSRLS`) and verifies:
1. Live PostgreSQL catalog posture (`verify_live_rls_posture() -> mode == 'live_pg_catalog'`).
2. Fail-closed zero-row return when `app.current_tenant_id`, `app.current_user_role`, or
   `app.current_agent_id` GUC is unset or unlisted.
3. Strict cross-tenant row isolation between `tenant-finvault-alpha` and `tenant-retailstream-beta`
   on both `tenant_incidents` and `tenant_runbooks`.
4. Restrictive write RBAC (`AS RESTRICTIVE FOR UPDATE`): `read_only_analyst` updates 0 rows while
   `sre_admin` on `cymbal_shared_diagnostic_agent` updates its own tenant's `summary` and is
   blocked on cross-tenant rows.
5. Column-scoped & action-scoped PostgreSQL privilege enforcement: `UPDATE ... SET tenant_id = ...`,
   `DELETE`, and `INSERT` as `cymbal_mcp_app` fail with `asyncpg.InsufficientPrivilegeError`.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator

import asyncpg
import pytest
from agents import platform_config
from mcp_server.db import RLSDatabasePool, make_asyncpg_pool_factory

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_GCP_TESTS") != "1",
    reason="Set RUN_LIVE_GCP_TESTS=1 to run against live AlloyDB PostgreSQL 18.",
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _resolve_active_gcloud_account() -> str:
    env_user = os.getenv("ALLOYDB_IAM_USER", "").strip()
    if env_user:
        return env_user
    import google.auth

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    sa_email = getattr(creds, "service_account_email", None)
    if isinstance(sa_email, str) and sa_email.endswith(".gserviceaccount.com"):
        return sa_email.removesuffix(".gserviceaccount.com")
    proc = subprocess.run(
        ["gcloud", "config", "get-value", "account"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    acct = proc.stdout.strip()
    if acct:
        return acct
    raise RuntimeError(
        "Set ALLOYDB_IAM_USER or configure an active gcloud account."
    )


@pytest.fixture(scope="module")
def live_alloydb_dsn() -> Iterator[tuple[str, bool]]:
    """Yields `(dsn, iam_auth)` connected to live AlloyDB PostgreSQL 18."""
    explicit_dsn = os.getenv("ALLOYDB_LIVE_DSN", "").strip()
    if explicit_dsn:
        yield explicit_dsn, os.getenv("ALLOYDB_LIVE_IAM_AUTH", "1") == "1"
        return

    proxy_bin = shutil.which("alloydb-auth-proxy") or os.path.expanduser(
        "~/.local/bin/alloydb-auth-proxy"
    )
    if not os.path.exists(proxy_bin):
        pytest.skip(
            "alloydb-auth-proxy not installed and ALLOYDB_LIVE_DSN not set."
        )

    project_id = platform_config.resolve_project_id()
    region = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
    instance_uri = os.getenv(
        "ALLOYDB_INSTANCE_URI",
        f"projects/{project_id}/locations/{region}/clusters/cymbal-pooled-rls-prod/"
        "instances/cymbal-pooled-rls-primary-prod",
    )
    iam_user = _resolve_active_gcloud_account()
    port = _find_free_port()
    proc = subprocess.Popen(
        [
            proxy_bin,
            instance_uri,
            "--public-ip",
            "--auto-iam-authn",
            "--address",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.time() + 25.0
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(
                    f"alloydb-auth-proxy exited early ({proc.returncode}): {out}"
                )
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    ready = True
                    break
            time.sleep(0.3)
        if not ready:
            pytest.fail(
                "Timed out waiting for alloydb-auth-proxy local listener."
            )

        from urllib.parse import quote

        dsn = (
            f"postgresql://{quote(iam_user, safe='')}@127.0.0.1:{port}/postgres"
        )
        yield dsn, True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_live_alloydb_postgres18_rls_posture_and_fail_closed_isolation(
    live_alloydb_dsn: tuple[str, bool],
) -> None:
    """Verifies real PostgreSQL 18 `pg_roles`/`pg_class` posture, fail-closed GUCs, and RBAC."""
    dsn, iam_auth = live_alloydb_dsn

    async def _run() -> None:
        pool = RLSDatabasePool(
            pool_factory=make_asyncpg_pool_factory(
                dsn,
                max_size=4,
                iam_auth=iam_auth,
                ssl=False,
                db_role="cymbal_mcp_app",
            )
        )
        try:
            # 1. Live `pg_roles` + `pg_class` posture verification (`cymbal_mcp_app` NOBYPASSRLS).
            posture = await pool.verify_live_rls_posture()
            assert posture["verified"] is True
            assert posture["mode"] == "live_pg_catalog"
            assert posture["role_name"] == "cymbal_mcp_app"
            assert posture["rolsuper"] is False
            assert posture["rolbypassrls"] is False
            assert set(posture["tables_verified"]) == {
                "tenant_incidents",
                "tenant_runbooks",
            }

            # 2. Fail-closed when any GUC (`user_role` or `agent_id`) is omitted on raw SQL!
            raw_pool = await pool._resolve_live_pool()
            assert raw_pool is not None
            async with raw_pool.acquire() as conn, conn.transaction():
                # No GUCs set -> 0 rows!
                unset_rows = await conn.fetch("SELECT * FROM tenant_incidents;")
                assert unset_rows == []
                # Only tenant_id set (missing user_role & agent_id) -> 0 rows!
                await conn.execute(
                    "SELECT set_config('app.current_tenant_id', 'tenant-finvault-alpha', true);"
                )
                partial_rows = await conn.fetch(
                    "SELECT * FROM tenant_incidents;"
                )
                assert partial_rows == []

            # 3. Tenant-isolated SELECT on `tenant_incidents` and `tenant_runbooks`!
            fv_rows = await pool.query_incidents(
                tenant_id="tenant-finvault-alpha",
                user_role="sre_admin",
                agent_id="cymbal_shared_diagnostic_agent",
            )
            fv_ids = {r["incident_id"] for r in fv_rows}
            assert {"INC-FV-1001", "INC-FV-1002"} <= fv_ids
            assert all(
                r["tenant_id"] == "tenant-finvault-alpha" for r in fv_rows
            )
            assert "INC-RS-2001" not in fv_ids

            rs_rows = await pool.query_incidents(
                tenant_id="tenant-retailstream-beta",
                user_role="read_only_analyst",
                agent_id="cymbal_shared_diagnostic_agent",
            )
            rs_ids = {r["incident_id"] for r in rs_rows}
            assert "INC-RS-2001" in rs_ids
            assert all(
                r["tenant_id"] == "tenant-retailstream-beta" for r in rs_rows
            )

            fv_rbs = await pool.query_runbooks(
                tenant_id="tenant-finvault-alpha",
                user_role="compliance_officer",
                agent_id="finvault_regulatory_escalation_agent",
            )
            assert [rb["runbook_id"] for rb in fv_rbs] == ["RB-FV-01"]

            # Unlisted role -> 0 rows enforced inside PostgreSQL RLS policy!
            unlisted_rows = await pool.query_incidents(
                tenant_id="tenant-finvault-alpha",
                user_role="external_auditor",
                agent_id="cymbal_shared_diagnostic_agent",
            )
            assert unlisted_rows == []

            # 4. Restrictive Write RBAC (`AS RESTRICTIVE FOR UPDATE`):
            #    - `read_only_analyst` updates 0 rows!
            denied_update = await pool.update_incident(
                tenant_id="tenant-finvault-alpha",
                incident_id="INC-FV-1002",
                user_role="read_only_analyst",
                agent_id="cymbal_shared_diagnostic_agent",
                summary="Analyst unauthorized write",
            )
            assert denied_update is None

            #    - Cross-tenant `sre_admin` updates 0 rows!
            cross_update = await pool.update_incident(
                tenant_id="tenant-retailstream-beta",
                incident_id="INC-FV-1002",
                user_role="sre_admin",
                agent_id="cymbal_shared_diagnostic_agent",
                summary="Cross-tenant write attempt",
            )
            assert cross_update is None

            #    - Entitled `sre_admin` updates `summary` and restores original cleanly!
            orig_summary = next(
                r["summary"]
                for r in fv_rows
                if r["incident_id"] == "INC-FV-1002"
            )
            updated = await pool.update_incident(
                tenant_id="tenant-finvault-alpha",
                incident_id="INC-FV-1002",
                user_role="sre_admin",
                agent_id="cymbal_shared_diagnostic_agent",
                summary=f"{orig_summary} [verified live]",
            )
            assert updated is not None
            assert updated["summary"].endswith("[verified live]")
            await pool.update_incident(
                tenant_id="tenant-finvault-alpha",
                incident_id="INC-FV-1002",
                user_role="sre_admin",
                agent_id="cymbal_shared_diagnostic_agent",
                summary=orig_summary,
            )

            # 5. Column-scoped & action-scoped PostgreSQL privilege enforcement (`cymbal_mcp_app`):
            async with raw_pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.current_tenant_id', 'tenant-finvault-alpha', true);"
                )
                await conn.execute(
                    "SELECT set_config('app.current_user_role', 'sre_admin', true);"
                )
                await conn.execute(
                    "SELECT set_config('app.current_agent_id', $1, true);",
                    "cymbal_shared_diagnostic_agent",
                )
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute(
                        "UPDATE tenant_incidents SET tenant_id = 'tenant-retailstream-beta' "
                        "WHERE incident_id = 'INC-FV-1001';"
                    )
            async with raw_pool.acquire() as conn, conn.transaction():
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute(
                        "DELETE FROM tenant_incidents WHERE incident_id = 'INC-FV-1001';"
                    )
            async with raw_pool.acquire() as conn, conn.transaction():
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute(
                        "INSERT INTO tenant_incidents "
                        "(incident_id, tenant_id, service_name, severity, summary) "
                        "VALUES ('INC-ROGUE-1', 'tenant-finvault-alpha', 'svc', 'P1', 'rogue');"
                    )
        finally:
            await pool.close()

    asyncio.run(_run())
