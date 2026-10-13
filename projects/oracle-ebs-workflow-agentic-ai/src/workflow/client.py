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

"""Oracle EBS Workflow Execution & Data Access Client."""

import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException, status
from src.a2a.schemas import (
    NotificationDetail,
    NotificationItem,
    extract_amount_from_attributes,
    parse_amount_value,
)
from src.config import Settings, get_settings
from src.gemini_cli_extensions.oracle import ExecutionEngine
from src.mcp.ebs_db_client import load_plsql_template
from src.mcp.ebs_rest_client import EBSISGWorkflowRestClient
from src.workflow.policy import PolicyEngine

logger = logging.getLogger(__name__)


class EBSWorkflowClient:
    """Certified Oracle EBS Workflow client with ISG REST and PL/SQL paths."""

    _default_isg_query_supported: bool = True

    def __init__(
        self,
        engine: ExecutionEngine | Any | None = None,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.engine = engine or ExecutionEngine(
            dsn=self.settings.db.dsn,
            user=self.settings.db.user,
            password=self.settings.db.password,
        )
        self._http_client = http_client
        self._custom_http_client = http_client is not None
        self._isg_query_supported: bool = (
            True
            if self._custom_http_client
            else EBSWorkflowClient._default_isg_query_supported
        )
        self.rest_client = EBSISGWorkflowRestClient(
            base_url=self.settings.workflow.isg_base_url,
            http_client=http_client,
        )

    def set_http_client(self, http_client: httpx.Client) -> None:
        """Override the HTTP client instance (used for testing)."""
        self._http_client = http_client
        self._custom_http_client = True
        self._isg_query_supported = True
        self.rest_client.set_http_client(http_client)

    def _mark_isg_query_unsupported(self) -> None:
        """Cache ISG REST query unavailability to prevent repeat timeouts."""
        self._isg_query_supported = False
        if not self._custom_http_client:
            EBSWorkflowClient._default_isg_query_supported = False

    def _get_http_client(self) -> httpx.Client:
        """Retrieve or initialize persistent HTTP client for REST calls."""
        if self._http_client is None:
            auth = self.rest_client.get_basic_auth()
            self._http_client = httpx.Client(
                timeout=30.0,
                auth=auth,
                headers=self.rest_client.build_headers(),
            )
            self.rest_client.set_http_client(self._http_client)
        return self._http_client

    def list_notifications(
        self,
        recipient: str | None = None,
        message_type: str | None = None,
        status_val: str = "OPEN",
        limit: int = 50,
        offset: int = 0,
    ) -> list[NotificationItem]:
        """Query pending notifications via ISG REST with PL/SQL API fallback."""
        if limit < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Query limit must be greater than or equal to 1",
            )
        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Query offset must be greater than or equal to 0",
            )

        if self._isg_query_supported:
            self._get_http_client()
            try:
                items_list = self.rest_client.list_notifications_sync(
                    recipient=recipient,
                    message_type=message_type,
                    status_val=status_val,
                    limit=limit,
                    offset=offset,
                )
                return [self._map_notification_row(r) for r in items_list]
            except (httpx.RequestError, RuntimeError, HTTPException) as exc:
                if isinstance(exc, HTTPException) and (
                    self._custom_http_client
                    or exc.status_code != status.HTTP_404_NOT_FOUND
                ):
                    raise
                self._mark_isg_query_unsupported()
                logger.warning(
                    "ISG REST list_notifications failed (%s), "
                    "falling back to secondary PL/SQL API",
                    exc,
                )

        return self._execute_plsql_list_notifications(
            recipient=recipient,
            message_type=message_type,
            status_val=status_val,
            limit=limit,
            offset=offset,
        )

    def _execute_plsql_list_notifications(
        self,
        recipient: str | None,
        message_type: str | None,
        status_val: str,
        limit: int,
        offset: int,
    ) -> list[NotificationItem]:
        """Secondary certified PL/SQL API call for open worklist."""
        plsql_block = load_plsql_template("list_notifications.sql")
        res = self.engine.execute_plsql(
            plsql_block,
            {
                "recipient": recipient,
                "message_type": message_type,
                "status_val": status_val,
                "limit": limit,
                "offset": offset,
            },
        )
        raw_json = res.get("out_json")
        rows: list[dict[str, Any]] = json.loads(raw_json) if raw_json else []
        return [self._map_notification_row(r) for r in rows]

    def get_notification(self, nid: int) -> NotificationItem:
        """Fetch a single notification by ID with PL/SQL API fallback."""
        if nid <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Notification ID must be a positive integer",
            )

        if self._isg_query_supported:
            self._get_http_client()
            try:
                raw_row = self.rest_client.get_notification_sync(nid)
                return self._map_notification_row(raw_row)
            except (httpx.RequestError, RuntimeError, HTTPException) as exc:
                if isinstance(exc, HTTPException) and (
                    self._custom_http_client
                    or exc.status_code != status.HTTP_404_NOT_FOUND
                ):
                    raise
                self._mark_isg_query_unsupported()
                logger.warning(
                    "ISG REST get_notification(%s) failed (%s), "
                    "falling back to secondary PL/SQL API",
                    nid,
                    exc,
                )

        return self._execute_plsql_get_notification(nid)

    def _execute_plsql_get_notification(self, nid: int) -> NotificationItem:
        """Secondary certified PL/SQL API call for single notification."""
        plsql_block = load_plsql_template("get_notification_info.sql")
        res = self.engine.execute_plsql(plsql_block, {"nid": nid})
        raw_json = res.get("out_json")
        if not raw_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow notification {nid} not found",
            )
        row = json.loads(raw_json)
        if not isinstance(row, dict) or not row.get("notification_id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow notification {nid} not found",
            )
        return self._map_notification_row(row)

    def get_notification_attributes(
        self, nid: int, verify_exists: bool = True
    ) -> dict[str, Any]:
        """Fetch attribute key-value pairs via ISG REST or PL/SQL API."""
        if nid <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Notification ID must be a positive integer",
            )

        if self._isg_query_supported:
            self._get_http_client()
            try:
                raw_attrs = self.rest_client.get_notification_attributes_sync(
                    nid
                )
                attributes: dict[str, Any] = {}
                for k, v in raw_attrs.items():
                    key = str(k).upper()
                    attributes[key] = (
                        float(v) if isinstance(v, (int, float)) else v
                    )
                return attributes
            except (httpx.RequestError, RuntimeError, HTTPException) as exc:
                if isinstance(exc, HTTPException) and (
                    self._custom_http_client
                    or exc.status_code != status.HTTP_404_NOT_FOUND
                ):
                    raise
                self._mark_isg_query_unsupported()
                logger.warning(
                    "ISG REST get_notification_attributes(%s) failed (%s), "
                    "falling back to secondary PL/SQL API",
                    nid,
                    exc,
                )

        return self._execute_plsql_get_notification_attributes(
            nid, verify_exists=verify_exists
        )

    def _execute_plsql_get_notification_attributes(
        self, nid: int, verify_exists: bool = True
    ) -> dict[str, Any]:
        """Secondary certified PL/SQL API call for notification attributes."""
        if verify_exists:
            self.get_notification(nid)

        plsql_block = load_plsql_template("get_notification_attrs.sql")
        res = self.engine.execute_plsql(plsql_block, {"nid": nid})
        raw_json = res.get("out_json")
        parsed = json.loads(raw_json) if raw_json else []
        attributes: dict[str, Any] = {}
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                name = str(k).upper()
                attributes[name] = (
                    float(v) if isinstance(v, (int, float)) else v
                )
            return attributes

        for row in parsed:
            name = str(row.get("name", "")).upper()
            if row.get("number_value") is not None:
                attributes[name] = float(row["number_value"])
            elif row.get("date_value") is not None:
                attributes[name] = str(row["date_value"])
            else:
                attributes[name] = row.get("text_value")
        return attributes

    def get_notification_detail(self, nid: int) -> NotificationDetail:
        """Fetch composite notification header and associated attributes."""
        header = self.get_notification(nid)
        attributes = self.get_notification_attributes(nid, verify_exists=False)
        if header.amount is None:
            header.amount = extract_amount_from_attributes(
                attributes, header.subject
            )
        PolicyEngine.evaluate(header, attributes)
        return NotificationDetail(header=header, attributes=attributes)

    def respond_via_plsql(
        self,
        nid: int,
        action: str,
        comment: str,
        responder: str | None = None,
    ) -> dict[str, Any]:
        """Path A (Secondary): Execute apps.wf_notification.respond."""
        if nid <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Notification ID must be a positive integer",
            )

        notification = self.get_notification(nid)
        if notification.status.upper() != "OPEN":
            act_verb = "approved" if action.upper() == "APPROVE" else "rejected"
            raise RuntimeError(
                f"Notification #{nid} is already "
                f"{notification.status.upper()} and cannot be {act_verb}; "
                "no action is required."
            )

        resp_user = (
            responder or notification.recipient_role or self.settings.db.user
        )
        plsql_block = load_plsql_template("respond_notification.sql")
        params = {
            "user_id": self.settings.fnd.user_id,
            "resp_id": self.settings.fnd.resp_id,
            "resp_appl_id": self.settings.fnd.resp_appl_id,
            "nid": nid,
            "action_result": (
                "APPROVED" if action.upper() == "APPROVE" else "REJECTED"
            ),
            "comment_text": comment,
            "responder_name": resp_user,
            "recipient_role": notification.recipient_role,
        }

        logger.info(
            "Path A (PL/SQL Secondary): "
            "apps.wf_notification.respond(nid=%s, action=%s)",
            nid,
            action,
        )
        self.engine.execute_plsql(plsql_block, params)
        return {
            "status": "SUCCESS",
            "execution_path": "PLSQL",
            "notification_id": nid,
            "action": action.upper(),
            "responder": resp_user,
            "message": (
                f"Successfully recorded {action.upper()} "
                "response via PL/SQL API"
            ),
        }

    def respond_via_rest(
        self,
        nid: int,
        action: str,
        comment: str,
        responder: str | None = None,
        fallback_on_error: bool = False,
    ) -> dict[str, Any]:
        """Path B (Primary): POST /webservices/rest/wf/respond."""
        if nid <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Notification ID must be a positive integer",
            )

        notification = self.get_notification(nid)
        if notification.status.upper() != "OPEN":
            act_verb = "approved" if action.upper() == "APPROVE" else "rejected"
            raise RuntimeError(
                f"Notification #{nid} is already "
                f"{notification.status.upper()} and cannot be {act_verb}; "
                "no action is required."
            )

        resp_user = (
            responder or notification.recipient_role or self.settings.db.user
        )
        self._get_http_client()
        try:
            self.rest_client.respond_to_notification_sync(
                nid=nid,
                action=action,
                comment=comment,
                user_name=resp_user,
            )
            if not self._custom_http_client:
                post_check = self.get_notification(nid)
                if post_check.status.upper() == "OPEN":
                    if fallback_on_error:
                        logger.warning(
                            "ISG REST respond returned 200 for nid=%s "
                            "but status remained OPEN; falling back to "
                            "secondary PL/SQL API",
                            nid,
                        )
                        return self.respond_via_plsql(
                            nid=nid,
                            action=action,
                            comment=comment,
                            responder=responder,
                        )
                    raise RuntimeError(
                        f"Notification #{nid} remained OPEN "
                        "after ISG REST respond."
                    )
            return {
                "status": "SUCCESS",
                "execution_path": "REST",
                "notification_id": nid,
                "action": action.upper(),
                "responder": resp_user,
                "message": (
                    f"Successfully recorded {action.upper()} "
                    "response via ISG REST"
                ),
            }
        except (httpx.RequestError, RuntimeError, HTTPException) as exc:
            if isinstance(exc, HTTPException) and (
                not fallback_on_error
                or self._custom_http_client
                or exc.status_code != status.HTTP_404_NOT_FOUND
            ):
                raise
            err_str = str(exc)
            if "ORA-20002" in err_str or "3202" in err_str:
                raise
            logger.warning(
                "ISG REST respond error (%s) for nid=%s, "
                "falling back to secondary PL/SQL API: %s",
                exc,
                nid,
                fallback_on_error,
            )
            if fallback_on_error:
                return self.respond_via_plsql(
                    nid=nid,
                    action=action,
                    comment=comment,
                    responder=responder,
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Failed to communicate with Oracle EBS ISG REST "
                    f"endpoint: {exc}"
                ),
            ) from exc

    def respond(
        self,
        nid: int,
        action: str,
        comment: str,
        responder: str | None = None,
        path: str = "REST",
    ) -> dict[str, Any]:
        """Dispatch workflow response via ISG REST or PL/SQL."""
        normalized_action = action.strip().upper()
        if normalized_action not in ("APPROVE", "REJECT"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Invalid action '{action}'. Must be 'APPROVE' or 'REJECT'"
                ),
            )

        chosen_path = (
            (path or self.settings.workflow.default_path).strip().upper()
        )
        if chosen_path == "REST":
            return self.respond_via_rest(
                nid=nid,
                action=normalized_action,
                comment=comment,
                responder=responder,
                fallback_on_error=True,
            )
        if chosen_path == "PLSQL":
            return self.respond_via_plsql(
                nid=nid,
                action=normalized_action,
                comment=comment,
                responder=responder,
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Unsupported execution path '{path}'. Choose 'REST' or 'PLSQL'"
            ),
        )

    def _map_notification_row(self, row: dict[str, Any]) -> NotificationItem:
        """Map row or JSON object to typed NotificationItem."""
        raw_attrs = row.get("attributes")
        attrs_dict = raw_attrs if isinstance(raw_attrs, dict) else {}
        item = NotificationItem(
            notification_id=int(row["notification_id"]),
            message_type=str(row["message_type"]),
            message_name=str(row.get("message_name", "")),
            recipient_role=str(row["recipient_role"]),
            status=str(row.get("status", "OPEN")),
            subject=str(row.get("subject", "")),
            priority=int(row.get("priority", 50)),
            begin_date=row.get("begin_date"),
            due_date=row.get("due_date"),
            amount=self._extract_amount_from_row(row),
            requester=row.get("recipient_role"),
            attributes=attrs_dict,
        )
        PolicyEngine.evaluate(item, attrs_dict)
        return item

    @staticmethod
    def _extract_amount_from_row(row: dict[str, Any]) -> float | None:
        """Attempt to extract amount from row data, attributes, or subject."""
        parsed = parse_amount_value(row.get("amount"))
        if parsed is not None:
            return parsed
        return extract_amount_from_attributes(
            row.get("attributes"), str(row.get("subject") or "")
        )

    def close(self) -> None:
        """Close associated engine and HTTP client connections."""
        self.engine.close()
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None
            self.rest_client.set_http_client(None)


OracleWorkflowClient = EBSWorkflowClient
