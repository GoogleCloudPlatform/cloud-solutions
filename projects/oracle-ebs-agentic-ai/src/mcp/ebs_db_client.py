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

"""Oracle EBS Database Client with Gemini Extensions & Oracle Skills."""

import logging
import os
import re
import sqlite3
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, status
from pydantic import BaseModel, Field
from src.gemini_cli_extensions.oracle import (
    DB_EXCEPTIONS,
)
from src.gemini_cli_extensions.oracle import (
    ExecutionEngine as GeminiOracleEngine,
)
from src.oracle.skills import NLToSQLEngine as OracleSkillsEngine

logger = logging.getLogger(__name__)


class EBSDatabaseClient:
    """Secure Database Client for Oracle E-Business Suite (EBS)."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        service_name: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.environment = os.getenv("ENVIRONMENT", "dev").lower()
        self.is_dev_mode = self.environment in (
            "dev",
            "development",
            "demo",
            "test",
        )

        oracle_port = os.getenv("ORACLE_PORT")
        self.host = (
            host
            or os.getenv("ORACLE_HOST")
            or ("127.0.0.1" if self.is_dev_mode else None)
        )
        self.port = (
            port
            or (int(oracle_port) if oracle_port else None)
            or (1521 if self.is_dev_mode else None)
        )
        self.service_name = (
            service_name
            or os.getenv("ORACLE_SERVICE_NAME")
            or ("ebsdb" if self.is_dev_mode else None)
        )
        self.user = (
            user
            or os.getenv("ORACLE_USER")
            or ("apps" if self.is_dev_mode else None)
        )
        self.password = (
            password
            if password is not None
            else (
                os.getenv("ORACLE_PASSWORD")
                if os.getenv("ORACLE_PASSWORD") is not None
                else ("apps" if self.is_dev_mode else None)
            )
        )

        missing_vars: List[str] = []
        if not self.host:
            missing_vars.append("ORACLE_HOST")
        if not self.port:
            missing_vars.append("ORACLE_PORT")
        if not self.service_name:
            missing_vars.append("ORACLE_SERVICE_NAME")
        if not self.user:
            missing_vars.append("ORACLE_USER")
        if self.password is None:
            missing_vars.append("ORACLE_PASSWORD")

        if missing_vars:
            vars_str = ", ".join(missing_vars)
            raise ValueError(
                f"Missing required Oracle DB configuration: {vars_str}"
            )

        self.dsn = f"{self.host}:{self.port}/{self.service_name}"

        # Bind to gemini-cli-extensions/oracle execution engine
        self.execution_engine = GeminiOracleEngine(
            dsn=self.dsn,
            user=self.user or "",
            password=self.password or "",
        )

        # Bind to oracle/skills NL-to-SQL engine
        self.skills_engine = OracleSkillsEngine(
            execution_engine=self.execution_engine,
        )

        self._connection: Any = None
        self._context_initialized: bool = False
        try:
            self.connect()
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
            sqlite3.Error,
            *DB_EXCEPTIONS,
        ) as exc:
            logger.warning("Initial DB connection warning: %s", exc)

    def validate_read_only_sql(self, query: str) -> Optional[Dict[str, str]]:
        """Validate that SQL query is a read-only SELECT statement.

        Args:
            query: SQL query string to validate.

        Returns:
            Optional error dict if validation fails, None if valid.
        """
        clean_query = query.strip()
        upper_query = clean_query.upper()

        if not (
            upper_query.startswith("SELECT") or upper_query.startswith("WITH")
        ):
            logger.warning("Disallowed non-SELECT query attempt: %s", query)
            return {"error": "Security Error: Only SELECT queries permitted."}

        forbidden_keywords = (
            "UPDATE",
            "DELETE",
            "DROP",
            "INSERT",
            "TRUNCATE",
            "ALTER",
            "GRANT",
            "REVOKE",
            "EXEC",
        )
        for kw in forbidden_keywords:
            if re.search(r"\b" + kw + r"\b", upper_query):
                logger.warning(
                    "Disallowed mutating keyword '%s' in query: %s", kw, query
                )
                return {"error": f"Security Error: Keyword '{kw}' not allowed."}
        return None

    def connect(self) -> Any:
        """Establish connection via Gemini Extension Engine."""
        try:
            self._connection = self.execution_engine.connect()
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
            sqlite3.Error,
            *DB_EXCEPTIONS,
        ) as exc:
            logger.warning("Execution engine connection failed: %s", exc)
            self._connection = None
        return self._connection

    def initialize_apps_context(
        self,
        user_id: Optional[int] = None,
        resp_id: Optional[int] = None,
        resp_appl_id: Optional[int] = None,
    ) -> bool:
        """Execute FND_GLOBAL.APPS_INITIALIZE for Applications Context.

        Args:
            user_id: Oracle Apps User ID (default 1015).
            resp_id: Responsibility ID (default 50625).
            resp_appl_id: Application ID (default 201).

        Returns:
            bool: True if context initialization succeeded.
        """
        final_user_id = (
            user_id
            if user_id is not None
            else int(os.getenv("FND_USER_ID", "1015"))
        )
        final_resp_id = (
            resp_id
            if resp_id is not None
            else int(os.getenv("FND_RESP_ID", "50625"))
        )
        final_resp_appl_id = (
            resp_appl_id
            if resp_appl_id is not None
            else int(os.getenv("FND_RESP_APPL_ID", "201"))
        )

        init_sql = """
        BEGIN
            FND_GLOBAL.APPS_INITIALIZE(
                user_id      => :user_id,
                resp_id      => :resp_id,
                resp_appl_id => :resp_appl_id
            );
        END;
        """
        params = {
            "user_id": final_user_id,
            "resp_id": final_resp_id,
            "resp_appl_id": final_resp_appl_id,
        }

        logger.info(
            "Initializing Apps Context: user_id=%s, resp_id=%s, "
            "resp_appl_id=%s",
            final_user_id,
            final_resp_id,
            final_resp_appl_id,
        )

        if self._connection:
            try:
                cursor = self._connection.cursor()
                cursor.execute(init_sql, params)
                self._connection.commit()
                cursor.close()
                self._context_initialized = True
                return True
            except (RuntimeError, ValueError, AttributeError, OSError) as exc:
                logger.error(
                    "Failed to execute FND_GLOBAL.APPS_INITIALIZE: %s", exc
                )
                return False

        # Execute through Gemini Oracle extension engine bridge
        try:
            self.execution_engine.execute(init_sql, params)
            self._context_initialized = True
            return True
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
            sqlite3.Error,
            *DB_EXCEPTIONS,
        ) as exc:
            logger.warning(
                "Failed to execute FND_GLOBAL.APPS_INITIALIZE: %s", exc
            )
            if self.is_dev_mode:
                self._context_initialized = True
                return True
            return False

    def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Executes a SQL query against Oracle EBS database."""

        if (
            not self.execution_engine.pool
            and not self.execution_engine.connection
        ):
            try:
                self.connect()
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
                sqlite3.Error,
                *DB_EXCEPTIONS,
            ) as exc:
                logger.warning("Lazy DB connection attempt warning: %s", exc)

        if not self._context_initialized:
            try:
                self.initialize_apps_context()
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
                sqlite3.Error,
                *DB_EXCEPTIONS,
            ) as exc:
                logger.warning("Apps Context initialization warning: %s", exc)

        try:
            results = self.execution_engine.execute(query, params)
            if results is not None and isinstance(results, list):
                return results
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
            sqlite3.Error,
            *DB_EXCEPTIONS,
        ) as exc:
            logger.warning("Direct SQL execution warning: %s", exc)

        return []

    def execute_mutation(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Executes a SQL DML mutation query with auto-commit."""
        if not self._context_initialized:
            try:
                self.initialize_apps_context()
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
                sqlite3.Error,
            ) as exc:
                logger.warning("Apps Context initialization warning: %s", exc)

        try:
            results = self.execution_engine.execute(query, params)
            if self._connection:
                self._connection.commit()
            rows_cnt = len(results) if isinstance(results, list) else 1
            return {
                "status": "success",
                "rows_affected": rows_cnt,
            }
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
            sqlite3.Error,
        ) as exc:
            logger.error("Mutation execution error: %s", exc)
            return {"status": "error", "message": str(exc)}

    def execute_nl_query(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute natural language query via Oracle Skills engine."""
        if (
            not self.execution_engine.pool
            and not self.execution_engine.connection
        ):
            try:
                self.connect()
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
                sqlite3.Error,
            ) as exc:
                logger.warning("Lazy DB connection attempt warning: %s", exc)

        if not self._context_initialized:
            try:
                self.initialize_apps_context()
            except (
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OSError,
                RuntimeError,
                sqlite3.Error,
            ) as exc:
                logger.warning("Apps Context initialization warning: %s", exc)

        try:
            results = self.skills_engine.translate_and_execute(prompt, context)
            if results is not None and isinstance(results, list):
                return results
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            RuntimeError,
            sqlite3.Error,
            *DB_EXCEPTIONS,
        ) as exc:
            logger.warning("NL query translation execution warning: %s", exc)

        return []

    def is_context_initialized(self) -> bool:
        """Return status of Apps Context initialization."""
        return self._context_initialized


@lru_cache
def get_db_client() -> EBSDatabaseClient:
    """FastAPI Dependency Provider for EBSDatabaseClient."""
    return EBSDatabaseClient()


app = FastAPI(
    title="Oracle EBS MCP Server",
    description="MCP Server for Oracle EBS Database Client & Gemini Extensions",
    version="1.0.0",
)


class QueryRequest(BaseModel):
    """Payload for natural language query execution."""

    prompt: str = Field(..., description="Natural language query prompt")


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "oracle_ebs_mcp_server"}


@app.post("/execute")
def execute(
    req: QueryRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Execute query endpoint."""
    results = db_client.execute_nl_query(req.prompt)
    return {"status": "success", "results": results}
