# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Oracle EBS Database Client with certified PL/SQL API and ISG REST."""

import json
import logging
import re
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import oracledb
from fastapi import HTTPException, status
from src.a2a.schemas import (
    ALLOWED_WORKFLOW_TYPES,
    extract_amount_from_attributes,
    parse_amount_value,
)
from src.config import get_settings
from src.mcp.ebs_rest_client import EBSISGWorkflowRestClient

ORACLE_DRIVER: ModuleType | None = oracledb

logger = logging.getLogger(__name__)

_SQL_DIR = Path(__file__).resolve().parent.parent / "workflow" / "sql"


@lru_cache
def load_plsql_template(filename: str) -> str:
    """Load and cache an external PL/SQL block from src/workflow/sql/."""
    return (_SQL_DIR / filename).read_text(encoding="utf-8").strip()


class EBSDatabaseClient:
    """Manages pooled connections to Oracle EBS and executes certified APIs."""

    def __init__(
        self,
        user: str,
        password: str,
        dsn: str,
        min_conns: int = 1,
        max_conns: int = 5,
    ) -> None:
        self.user = user
        self.password = password
        self.dsn = dsn
        self.min_conns = min_conns
        self.max_conns = max_conns
        self.pool: Any = None
        self.rest_client = EBSISGWorkflowRestClient()

    @staticmethod
    def _is_legacy_verifier_error(exc: BaseException) -> bool:
        """Return True if exception is a DPY-3015 / 0x939 verifier error."""
        msg = str(exc)
        return "DPY-3015" in msg or "0x939" in msg

    def _create_driver_pool(self) -> Any:
        """Create and return an Oracle connection pool instance."""
        if ORACLE_DRIVER is None:
            return None
        if hasattr(ORACLE_DRIVER, "create_pool"):
            return ORACLE_DRIVER.create_pool(
                user=self.user,
                password=self.password,
                dsn=self.dsn,
                min=self.min_conns,
                max=self.max_conns,
                increment=1,
            )
        if hasattr(ORACLE_DRIVER, "SessionPool"):
            return ORACLE_DRIVER.SessionPool(
                user=self.user,
                password=self.password,
                dsn=self.dsn,
                min=self.min_conns,
                max=self.max_conns,
                increment=1,
            )
        return None

    def _enable_thick_mode(self) -> None:
        """Switch python-oracledb from Thin Mode to Thick Mode for 0x939."""
        if ORACLE_DRIVER is None or not hasattr(
            ORACLE_DRIVER, "init_oracle_client"
        ):
            return
        if self.pool is not None and hasattr(self.pool, "close"):
            try:
                self.pool.close(force=True)
            except (oracledb.Error, RuntimeError, TypeError, OSError) as exc:
                logger.debug("Ignoring error closing Thin pool: %s", exc)
            self.pool = None
        driver_mode_mod = getattr(
            ORACLE_DRIVER, "driver_mode", None
        ) or sys.modules.get("oracledb.driver_mode")
        mode_mgr = getattr(driver_mode_mod, "manager", None)
        if mode_mgr is not None and getattr(mode_mgr, "thin_mode", None):
            mode_mgr.thin_mode = None
        ORACLE_DRIVER.init_oracle_client()
        logger.info("Switched python-oracledb to Thick Mode for %s", self.dsn)

    def _self_heal_verifier(self, conn: Any) -> None:
        """Best-effort upgrade of legacy 10G verifier after Thick login."""
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_$#]{0,127}", self.user):
            return
        if not self.password or any(
            ch in self.password for ch in ('"', "\n", "\r", "\x00")
        ):
            return
        cursor = conn.cursor()
        try:
            for stmt in (
                load_plsql_template("enable_case_sensitive_logon.sql"),
                f'ALTER USER {self.user} IDENTIFIED BY "{self.password}"',
            ):
                try:
                    cursor.execute(stmt, {})
                except (
                    oracledb.Error,
                    RuntimeError,
                    ValueError,
                    OSError,
                ) as exc:
                    logger.debug("Skipping verifier self-heal step: %s", exc)
        finally:
            cursor.close()

    def _ensure_agent_package(self) -> None:
        """Acquire bootstrap connection, self-heal verifier, and compile pkg."""
        healed = False
        try:
            if self.pool is None:
                self.pool = self._create_driver_pool()
            if self.pool is None:
                return
            conn = self.pool.acquire()
        except (oracledb.Error, RuntimeError, ValueError, OSError) as exc:
            if not self._is_legacy_verifier_error(exc):
                raise
            self._enable_thick_mode()
            self.pool = self._create_driver_pool()
            if self.pool is None:
                return
            conn = self.pool.acquire()
            healed = True
        try:
            if healed:
                self._self_heal_verifier(conn)
            cursor = conn.cursor()
            try:
                if not hasattr(cursor, "fetchone"):
                    return
                cursor.execute(
                    load_plsql_template("check_agent_pkg_status.sql"), {}
                )
                row = cursor.fetchone()
                valid_count = int(row[0]) if row else 0
                if valid_count < 2:
                    cursor.execute(
                        load_plsql_template("xx_ebs_wf_agent_pkg_spec.sql"), {}
                    )
                    cursor.execute(
                        load_plsql_template("xx_ebs_wf_agent_pkg_body.sql"), {}
                    )
                    conn.commit()
                    logger.info(
                        "Compiled APPS.XX_EBS_WF_AGENT_PKG on %s", self.dsn
                    )
            finally:
                cursor.close()
        finally:
            self.release_connection(conn)

    def initialize_pool(self) -> None:
        """Initialize the database connection pool with Thick fallback."""
        if ORACLE_DRIVER is None:
            logger.warning(
                "Oracle driver (oracledb) not installed; "
                "operating without active DB pool."
            )
            return
        try:
            self.pool = None
            self._ensure_agent_package()
            logger.info(
                "Oracle EBS connection pool initialized for %s", self.dsn
            )
        except (oracledb.Error, RuntimeError, ValueError, OSError) as exc:
            logger.error("Failed to initialize Oracle EBS pool: %s", exc)
            raise

    def get_connection(self) -> Any:
        """Acquire a connection from the pool, initializing lazily if needed."""
        if self.pool is None and ORACLE_DRIVER is not None:
            self.initialize_pool()
        if self.pool is not None:
            return self.pool.acquire()
        if ORACLE_DRIVER is not None:
            try:
                return ORACLE_DRIVER.connect(
                    user=self.user, password=self.password, dsn=self.dsn
                )
            except (oracledb.Error, RuntimeError, ValueError, OSError) as exc:
                if not self._is_legacy_verifier_error(exc):
                    raise
                self._enable_thick_mode()
                conn = ORACLE_DRIVER.connect(
                    user=self.user, password=self.password, dsn=self.dsn
                )
                self._self_heal_verifier(conn)
                return conn
        raise RuntimeError(
            "Database driver ORACLE_DRIVER is not available and no pool exists."
        )

    def release_connection(self, conn: Any) -> None:
        """Release or close an acquired database connection."""
        if self.pool is not None:
            self.pool.release(conn)
        else:
            conn.close()

    def execute_plsql(
        self, plsql_block: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute certified PL/SQL API block with optional CLOB JSON output."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            try:
                bind_params = dict(params or {})
                out_var = None
                if ":out_json" in plsql_block and hasattr(cursor, "var"):
                    clob_type = getattr(ORACLE_DRIVER, "DB_TYPE_CLOB", str)
                    out_var = cursor.var(clob_type)
                    bind_params["out_json"] = out_var
                cursor.execute(plsql_block, bind_params)
                result: dict[str, Any] = {"status": "SUCCESS"}
                if out_var is not None:
                    raw_val = out_var.getvalue()
                    if hasattr(raw_val, "read"):
                        raw_val = raw_val.read()
                    result["out_json"] = raw_val
                conn.commit()
                return result
            finally:
                cursor.close()
        finally:
            self.release_connection(conn)

    def initialize_apps_context(
        self,
        cursor: Any,
        user_id: int,
        resp_id: int,
        resp_appl_id: int,
    ) -> None:
        """Initialize Oracle EBS applications session security context."""
        plsql = load_plsql_template("init_apps_context.sql")
        cursor.execute(
            plsql,
            {
                "user_id": user_id,
                "resp_id": resp_id,
                "resp_appl_id": resp_appl_id,
            },
        )
        logger.info(
            "FND security context initialized for user_id=%s, resp_id=%s, "
            "resp_appl_id=%s",
            user_id,
            resp_id,
            resp_appl_id,
        )

    def respond_to_notification(
        self,
        nid: int,
        action: str,
        comment: str,
        user_name: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Safely respond to a notification through ISG REST or PL/SQL API."""
        normalized_action = self.rest_client.validate_respond_inputs(
            nid, action
        )
        ctx = context or {}
        if not ctx.get("force_plsql"):
            try:
                res = self.rest_client.respond_to_notification_sync(
                    nid=nid,
                    action=normalized_action,
                    comment=comment,
                    user_name=user_name,
                )
                return {
                    "status": "SUCCESS",
                    "notification_id": nid,
                    "action": normalized_action,
                    "responder": user_name,
                    "comments": comment,
                    "execution_path": "REST",
                    "details": res,
                }
            except (HTTPException, RuntimeError) as exc:
                if isinstance(exc, HTTPException) and exc.status_code in (
                    status.HTTP_404_NOT_FOUND,
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                ):
                    raise
                logger.warning(
                    "ISG REST respond_to_notification failed (%s), "
                    "falling back to secondary certified PL/SQL execution",
                    exc,
                )
        settings = get_settings()
        user_id = ctx.get("user_id", settings.fnd_user_id)
        resp_id = ctx.get("resp_id", settings.fnd_resp_id)
        resp_appl_id = ctx.get("resp_appl_id", settings.fnd_resp_appl_id)

        plsql = load_plsql_template("respond_notification_pkg.sql")
        self.execute_plsql(
            plsql,
            {
                "user_id": user_id,
                "resp_id": resp_id,
                "resp_appl_id": resp_appl_id,
                "nid": nid,
                "result_val": (
                    "APPROVED"
                    if normalized_action == "APPROVE"
                    else "REJECTED"
                ),
                "comment_val": comment,
                "responder_val": user_name,
            },
        )
        return {
            "status": "SUCCESS",
            "notification_id": nid,
            "action": normalized_action,
            "responder": user_name,
            "comments": comment,
        }

    def get_pending_notifications(
        self,
        recipient: str | None = None,
        notification_type: str | None = None,
        max_amount: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve pending notifications through ISG REST or PL/SQL API."""
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Limit must be between 1 and 100",
            )
        if max_amount is not None and max_amount < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="max_amount cannot be negative",
            )
        normalized_type: str | None = None
        if notification_type is not None:
            normalized_type = notification_type.upper().strip()
            if normalized_type not in ALLOWED_WORKFLOW_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Invalid notification_type: {notification_type}",
                )

        try:
            rest_items = self.rest_client.get_pending_notifications_sync(
                recipient=recipient,
                notification_type=normalized_type,
                max_amount=max_amount,
                limit=limit,
            )
            if rest_items:
                return rest_items
        except (HTTPException, RuntimeError) as exc:
            if isinstance(exc, HTTPException) and exc.status_code in (
                status.HTTP_404_NOT_FOUND,
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            ):
                raise
            logger.warning(
                "ISG REST get_pending_notifications failed (%s), "
                "falling back to secondary certified PL/SQL API",
                exc,
            )

        plsql = load_plsql_template("list_notifications.sql")
        res = self.execute_plsql(
            plsql,
            {
                "recipient": recipient,
                "message_type": normalized_type,
                "status_val": "OPEN",
                "limit": limit,
                "offset": 0,
            },
        )
        raw_val = res.get("out_json")
        items_list: list[dict[str, Any]] = (
            json.loads(raw_val) if raw_val else []
        )
        results: list[dict[str, Any]] = []
        for item in items_list:
            amt = parse_amount_value(item.get("amount"))
            if amt is None:
                amt = extract_amount_from_attributes(
                    item.get("attributes"), item.get("subject")
                )
            item["amount"] = amt
            item.setdefault("attributes", {})
            if max_amount is not None and amt is not None and amt > max_amount:
                continue
            results.append(item)
        return results
