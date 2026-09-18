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

"""A2A Reverse Proxy & Cognitive Dispatcher module."""

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, status
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError, field_validator
from src.a2a.ai_client import (
    get_ai_client,
    get_candidate_models,
)
from src.a2a.schemas import (
    SAFE_EXCEPTIONS,
    DSOCalculationRequest,
    InvoiceListRequest,
    InvoiceStatusRequest,
    ItemListRequest,
    ItemSuppliersRequest,
    NegotiationRequest,
    OrganizationListRequest,
    StockCheckRequest,
    SupplierItemsRequest,
    SupplierListRequest,
)

logger = logging.getLogger(__name__)

proxy_router = APIRouter()

EXPECTED_API_KEY = os.environ.get("EBS_API_KEY", "")
_OIDC_TOKEN_CACHE: Dict[str, str] = {}
_METADATA_STATE: Dict[str, float] = {"unavailable_until": 0.0}
_CLIENT_CACHE: Dict[str, Optional[httpx.AsyncClient]] = {"client": None}


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> bool:
    """Verify API Key header when EBS_API_KEY environment variable is set."""
    if not EXPECTED_API_KEY:
        return True

    provided_key = x_api_key
    if not provided_key and authorization:
        if authorization.startswith("Bearer "):
            provided_key = authorization.split("Bearer ", 1)[1]
        else:
            provided_key = authorization
    if provided_key != EXPECTED_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key header (X-API-Key)",
        )
    return True


async def _get_forward_headers(target_url: str) -> Dict[str, str]:
    """Construct headers for proxying requests to internal worker services."""
    headers = {"Content-Type": "application/json"}
    if (
        not target_url.startswith("https://")
        or "127.0.0.1" in target_url
        or "localhost" in target_url
    ):
        return headers

    if target_url in _OIDC_TOKEN_CACHE:
        headers["Authorization"] = f"Bearer {_OIDC_TOKEN_CACHE[target_url]}"
        return headers

    now = time.time()
    if now < _METADATA_STATE["unavailable_until"]:
        return headers

    try:
        client = _get_shared_async_client()
        meta_res = await client.get(
            "http://metadata.google.internal/computeMetadata/v1/"
            "instance/service-accounts/default/identity",
            params={"audience": target_url},
            headers={"Metadata-Flavor": "Google"},
        )
        if meta_res.status_code == 200:
            token = meta_res.text.strip()
            _OIDC_TOKEN_CACHE[target_url] = token
            headers["Authorization"] = f"Bearer {token}"
        else:
            _METADATA_STATE["unavailable_until"] = now + 60.0
    except (httpx.HTTPError, OSError):
        _METADATA_STATE["unavailable_until"] = now + 60.0
    return headers


def _get_inventory_agent_url(req: Optional[Request] = None) -> str:
    env_url = os.environ.get("INVENTORY_AGENT_URL", "")
    if env_url:
        return env_url
    if req:
        host = (
            req.headers.get("x-forwarded-host")
            or req.headers.get("host")
            or str(req.url.hostname or "")
        )
        if "a2a-server" in host:
            target_host = host.replace("a2a-server", "inventory-agent")
            return f"https://{target_host}"
    return "http://127.0.0.1:8001"


def _get_financial_agent_url(req: Optional[Request] = None) -> str:
    env_url = os.environ.get("FINANCIAL_AGENT_URL", "")
    if env_url:
        return env_url
    if req:
        host = (
            req.headers.get("x-forwarded-host")
            or req.headers.get("host")
            or str(req.url.hostname or "")
        )
        if "a2a-server" in host:
            target_host = host.replace("a2a-server", "financial-agent")
            return f"https://{target_host}"
    return "http://127.0.0.1:8002"


def _get_supplier_agent_url(req: Optional[Request] = None) -> str:
    env_url = os.environ.get("SUPPLIER_AGENT_URL", "")
    if env_url:
        return env_url
    if req:
        host = (
            req.headers.get("x-forwarded-host")
            or req.headers.get("host")
            or str(req.url.hostname or "")
        )
        if "a2a-server" in host:
            target_host = host.replace("a2a-server", "supplier-agent")
            return f"https://{target_host}"
    return "http://127.0.0.1:8003"


def _get_shared_async_client() -> httpx.AsyncClient:
    client = _CLIENT_CACHE.get("client")
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=120.0,
            limits=httpx.Limits(
                max_keepalive_connections=20, max_connections=50
            ),
        )
        _CLIENT_CACHE["client"] = client
    return client


async def _forward_request(
    target_url: str, path: str, payload: dict, req: Request
) -> Dict[str, Any]:
    """Unified HTTP forwarder with Google Cloud OIDC header injection."""
    verify_api_key(
        req.headers.get("x-api-key"), req.headers.get("authorization")
    )
    target_endpoint = f'{target_url.rstrip("/")}/{path.lstrip("/")}'
    headers = await _get_forward_headers(target_url)
    try:
        client = _get_shared_async_client()
        res = await client.post(target_endpoint, json=payload, headers=headers)
        if res.status_code != 200:
            err_text = res.text or f"Worker HTTP {res.status_code}"
            return {
                "status": "ERROR",
                "error": err_text,
                "detail": err_text,
                "text": f"Worker service returned error: {err_text}",
                "content": f"Worker service returned error: {err_text}",
                "message": f"Worker service returned error: {err_text}",
            }
        res_json = res.json()
        if isinstance(res_json, dict):
            return res_json
        return {"status": "SUCCESS", "data": res_json}
    except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
        err_msg = f"Failed to reach worker service at {target_endpoint}: {exc}"
        logger.warning(err_msg)
        return {
            "status": "ERROR",
            "error": err_msg,
            "detail": err_msg,
            "text": err_msg,
            "content": err_msg,
            "message": err_msg,
        }


def _extract_user_prompt(body: Any) -> str:
    """Extract plain text string from A2A conversational payload."""
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
            texts = []
            for p in parts:
                if (
                    isinstance(p, dict)
                    and "text" in p
                    and isinstance(p["text"], str)
                ):
                    texts.append(p["text"])
                elif isinstance(p, str):
                    texts.append(p)
            if texts:
                return " ".join(texts).strip()

    if "params" in body and isinstance(body["params"], dict):
        extracted = _extract_user_prompt(body["params"])
        if extracted:
            return extracted

    return ""


class ActionPlan(BaseModel):
    """Cognitive action plan generated by Gemini Dispatcher."""

    action: str = Field(
        description=(
            "check_stock | invoice_status | calculate_dso | negotiate |"
            " organizations | items | suppliers | item_suppliers |"
            " supplier_items | recent_invoices | help"
        )
    )
    item_code: Optional[str] = Field(
        default=None, description="Item code or ID (e.g. AS54888)"
    )
    organization_id: Optional[int] = Field(
        default=None, description="Organization ID (e.g. 204)"
    )
    organization_code: Optional[str] = Field(
        default=None, description="Organization Code (e.g. V1, AD1)"
    )
    invoice_num: Optional[str] = Field(
        default=None, description="Invoice number (e.g. INV-2024-001)"
    )
    supplier_id: Optional[int] = Field(
        default=None, description="Oracle Supplier or Vendor ID (e.g. 515)"
    )
    supplier_name: Optional[str] = Field(
        default=None, description="Supplier or Vendor Name"
    )
    quantity: Optional[int] = Field(
        default=100, description="Quantity for negotiation or restock"
    )
    target_unit_price: Optional[float] = Field(
        default=None, description="Target unit price for negotiation"
    )
    period_days: Optional[int] = Field(
        default=90, description="Historical period in days for DSO"
    )
    total_accounts_receivable: Optional[float] = Field(
        default=None, description="Total outstanding AR balance if provided"
    )
    total_credit_sales: Optional[float] = Field(
        default=None, description="Total credit sales if provided"
    )
    limit: Optional[int] = Field(
        default=50,
        description="Max record limit for catalog or list lookups (1-100)",
    )

    @field_validator("limit", mode="before")
    @classmethod
    def clamp_limit(cls, v: Any) -> int:
        """Clamp limit between 1 and 100 to prevent validation errors."""
        if v is None:
            return 50
        try:
            val = int(v)
            return max(1, min(val, 100))
        except (ValueError, TypeError):
            return 50


DISPATCHER_PROMPT = """You are the Oracle EBS Query Dispatcher.
Analyze the user's natural language request and select the single best action
and parameters:
- check_stock: When checking on-hand inventory balances for an item.
- item_suppliers: When asking which suppliers/vendors supply a specific item.
- supplier_items: When asking which items are supplied by a specific supplier
  or vendor ID/name (e.g. 'Give me the items for supplier 515').
- organizations: When listing or exploring warehouse organizations.
- items: When listing items in an inventory catalog (extract organization_id or
  organization_code).
- suppliers: When listing approved general vendors/suppliers.
- recent_invoices: When listing recent AP invoices or viewing invoice overview.
- invoice_status: When querying a specific AP invoice status or number.
- calculate_dso: When calculating Days Sales Outstanding or receivables (extract
  period_days, and optional total_accounts_receivable or total_credit_sales if provided).
- negotiate: When requesting restock quotes or negotiating purchase prices.
- help: When asking for general capabilities or greetings.
"""


SYSTEM_INSTRUCTION = (
    "You are the Oracle EBS Autonomous Assistant Response Synthesizer.\n"
    "Your job is to transform raw JSON data returned from Oracle E-Business "
    "Suite database and worker microservices into direct, executive-grade "
    "Markdown responses.\n\n"
    "Guidelines:\n"
    "1. FULL RECORD TABLE RENDERING (CRITICAL):\n"
    "   When the raw data contains an array of records (such as "
    "organizations, items, suppliers, or invoices) or when the user asks "
    "for a table or list, you MUST render the FULL Markdown table displaying "
    "EVERY record with its individual columns (e.g. Organization ID, "
    "Organization Code, Organization Name).\n"
    "   NEVER replace, omit, or collapse the records into a high-level count "
    "summary table (e.g., do NOT just show 'Total Organizations: 50'). "
    "Display the actual row-by-row data.\n"
    "   RECORD COUNT & QUERY LIMIT NOTIFICATION:\n"
    "   State clearly how many records are being displayed (e.g. 'Showing 50 "
    "records...', 'Showing 42 organizations...').\n"
    "   If the user asked for more records than the system query limit (e.g. "
    "asking for 300 records when the maximum limit is 100), explicitly "
    "inform the user that only 100 records are being shown due to the limit.\n"
    "2. For single entity checks (stock verification, single invoice status, "
    "or DSO calculation), display key metrics in bullet points and include "
    "status emojis (e.g. 🚨 CRITICAL, 🟢 NORMAL, 📄 APPROVED).\n"
    "3. Provide 2-3 recommended next actions at response end.\n"
    "   CRITICAL RULE FOR RECOMMENDED NEXT ACTIONS:\n"
    "   Recommend ONLY actions that this application can actually perform via "
    "supported user queries.\n"
    "   Do NOT suggest offline manual tasks or external administrative "
    "actions like creating POs, updating master data, or changing vendor "
    "settings.\n"
    "   Recommend ONLY supported in-app queries such as:\n"
    "   - 'Check stock for item [item_code] in Organization [org_id]'\n"
    "   - 'List suppliers for item [item_code]'\n"
    "   - 'List items supplied by vendor [supplier_id]'\n"
    "   - 'Negotiate restock for [qty] units of item [item_code]'\n"
    "   - 'Inspect status for invoice [invoice_num]'\n"
    "   - 'Calculate DSO metrics for accounts receivable'\n"
    "   - 'List all inventory items in Organization [org_id]'\n"
    "   - 'List all inventory organizations'\n"
    "   - 'List all approved suppliers'\n"
    "4. Be concise, direct, professional, and do NOT output raw JSON."
)


def _generate_content_with_fallback(
    ai_client: genai.Client,
    contents: Any,
    config: types.GenerateContentConfig,
    fast_tier: bool = True,
) -> tuple[Optional[Any], Optional[str]]:
    """Attempt primary model generation, with fallback or error return."""
    models_to_try = get_candidate_models(fast_tier)
    seen_models = set()

    if getattr(config, "thinking_config", None) is None and hasattr(
        types, "ThinkingConfig"
    ):
        try:
            config.thinking_config = types.ThinkingConfig(thinking_budget=0)
        except (AttributeError, TypeError, ValueError):
            pass

    for m in models_to_try:
        if not m or m in seen_models:
            continue
        seen_models.add(m)
        try:
            resp = ai_client.models.generate_content(
                model=m,
                contents=contents,
                config=config,
            )
            return resp, None
        except SAFE_EXCEPTIONS as exc:
            logger.warning("Model '%s' unavailable: %s", m, exc)

    err_msg = (
        "⚠️ **Model Access Error**: Gemini Flash models are not available in "
        "your Google Cloud project or region. Please ensure the Vertex AI API "
        "is enabled and Gemini models are configured."
    )
    return None, err_msg


def synthesize_response(user_query: str, raw_data: Dict[str, Any]) -> str:
    """Format worker output into markdown tables using Gemini reasoning."""
    ai_client = get_ai_client()
    if not ai_client:
        return f"```json\n{json.dumps(raw_data, indent=2)}\n```"

    prompt = (
        f"User Query: {user_query}\n"
        f"Raw Oracle EBS Data: {json.dumps(raw_data)}\n\n"
        "Instructions: Formulate a direct, executive-grade response. "
        "If the raw data contains an array of records (such as organizations, "
        "items, suppliers, or invoices), render the complete Markdown table "
        "displaying all records and their columns. Tell the user how many "
        "records are being shown (e.g. 'Showing X records...'). If the user "
        "requested more records than the query limit (e.g. asking for 300 "
        "when 100 records are returned), inform the user that only 100 "
        "records are being shown due to the limit. Highlight alerts and "
        "suggest proactive next actions following system instructions."
    )
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.1,
        max_output_tokens=2048,
        thinking_config=(
            types.ThinkingConfig(thinking_budget=0)
            if hasattr(types, "ThinkingConfig")
            else None
        ),
    )
    resp, err_msg = _generate_content_with_fallback(
        ai_client, prompt, config, fast_tier=True
    )
    if resp and resp.text:
        return resp.text
    if err_msg:
        return f"{err_msg}\n\n```json\n{json.dumps(raw_data, indent=2)}\n```"
    return str(raw_data)


def _format_a2a_response(
    raw_res: Dict[str, Any], user_query: str = "", req_id: Any = 1
) -> Dict[str, Any]:
    """Format response into standard A2A JSON-RPC envelope."""
    if isinstance(raw_res, dict) and "jsonrpc" in raw_res:
        return raw_res

    if (
        isinstance(raw_res, dict)
        and raw_res.get("text")
        and (
            not user_query or raw_res.get("gateway") == "Oracle EBS A2A Gateway"
        )
    ):
        formatted_text = str(raw_res["text"])
    elif isinstance(raw_res, dict):
        formatted_text = synthesize_response(user_query, raw_res)
    else:
        formatted_text = str(raw_res)

    uid = str(uuid.uuid4())[:8]
    msg_id = f"msg-{uid}"
    ctx_id = f"ctx-{uid}"
    task_id = f"task-{uid}"

    result_obj = {
        "role": "agent",
        "parts": [{"text": formatted_text}],
        "message": {"role": "agent", "parts": [{"text": formatted_text}]},
        "messageId": msg_id,
        "message_id": msg_id,
        "contextId": ctx_id,
        "context_id": ctx_id,
        "id": task_id,
        "status": {"state": "completed"},
        "text": formatted_text,
        "content": formatted_text,
        "data": raw_res,
    }
    res_dict = {
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
    }
    if isinstance(raw_res, dict):
        for k, v in raw_res.items():
            if k not in res_dict:
                res_dict[k] = v
    return res_dict


def _sanitize_limit(
    val: Optional[int], default: int = 50, max_val: int = 100
) -> int:
    """Sanitize and clamp pagination limits to prevent validation errors."""
    if val is None:
        return default
    try:
        num = int(val)
        if num <= 0:
            return default
        return min(num, max_val)
    except (ValueError, TypeError):
        return default


async def _execute_action_plan(
    plan: Optional[ActionPlan], req: Request
) -> Optional[Dict[str, Any]]:
    """Route ActionPlan directly using dictionary dispatch map."""
    if plan and plan.action in ACTION_ROUTE_MAP:
        handler = ACTION_ROUTE_MAP[plan.action]
        try:
            return await handler(plan, req)
        except (ValidationError, HTTPException, *SAFE_EXCEPTIONS) as exc:
            logger.error(
                "Action execution error for action '%s': %s", plan.action, exc
            )
            return {
                "status": "ERROR",
                "detail": str(exc),
                "text": f"Agent request error: {exc}",
                "content": f"Agent request error: {exc}",
                "message": f"Agent request error: {exc}",
            }
    return None


@proxy_router.api_route("/", methods=["GET", "POST", "OPTIONS", "PUT"])
@proxy_router.api_route("/message", methods=["GET", "POST", "OPTIONS", "PUT"])
@proxy_router.api_route("/messages", methods=["GET", "POST", "OPTIONS", "PUT"])
@proxy_router.api_route("/task", methods=["GET", "POST", "OPTIONS", "PUT"])
@proxy_router.api_route("/tasks", methods=["GET", "POST", "OPTIONS", "PUT"])
@proxy_router.api_route(
    "/tasks/send", methods=["GET", "POST", "OPTIONS", "PUT"]
)
@proxy_router.api_route(
    "/v1/message", methods=["GET", "POST", "OPTIONS", "PUT"]
)
@proxy_router.api_route(
    "/v1/messages", methods=["GET", "POST", "OPTIONS", "PUT"]
)
@proxy_router.api_route("/v1/tasks", methods=["GET", "POST", "OPTIONS", "PUT"])
@proxy_router.api_route(
    "/a2a/v1/message", methods=["GET", "POST", "OPTIONS", "PUT"]
)
@proxy_router.api_route(
    "/a2a/v1/messages", methods=["GET", "POST", "OPTIONS", "PUT"]
)
@proxy_router.api_route(
    "/a2a/v1/tasks", methods=["GET", "POST", "OPTIONS", "PUT"]
)
@proxy_router.api_route("/rpc", methods=["GET", "POST", "OPTIONS", "PUT"])
@proxy_router.api_route("/jsonrpc", methods=["GET", "POST", "OPTIONS", "PUT"])
async def dispatch_a2a_message(req: Request) -> Dict[str, Any]:
    """Unified A2A Cognitive Message Dispatcher using Gemini reasoning."""
    verify_api_key(
        req.headers.get("x-api-key"), req.headers.get("authorization")
    )
    try:
        body = await req.json()
        if isinstance(body, dict):
            req.scope["_json"] = body
    except SAFE_EXCEPTIONS:
        body = {}

    req_id = body.get("id", 1) if isinstance(body, dict) else 1
    params = (
        body.get("params") if isinstance(body.get("params"), dict) else body
    )
    text = _extract_user_prompt(body)

    ai_client = get_ai_client()
    plan: Optional[ActionPlan] = None
    model_err: Optional[str] = None

    if ai_client and text:
        config = types.GenerateContentConfig(
            system_instruction=DISPATCHER_PROMPT,
            response_mime_type="application/json",
            response_schema=ActionPlan,
            temperature=0.0,
            max_output_tokens=300,
            thinking_config=(
                types.ThinkingConfig(thinking_budget=0)
                if hasattr(types, "ThinkingConfig")
                else None
            ),
        )
        resp, model_err = _generate_content_with_fallback(
            ai_client,
            f"User Query: {text}\nParams: {json.dumps(params)}",
            config,
            fast_tier=True,
        )
        if resp and resp.text:
            try:
                plan = ActionPlan.model_validate_json(resp.text)
            except SAFE_EXCEPTIONS as exc:
                logger.warning("ActionPlan parsing error: %s", exc)

    raw_res = await _execute_action_plan(plan, req)
    if raw_res is not None:
        return _format_a2a_response(raw_res, user_query=text, req_id=req_id)

    if model_err and text:
        return _format_a2a_response(
            {"status": "ERROR", "text": model_err},
            user_query=text,
            req_id=req_id,
        )

    msg_text = (
        "🤖 **Oracle EBS Autonomous Assistant**\n\n"
        "I am your AI agent connected to live Oracle EBS DB & worker "
        "services. Here is what I can do:\n\n"
        "### 📦 1. Inventory & Stock Management\n"
        "*Query on-hand quantities, safety stock, and warehouse details.*\n"
        "- **Check Inventory Stock**: *'Check stock AS54888 in Org 204'* "
        "or *'in Org code V1'*\n"
        "- **List Inventory Items**: "
        "*'List items for Organization code AD1'* or *'in Org 204'*\n"
        "- **View Organizations**: *'List all inventory organizations'*\n\n"
        "### 💰 2. Accounts Payable & Financial Operations\n"
        "*Inspect invoice approval statuses, payment terms, and balances.*\n"
        "- **Inspect AP Invoice Status**: "
        "*'Status for invoice INV-2024-001'*\n"
        "- **List Recent Invoices**: *'Show recent AP invoices'*\n\n"
        "### 📊 3. Accounts Receivable & Financial Metrics\n"
        "*Evaluate Days Sales Outstanding (DSO) and liquidity metrics.*\n"
        "- **Calculate DSO (Live Oracle DB)**: "
        "*'Calculate DSO for receivables'* or *'Calculate 90 day DSO'*\n"
        "- **Calculate DSO with Custom Inputs**: "
        "*'Calculate DSO with AR 450000 and sales 1000000 for period 90'*\n"
        "- **View Receivables Overview**: *'Show receivables overview'*\n\n"
        "### 🤝 4. Procurement & Supplier Negotiation\n"
        "*Retrieve supplier catalogs and conduct restock negotiations.*\n"
        "- **Supplier Negotiation**: *'Negotiate restock 500 units AS54888'*\n"
        "- **View Approved Suppliers**: *'List suppliers for item AS54888'*\n"
        "- **Supplier Items Catalog**: "
        "*'Give me the items for supplier 515'*\n\n"
        "---\n"
        "💡 *Type any query above or ask a custom question to get started!*"
    )
    raw_greeting = {
        "status": "SUCCESS",
        "gateway": "Oracle EBS A2A Gateway",
        "text": msg_text,
        "content": msg_text,
        "message": msg_text,
        "supported_actions": [
            "check_stock",
            "invoice_status",
            "calculate_dso",
            "negotiate",
            "organizations",
            "items",
            "suppliers",
            "item_suppliers",
            "supplier_items",
            "recent_invoices",
        ],
    }
    return _format_a2a_response(raw_greeting, user_query="", req_id=req_id)


@proxy_router.post("/check-stock")
async def check_stock(
    request: StockCheckRequest, req: Request
) -> Dict[str, Any]:
    """Proxy inventory stock check to Inventory Agent worker service."""
    inv_url = _get_inventory_agent_url(req)
    payload = request.model_dump()
    if payload.get("item_code") and not payload.get("item_id"):
        payload["item_id"] = payload["item_code"]
    elif payload.get("item_id") and not payload.get("item_code"):
        payload["item_code"] = payload["item_id"]
    return await _forward_request(inv_url, "/check-stock", payload, req)


@proxy_router.post("/invoice-status")
async def invoice_status(
    request: InvoiceStatusRequest, req: Request
) -> Dict[str, Any]:
    """Proxy invoice status query to Financial Agent worker service."""
    fin_url = _get_financial_agent_url(req)
    payload = request.model_dump()
    if payload.get("invoice_num") and not payload.get("invoice_number"):
        payload["invoice_number"] = payload["invoice_num"]
    elif payload.get("invoice_number") and not payload.get("invoice_num"):
        payload["invoice_num"] = payload["invoice_number"]
    return await _forward_request(fin_url, "/invoice-status", payload, req)


@proxy_router.post("/calculate-dso")
async def calculate_dso(
    request: DSOCalculationRequest, req: Request
) -> Dict[str, Any]:
    """Proxy DSO metrics calculation to Financial Agent worker service."""
    fin_url = _get_financial_agent_url(req)
    return await _forward_request(
        fin_url, "/calculate-dso", request.model_dump(), req
    )


@proxy_router.post("/negotiate")
async def negotiate(
    request: NegotiationRequest, req: Request
) -> Dict[str, Any]:
    """Proxy PO negotiation request to Supplier Agent worker service."""
    sup_url = _get_supplier_agent_url(req)
    payload = request.model_dump()
    if request.item_code and not payload.get("item_id"):
        payload["item_id"] = request.item_code
    return await _forward_request(sup_url, "/negotiate", payload, req)


@proxy_router.post("/organizations")
@proxy_router.get("/organizations")
async def organizations(
    req: Request, request: OrganizationListRequest = OrganizationListRequest()
) -> Dict[str, Any]:
    """Proxy organizations list query to Inventory Agent worker service."""
    inv_url = _get_inventory_agent_url(req)
    payload = request.model_dump()
    return await _forward_request(inv_url, "/organizations", payload, req)


@proxy_router.post("/items")
@proxy_router.get("/items")
async def items(
    req: Request, request: ItemListRequest = ItemListRequest()
) -> Dict[str, Any]:
    """Proxy inventory items catalog query to Inventory Agent worker
    service."""
    inv_url = _get_inventory_agent_url(req)
    payload = request.model_dump()
    return await _forward_request(inv_url, "/items", payload, req)


@proxy_router.post("/suppliers")
@proxy_router.get("/suppliers")
async def suppliers(
    req: Request, request: SupplierListRequest = SupplierListRequest()
) -> Dict[str, Any]:
    """Proxy suppliers list query to Supplier Agent worker service."""
    sup_url = _get_supplier_agent_url(req)
    payload = request.model_dump()
    return await _forward_request(sup_url, "/suppliers", payload, req)


@proxy_router.post("/item-suppliers")
async def item_suppliers(
    request: ItemSuppliersRequest, req: Request
) -> Dict[str, Any]:
    """Proxy item suppliers query to Inventory Agent worker service."""
    inv_url = _get_inventory_agent_url(req)
    return await _forward_request(
        inv_url, "/item-suppliers", request.model_dump(), req
    )


@proxy_router.post("/recent-invoices")
@proxy_router.get("/recent-invoices")
async def recent_invoices(
    req: Request, request: InvoiceListRequest = InvoiceListRequest()
) -> Dict[str, Any]:
    """Proxy recent invoices query to Financial Agent worker service."""
    fin_url = _get_financial_agent_url(req)
    payload = request.model_dump()
    return await _forward_request(fin_url, "/recent-invoices", payload, req)


@proxy_router.post("/supplier-items")
@proxy_router.get("/supplier-items")
async def supplier_items(
    req: Request, request: SupplierItemsRequest = SupplierItemsRequest()
) -> Dict[str, Any]:
    """Proxy supplier items query to Supplier Agent worker service."""
    sup_url = _get_supplier_agent_url(req)
    payload = request.model_dump()
    return await _forward_request(sup_url, "/supplier-items", payload, req)


ACTION_ROUTE_MAP: Dict[str, Any] = {
    "check_stock": lambda p, req: check_stock(
        StockCheckRequest(
            item_code=p.item_code,
            item_id=p.item_code,
            organization_id=p.organization_id,
            organization_code=p.organization_code,
        ),
        req,
    ),
    "item_suppliers": lambda p, req: item_suppliers(
        ItemSuppliersRequest(
            item_code=p.item_code,
            organization_id=p.organization_id,
        ),
        req,
    ),
    "supplier_items": lambda p, req: supplier_items(
        req,
        SupplierItemsRequest(
            supplier_id=p.supplier_id,
            supplier_name=p.supplier_name,
            limit=_sanitize_limit(p.limit),
        ),
    ),
    "organizations": lambda p, req: organizations(
        req, OrganizationListRequest(limit=_sanitize_limit(p.limit))
    ),
    "items": lambda p, req: items(
        req,
        ItemListRequest(
            organization_id=p.organization_id,
            organization_code=p.organization_code,
            limit=_sanitize_limit(p.limit),
        ),
    ),
    "suppliers": lambda p, req: suppliers(
        req, SupplierListRequest(limit=_sanitize_limit(p.limit))
    ),
    "recent_invoices": lambda p, req: recent_invoices(
        req, InvoiceListRequest(limit=_sanitize_limit(p.limit))
    ),
    "invoice_status": lambda p, req: invoice_status(
        InvoiceStatusRequest(
            invoice_num=p.invoice_num, invoice_number=p.invoice_num
        ),
        req,
    ),
    "calculate_dso": lambda p, req: calculate_dso(
        DSOCalculationRequest(
            period_days=p.period_days or 90,
            total_accounts_receivable=p.total_accounts_receivable,
            total_credit_sales=p.total_credit_sales,
        ),
        req,
    ),
    "negotiate": lambda p, req: negotiate(
        NegotiationRequest(
            item_code=p.item_code,
            item_id=p.item_code,
            quantity=p.quantity or 100,
            target_unit_price=p.target_unit_price,
        ),
        req,
    ),
}
