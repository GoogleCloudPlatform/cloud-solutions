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

"""Gemini CLI Extension Execution Engine for Oracle EBS PL/SQL and ISG REST."""

import logging
from typing import Any

from src.mcp.ebs_db_client import ORACLE_DRIVER, EBSDatabaseClient
from src.mcp.ebs_rest_client import EBSISGWorkflowRestClient

__all__ = ["ORACLE_DRIVER", "ExecutionEngine"]

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Certified Execution Engine exposing PL/SQL API and ISG REST channels."""

    def __init__(self, dsn: str, user: str, password: str) -> None:
        self.dsn = dsn
        self.user = user
        self.password = password
        self._db_client: EBSDatabaseClient | None = None
        self._rest_client: EBSISGWorkflowRestClient | None = None

    @property
    def db_client(self) -> EBSDatabaseClient:
        """Lazy load database client."""
        if self._db_client is None:
            # When Pylint runs across the monorepo, it may resolve
            # src.mcp.ebs_db_client to oracle-ebs-agentic-ai's definition.
            # pylint: disable-next=unexpected-keyword-arg
            self._db_client = EBSDatabaseClient(
                user=self.user, password=self.password, dsn=self.dsn
            )
        return self._db_client

    @property
    def rest_client(self) -> EBSISGWorkflowRestClient:
        """Lazy load ISG REST client."""
        if self._rest_client is None:
            self._rest_client = EBSISGWorkflowRestClient()
        return self._rest_client

    def get_pool(self) -> Any:
        """Retrieve the underlying Oracle connection pool."""
        return self.db_client.pool

    def execute_plsql(
        self, plsql_block: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute certified PL/SQL API block via shared EBSDatabaseClient."""
        return self.db_client.execute_plsql(plsql_block, params)

    def respond_plsql(
        self,
        nid: int,
        action: str,
        comment: str,
        user_name: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Channel helper to respond to notification via certified PL/SQL."""
        return self.db_client.respond_to_notification(
            nid=nid,
            action=action,
            comment=comment,
            user_name=user_name,
            context=context,
        )

    async def respond_rest(
        self,
        nid: int,
        action: str,
        comment: str,
        user_name: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """Respond to notification via certified ISG REST API."""
        return await self.rest_client.respond_to_notification(
            nid=nid,
            action=action,
            comment=comment,
            user_name=user_name,
            auth_token=auth_token,
        )

    def close(self) -> None:
        """Close connection pool resources."""
        if self._db_client and self._db_client.pool is not None:
            try:
                self._db_client.pool.close()
            except (RuntimeError, ValueError, AttributeError, OSError):
                pass
