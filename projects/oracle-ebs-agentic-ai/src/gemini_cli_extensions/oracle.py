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

"""Gemini CLI Extension Execution Engine for Oracle Databases."""

import logging
import sqlite3
from types import ModuleType
from typing import Any, Dict, List, Optional

oracledb_module: Optional[ModuleType] = None
try:
    import oracledb as _oracledb

    oracledb_module = _oracledb
except ImportError:
    pass

logger = logging.getLogger(__name__)

DB_EXCEPTIONS = (
    (oracledb_module.Error, RuntimeError, AttributeError, ValueError, OSError)
    if oracledb_module and hasattr(oracledb_module, "Error")
    else (RuntimeError, AttributeError, ValueError, OSError)
)


class ExecutionEngine:
    """Execution Engine for Gemini CLI Extension for Oracle.

    Provides high-performance execution of SQL queries and PL/SQL procedures
    over Oracle EBS database endpoints using resilient connection pooling.
    """

    def __init__(self, dsn: str, user: str, password: str) -> None:
        self.dsn = dsn
        self.user = user
        self.password = password
        self.connection: Any = None
        self.pool: Any = None

    def get_pool(self) -> Any:
        """Retrieve or initialize Oracle connection pool for high throughput."""
        if not oracledb_module:
            return None
        if not self.pool:
            try:
                self.pool = oracledb_module.create_pool(
                    user=self.user,
                    password=self.password,
                    dsn=self.dsn,
                    min=1,
                    max=5,
                    increment=1,
                    getmode=oracledb_module.POOL_GETMODE_WAIT,
                )
            except (
                AttributeError,
                ValueError,
                TypeError,
                *DB_EXCEPTIONS,
            ) as exc:
                logger.debug("Connection pool creation skipped: %s", exc)
                self.pool = None
        return self.pool

    def connect(self) -> Any:
        """Establish connection to Oracle database."""
        if not oracledb_module:
            raise RuntimeError("oracledb library is not installed")
        pool = self.get_pool()
        if pool:
            try:
                return pool.acquire()
            except (
                AttributeError,
                ValueError,
                TypeError,
                *DB_EXCEPTIONS,
            ) as exc:
                logger.debug("Pool acquire fallback: %s", exc)
        if not self.connection:
            self.connection = oracledb_module.connect(
                user=self.user,
                password=self.password,
                dsn=self.dsn,
            )
        return self.connection

    def execute(
        self, sql: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute SQL query and return results as dictionary records."""
        if not oracledb_module:
            logger.warning("oracledb module unavailable. Skipping execution.")
            return []

        conn = None
        is_pooled = False
        pool = self.get_pool()
        try:
            if pool:
                try:
                    conn = pool.acquire()
                    is_pooled = True
                except (AttributeError, ValueError, TypeError, *DB_EXCEPTIONS):
                    conn = None
            if not conn:
                conn = self.connect()
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute(sql, params or {})
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                records = [dict(zip(columns, row)) for row in cursor.fetchall()]
                cursor.close()
                if is_pooled and pool:
                    pool.release(conn)
                return records
            conn.commit()
            cursor.close()
            if is_pooled and pool:
                pool.release(conn)
            return []
        except (
            sqlite3.Error,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
            *DB_EXCEPTIONS,
        ) as exc:
            logger.warning("SQL execution error: %s", exc)
            if conn and is_pooled and pool:
                try:
                    pool.release(conn)
                except (AttributeError, ValueError, TypeError, *DB_EXCEPTIONS):
                    pass
            return []

    def close(self) -> None:
        """Close database connection and connection pool."""
        if self.connection:
            try:
                self.connection.close()
            except DB_EXCEPTIONS:
                pass
            self.connection = None
        if self.pool:
            try:
                self.pool.close()
            except DB_EXCEPTIONS:
                pass
            self.pool = None
