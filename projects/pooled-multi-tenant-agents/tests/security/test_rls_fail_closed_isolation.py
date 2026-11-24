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

"""Breach Simulation 4: AlloyDB Row-Level Security (RLS) Fail-Closed Isolation (Pillar 4 — Hop 5).

Verifies:
1. `SET LOCAL app.current_tenant_id` strictly isolates rows returned to FinVault Bank vs.
   RetailStream Corp on the shared `tenant_incidents` table.
2. Missing or empty tenant context fails closed (returns 0 rows).
3. SQL injection attempting to reset/override `app.current_tenant_id` or inject `OR 1=1` is blocked.
"""

from __future__ import annotations

import pytest
from mcp_server.db import RLSDatabasePool


async def test_rls_strictly_isolates_finvault_and_retailstream_rows(
    db_pool: RLSDatabasePool,
) -> None:
    fv_rows = await db_pool.query_incidents(tenant_id="tenant-finvault-alpha")
    assert len(fv_rows) == 2
    assert all(r["tenant_id"] == "tenant-finvault-alpha" for r in fv_rows)
    assert (
        db_pool.last_executed_guc
        == "SET LOCAL app.current_tenant_id = 'tenant-finvault-alpha';"
    )

    rs_rows = await db_pool.query_incidents(
        tenant_id="tenant-retailstream-beta"
    )
    assert len(rs_rows) == 1
    assert rs_rows[0]["incident_id"] == "INC-RS-2001"
    assert rs_rows[0]["tenant_id"] == "tenant-retailstream-beta"
    assert (
        db_pool.last_executed_guc
        == "SET LOCAL app.current_tenant_id = 'tenant-retailstream-beta';"
    )


async def test_rls_fails_closed_when_tenant_context_missing(
    db_pool: RLSDatabasePool,
) -> None:
    assert await db_pool.query_incidents(tenant_id=None) == []
    assert await db_pool.query_incidents(tenant_id="") == []
    assert await db_pool.query_incidents(tenant_id="   ") == []
    assert await db_pool.query_runbooks(tenant_id=None) == []


async def test_rls_blocks_sql_guc_override_and_tautology_injection(
    db_pool: RLSDatabasePool,
) -> None:
    with pytest.raises(PermissionError, match="E_RLS_TAMPERING_DETECTED"):
        await db_pool.query_incidents(
            tenant_id="tenant-retailstream-beta",
            raw_sql=(
                "SELECT * FROM tenant_incidents; SET LOCAL app.current_tenant_id = "
                "'tenant-finvault-alpha';"
            ),
        )

    with pytest.raises(PermissionError, match="E_RLS_TAMPERING_DETECTED"):
        await db_pool.query_incidents(
            tenant_id="tenant-retailstream-beta",
            raw_sql="SELECT * FROM tenant_incidents WHERE severity = 'P1' OR 1=1;",
        )
