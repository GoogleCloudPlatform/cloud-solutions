#!/usr/bin/env python3
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

# pylint: disable=broad-exception-caught,import-outside-toplevel,line-too-long
# pylint: disable=wrong-import-position

"""Idempotent AlloyDB for PostgreSQL 18 RLS & RBAC bootstrap utility.

Applies `mcp_server/schema.sql`, seeds `DEFAULT_SEEDED_INCIDENTS` and `DEFAULT_SEEDED_RUNBOOKS`,
and optionally grants the non-superuser `cymbal_mcp_app` role (`NOSUPERUSER NOBYPASSRLS`) to one or
more Cloud IAM database users (`<sa-name>@<project>.iam` or `<user>@<domain>`).
"""

from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server.db import (
    DEFAULT_SEEDED_INCIDENTS,
    DEFAULT_SEEDED_RUNBOOKS,
    resolve_gcp_iam_db_token,
)

_SAFE_PG_ROLE_RE = re.compile(r"^[A-Za-z0-9._@-]{1,128}$")


def _quote_ident(role_name: str) -> str:
    cleaned = role_name.strip()
    if not _SAFE_PG_ROLE_RE.fullmatch(cleaned) or '"' in cleaned:
        raise ValueError(f"Unsafe PostgreSQL role identifier: {role_name!r}")
    return f'"{cleaned}"'


async def _connect_with_retry(
    dsn: str,
    *,
    iam_auth: bool,
    attempts: int = 20,
    delay_seconds: float = 1.0,
) -> object:
    import asyncpg

    last_exc: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            kwargs: dict[str, object] = {}
            if iam_auth:
                kwargs["password"] = resolve_gcp_iam_db_token()
            return await asyncpg.connect(dsn=dsn, **kwargs)
        except Exception as exc:
            last_exc = exc
            await asyncio.sleep(delay_seconds)
    assert last_exc is not None
    raise last_exc


async def bootstrap_alloydb(
    *,
    dsn: str,
    iam_auth: bool = False,
    schema_path: Path | None = None,
    grant_iam_users: list[str] | None = None,
) -> dict[str, object]:
    """Applies RLS DDL, seeds multi-tenant rows, and configures least-privilege IAM DB users."""
    resolved_schema = schema_path or (REPO_ROOT / "mcp_server" / "schema.sql")
    ddl = resolved_schema.read_text(encoding="utf-8")

    conn = await _connect_with_retry(dsn, iam_auth=iam_auth)
    try:
        async with conn.transaction():  # type: ignore[attr-defined]
            await conn.execute(ddl)  # type: ignore[attr-defined]
            # Table owner seeding: `alloydbsuperuser` is NOBYPASSRLS in managed AlloyDB, so
            # `FORCE ROW LEVEL SECURITY` blocks un-scoped admin INSERTs unless relaxed inside
            # this atomic bootstrap transaction and immediately re-armed before COMMIT.
            await conn.execute("ALTER TABLE tenant_incidents NO FORCE ROW LEVEL SECURITY;")  # type: ignore[attr-defined]
            await conn.execute("ALTER TABLE tenant_runbooks NO FORCE ROW LEVEL SECURITY;")  # type: ignore[attr-defined]

            for inc in DEFAULT_SEEDED_INCIDENTS:
                await conn.execute(  # type: ignore[attr-defined]
                    """
                    INSERT INTO tenant_incidents (
                        incident_id, tenant_id, service_name, severity, summary, pii_notes
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (incident_id) DO UPDATE SET
                        tenant_id = EXCLUDED.tenant_id,
                        service_name = EXCLUDED.service_name,
                        severity = EXCLUDED.severity,
                        summary = EXCLUDED.summary,
                        pii_notes = EXCLUDED.pii_notes;
                    """,
                    inc.incident_id,
                    inc.tenant_id,
                    inc.service_name,
                    inc.severity,
                    inc.summary,
                    inc.pii_notes,
                )

            seeded_runbook_count = 0
            for runbook_list in DEFAULT_SEEDED_RUNBOOKS.values():
                for rb in runbook_list:
                    await conn.execute(  # type: ignore[attr-defined]
                        """
                        INSERT INTO tenant_runbooks (
                            runbook_id, tenant_id, title, remediation_steps
                        )
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (runbook_id) DO UPDATE SET
                            tenant_id = EXCLUDED.tenant_id,
                            title = EXCLUDED.title,
                            remediation_steps = EXCLUDED.remediation_steps;
                        """,
                        rb["runbook_id"],
                        rb["tenant_id"],
                        rb["title"],
                        rb["remediation_steps"],
                    )
                    seeded_runbook_count += 1

            await conn.execute("ALTER TABLE tenant_incidents FORCE ROW LEVEL SECURITY;")  # type: ignore[attr-defined]
            await conn.execute("ALTER TABLE tenant_runbooks FORCE ROW LEVEL SECURITY;")  # type: ignore[attr-defined]

            granted_users: list[str] = []
            for raw_user in grant_iam_users or []:
                ident = _quote_ident(raw_user)
                await conn.execute("GRANT CONNECT ON DATABASE postgres TO " + ident + ";")  # type: ignore[attr-defined]
                await conn.execute("GRANT USAGE ON SCHEMA public TO " + ident + ";")  # type: ignore[attr-defined]
                await conn.execute("GRANT cymbal_mcp_app TO " + ident + ";")  # type: ignore[attr-defined]
                granted_users.append(raw_user.strip())

        version = str(await conn.fetchval("SELECT version();"))  # type: ignore[attr-defined]
        return {
            "status": "ALLOYDB_RLS_BOOTSTRAPPED",
            "postgres_version": version,
            "incidents_seeded": len(DEFAULT_SEEDED_INCIDENTS),
            "runbooks_seeded": seeded_runbook_count,
            "granted_iam_users": granted_users,
        }
    finally:
        await conn.close()  # type: ignore[attr-defined]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn", default="", help="Direct PostgreSQL connection DSN."
    )
    parser.add_argument(
        "--instance-uri",
        default="",
        help="Optional AlloyDB instance URI to connect via local alloydb-auth-proxy.",
    )
    parser.add_argument(
        "--db-user",
        default="",
        help="Database user when connecting via --instance-uri.",
    )
    parser.add_argument(
        "--proxy-port",
        type=int,
        default=15432,
        help="Local loopback port for alloydb-auth-proxy (default: 15432).",
    )
    parser.add_argument(
        "--private-ip",
        action="store_true",
        help=(
            "Connect the proxy to the instance's private VPC address instead of its public IP "
            "(needed when Terraform `alloydb_enable_public_ip = false`; this machine must be able "
            "to reach the VPC)."
        ),
    )
    parser.add_argument(
        "--iam-auth",
        action="store_true",
        help="Authenticate with a short-lived Google Cloud IAM OAuth2 token.",
    )
    parser.add_argument(
        "--grant-iam-user",
        action="append",
        default=[],
        help="IAM database user to grant `cymbal_mcp_app` (may be passed multiple times).",
    )
    args = parser.parse_args()

    proxy_proc: subprocess.Popen[str] | None = None
    try:
        dsn = args.dsn.strip()
        if args.instance_uri.strip():
            if not args.db_user.strip():
                raise ValueError(
                    "--db-user is required when --instance-uri is set."
                )
            proxy_bin = shutil.which("alloydb-auth-proxy") or str(
                Path.home() / ".local" / "bin" / "alloydb-auth-proxy"
            )
            if not Path(proxy_bin).is_file():
                raise FileNotFoundError(
                    "alloydb-auth-proxy was not found on PATH or in ~/.local/bin. Install it "
                    "(https://cloud.google.com/alloydb/docs/auth-proxy/connect#install) and "
                    "re-run; scripts/deploy.sh downloads it on Linux and macOS."
                )
            proxy_cmd = [proxy_bin, args.instance_uri.strip()]
            if not args.private_ip:
                proxy_cmd.append("--public-ip")
            proxy_cmd += [
                "--auto-iam-authn",
                "--address",
                "127.0.0.1",
                "--port",
                str(args.proxy_port),
            ]
            proxy_proc = subprocess.Popen(
                proxy_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            deadline = time.monotonic() + 20.0
            while True:
                if proxy_proc.poll() is not None:
                    out = proxy_proc.stdout.read() if proxy_proc.stdout else ""
                    raise RuntimeError(
                        f"alloydb-auth-proxy exited early ({proxy_proc.returncode}): {out}"
                    )
                try:
                    with socket.create_connection(
                        ("127.0.0.1", args.proxy_port), timeout=0.5
                    ):
                        break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"alloydb-auth-proxy did not listen on 127.0.0.1:{args.proxy_port} "
                            "within 20s"
                        ) from exc
                    time.sleep(0.25)
            encoded_user = quote(args.db_user.strip(), safe="")
            dsn = f"postgresql://{encoded_user}@127.0.0.1:{args.proxy_port}/postgres"
        if not dsn:
            raise ValueError("Provide either --dsn or --instance-uri.")

        receipt = asyncio.run(
            bootstrap_alloydb(
                dsn=dsn,
                iam_auth=args.iam_auth,
                grant_iam_users=args.grant_iam_user,
            )
        )
        print(receipt)
        return 0
    finally:
        if proxy_proc is not None:
            proxy_proc.terminate()
            try:
                proxy_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
