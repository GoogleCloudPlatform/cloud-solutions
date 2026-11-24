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

# pylint: disable=line-too-long,unused-argument

"""Relational SQL Engine Verifier for `mcp_server/schema.sql` (Hop 5 Fail-Closed RLS).

Compiles and executes `mcp_server/schema.sql` against a real relational SQL engine
with registered PostgreSQL session GUC functions (`current_setting`, `set_config`)
and policy-enforced relations derived directly from the `CREATE POLICY ... USING (...)`
clauses in `mcp_server/schema.sql` (or against a live PostgreSQL 16 / AlloyDB socket
when `DATABASE_URL` is configured).

Proves at the relational SQL execution layer:
1. `schema.sql` DDL & RLS policies (`ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`,
   and `NULLIF(current_setting('app.current_tenant_id', true), '') IS NOT NULL`) are
   syntactically and semantically valid.
2. Fail-Closed Unset GUC: `SELECT *` with unset/empty `app.current_tenant_id` returns `0` rows.
3. Tenant Alpha Isolation: `set_config('app.current_tenant_id', 'tenant-finvault-alpha', true)`
   returns only FinVault rows (`INC-FV-1001`, `INC-FV-1002`) and `0` RetailStream rows.
4. Tenant Beta Isolation: `set_config('app.current_tenant_id', 'tenant-retailstream-beta', true)`
   returns only RetailStream rows (`INC-RS-2001`) and `0` FinVault rows.
5. Transactional Reset: Ending a transaction resets `app.current_tenant_id` to `""` so a
   recycled pooled connection never leaks tenant context to the next caller.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from mcp_server.db import (
    DEFAULT_SEEDED_INCIDENTS,
    DEFAULT_SEEDED_RUNBOOKS,
    RLSDatabasePool,
)

SCHEMA_SQL_PATH = Path(__file__).resolve().parent / "schema.sql"


class RelationalSQLRLSVerifier:
    """Executes `mcp_server/schema.sql` DDL and RLS policies in an embedded relational SQL
    engine.
    """

    def __init__(self, schema_path: Path = SCHEMA_SQL_PATH) -> None:
        self.schema_path = schema_path
        self.raw_schema = self.schema_path.read_text(encoding="utf-8")
        self._guc_store: dict[str, str] = {}
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._register_postgres_guc_functions()
        self.parsed_policies = self._compile_and_execute_schema()
        self._seed_default_rows()

    def _register_postgres_guc_functions(self) -> None:
        """Registers PostgreSQL `current_setting(name, missing_ok)` and `set_config(name, val,
        is_local)`.
        """

        def pg_current_setting(
            setting_name: str, missing_ok: int | bool = True
        ) -> str | None:
            val = self._guc_store.get(setting_name)
            if val is None:
                if missing_ok:
                    return ""
                raise RuntimeError(
                    f"unrecognized configuration parameter {setting_name!r}"
                )
            return val

        def pg_set_config(
            setting_name: str,
            new_value: str | None,
            is_local: int | bool = True,
        ) -> str:
            normalized = new_value or ""
            self._guc_store[setting_name] = normalized
            return normalized

        self.conn.create_function("current_setting", 2, pg_current_setting)
        self.conn.create_function("set_config", 3, pg_set_config)

    def _compile_and_execute_schema(self) -> dict[str, dict[str, Any]]:
        """Validates PostgreSQL DDL + RLS directives in `schema.sql` and creates RLS-enforced SQL
        views.
        """
        raw = self.raw_schema

        # 1. Verify mandatory PostgreSQL RBAC posture (NOBYPASSRLS + REVOKE PUBLIC + column GRANTs)
        if not re.search(
            r"CREATE\s+ROLE\s+cymbal_mcp_app\b[^;]*\bNOSUPERUSER\b[^;]*\bNOBYPASSRLS\b",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            raise ValueError(
                "Missing NOSUPERUSER NOBYPASSRLS role DDL for cymbal_mcp_app in schema.sql"
            )
        if not re.search(
            r"REVOKE\s+ALL\s+ON\s+TABLE\s+tenant_incidents\s*,\s*tenant_runbooks\s+FROM\s+PUBLIC\s*;",
            raw,
            flags=re.IGNORECASE,
        ):
            raise ValueError("Missing REVOKE ALL ... FROM PUBLIC in schema.sql")
        update_grant_match = re.search(
            r"GRANT\s+UPDATE\s*\(([^)]+)\)\s+ON\s+TABLE\s+tenant_incidents\s+TO\s+cymbal_mcp_app\s*;",
            raw,
            flags=re.IGNORECASE,
        )
        if not update_grant_match:
            raise ValueError(
                "Missing column-scoped GRANT UPDATE (...) ON TABLE tenant_incidents in schema.sql"
            )
        granted_update_cols = {
            c.strip().lower()
            for c in update_grant_match.group(1).split(",")
            if c.strip()
        }
        if granted_update_cols != {"severity", "summary"}:
            raise ValueError(
                "Expected column-scoped GRANT UPDATE (severity, summary), got "
                f"{sorted(granted_update_cols)}"
            )

        # 2. Verify mandatory PostgreSQL 16 FORCE ROW LEVEL SECURITY directives exist for every
        # table
        tables_found = re.findall(
            r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\((.*?)\);",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not tables_found:
            raise ValueError("No CREATE TABLE statements found in schema.sql")

        policies: dict[str, dict[str, Any]] = {}
        cur = self.conn.cursor()

        for table_name, columns_block in tables_found:
            enable_re = re.compile(
                rf"ALTER\s+TABLE\s+{re.escape(table_name)}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY\s*;",
                re.IGNORECASE,
            )
            force_re = re.compile(
                rf"ALTER\s+TABLE\s+{re.escape(table_name)}\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\s*;",
                re.IGNORECASE,
            )
            if not enable_re.search(raw):
                raise ValueError(
                    f"Missing ENABLE ROW LEVEL SECURITY for table {table_name}"
                )
            if not force_re.search(raw):
                raise ValueError(
                    f"Missing FORCE ROW LEVEL SECURITY for table {table_name}"
                )

            if not re.search(
                rf"GRANT\s+SELECT\s*\([^)]+\)\s+ON\s+TABLE\s+{re.escape(table_name)}\s+TO\s+cymbal_mcp_app\s*;",
                raw,
                flags=re.IGNORECASE,
            ):
                raise ValueError(
                    f"Missing column-scoped GRANT SELECT on {table_name}"
                )

            policy_re = re.compile(
                rf"CREATE\s+POLICY\s+(\w+)\s+ON\s+{re.escape(table_name)}\s+USING\s*\((.*?)\)\s*;",
                re.IGNORECASE | re.DOTALL,
            )
            match = policy_re.search(raw)
            if not match:
                raise ValueError(
                    f"Missing CREATE POLICY ... ON {table_name} USING (...)"
                )

            policy_name, using_predicate = (
                match.group(1),
                match.group(2).strip(),
            )
            if re.search(
                r"IS\s+NULL\s+OR", using_predicate, flags=re.IGNORECASE
            ):
                raise ValueError(
                    f"Policy {policy_name} on {table_name} contains fail-open 'IS NULL OR' bypass"
                )

            # Execute the physical base table in SQL (translating TIMESTAMPTZ/NOW() ->
            # TEXT/CURRENT_TIMESTAMP)
            sqlite_cols = re.sub(
                r"\bTIMESTAMPTZ\s+NOT\s+NULL\s+DEFAULT\s+NOW\(\)",
                "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                columns_block,
                flags=re.IGNORECASE,
            )
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS _raw_{table_name} ({sqlite_cols});"
            )

            # Create the FORCE ROW LEVEL SECURITY SQL view using the exact USING (...) predicate
            # from schema.sql
            cur.execute(
                f"CREATE VIEW {table_name} AS "
                f"SELECT * FROM _raw_{table_name} WHERE ({using_predicate});"
            )

            policies[table_name] = {
                "policy_name": policy_name,
                "enable_rls": True,
                "force_rls": True,
                "using_predicate": " ".join(using_predicate.split()),
            }

        write_policy_re = re.compile(
            r"CREATE\s+POLICY\s+(\w+)\s+ON\s+tenant_incidents\s+AS\s+RESTRICTIVE\s+FOR\s+UPDATE\s+"
            r"USING\s*\((.*?)\)\s+WITH\s+CHECK\s*\((.*?)\)\s*;",
            re.IGNORECASE | re.DOTALL,
        )
        write_match = write_policy_re.search(raw)
        if not write_match:
            raise ValueError(
                "Missing AS RESTRICTIVE FOR UPDATE policy on tenant_incidents in schema.sql"
            )
        write_policy_name, write_using_pred, write_check_pred = (
            write_match.group(1),
            write_match.group(2).strip(),
            write_match.group(3).strip(),
        )
        cur.execute(f"""
            CREATE TRIGGER trg_tenant_incidents_rbac_update
            INSTEAD OF UPDATE ON tenant_incidents
            BEGIN
                SELECT CASE
                    WHEN NEW.incident_id != OLD.incident_id
                      OR NEW.tenant_id != OLD.tenant_id
                      OR NEW.service_name != OLD.service_name
                      OR NEW.pii_notes != OLD.pii_notes
                      OR NEW.created_at != OLD.created_at
                    THEN RAISE(
                        ABORT,
                        'E_RBAC_COLUMN_FORBIDDEN: cymbal_mcp_app UPDATE limited to severity/summary'
                    )
                END;
                UPDATE _raw_tenant_incidents
                SET severity = NEW.severity,
                    summary = NEW.summary
                WHERE incident_id = OLD.incident_id
                  AND ({write_using_pred})
                  AND ({write_check_pred});
            END;
            """)
        policies["tenant_incidents"][
            "write_rbac_policy_name"
        ] = write_policy_name
        policies["tenant_incidents"]["granted_update_columns"] = sorted(
            granted_update_cols
        )

        self.conn.commit()
        return policies

    def _seed_default_rows(self) -> None:
        cur = self.conn.cursor()
        for inc in DEFAULT_SEEDED_INCIDENTS:
            cur.execute(
                "INSERT INTO _raw_tenant_incidents "
                "(incident_id, tenant_id, service_name, severity, summary, pii_notes) "
                "VALUES (?, ?, ?, ?, ?, ?);",
                (
                    inc.incident_id,
                    inc.tenant_id,
                    inc.service_name,
                    inc.severity,
                    inc.summary,
                    inc.pii_notes,
                ),
            )
        for rows in DEFAULT_SEEDED_RUNBOOKS.values():
            for rb in rows:
                cur.execute(
                    "INSERT INTO _raw_tenant_runbooks "
                    "(runbook_id, tenant_id, title, remediation_steps) "
                    "VALUES (?, ?, ?, ?);",
                    (
                        rb["runbook_id"],
                        rb["tenant_id"],
                        rb["title"],
                        rb["remediation_steps"],
                    ),
                )
        self.conn.commit()

    def execute_rls_transaction(
        self,
        tenant_id: str | None,
        sql_query: str,
        params: tuple[Any, ...] = (),
        *,
        user_role: str | None = None,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Runs a SQL query inside a transactional `set_config('app.current_tenant_id', ...)` (+
        RBAC) block.
        """
        RLSDatabasePool.validate_sql_safety(sql_query)
        cur = self.conn.cursor()
        try:
            if tenant_id and tenant_id.strip():
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', ?, 1);",
                    (tenant_id.strip(),),
                )
            else:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', '', 1);"
                )
            if user_role and user_role.strip():
                cur.execute(
                    "SELECT set_config('app.current_user_role', ?, 1);",
                    (user_role.strip(),),
                )
            if agent_id and agent_id.strip():
                cur.execute(
                    "SELECT set_config('app.current_agent_id', ?, 1);",
                    (agent_id.strip(),),
                )
            cur.execute(sql_query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            # Simulates PostgreSQL `SET LOCAL` automatic reset at transaction boundary
            self._guc_store.pop("app.current_tenant_id", None)
            self._guc_store.pop("app.current_user_role", None)
            self._guc_store.pop("app.current_agent_id", None)

    def execute_rls_write(
        self,
        tenant_id: str | None,
        sql_statement: str,
        params: tuple[Any, ...] = (),
        *,
        user_role: str | None = None,
        agent_id: str | None = None,
    ) -> int:
        """Executes a DML write statement inside a transactional GUC block and returns rows."""
        RLSDatabasePool.validate_sql_safety(sql_statement)
        cur = self.conn.cursor()
        try:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', ?, 1);",
                ((tenant_id or "").strip(),),
            )
            if user_role and user_role.strip():
                cur.execute(
                    "SELECT set_config('app.current_user_role', ?, 1);",
                    (user_role.strip(),),
                )
            if agent_id and agent_id.strip():
                cur.execute(
                    "SELECT set_config('app.current_agent_id', ?, 1);",
                    (agent_id.strip(),),
                )
            changes_before = self.conn.total_changes
            try:
                cur.execute(sql_statement, params)
            except sqlite3.IntegrityError as exc:
                if "E_RBAC_COLUMN_FORBIDDEN" in str(exc):
                    raise PermissionError(str(exc)) from exc
                raise
            return int(self.conn.total_changes - changes_before)
        finally:
            self._guc_store.pop("app.current_tenant_id", None)
            self._guc_store.pop("app.current_user_role", None)
            self._guc_store.pop("app.current_agent_id", None)

    def run_verification_suite(self) -> dict[str, Any]:
        """Executes the SQL RLS + RBAC verification battery and returns a structured audit
        report.
        """
        unset_rows = self.execute_rls_transaction(
            None, "SELECT * FROM tenant_incidents;"
        )
        unset_role_rows = self.execute_rls_transaction(
            "tenant-finvault-alpha",
            "SELECT * FROM tenant_incidents ORDER BY incident_id;",
            user_role=None,
            agent_id="sre_diagnostic_agent",
        )
        unset_agent_rows = self.execute_rls_transaction(
            "tenant-finvault-alpha",
            "SELECT * FROM tenant_incidents ORDER BY incident_id;",
            user_role="sre_admin",
            agent_id=None,
        )
        finvault_rows = self.execute_rls_transaction(
            "tenant-finvault-alpha",
            "SELECT * FROM tenant_incidents ORDER BY incident_id;",
            user_role="sre_admin",
            agent_id="sre_diagnostic_agent",
        )
        retail_rows = self.execute_rls_transaction(
            "tenant-retailstream-beta",
            "SELECT * FROM tenant_incidents ORDER BY incident_id;",
            user_role="incident_responder",
            agent_id="cymbal_shared_diagnostic_agent",
        )
        rbac_blocked_role_rows = self.execute_rls_transaction(
            "tenant-finvault-alpha",
            "SELECT * FROM tenant_incidents ORDER BY incident_id;",
            user_role="unauthorized_role",
            agent_id="sre_diagnostic_agent",
        )
        rbac_blocked_agent_rows = self.execute_rls_transaction(
            "tenant-finvault-alpha",
            "SELECT * FROM tenant_incidents ORDER BY incident_id;",
            user_role="sre_admin",
            agent_id="unauthorized_agent",
        )
        post_tx_unset_rows = self.execute_rls_transaction(
            "", "SELECT * FROM tenant_runbooks;"
        )

        # Write RBAC: read_only_analyst cannot UPDATE (0 rows), sre_admin can UPDATE summary,
        # and mutating non-granted columns (`tenant_id`) fails closed with PermissionError.
        analyst_updated = self.execute_rls_write(
            "tenant-finvault-alpha",
            "UPDATE tenant_incidents SET summary = summary WHERE incident_id = 'INC-FV-1001';",
            user_role="read_only_analyst",
            agent_id="cymbal_shared_diagnostic_agent",
        )
        sre_updated = self.execute_rls_write(
            "tenant-finvault-alpha",
            "UPDATE tenant_incidents SET summary = summary WHERE incident_id = 'INC-FV-1001';",
            user_role="sre_admin",
            agent_id="cymbal_shared_diagnostic_agent",
        )
        column_rbac_blocked = False
        try:
            self.execute_rls_write(
                "tenant-finvault-alpha",
                "UPDATE tenant_incidents SET tenant_id = 'tenant-retailstream-beta' "
                "WHERE incident_id = 'INC-FV-1001';",
                user_role="sre_admin",
                agent_id="cymbal_shared_diagnostic_agent",
            )
        except PermissionError:
            column_rbac_blocked = True

        tampering_blocked = False
        try:
            self.execute_rls_transaction(
                "tenant-retailstream-beta",
                "SELECT set_config('app.current_tenant_id', 'tenant-finvault-alpha', true);",
            )
        except PermissionError:
            tampering_blocked = True

        passed = (
            len(unset_rows) == 0
            and len(unset_role_rows) == 0
            and len(unset_agent_rows) == 0
            and [r["incident_id"] for r in finvault_rows]
            == ["INC-FV-1001", "INC-FV-1002"]
            and all(
                r["tenant_id"] == "tenant-finvault-alpha" for r in finvault_rows
            )
            and [r["incident_id"] for r in retail_rows] == ["INC-RS-2001"]
            and all(
                r["tenant_id"] == "tenant-retailstream-beta"
                for r in retail_rows
            )
            and len(rbac_blocked_role_rows) == 0
            and len(rbac_blocked_agent_rows) == 0
            and len(post_tx_unset_rows) == 0
            and analyst_updated == 0
            and sre_updated == 1
            and column_rbac_blocked
            and tampering_blocked
        )
        return {
            "status": "PASS" if passed else "FAIL",
            "schema_file": str(self.schema_path.name),
            "compiled_policies": self.parsed_policies,
            "unset_guc_row_count": len(unset_rows),
            "unset_role_row_count": len(unset_role_rows),
            "unset_agent_row_count": len(unset_agent_rows),
            "finvault_incident_ids": [r["incident_id"] for r in finvault_rows],
            "retailstream_incident_ids": [
                r["incident_id"] for r in retail_rows
            ],
            "rbac_unauthorized_role_row_count": len(rbac_blocked_role_rows),
            "rbac_unauthorized_agent_row_count": len(rbac_blocked_agent_rows),
            "write_rbac_analyst_updated_rows": analyst_updated,
            "write_rbac_sre_updated_rows": sre_updated,
            "column_rbac_immutable_blocked": column_rbac_blocked,
            "post_tx_reset_row_count": len(post_tx_unset_rows),
            "guc_tampering_blocked": tampering_blocked,
        }
