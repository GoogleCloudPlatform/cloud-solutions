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

"""Unified A2A Proxy and Request Forwarder for Oracle EBS Workflow."""

import json
import logging
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, NoReturn

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from google.auth import exceptions as google_auth_exceptions
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.genai import types
from google.oauth2 import id_token
from pydantic import ValidationError
from src.a2a.ai_client import (
    GENAI_CALL_EXCEPTIONS,
    generate_content_with_models,
    get_ai_client,
)
from src.a2a.formatter import synthesize_response
from src.a2a.schemas import (
    ActionPlan,
    WorkflowActionRequest,
    WorkflowActionResponse,
    WorklistResponse,
)
from src.a2a.session_store import (
    SessionData,
    extract_session_id,
    get_session_store,
    is_confirmation_prompt,
)
from src.config import get_settings

logger = logging.getLogger("oracle_ebs_workflow.a2a.proxy")

router = APIRouter(tags=["A2A Proxy"])

GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "help",
    "start",
    "who are you",
    "what can you do",
    "capabilities",
    "menu",
}

_PROMPTS_DIR = Path(__file__).with_name("prompts")


@lru_cache
def _load_prompt_template(filename: str) -> str:
    """Load and cache externalized prompt or greeting template once."""
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


WORKFLOW_GREETING_TEXT = _load_prompt_template("workflow_greeting.txt")
DISPATCHER_PROMPT = _load_prompt_template("dispatcher_prompt.txt")

_SQL_GUARDRAIL_PATTERN = re.compile(
    r"(?:"
    r"\b(?:SELECT|DELETE|DROP|TRUNCATE|INSERT|ALTER|SQL|GRANT|REVOKE|"
    r"EXEC|EXECUTE)\b"
    r"|\bUPDATE\b[\s\S]{1,120}\b(?:SET|TABLE|WHERE|STATEMENT|QUERY)\b"
    r"|\bUNION\s+(?:ALL\s+)?SELECT\b"
    r"|(?:['\"]\s*(?:OR|AND)\s*['\"]?\d+['\"]?\s*=\s*['\"]?\d+)"
    r"|(?:\bOR\s+1\s*=\s*1\b)"
    r"|(?:;\s*--)"
    r"|(?:/\*[\s\S]*?\*/)"
    r")",
    re.IGNORECASE,
)

_GIBBERISH_TOKEN_PATTERN = re.compile(
    r"[bcdfghjklmnpqrstvwxz]{6,}", re.IGNORECASE
)

_WORKFLOW_INTENT_PATTERN = re.compile(
    r"\b(?:"
    r"workflow|workflows|notification|notifications|pending|worklist|queue|"
    r"triage|approve|approval|approvals|reject|rejection|inspect|detail|"
    r"details|verify|policy|policies|compliance|compliant|violation|"
    r"violations|risk|risks|expense|expenses|report|reports|apexp|po|pos|"
    r"purchase|poappr|poapprv|req|reqs|requisition|requisitions|reqappr|"
    r"invoice|invoices|contract|contracts|timecard|timecards|item|items|"
    r"confirm|confirmed|proceed|execute|yes|status|summary|list|show|check|"
    r"audit|review|action|actions|open|supplier|suppliers|vendor|vendors|"
    r"budget|receipt|receipts|inbox|task|tasks|request|requests|waiting|"
    r"assigned|recipient|role|manager|approver|amount|total|high|medium|"
    r"low|critical|flag|flagged|nid|help|capabilities|recommendation|"
    r"recommendations|recommended|option|options|step|steps|first|second|"
    r"third|next|\d{4,}"
    r")\b",
    re.IGNORECASE,
)


def sanitize_user_input(text: str) -> str:
    """Sanitize user input by removing control chars and HTML markup."""
    if not text:
        return ""
    no_ctrl = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    no_html = re.sub(r"<[^>]*>", "", no_ctrl)
    return " ".join(no_html.split())[:2000]


def is_guardrail_fallback_required(text: str) -> bool:
    """Check if input is SQL/injection, gibberish, or out-of-scope."""
    clean = text.strip()
    if not clean:
        return True
    if _SQL_GUARDRAIL_PATTERN.search(clean):
        return True
    if _GIBBERISH_TOKEN_PATTERN.search(clean):
        return True
    return not bool(_WORKFLOW_INTENT_PATTERN.search(clean))


def _resolve_recommendation_reference(
    prompt: str, recommendations: list[str]
) -> str:
    """Resolve ordinal recommendation references to stored recommendation."""
    lower_p = prompt.lower()
    if not re.search(
        r"\b(?:recommendation|recommendations|option|next\s+step)\b", lower_p
    ):
        return prompt
    idx: int | None = None
    if re.search(r"\b(?:first|1st|one|1)\b", lower_p):
        idx = 0
    elif re.search(r"\b(?:second|2nd|two|2)\b", lower_p):
        idx = 1
    elif re.search(r"\b(?:third|3rd|three|3)\b", lower_p):
        idx = 2
    if idx is not None:
        if idx < len(recommendations):
            return f"Verify policy and inspect: {recommendations[idx]}"
        default_recs = [
            "Verify receipt attachments for pending Expense Report(s)",
            "Confirm approved supplier for Purchase Order(s)",
            "Check quarterly budget caps for Requisition(s)",
        ]
        return f"Verify policy and inspect: {default_recs[idx]}"
    if recommendations:
        return f"Verify policy and inspect: {recommendations[0]}"
    return prompt


def is_greeting(text: str) -> bool:
    """Check if user prompt is a greeting or capability inquiry."""
    clean = text.lower().strip().strip("!.,?:;")
    if not clean:
        return True
    if clean in GREETING_WORDS:
        return True
    return any(clean.startswith(f"{w} ") for w in ("hi", "hello", "hey"))


def _extract_turn_text(item: dict[str, Any]) -> str:
    """Extract message string from a single turn item."""
    if "text" in item and isinstance(item["text"], str):
        return item["text"].strip()
    if "parts" in item and isinstance(item["parts"], list):
        parts_txt = [
            p.get("text", "") if isinstance(p, dict) else str(p)
            for p in item["parts"]
        ]
        return " ".join(t for t in parts_txt if t).strip()
    if "content" in item and isinstance(item["content"], str):
        return item["content"].strip()
    return ""


def _extract_conversation_turns(body: Any) -> list[str]:
    """Extract prior conversation turns from payload if provided."""
    if not isinstance(body, dict):
        return []

    raw = body.get("messages") or body.get("history") or body.get("turns")
    if not raw and isinstance(body.get("params"), dict):
        params = body["params"]
        raw = (
            params.get("messages")
            or params.get("history")
            or params.get("turns")
        )

    if not isinstance(raw, list):
        return []

    turns: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            role = str(item.get("role", "user")).capitalize()
            txt = _extract_turn_text(item)
            if txt:
                turns.append(f"{role}: {txt}")
    return turns


def _extract_user_prompt(body: Any) -> str:
    """Extract plain text from A2A payload or Gemini format."""
    if not body or not isinstance(body, dict):
        return ""

    for key in ("text", "prompt", "query", "input"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    val_msg = body.get("message")
    if isinstance(val_msg, str) and val_msg.strip():
        return val_msg.strip()

    if isinstance(val_msg, dict):
        parts = val_msg.get("parts")
        if isinstance(parts, list):
            texts: list[str] = []
            for p in parts:
                if (
                    isinstance(p, dict)
                    and "text" in p
                    and isinstance(p["text"], str)
                ):
                    texts.append(p["text"])
            if texts:
                return " ".join(texts).strip()
        for sub_k in ("text", "content"):
            sub_val = val_msg.get(sub_k)
            if isinstance(sub_val, str) and sub_val.strip():
                return sub_val.strip()

    if isinstance(body.get("params"), dict):
        return _extract_user_prompt(body["params"])

    return ""


def _extract_error_detail(resp: httpx.Response) -> str:
    """Safely extract error message string from response payload."""
    try:
        data = resp.json()
        if isinstance(data, dict):
            if "detail" in data:
                return str(data["detail"])
            if "message" in data:
                return str(data["message"])
            if "error" in data:
                return str(data["error"])
    except ValueError:
        logger.warning(
            "Upstream non-JSON error payload (status=%s): %s",
            resp.status_code,
            resp.text,
        )
    return f"Upstream workflow service returned HTTP {resp.status_code}."


def _raise_upstream_http_error(resp: httpx.Response, endpoint: str) -> NoReturn:
    """Log upstream error payload internally and raise generic HTTPException."""
    logger.warning(
        "Upstream workflow request to %s failed (status=%s): %s",
        endpoint,
        resp.status_code,
        resp.text,
    )
    raise HTTPException(
        status_code=resp.status_code,
        detail="Upstream workflow service request failed.",
    )


_SHARED_CLIENT: httpx.AsyncClient | None = None


def get_shared_client() -> httpx.AsyncClient:
    """Provide a shared httpx.AsyncClient for connection reuse."""
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None or _SHARED_CLIENT.is_closed:
        _SHARED_CLIENT = httpx.AsyncClient(timeout=60.0)
    return _SHARED_CLIENT


def get_id_token(target_url: str) -> str | None:
    """Fetch OIDC ID token for target Cloud Run service."""
    if "localhost" in target_url or "127.0.0.1" in target_url:
        return None
    try:
        auth_req = GoogleAuthRequest()
        token = id_token.fetch_id_token(auth_req, target_url)
        return token
    except (google_auth_exceptions.GoogleAuthError, OSError) as exc:
        logger.debug("OIDC token fetch skipped (local environment): %s", exc)
        return None


async def get_forward_headers(
    target_url: str | None = None,
) -> dict[str, str]:
    """Helper returning forwarding headers with optional OIDC injection."""
    headers = {"Content-Type": "application/json"}
    if target_url:
        is_local = "localhost" in target_url or "127.0.0.1" in target_url
        if not is_local:
            token = get_id_token(target_url)
            if token:
                headers["Authorization"] = f"Bearer {token}"
    return headers


def get_workflow_agent_url(req: Request | None = None) -> str:
    """Resolve worker URL, supporting Cloud Run hostname mappings."""
    settings = get_settings()
    if req:
        host = (
            req.headers.get("x-forwarded-host") or req.headers.get("host") or ""
        )
        if "a2a-workflow-server" in host:
            target_host = host.replace("a2a-workflow-server", "workflow-agent")
            return f"https://{target_host}"
    return settings.workflow_agent_url


async def forward_request(
    method: str,
    target_service_url: str,
    path: str,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
) -> httpx.Response:
    """Forward request to downstream Cloud Run with OIDC token injection."""
    client = get_shared_client()
    base_url = target_service_url.rstrip("/")
    rel_path = path.lstrip("/")
    url = f"{base_url}/{rel_path}"
    fwd_headers: dict[str, str] = {}

    oidc_token = get_id_token(target_service_url)
    if oidc_token:
        fwd_headers["Authorization"] = f"Bearer {oidc_token}"

    return await client.request(
        method=method,
        url=url,
        headers=fwd_headers,
        params=params,
        json=json_body,
    )


def _format_a2a_response(
    raw_res: Any,
    user_query: str = "",
    req_id: Any = 1,
    recipient: str | None = None,
    session: SessionData | None = None,
) -> dict[str, Any]:
    """Format response into standard A2A JSON-RPC 2.0 envelope."""
    if isinstance(raw_res, dict) and "jsonrpc" in raw_res:
        return raw_res

    has_workflow_data = isinstance(raw_res, dict) and any(
        k in raw_res
        for k in (
            "items",
            "notifications",
            "evaluations",
            "results",
            "processed_items",
            "failed_items",
            "header",
            "details",
        )
    )
    if (
        isinstance(raw_res, dict)
        and (raw_res.get("text") or raw_res.get("reply"))
        and not has_workflow_data
    ):
        formatted_text = str(raw_res.get("text") or raw_res.get("reply"))
    elif isinstance(raw_res, dict):
        formatted_text = synthesize_response(raw_res, user_query)
    else:
        formatted_text = str(raw_res)

    uid = str(uuid.uuid4())[:8]
    msg_id = f"msg-{uid}"
    ctx_id = (
        session.session_id
        if session and session.session_id != "default_session"
        else f"ctx-{uid}"
    )
    task_id = f"task-{uid}"
    if session is not None:
        store = get_session_store()
        store.bind_alias(ctx_id, session)
        store.bind_alias(task_id, session)

    result_obj = {
        "role": "agent",
        "parts": [{"text": formatted_text}],
        "message": {
            "role": "agent",
            "parts": [{"text": formatted_text}],
            "contextId": ctx_id,
        },
        "messageId": msg_id,
        "message_id": msg_id,
        "contextId": ctx_id,
        "context_id": ctx_id,
        "id": task_id,
        "status": {"state": "completed"},
        "text": formatted_text,
        "content": formatted_text,
        "data": (
            raw_res if isinstance(raw_res, dict) else {"content": str(raw_res)}
        ),
    }

    return {
        "jsonrpc": "2.0",
        "id": req_id if req_id is not None else 1,
        "result": result_obj,
        "status": (
            raw_res.get("status", "SUCCESS")
            if isinstance(raw_res, dict)
            else "SUCCESS"
        ),
        "text": formatted_text,
        "content": formatted_text,
        "message": formatted_text,
        "reply": formatted_text,
        "recipient": recipient or "OPERATIONS",
        "raw_data": raw_res if isinstance(raw_res, dict) else {},
    }


async def _handle_notifications_action(
    target_url: str, plan: ActionPlan
) -> dict[str, Any]:
    """Execute worklist notifications query."""
    params: dict[str, Any] = {"limit": plan.limit or 50}
    if plan.recipient:
        params["recipient"] = plan.recipient
        path = "/worklist/pending"
    else:
        path = "/notifications"

    if plan.notification_type:
        params["notification_type"] = plan.notification_type
        params["message_type"] = plan.notification_type
    if plan.max_amount is not None:
        params["max_amount"] = plan.max_amount

    resp = await forward_request(
        method="GET",
        target_service_url=target_url,
        path=path,
        params=params,
    )
    if resp.status_code == 200:
        return resp.json()
    err_detail = _extract_error_detail(resp)
    return {
        "status": "ERROR",
        "detail": err_detail,
        "recipient": plan.recipient,
        "items": [],
    }


async def _resolve_target_nids(
    target_url: str, plan: ActionPlan, default_limit: int = 25
) -> list[int]:
    """Resolve target notification IDs from plan or matching items."""
    nids = list(
        plan.notification_ids
        or ([plan.notification_id] if plan.notification_id else [])
    )
    desired_count = plan.limit or 1
    if not nids or (plan.notification_type and len(nids) < desired_count):
        list_plan = plan.model_copy(
            update={"limit": plan.limit or default_limit}
        )
        worklist_data = await _handle_notifications_action(
            target_url, list_plan
        )
        items = (
            worklist_data.get("items")
            or worklist_data.get("notifications")
            or []
        )
        fetched_nids = [
            int(item["notification_id"])
            for item in items
            if isinstance(item, dict) and "notification_id" in item
        ]
        if fetched_nids:
            nids = fetched_nids
    return nids


async def _handle_inspect_action(
    target_url: str, plan: ActionPlan
) -> dict[str, Any]:
    """Execute single or multi-notification inspection."""
    nids = await _resolve_target_nids(target_url, plan, default_limit=10)
    if not nids:
        return {
            "status": "ERROR",
            "detail": (
                "Please specify a notification ID to inspect "
                "(e.g. 'Inspect notification 7857291')."
            ),
        }
    if len(nids) == 1:
        nid = nids[0]
        resp = await forward_request(
            method="GET",
            target_service_url=target_url,
            path=f"/notifications/{nid}",
        )
        if resp.status_code == 200:
            return resp.json()
        err_detail = _extract_error_detail(resp)
        return {
            "status": "ERROR",
            "detail": (
                err_detail or f"Notification {nid} not found in Oracle EBS."
            ),
            "notification_id": nid,
        }

    details: list[dict[str, Any]] = []
    for nid in nids[:10]:
        resp = await forward_request(
            method="GET",
            target_service_url=target_url,
            path=f"/notifications/{nid}",
        )
        if resp.status_code == 200:
            details.append(resp.json())
    if details:
        return {"status": "SUCCESS", "details": details}
    return {
        "status": "ERROR",
        "detail": f"Notifications {nids} not found in Oracle EBS.",
    }


async def _handle_verify_action(
    target_url: str, plan: ActionPlan
) -> dict[str, Any]:
    """Execute policy verification."""
    nids = await _resolve_target_nids(target_url, plan, default_limit=25)
    if not nids:
        return {"status": "SUCCESS", "items": []}

    payload: dict[str, Any] = {"notification_ids": nids}
    if plan.recipient:
        payload["recipient"] = plan.recipient

    resp = await forward_request(
        method="POST",
        target_service_url=target_url,
        path="/verify-policy",
        json_body=payload,
    )
    if resp.status_code == 200:
        result_data: dict[str, Any] = resp.json()
        if len(nids) <= 5:
            details: list[dict[str, Any]] = []
            for nid in nids:
                det_resp = await forward_request(
                    method="GET",
                    target_service_url=target_url,
                    path=f"/notifications/{nid}",
                )
                if det_resp.status_code == 200:
                    details.append(det_resp.json())
            if details:
                result_data["details"] = details
        return result_data
    err_detail = _extract_error_detail(resp)
    return {
        "status": "ERROR",
        "detail": (
            err_detail
            or f"Policy verification failed for notification(s) {nids}."
        ),
        "notification_ids": nids,
    }


async def _handle_triage_action(
    target_url: str, plan: ActionPlan
) -> dict[str, Any]:
    """Execute triage summary analysis."""
    params: dict[str, Any] = {"limit": plan.limit or 50}
    if plan.recipient:
        params["recipient"] = plan.recipient
    if plan.notification_type:
        params["message_type"] = plan.notification_type

    resp = await forward_request(
        method="GET",
        target_service_url=target_url,
        path="/triage",
        params=params,
    )
    if resp.status_code == 200:
        data = resp.json()
        if plan.recipient:
            data["recipient"] = plan.recipient
        return data
    err_detail = _extract_error_detail(resp)
    return {
        "status": "ERROR",
        "detail": err_detail,
        "recipient": plan.recipient,
        "items": [],
    }


async def _handle_respond_action(
    target_url: str,
    action: str,
    plan: ActionPlan,
) -> dict[str, Any]:
    """Execute approve or reject workflow response."""
    nids = plan.notification_ids or (
        [plan.notification_id] if plan.notification_id else []
    )
    if not nids:
        return {
            "status": "ERROR",
            "detail": (
                f"Please specify notification ID(s) to {action} "
                f"(e.g. '{action.capitalize()} notification 7857291')."
            ),
        }
    act_upper = "APPROVE" if action == "approve" else "REJECT"
    resp = await forward_request(
        method="POST",
        target_service_url=target_url,
        path="/worklist/respond",
        json_body={
            "notification_ids": nids,
            "action": act_upper,
            "comments": (
                plan.comments
                or f"{act_upper} via Oracle EBS Workflow AI Assistant"
            ),
            "responder": plan.recipient or "OPERATIONS",
            "confirmed": bool(plan.confirmed),
        },
    )
    if resp.status_code == 200:
        return resp.json()
    err_detail = _extract_error_detail(resp)
    err_msg = (
        err_detail or f"Failed to execute {action} for notifications {nids}."
    )
    return {
        "status": "ERROR",
        "detail": err_msg,
    }


async def _execute_workflow_action(
    plan: ActionPlan,
    req: Request,
) -> dict[str, Any]:
    """Route ActionPlan to downstream workflow agent microservice."""
    target_url = get_workflow_agent_url(req)
    action = plan.action.lower()

    if action in ("help", "greeting"):
        return {
            "status": "SUCCESS",
            "text": WORKFLOW_GREETING_TEXT,
            "reply": WORKFLOW_GREETING_TEXT,
        }

    handler_map = {
        "notifications": _handle_notifications_action,
        "pending": _handle_notifications_action,
        "list": _handle_notifications_action,
        "inspect": _handle_inspect_action,
        "verify_policy": _handle_verify_action,
        "policy": _handle_verify_action,
        "verify": _handle_verify_action,
        "triage": _handle_triage_action,
    }

    if action in handler_map:
        return await handler_map[action](target_url, plan)

    if action in ("approve", "reject"):
        return await _handle_respond_action(target_url, action, plan)

    return {
        "status": "SUCCESS",
        "text": WORKFLOW_GREETING_TEXT,
        "reply": WORKFLOW_GREETING_TEXT,
    }


def _extract_closed_or_completed_nids(raw_res: dict[str, Any]) -> list[int]:
    """Extract notification IDs that were completed or already closed."""
    closed_nids: list[int] = []
    for item in raw_res.get("processed_items", []):
        if isinstance(item, dict) and item.get("notification_id"):
            closed_nids.append(int(item["notification_id"]))
    for item in raw_res.get("failed_items", []):
        if isinstance(item, dict) and item.get("notification_id"):
            msg = str(item.get("message") or item.get("error") or "").lower()
            if "already " in msg or "no longer open" in msg:
                closed_nids.append(int(item["notification_id"]))
    for item in raw_res.get("results", []):
        if isinstance(item, dict) and item.get("notification_id"):
            st = str(item.get("status", "")).upper()
            msg = str(item.get("message") or item.get("error") or "").lower()
            if st == "SUCCESS" or "already " in msg or "no longer open" in msg:
                closed_nids.append(int(item["notification_id"]))
    return closed_nids


def _update_session_from_result(
    session: Any, raw_res: dict[str, Any], plan: ActionPlan
) -> None:
    """Synchronize session state from workflow execution response."""
    if raw_res.get("status") == "CONFIRMATION_REQUIRED":
        raw_prop = raw_res.get("proposal", raw_res)
        prop_data = dict(raw_prop) if isinstance(raw_prop, dict) else {}
        if not prop_data.get("comments") and plan.comments:
            prop_data["comments"] = plan.comments
        session.set_pending_proposal(prop_data)
    elif raw_res.get("status") in ("COMPLETED", "SUCCESS"):
        closed_nids = _extract_closed_or_completed_nids(raw_res)
        session.clear_pending_proposal()
        session.remove_completed_notifications(closed_nids)
        if closed_nids or raw_res.get("status") == "COMPLETED":
            get_session_store().sync_completed_notifications(closed_nids)

    items = raw_res.get("items") or raw_res.get("notifications") or []
    if isinstance(items, list) and items:
        nids = [
            int(it["notification_id"])
            for it in items
            if isinstance(it, dict) and "notification_id" in it
        ]
        actionable_types = {
            "APEXP",
            "POAPPR",
            "POAPPRV",
            "REQAPPR",
            "OKCAUKAP",
            "APINV",
        }
        actionable_low_risk = [
            int(it["notification_id"])
            for it in items
            if isinstance(it, dict)
            and "notification_id" in it
            and str(it.get("message_type", "")).upper() in actionable_types
            and it.get("risk_level", "LOW") == "LOW"
        ]
        all_low_risk = [
            int(it["notification_id"])
            for it in items
            if isinstance(it, dict)
            and "notification_id" in it
            and it.get("risk_level", "LOW") == "LOW"
        ]
        low_risk = (actionable_low_risk or all_low_risk)[:10]
        by_type_map: dict[str, list[int]] = {}
        for it in items:
            if (
                isinstance(it, dict)
                and "notification_id" in it
                and it.get("message_type")
            ):
                m_type = str(it["message_type"]).upper()
                item_nid = int(it["notification_id"])
                by_type_map.setdefault(m_type, []).append(item_nid)
                if m_type == "POAPPRV":
                    by_type_map.setdefault("POAPPR", []).append(item_nid)
                elif m_type == "REQAPPRV":
                    by_type_map.setdefault("REQAPPR", []).append(item_nid)
        raw_recs = raw_res.get("proactive_next_steps")
        recs_list = (
            [str(r) for r in raw_recs if r]
            if isinstance(raw_recs, list)
            else None
        )
        if nids:
            session.set_triage_items(
                nids,
                low_risk_ids=low_risk,
                items_by_type=by_type_map,
                recommendations=recs_list,
            )

    details_out = raw_res.get("details")
    if isinstance(details_out, list) and details_out:
        det_nids = [
            int(d["header"]["notification_id"])
            for d in details_out
            if isinstance(d, dict)
            and isinstance(d.get("header"), dict)
            and "notification_id" in d["header"]
            and str(d["header"].get("status", "OPEN")).upper() == "OPEN"
        ]
        if det_nids:
            session.last_notification_ids = det_nids
            session.last_low_risk_ids = det_nids

    hdr = raw_res.get("header")
    if isinstance(hdr, dict) and ("notification_id" in hdr or "nid" in hdr):
        nid_val = hdr.get("notification_id") or hdr.get("nid")
        if nid_val:
            if str(hdr.get("status", "OPEN")).upper() == "OPEN":
                session.last_notification_ids = [int(nid_val)]
            else:
                session.remove_completed_notifications([int(nid_val)])


async def _parse_request_body(req: Request) -> dict[str, Any]:
    """Extract a JSON dictionary payload from POST/PUT/PATCH requests."""
    if req.method not in ("POST", "PUT", "PATCH"):
        return {}
    try:
        parsed = await req.json()
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass
    return {}


async def _try_handle_confirmation_shortcut(
    prompt: str,
    req: Request,
    session: SessionData,
    req_id: Any,
    recipient: str | None,
) -> dict[str, Any] | None:
    """Execute staged proposals or triaged items when user confirms."""
    if not is_confirmation_prompt(prompt):
        return None

    store = get_session_store()
    plan: ActionPlan | None = None
    prop = (
        session.clear_pending_proposal() or store.get_latest_pending_proposal()
    )
    if prop:
        raw_act = str(prop.get("action") or "approve").strip().lower()
        act_name = "reject" if raw_act == "reject" else "approve"
        plan = ActionPlan(
            action=act_name,
            notification_ids=prop.get("notification_ids", []),
            confirmed=True,
            comments=prop.get("comments") or "Confirmed via AI Assistant",
            recipient=recipient,
        )
    else:
        active = (
            session
            if (session.last_low_risk_ids or session.last_notification_ids)
            else (store.get_latest_active_session() or session)
        )
        target_nids = active.last_low_risk_ids or active.last_notification_ids
        if target_nids:
            plan = ActionPlan(
                action="approve",
                notification_ids=target_nids,
                confirmed=True,
                comments="Bulk approval confirmed via AI Assistant",
                recipient=recipient,
            )

    if plan is None:
        return None

    raw_res = await _execute_workflow_action(plan, req)
    _update_session_from_result(session, raw_res, plan)
    session.add_turn("user", prompt)
    res_obj = _format_a2a_response(
        raw_res,
        user_query=prompt,
        req_id=req_id,
        recipient=recipient,
        session=session,
    )
    session.add_turn("agent", res_obj.get("text", ""))
    return res_obj


def _classify_intent_plan(
    prompt: str,
    body: dict[str, Any],
    session: SessionData,
    recipient: str | None,
) -> ActionPlan:
    """Classify user intent into a structured ActionPlan using Gemini."""
    plan = ActionPlan(action="notifications", recipient=recipient)
    ai_client = get_ai_client()
    if not (ai_client and prompt):
        return plan

    try:
        config = types.GenerateContentConfig(
            system_instruction=DISPATCHER_PROMPT,
            response_mime_type="application/json",
            response_schema=ActionPlan,
            temperature=0.0,
            max_output_tokens=2048,
        )
        active = (
            session
            if session.has_context()
            else (get_session_store().get_latest_active_session() or session)
        )
        dialogue_turns = active.get_formatted_turns(max_turns=6)
        body_turns = _extract_conversation_turns(body)
        all_turns = dialogue_turns or body_turns
        history_prefix = (
            "Conversation History:\n" + "\n".join(all_turns) + "\n\n"
            if all_turns
            else ""
        )
        if active.pending_proposal:
            prop_act = active.pending_proposal.get("action", "APPROVE")
            prop_nids = active.pending_proposal.get("notification_ids", [])
            history_prefix += (
                f"Staged Confirmation Proposal: action={prop_act}, "
                f"notification_ids={prop_nids}\n\n"
            )
        dispatch_input = (
            f"{history_prefix}Latest User Query: {prompt}\n"
            f"Context: {json.dumps(body)}"
        )
        resp = generate_content_with_models(
            ai_client,
            dispatch_input,
            config,
            fast_tier=True,
        )
        if resp and getattr(resp, "text", None):
            plan = ActionPlan.model_validate_json(resp.text)
    except (
        *GENAI_CALL_EXCEPTIONS,
        ValidationError,
        RuntimeError,
    ) as exc:
        logger.warning("Gemini intent dispatch failed: %s", exc)
    return plan


def _hydrate_plan_from_session(
    plan: ActionPlan,
    prompt: str,
    body: dict[str, Any],
    session: SessionData,
) -> None:
    """Hydrate missing notification IDs and flags from session context."""
    active = (
        session
        if session.has_context()
        else (get_session_store().get_latest_active_session() or session)
    )
    is_explicit_confirm = bool(
        re.search(
            r"\b(?:confirm|confirmed|yes|proceed|execute)\b",
            prompt,
            re.IGNORECASE,
        )
    ) or bool(isinstance(body, dict) and body.get("confirmed") is True)

    if plan.action == "help" and is_explicit_confirm:
        if active.pending_proposal:
            raw_act = (
                str(active.pending_proposal.get("action") or "approve")
                .strip()
                .lower()
            )
            plan.action = "reject" if raw_act == "reject" else "approve"
        elif active.last_low_risk_ids or active.last_notification_ids:
            plan.action = "approve"

    if plan.action in ("inspect", "verify_policy", "policy", "verify"):
        if not plan.notification_type:
            lower_p = prompt.lower()
            if "expense" in lower_p or "apexp" in lower_p:
                plan.notification_type = "APEXP"
            elif "purchase order" in lower_p or "poappr" in lower_p:
                plan.notification_type = "POAPPR"
            elif "requisition" in lower_p or "reqappr" in lower_p:
                plan.notification_type = "REQAPPR"
        count_match = re.search(
            r"\b(\d{1,2})\s+(?:pending\s+)?(?:expense|purchase|po\b|"
            r"requisition|req\b|item|notification|high[- ]risk)",
            prompt.lower(),
        )
        if count_match:
            plan.limit = int(count_match.group(1))
        if plan.notification_type:
            type_key = plan.notification_type.upper()
            session_type_nids = active.last_items_by_type.get(type_key, [])
            current_nids = plan.notification_ids or (
                [plan.notification_id] if plan.notification_id else []
            )
            if session_type_nids and len(current_nids) <= 1:
                max_items = plan.limit or len(session_type_nids)
                plan.notification_ids = session_type_nids[:max_items]

    if plan.action in ("approve", "reject"):
        plan.confirmed = is_explicit_confirm
        if not plan.notification_ids:
            if plan.notification_id:
                plan.notification_ids = [plan.notification_id]
            elif (
                plan.notification_type
                and plan.notification_type.upper() in active.last_items_by_type
            ):
                plan.notification_ids = active.last_items_by_type[
                    plan.notification_type.upper()
                ]
            elif active.pending_proposal:
                plan.notification_ids = active.pending_proposal.get(
                    "notification_ids", []
                )
            elif active.last_low_risk_ids:
                plan.notification_ids = active.last_low_risk_ids
            elif active.last_notification_ids:
                plan.notification_ids = active.last_notification_ids


@router.post("/", operation_id="dispatch_a2a_message_root")
@router.post("/chat", operation_id="dispatch_a2a_message_chat")
@router.api_route("/", methods=["GET", "PUT"], include_in_schema=False)
@router.api_route(
    "/message", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/messages", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/task", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/tasks", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/tasks/send", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/v1/tasks", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/v1/message", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/v1/messages", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/a2a/v1/message", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/a2a/v1/messages", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/a2a/v1/tasks", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/rpc", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.api_route(
    "/jsonrpc", methods=["GET", "POST", "PUT"], include_in_schema=False
)
@router.get("/chat", include_in_schema=False)
async def dispatch_a2a_message(req: Request) -> dict[str, Any]:
    """Unified A2A Message Dispatcher for Gemini Enterprise and A2A."""
    if req.method == "OPTIONS":
        return {"status": "ok"}

    body = await _parse_request_body(req)
    req_id = body.get("id", 1)
    prompt = sanitize_user_input(_extract_user_prompt(body))
    recipient = ActionPlan.sanitize_recipient(
        body.get("recipient", body.get("user_id"))
    )

    session_store = get_session_store()
    session_id = extract_session_id(body, req.headers)
    session = session_store.get_or_create(session_id)

    if is_greeting(prompt):
        return _format_a2a_response(
            {
                "status": "SUCCESS",
                "text": WORKFLOW_GREETING_TEXT,
                "reply": WORKFLOW_GREETING_TEXT,
            },
            user_query="",
            req_id=req_id,
            recipient=recipient,
        )

    shortcut_res = await _try_handle_confirmation_shortcut(
        prompt, req, session, req_id, recipient
    )
    if shortcut_res is not None:
        return shortcut_res

    if is_guardrail_fallback_required(prompt):
        return _format_a2a_response(
            {
                "status": "SUCCESS",
                "text": WORKFLOW_GREETING_TEXT,
                "reply": WORKFLOW_GREETING_TEXT,
            },
            user_query="",
            req_id=req_id,
            recipient=recipient,
        )

    session.add_turn("user", prompt)
    prompt = _resolve_recommendation_reference(
        prompt, session.last_recommendations
    )
    plan = _classify_intent_plan(prompt, body, session, recipient)
    _hydrate_plan_from_session(plan, prompt, body, session)

    raw_res = await _execute_workflow_action(plan, req)
    _update_session_from_result(session, raw_res, plan)

    res_dict = _format_a2a_response(
        raw_res,
        user_query=prompt,
        req_id=req_id,
        recipient=recipient,
        session=session,
    )
    session.add_turn("agent", res_dict.get("text", ""))
    return res_dict


@router.get("/worklist/pending", summary="Forwarder: Retrieve Pending Worklist")
async def proxy_get_pending_worklist(
    req: Request,
    recipient: str = Query(..., description="Recipient username or role"),
    notification_type: str | None = Query(
        None, description="APEXP, POAPPR, REQAPPR"
    ),
    max_amount: float | None = Query(None, description="Max amount filter"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
) -> WorklistResponse:
    """Forward worklist query with OIDC authentication."""
    target_url = get_workflow_agent_url(req)
    params: dict[str, Any] = {
        "recipient": recipient,
        "limit": limit,
    }
    if notification_type:
        params["notification_type"] = notification_type
    if max_amount is not None:
        params["max_amount"] = max_amount

    resp = await forward_request(
        method="GET",
        target_service_url=target_url,
        path="/worklist/pending",
        params=params,
    )
    if resp.status_code == 200:
        return WorklistResponse.model_validate(resp.json())
    _raise_upstream_http_error(resp, "/worklist/pending")


@router.post("/worklist/respond", summary="Forwarder: Execute Workflow Action")
async def proxy_respond_workflow(
    req: Request,
    request: WorkflowActionRequest,
) -> WorkflowActionResponse:
    """Forward action execution with OIDC authentication."""
    target_url = get_workflow_agent_url(req)
    resp = await forward_request(
        method="POST",
        target_service_url=target_url,
        path="/worklist/respond",
        json_body=request.model_dump(),
    )
    if resp.status_code == 200:
        return WorkflowActionResponse.model_validate(resp.json())
    _raise_upstream_http_error(resp, "/worklist/respond")


@router.get(
    "/notifications",
    summary="Forwarder: List Notifications (Fallback)",
)
async def proxy_list_notifications(
    req: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    """Forward list notifications query."""
    target_url = get_workflow_agent_url(req)
    resp = await forward_request(
        method="GET",
        target_service_url=target_url,
        path="/notifications",
        params={"limit": limit, "offset": offset},
    )
    if resp.status_code == 200:
        data = resp.json()
        return data if isinstance(data, list) else []
    _raise_upstream_http_error(resp, "/notifications")


@router.get(
    "/notifications/{notification_id}",
    summary="Forwarder: Inspect Notification",
)
async def proxy_get_notification(
    req: Request,
    notification_id: int,
) -> dict[str, Any]:
    """Forward single notification inspection."""
    if notification_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Notification ID must be a positive integer",
        )
    target_url = get_workflow_agent_url(req)
    resp = await forward_request(
        method="GET",
        target_service_url=target_url,
        path=f"/notifications/{notification_id}",
    )
    if resp.status_code == 200:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    _raise_upstream_http_error(resp, f"/notifications/{notification_id}")


@router.post(
    "/verify-policy",
    summary="Forwarder: Verify Corporate Policy Compliance",
)
async def proxy_verify_policy(
    req: Request,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Forward policy verification batch."""
    target_url = get_workflow_agent_url(req)
    resp = await forward_request(
        method="POST",
        target_service_url=target_url,
        path="/verify-policy",
        json_body=body,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    _raise_upstream_http_error(resp, "/verify-policy")


@router.get(
    "/triage",
    summary="Forwarder: Triage Worklist Notifications",
)
async def proxy_triage_worklist(
    req: Request,
    recipient: str | None = Query(None),
    message_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Forward triage summary request."""
    target_url = get_workflow_agent_url(req)
    params: dict[str, Any] = {"limit": limit}
    if recipient:
        params["recipient"] = recipient
    if message_type:
        params["message_type"] = message_type
    resp = await forward_request(
        method="GET",
        target_service_url=target_url,
        path="/triage",
        params=params,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    _raise_upstream_http_error(resp, "/triage")


@router.post(
    "/execute",
    summary="Forwarder: Certified Workflow Execution",
)
async def proxy_execute_action(
    req: Request,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Forward certified workflow action execution."""
    target_url = get_workflow_agent_url(req)
    resp = await forward_request(
        method="POST",
        target_service_url=target_url,
        path="/execute",
        json_body=body,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    _raise_upstream_http_error(resp, "/execute")
