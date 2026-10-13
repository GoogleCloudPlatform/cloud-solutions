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

"""Oracle EBS Integrated SOA Gateway (ISG) REST Client."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
from fastapi import HTTPException, status
from src.config import get_settings

logger = logging.getLogger(__name__)


class EBSISGWorkflowRestClient:
    """Certified client for Oracle EBS ISG REST Workflow services."""

    def __init__(
        self,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        raw_url = base_url or settings.isg_rest_base_url
        self.base_url = raw_url.rstrip("/")
        self.endpoint = f"{self.base_url}/webservices/rest/wf/respond"
        self.setattr_endpoint = (
            f"{self.base_url}/webservices/rest/wf/setattrtext/"
        )
        self.notifications_endpoint = (
            f"{self.base_url}/webservices/rest/wf/notifications"
        )
        self.isg_username = settings.workflow.isg_username
        self.isg_password = settings.workflow.isg_password
        self._http_client: httpx.Client | None = http_client

    def set_http_client(self, http_client: httpx.Client | None) -> None:
        """Configure an external or persistent synchronous HTTP client."""
        self._http_client = http_client

    def build_headers(self, auth_token: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers

    def get_basic_auth(
        self, auth_token: str | None = None
    ) -> httpx.BasicAuth | None:
        if not auth_token and self.isg_username and self.isg_password:
            return httpx.BasicAuth(self.isg_username, self.isg_password)
        return None

    @contextmanager
    def _sync_client(
        self, auth_token: str | None = None
    ) -> Iterator[httpx.Client]:
        """Yield injected HTTP client or a managed temporary httpx.Client."""
        if self._http_client is not None:
            yield self._http_client
            return
        auth = self.get_basic_auth(auth_token)
        with httpx.Client(timeout=30.0, auth=auth) as client:
            yield client

    @staticmethod
    def build_isg_payloads(
        nid: int, normalized_action: str, comment: str, user_name: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Construct certified SETATTRTEXT and RESPOND ISG REST payloads."""
        rest_header = {
            "@xmlns": "http://xmlns.oracle.com/apps/fnd/rest/header",
            "Responsibility": "SYSTEM_ADMINISTRATOR",
            "RespApplication": "SYSADMIN",
            "SecurityGroup": "STANDARD",
            "NLSLanguage": "AMERICAN",
        }
        result_val = (
            "APPROVED" if normalized_action == "APPROVE" else "REJECTED"
        )
        setattr_payload = {
            "SETATTRTEXT_Input": {
                "@xmlns": (
                    "http://xmlns.oracle.com/apps/owf/rest/wf/setattrtext/"
                ),
                "RESTHeader": rest_header,
                "InputParameters": {
                    "NID": nid,
                    "ANAME": "RESULT",
                    "AVALUE": result_val,
                },
            }
        }
        respond_payload = {
            "RESPOND_Input": {
                "@xmlns": "http://xmlns.oracle.com/apps/owf/rest/wf/respond/",
                "RESTHeader": rest_header,
                "InputParameters": {
                    "NID": nid,
                    "RESPOND_COMMENT": comment,
                    "RESPONDER": user_name,
                },
            }
        }
        return setattr_payload, respond_payload

    _build_isg_payloads = build_isg_payloads

    @staticmethod
    def validate_respond_inputs(nid: int, action: str) -> str:
        """Validate notification ID and response action."""
        if nid <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Notification ID must be a positive integer",
            )
        normalized_action = action.upper().strip()
        if normalized_action not in ("APPROVE", "REJECT"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Unsupported action: {action}. "
                    "Must be APPROVE or REJECT."
                ),
            )
        return normalized_action

    async def respond_to_notification(
        self,
        nid: int,
        action: str,
        comment: str,
        user_name: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch certified workflow response to ISG REST endpoint (Async)."""
        normalized_action = self.validate_respond_inputs(nid, action)
        setattr_payload, payload = self.build_isg_payloads(
            nid, normalized_action, comment, user_name
        )
        headers = self.build_headers(auth_token)
        auth = self.get_basic_auth(auth_token)

        async with httpx.AsyncClient(timeout=30.0, auth=auth) as client:
            try:
                await client.post(
                    self.setattr_endpoint,
                    json=setattr_payload,
                    headers=headers,
                )
                response = await client.post(
                    f"{self.endpoint}/", json=payload, headers=headers
                )
                if response.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            f"Workflow notification {nid} not found on ISG REST"
                        ),
                    )
                if (
                    response.status_code
                    == status.HTTP_422_UNPROCESSABLE_CONTENT
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=response.text,
                    )
                response.raise_for_status()
                if response.status_code == status.HTTP_204_NO_CONTENT:
                    return {
                        "status": "SUCCESS",
                        "notification_id": nid,
                        "action": normalized_action,
                        "responder": user_name,
                    }
                return response.json()
            except httpx.HTTPError as exc:
                logger.error(
                    "ISG REST execution failed for NID %s: %s", nid, exc
                )
                raise RuntimeError(f"ISG REST API error: {exc}") from exc

    def respond_to_notification_sync(
        self,
        nid: int,
        action: str,
        comment: str,
        user_name: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch certified workflow response to ISG REST endpoint (Sync)."""
        normalized_action = self.validate_respond_inputs(nid, action)
        setattr_payload, payload = self.build_isg_payloads(
            nid, normalized_action, comment, user_name
        )
        headers = self.build_headers(auth_token)

        with self._sync_client(auth_token) as client:
            try:
                setattr_resp = client.post(
                    self.setattr_endpoint,
                    json=setattr_payload,
                    headers=headers,
                )
                if setattr_resp.status_code not in (200, 201, 202, 204):
                    logger.debug(
                        "ISG REST setattrtext(RESULT) returned %s for nid=%s",
                        setattr_resp.status_code,
                        nid,
                    )
                response = client.post(
                    f"{self.endpoint}/", json=payload, headers=headers
                )
                if response.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            f"Workflow notification {nid} not found on ISG REST"
                        ),
                    )
                if (
                    response.status_code
                    == status.HTTP_422_UNPROCESSABLE_CONTENT
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=response.text,
                    )
                if response.status_code not in (200, 201, 202, 204):
                    raise RuntimeError(
                        f"ISG REST call failed ({response.status_code}): "
                        f"{response.text}"
                    )
                if response.status_code == status.HTTP_204_NO_CONTENT:
                    return {
                        "status": "SUCCESS",
                        "notification_id": nid,
                        "action": normalized_action,
                        "responder": user_name,
                    }
                return response.json()
            except httpx.HTTPError as exc:
                logger.error(
                    "ISG REST execution failed for NID %s: %s", nid, exc
                )
                raise RuntimeError(f"ISG REST API error: {exc}") from exc

    def list_notifications_sync(
        self,
        recipient: str | None = None,
        message_type: str | None = None,
        status_val: str = "OPEN",
        limit: int = 50,
        offset: int = 0,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve pending notifications via ISG REST (Sync)."""
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

        params: dict[str, Any] = {
            "status": status_val,
            "limit": limit,
            "offset": offset,
        }
        if recipient:
            params["recipient"] = recipient
        if message_type:
            params["message_type"] = message_type

        headers = self.build_headers(auth_token)
        with self._sync_client(auth_token) as client:
            try:
                resp = client.get(
                    self.notifications_endpoint,
                    params=params,
                    headers=headers,
                )
                if resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=resp.text,
                    )
                if resp.status_code != status.HTTP_200_OK:
                    raise RuntimeError(
                        f"ISG REST list_notifications returned status "
                        f"{resp.status_code}"
                    )
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("notifications") or data.get("items", [])
                return []
            except httpx.HTTPError as exc:
                logger.error("ISG REST list_notifications failed: %s", exc)
                raise RuntimeError(f"ISG REST API error: {exc}") from exc

    def get_notification_sync(
        self,
        nid: int,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve single notification header via ISG REST (Sync)."""
        if nid <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Notification ID must be a positive integer",
            )

        url = f"{self.notifications_endpoint}/{nid}"
        headers = self.build_headers(auth_token)
        with self._sync_client(auth_token) as client:
            try:
                resp = client.get(url, headers=headers)
                if resp.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Workflow notification {nid} not found",
                    )
                if resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=resp.text,
                    )
                if resp.status_code != status.HTTP_200_OK:
                    raise RuntimeError(
                        f"ISG REST get_notification({nid}) returned status "
                        f"{resp.status_code}"
                    )
                data = resp.json()
                return data if isinstance(data, dict) else {}
            except httpx.HTTPError as exc:
                logger.error(
                    "ISG REST get_notification failed for NID %s: %s", nid, exc
                )
                raise RuntimeError(f"ISG REST API error: {exc}") from exc

    def get_notification_attributes_sync(
        self,
        nid: int,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve notification attributes via ISG REST (Sync)."""
        if nid <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Notification ID must be a positive integer",
            )

        url = f"{self.notifications_endpoint}/{nid}/attributes"
        headers = self.build_headers(auth_token)
        with self._sync_client(auth_token) as client:
            try:
                resp = client.get(url, headers=headers)
                if resp.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Workflow notification {nid} not found",
                    )
                if resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=resp.text,
                    )
                if resp.status_code != status.HTTP_200_OK:
                    raise RuntimeError(
                        f"ISG REST get_notification_attributes({nid}) "
                        f"returned status {resp.status_code}"
                    )
                data = resp.json()
                return data if isinstance(data, dict) else {}
            except httpx.HTTPError as exc:
                logger.error(
                    "ISG REST get_attributes failed for NID %s: %s", nid, exc
                )
                raise RuntimeError(f"ISG REST API error: {exc}") from exc

    def get_pending_notifications_sync(
        self,
        recipient: str | None = None,
        notification_type: str | None = None,
        max_amount: float | None = None,
        limit: int = 50,
        auth_token: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve pending notifications formatted for worklist (Sync)."""
        items = self.list_notifications_sync(
            recipient=recipient,
            message_type=notification_type,
            status_val="OPEN",
            limit=limit,
            auth_token=auth_token,
        )
        filtered = []
        for item in items:
            amount = item.get("amount")
            if max_amount is not None and amount is not None:
                try:
                    if float(amount) > max_amount:
                        continue
                except (ValueError, TypeError):
                    pass
            filtered.append(item)
        return filtered

    def get_endpoint_url(self) -> str:
        """Return the target ISG REST endpoint URL."""
        return self.endpoint
