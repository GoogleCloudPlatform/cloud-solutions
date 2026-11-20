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

# pylint: disable=line-too-long

"""Initializes & Verifies Real PostgreSQL Row-Level Security (`mcp_server/schema.sql`) via
`asyncpg`.

Connects to `DATABASE_URL` (required; local Docker Postgres 16 from `docker-compose.yml`, Cloud SQL,
or AlloyDB):
1. Applies `mcp_server/schema.sql` (`ENABLE/FORCE ROW LEVEL SECURITY` on `tenant_incidents` &
   `tenant_runbooks`).
2. Creates a non-superuser role `cymbal_mcp_app` so PostgreSQL RLS policies are strictly enforced.
3. Seeds FinVault Bank (`tenant-finvault-alpha`) and RetailStream Corp (`tenant-retailstream-beta`)
   rows.
4. Verifies that querying without `SET LOCAL app.current_tenant_id` fails closed (`0 rows`), and
   querying with `SET LOCAL app.current_tenant_id = 'tenant-finvault-alpha'` returns only FinVault
   rows.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from mcp_server.db import (
    DEFAULT_SEEDED_INCIDENTS,
    RLSDatabasePool,
    make_asyncpg_pool_factory,
)

APP_ROLE_NAME = "cymbal_mcp_app"
APP_ROLE_PASSWORD = os.getenv(
    "WS2_POSTGRES_APP_PASSWORD", "cymbal-rls-password"
)


def build_app_role_dsn(
    admin_dsn: str,
    *,
    app_user: str = APP_ROLE_NAME,
    app_password: str = APP_ROLE_PASSWORD,
) -> str:
    """Rewrites `admin_dsn` credentials to connect as the non-superuser `cymbal_mcp_app` role."""
    parsed = urlsplit(admin_dsn)
    hostname = parsed.hostname
    if hostname is None:
        host_port = ""
    elif ":" in hostname and not hostname.startswith("["):
        host_port = f"[{hostname}]"
    else:
        host_port = hostname
    if parsed.port is not None and host_port:
        host_port = f"{host_port}:{parsed.port}"
    netloc = (
        f"{app_user}:{app_password}@{host_port}"
        if host_port
        else f"{app_user}:{app_password}@"
    )
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )


async def init_and_verify_postgres_rls(dsn: str) -> dict[str, int]:
    schema_path = (
        Path(__file__).resolve().parent.parent / "mcp_server" / "schema.sql"
    )
    schema_sql = schema_path.read_text(encoding="utf-8")
    escaped_password = APP_ROLE_PASSWORD.replace("'", "''")

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(schema_sql)
        await conn.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE_NAME}') THEN
                    CREATE ROLE {APP_ROLE_NAME}
                        LOGIN PASSWORD '{escaped_password}' NOSUPERUSER NOBYPASSRLS;
                END IF;
            END
            $$;
            GRANT SELECT, INSERT, UPDATE, DELETE
                ON tenant_incidents, tenant_runbooks TO {APP_ROLE_NAME};
            """)

        for inc in DEFAULT_SEEDED_INCIDENTS:
            await conn.execute(
                """
                INSERT INTO tenant_incidents (
                    incident_id, tenant_id, service_name, severity, summary, pii_notes
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (incident_id) DO NOTHING;
                """,
                inc.incident_id,
                inc.tenant_id,
                inc.service_name,
                inc.severity,
                inc.summary,
                inc.pii_notes,
            )

        # Verify fail-closed RLS as non-superuser role `cymbal_mcp_app`
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE cymbal_mcp_app;")
            unscoped_rows = await conn.fetch("SELECT * FROM tenant_incidents;")
            assert (
                len(unscoped_rows) == 0
            ), "Fail-closed RLS violated: returned rows without tenant_id!"

        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE cymbal_mcp_app;")
            await conn.execute(
                "SET LOCAL app.current_tenant_id = 'tenant-finvault-alpha';"
            )
            fv_rows = await conn.fetch("SELECT * FROM tenant_incidents;")
            assert len(fv_rows) == 2

        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE cymbal_mcp_app;")
            await conn.execute(
                "SET LOCAL app.current_tenant_id = 'tenant-retailstream-beta';"
            )
            rs_rows = await conn.fetch("SELECT * FROM tenant_incidents;")
            assert len(rs_rows) == 1

        rls_pool = RLSDatabasePool(
            pool_factory=make_asyncpg_pool_factory(
                dsn,
                user=APP_ROLE_NAME,
                password=APP_ROLE_PASSWORD,
            )
        )
        try:
            posture = await rls_pool.verify_live_rls_posture()
            assert posture["verified"] is True
            assert posture["mode"] == "live_pg_catalog"
            pooled_fv = await rls_pool.query_incidents(
                tenant_id="tenant-finvault-alpha"
            )
            assert len(pooled_fv) == 2
            pooled_rs = await rls_pool.query_incidents(
                tenant_id="tenant-retailstream-beta"
            )
            assert len(pooled_rs) == 1
        finally:
            await rls_pool.close()

        return {
            "unscoped_rows": len(unscoped_rows),
            "finvault_rows": len(fv_rows),
            "retailstream_rows": len(rs_rows),
            "rls_posture_verified": 1,
        }
    finally:
        await conn.close()


if __name__ == "__main__":
    target_dsn = os.getenv("DATABASE_URL", "").strip()
    if not target_dsn:
        # No built-in DSN: a default would carry a committed superuser password.
        raise SystemExit(
            "Set DATABASE_URL, e.g. for the docker-compose Postgres: "
            'DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@127.0.0.1:5432/cymbal_pooled_ops"'
        )
    print(asyncio.run(init_and_verify_postgres_rls(target_dsn)))
