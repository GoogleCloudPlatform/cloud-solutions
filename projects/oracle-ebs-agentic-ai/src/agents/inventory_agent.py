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

"""Inventory Agent Worker for Oracle EBS using Gemini Function Calling."""

import logging
import os
import re
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from google.genai import types
from pydantic import BaseModel, Field, model_validator
from src.a2a.agent_card import AgentCard
from src.a2a.ai_client import (
    generate_content_with_models,
    get_ai_client,
)
from src.a2a.schemas import SAFE_EXCEPTIONS
from src.mcp.ebs_db_client import EBSDatabaseClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """Lifespan handler to register Inventory Agent with A2A Server."""
    register_with_a2a()
    yield


app = FastAPI(
    title="Inventory Agent (Agentic)",
    description=(
        "LLM-native worker for Oracle EBS Inventory and Stock Level validation"
    ),
    version="2.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_db_exception_handler(request: Request, exc: Exception):
    """Sanitize database and internal errors to prevent schema leaks."""
    if isinstance(exc, HTTPException):
        raise exc
    logger.error("Unhandled exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database operation failed"},
    )


@lru_cache
def get_db_client() -> EBSDatabaseClient:
    """FastAPI Dependency Provider for EBSDatabaseClient."""
    return EBSDatabaseClient()


class InventoryQueryRequest(BaseModel):
    """Natural language inventory request for agentic reasoning."""

    query: str = Field(
        ...,
        description=(
            "Natural language question or request regarding inventory stock"
            " levels"
        ),
    )


class InventoryAnalysisResponse(BaseModel):
    """Structured output for LLM-native inventory reasoning."""

    summary: str = Field(description="Executive summary of inventory status")
    item_id: str = Field(
        default="UNKNOWN", description="Inventory Item ID or Code"
    )
    organization_id: Optional[int] = Field(
        default=None, description="Oracle Inventory Organization ID"
    )
    on_hand_quantity: float = Field(
        default=0.0, description="Current verified on-hand balance"
    )
    min_threshold: float = Field(
        default=10.0, description="Minimum acceptable threshold"
    )
    below_threshold: bool = Field(
        default=False, description="Whether on-hand is below threshold"
    )
    stock_status: str = Field(
        default="SUFFICIENT_STOCK",
        description="SUFFICIENT_STOCK, CRITICAL_LOW_STOCK, or ITEM_NOT_FOUND",
    )
    recommended_actions: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class StockCheckRequest(BaseModel):
    """Payload for inventory stock level verification."""

    item_id: Optional[str] = Field(
        default=None,
        description="Oracle EBS Inventory Item ID or Segment Code",
    )
    item_code: Optional[str] = Field(
        default=None, description="Oracle EBS Inventory Item Code"
    )
    organization_id: Optional[int] = Field(
        default=None, description="Oracle Inventory Organization ID"
    )
    organization_code: Optional[str] = Field(
        default=None, description="Oracle Organization Code (e.g. V1, M1)"
    )
    min_threshold: float = Field(
        default=10.0,
        description="Minimum acceptable on-hand quantity threshold",
    )


class StockCheckResponse(BaseModel):
    """Response with on-hand balance, threshold evaluation, & suppliers."""

    item_id: str
    organization_id: int
    on_hand_quantity: float
    min_threshold: float
    below_threshold: bool
    status: str
    primary_supplier_id: Optional[int] = Field(
        default=None, description="Primary Approved Supplier ID"
    )
    primary_supplier_name: Optional[str] = Field(
        default=None,
        description="Primary Approved Supplier Name",
    )
    approved_suppliers: List[Dict[str, Any]] = Field(
        default_factory=list, description="Approved suppliers for this item"
    )
    details: Dict[str, Any] = Field(default_factory=dict)


class OrganizationListRequest(BaseModel):
    """Payload for listing operating organizations."""

    limit: int = Field(
        default=50, ge=1, le=100, description="Max records to return (1-100)"
    )


class OrganizationItem(BaseModel):
    """Structured organization item representation."""

    organization_id: int
    organization_code: str
    organization_name: str
    ORGANIZATION_ID: Optional[int] = None
    ORGANIZATION_CODE: Optional[str] = None
    ORGANIZATION_NAME: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_casing_variants(cls, data: Any) -> Any:
        if isinstance(data, dict):
            oid = data.get("organization_id") or data.get("ORGANIZATION_ID")
            ocode = data.get("organization_code") or data.get(
                "ORGANIZATION_CODE"
            )
            oname = data.get("organization_name") or data.get(
                "ORGANIZATION_NAME"
            )
            return {
                "organization_id": oid,
                "organization_code": ocode,
                "organization_name": oname,
                "ORGANIZATION_ID": oid,
                "ORGANIZATION_CODE": ocode,
                "ORGANIZATION_NAME": oname,
            }
        return data


class OrganizationsResponse(BaseModel):
    """Structured output for organizations list."""

    status: str = "SUCCESS"
    total_found: int = 0
    organizations: List[OrganizationItem] = Field(default_factory=list)


class ItemListRequest(BaseModel):
    """Payload for listing inventory items in an organization."""

    organization_id: Optional[int] = Field(
        default=None,
        description="Oracle Inventory Organization ID (e.g. 204 or 1384)",
    )
    organization_code: Optional[str] = Field(
        default=None,
        description="Oracle Inventory Organization Code (e.g. V1 or PR4)",
    )
    limit: int = Field(
        default=50, ge=1, le=100, description="Max records to return (1-100)"
    )


class InventoryItemRecord(BaseModel):
    """Structured inventory item record."""

    inventory_item_id: Optional[int] = None
    item_code: str
    description: Optional[str] = None
    organization_id: int
    total_on_hand: float = 0.0
    primary_supplier_name: Optional[str] = None
    approved_suppliers: List[Dict[str, Any]] = Field(default_factory=list)
    ITEM_CODE: Optional[str] = None
    ORGANIZATION_ID: Optional[int] = None
    TOTAL_ON_HAND: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def populate_casing_variants(cls, data: Any) -> Any:
        if isinstance(data, dict):
            icode = (
                data.get("item_code")
                or data.get("ITEM_CODE")
                or data.get("SEGMENT1")
            )
            oid = data.get("organization_id") or data.get("ORGANIZATION_ID")
            qty = (
                data.get("total_on_hand")
                or data.get("TOTAL_ON_HAND")
                or data.get("TRANSACTION_QUANTITY")
                or data.get("PRIMARY_TRANSACTION_QUANTITY")
                or 0.0
            )
            d = dict(data)
            d["item_code"] = icode
            d["ITEM_CODE"] = icode
            d["organization_id"] = oid
            d["ORGANIZATION_ID"] = oid
            d["total_on_hand"] = float(qty)
            d["TOTAL_ON_HAND"] = float(qty)
            return d
        return data


class ItemsResponse(BaseModel):
    """Structured output for item catalog."""

    status: str = "SUCCESS"
    organization_id: int
    total_found: int = 0
    items: List[InventoryItemRecord] = Field(default_factory=list)


class ItemSupplierItem(BaseModel):
    """Structured supplier representation for an item."""

    supplier_id: int
    supplier_name: str
    unit_price: Optional[float] = None
    lead_time_days: Optional[int] = None
    SUPPLIER_ID: Optional[int] = None
    SUPPLIER_NAME: Optional[str] = None
    UNIT_PRICE: Optional[float] = None
    LEAD_TIME_DAYS: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def populate_casing_variants(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sid = data.get("supplier_id") or data.get("SUPPLIER_ID")
            sname = data.get("supplier_name") or data.get("SUPPLIER_NAME")
            price = data.get("unit_price") or data.get("UNIT_PRICE")
            lead = data.get("lead_time_days") or data.get("LEAD_TIME_DAYS")
            return {
                "supplier_id": sid,
                "supplier_name": sname,
                "unit_price": price,
                "lead_time_days": lead,
                "SUPPLIER_ID": sid,
                "SUPPLIER_NAME": sname,
                "UNIT_PRICE": price,
                "LEAD_TIME_DAYS": lead,
            }
        return data


class ItemSuppliersRequest(BaseModel):
    """Payload for retrieving approved suppliers for an inventory item."""

    item_code: str = Field(
        ..., description="Oracle EBS Item Code (e.g. AS54888)"
    )
    organization_id: Optional[int] = Field(
        default=None,
        description="Optional Oracle Inventory Organization ID filter",
    )


class ItemSuppliersResponse(BaseModel):
    """Response containing approved suppliers for an inventory item."""

    item_code: str
    organization_id: Optional[int] = None
    total_suppliers: int = 0
    primary_supplier_id: Optional[int] = None
    primary_supplier_name: Optional[str] = None
    suppliers: List[ItemSupplierItem] = Field(default_factory=list)


SYSTEM_INSTRUCTION = """
You are an expert Oracle EBS Inventory & Materials Management Architect.
You have access to the `execute_oracle_sql` tool to query inventory tables:
- apps.ORG_ORGANIZATION_DEFINITIONS: organization_id, organization_code, organization_name
- apps.MTL_SYSTEM_ITEMS_B: inventory_item_id, segment1 (item_code), organization_id, description
- apps.MTL_ONHAND_QUANTITIES_DETAIL: inventory_item_id, organization_id, subinventory_code, transaction_quantity
- apps.PO_LINES_ALL: po_header_id, item_id, unit_price
- apps.PO_HEADERS_ALL: po_header_id, vendor_id
- apps.AP_SUPPLIERS: vendor_id, vendor_name

OPERATING RULES:
1. Always formulate precise read-only SELECT queries using JOINs and bind variables where needed.
2. If an organization does not exist in apps.ORG_ORGANIZATION_DEFINITIONS, do NOT default to 204 or fabricate an organization. Report organization not found or organization_id = 0.
3. If an item does not exist in apps.MTL_SYSTEM_ITEMS_B for the requested organization, do NOT fabricate data. Set status to ITEM_NOT_FOUND.
4. Output strictly adheres to the requested JSON response schema.
5. RECORD POPULATION MANDATE:
   - When returning arrays of records, you MUST populate EVERY record dictionary with all actual columns queried from the database. NEVER return empty objects `{}` or summary-only counts.
   - For `organizations`: Each element in the list MUST include `organization_id`, `organization_code`, and `organization_name` (as well as uppercase `ORGANIZATION_ID`, `ORGANIZATION_CODE`, `ORGANIZATION_NAME`).
   - For `items`: Each element in the list MUST include `inventory_item_id`, `item_code`, `description`, `organization_id`, `total_on_hand` (as well as uppercase `ITEM_CODE`, `ORGANIZATION_ID`, `TOTAL_ON_HAND`).
   - For `suppliers` / `approved_suppliers`: Each element MUST include `supplier_id`, `supplier_name`, `unit_price`, and `lead_time_days` (set to null if not stored in the queried tables).
   - When rendering record tables, state how many records are being shown
     (e.g. 'Showing X records...'). If the requested count exceeds the
     100-record query limit (e.g. requesting 300), explain that only 100
     records are being shown due to the system query limit.
6. COLUMN INTEGRITY: Only query actual columns listed in the table definitions above. Never query unverified columns such as PRIMARY_VENDOR_ID or LEAD_TIME. Set unqueried schema fields like primary_supplier_id, primary_supplier_name, or lead_time_days to null.
7. STRICT QUERY EXECUTION LIMIT:
   Execute at most 2 tool queries total:
   - First query (if organization_code is provided): resolve organization_id from apps.ORG_ORGANIZATION_DEFINITIONS.
   - Second query: retrieve items from apps.MTL_SYSTEM_ITEMS_B for that organization.
   Do NOT retry or probe other tables if no records match. If no items are found, immediately output {"status": "SUCCESS", "organization_id": <resolved_id>, "total_found": 0, "items": []}.
"""


def make_execute_oracle_sql(
    db_client: EBSDatabaseClient,
) -> Callable[..., List[Dict[str, Any]]]:
    """Builds a read-only Oracle SQL execution tool with security validation."""

    def execute_oracle_sql(
        query: str, *args: Any, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Executes a read-only SQL query against Oracle EBS database.

        Args:
            query: SQL query string to execute against Oracle EBS.
        """
        clean_query = query.strip()
        upper_query = clean_query.upper()

        if not (
            upper_query.startswith("SELECT") or upper_query.startswith("WITH")
        ):
            logger.warning("Disallowed non-SELECT query attempt: %s", query)
            return [
                {
                    "error": (
                        "Security Error: Only read-only SELECT queries are"
                        " permitted."
                    )
                }
            ]

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
                return [
                    {
                        "error": (
                            f"Security Error: Keyword '{kw}' is not allowed in"
                            " read-only queries."
                        )
                    }
                ]

        logger.info("LLM generating SQL execution: %s", query)
        params = args[0] if args else kwargs.get("params")
        try:
            return db_client.execute_query(query, params)
        except SAFE_EXCEPTIONS as exc:
            setattr(execute_oracle_sql, "db_error", exc)
            raise

    setattr(execute_oracle_sql, "db_error", None)
    return execute_oracle_sql


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "agent": "inventory_agent"}


@app.post("/analyze-inventory", response_model=InventoryAnalysisResponse)
def analyze_inventory(
    request: InventoryQueryRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> InventoryAnalysisResponse:
    """Endpoint where Gemini handles reasoning & inventory evaluation."""
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query cannot be empty",
        )

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        f"Analyze inventory stock and warehouse entities for query: "
        f'"{request.query}". If the query asks to list organizations, '
        "items, or suppliers in a table, query the relevant database tables "
        "and provide the full Markdown table of all retrieved records in "
        "the `summary` as well as in `details`. State the number of records "
        "shown, clarifying if the 100-record query limit capped a larger "
        "request."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=InventoryAnalysisResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        return InventoryAnalysisResponse.model_validate_json(response.text)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI reasoning unavailable or failed",
    )


@app.post("/check-stock", response_model=StockCheckResponse)
def check_stock(
    request: StockCheckRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> StockCheckResponse:
    """Validate stock level and approved suppliers using Gemini Flash."""
    target_item = (
        request.item_code.strip() if request.item_code else None
    ) or (request.item_id.strip() if request.item_id else None)
    if not target_item:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required parameter: item_id or item_code",
        )

    target_org = (
        request.organization_id
        if request.organization_id is not None
        else (
            request.organization_code.strip()
            if request.organization_code
            else None
        )
    )
    if target_org is None or (isinstance(target_org, str) and not target_org):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="organization_id or organization_code must be specified",
        )
    if target_org == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item '{target_item}' not found in organization 0",
        )

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        f"Validate stock level and approved suppliers for item '{target_item}' "
        f"in organization '{target_org}' against safety threshold "
        f"'{request.min_threshold}'."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=StockCheckResponse,
            temperature=0.1,
        ),
    )
    if getattr(execute_oracle_sql, "db_error", None):
        raise getattr(execute_oracle_sql, "db_error")
    if response and response.text:
        result = StockCheckResponse.model_validate_json(response.text)
        if (
            result.status in ("ITEM_NOT_FOUND", "NOT_FOUND")
            or result.details.get("not_found") is True
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Item '{target_item}' not found in organization"
                    f" {target_org}"
                ),
            )
        return result
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI reasoning unavailable or failed",
    )


@app.post("/organizations", response_model=Dict[str, Any])
@app.get("/organizations", response_model=Dict[str, Any])
def list_organizations(
    request: Optional[OrganizationListRequest] = None,
    limit: int = 50,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Retrieve a paginated list of active warehouse organizations using
    Gemini."""
    raw_limit = request.limit if request else limit
    if raw_limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be greater than 0",
        )
    rec_limit = min(raw_limit, 100)

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        "Query apps.ORG_ORGANIZATION_DEFINITIONS to retrieve a paginated list "
        f"of active warehouse organizations (limit: {rec_limit}). In the "
        "response, populate the `organizations` list with every retrieved "
        "organization, including organization_id, organization_code, and "
        "organization_name. Note the count of records shown, indicating if "
        "the 100-record query limit capped a larger request."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=OrganizationsResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        res_obj = OrganizationsResponse.model_validate_json(response.text)
        out = res_obj.model_dump()
        for org in out.get("organizations", []):
            if "organization_id" in org and "ORGANIZATION_ID" not in org:
                org["ORGANIZATION_ID"] = org["organization_id"]
            if "organization_code" in org and "ORGANIZATION_CODE" not in org:
                org["ORGANIZATION_CODE"] = org["organization_code"]
            if "organization_name" in org and "ORGANIZATION_NAME" not in org:
                org["ORGANIZATION_NAME"] = org["organization_name"]
        return out
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI reasoning unavailable or failed",
    )


@app.post("/items")
@app.get("/items")
def get_inventory_items(
    request: Optional[ItemListRequest] = None,
    organization_id: Optional[int] = None,
    organization_code: Optional[str] = None,
    limit: int = 50,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Retrieve inventory item catalog for an organization using Gemini."""
    req_org_id = request.organization_id if request else organization_id
    req_org_code = request.organization_code if request else organization_code

    if req_org_id is None and not (req_org_code and req_org_code.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="organization_id or organization_code must be specified",
        )

    org_spec = req_org_code or str(req_org_id)
    raw_limit = request.limit if request else limit
    if raw_limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be greater than 0",
        )
    rec_limit = min(raw_limit, 100)

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        "Query apps.MTL_SYSTEM_ITEMS_B and "
        "apps.MTL_ONHAND_QUANTITIES_DETAIL to retrieve inventory items with "
        "descriptions, organization IDs, and aggregated on-hand quantities "
        f'for organization "{org_spec}" (limit: {rec_limit}). Set status '
        'to "SUCCESS". Populate the `items` list with every retrieved item '
        "record including inventory_item_id, item_code, description, "
        "organization_id, and total_on_hand. Indicate the count of records "
        "shown, clarifying if the 100-record limit capped a larger request."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=ItemsResponse,
            temperature=0.1,
        ),
    )
    if getattr(execute_oracle_sql, "db_error", None):
        raise getattr(execute_oracle_sql, "db_error")
    if response and response.text:
        items_res = ItemsResponse.model_validate_json(response.text)
        if items_res.organization_id <= 0 and items_res.total_found == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization '{org_spec}' not found",
            )
        out = items_res.model_dump()
        out["status"] = "SUCCESS"
        if out.get("organization_id", 0) <= 0 and req_org_id:
            out["organization_id"] = req_org_id
        for itm in out.get("items", []):
            if "item_code" in itm and "ITEM_CODE" not in itm:
                itm["ITEM_CODE"] = itm["item_code"]
            if "organization_id" in itm and "ORGANIZATION_ID" not in itm:
                itm["ORGANIZATION_ID"] = itm["organization_id"]
            if "total_on_hand" in itm and "TOTAL_ON_HAND" not in itm:
                itm["TOTAL_ON_HAND"] = itm["total_on_hand"]
            if "inventory_item_id" in itm and "INVENTORY_ITEM_ID" not in itm:
                itm["INVENTORY_ITEM_ID"] = itm["inventory_item_id"]
        return out
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI reasoning unavailable or failed",
    )


@app.post("/item-suppliers", response_model=ItemSuppliersResponse)
@app.get("/item-suppliers")
def get_item_suppliers(
    request: Optional[ItemSuppliersRequest] = None,
    item_code: Optional[str] = None,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> ItemSuppliersResponse:
    """Retrieve approved suppliers tied to a specific inventory item using
    Gemini."""
    target_code = request.item_code if request else item_code
    if not target_code or not target_code.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required parameter: item_code",
        )

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        "Find approved suppliers and purchase order pricing for item code "
        f'"{target_code}". Query apps.MTL_SYSTEM_ITEMS_B (segment1 = '
        f'"{target_code}") and join with apps.PO_LINES_ALL (on item_id = '
        "inventory_item_id), apps.PO_HEADERS_ALL (on po_header_id), and "
        "apps.AP_SUPPLIERS (on vendor_id). Select only vendor_id, "
        "vendor_name, and unit_price from these tables. Do not query "
        "PRIMARY_VENDOR_ID or LEAD_TIME from the database. Set "
        "primary_supplier_id, primary_supplier_name, and lead_time_days to "
        "null. Populate the `suppliers` list with every retrieved supplier "
        "record including supplier_id (vendor_id), supplier_name "
        "(vendor_name), unit_price, and lead_time_days."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=ItemSuppliersResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        return ItemSuppliersResponse.model_validate_json(response.text)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI reasoning unavailable or failed",
    )


def worker_get_item_suppliers(
    item_code: str,
    db_client: Optional[EBSDatabaseClient] = None,
) -> Dict[str, Any]:
    """Helper for worker agents to query item suppliers directly."""
    client = db_client or get_db_client()
    req = ItemSuppliersRequest(item_code=item_code)
    res = get_item_suppliers(request=req, db_client=client)
    return res.model_dump()


def register_with_a2a(
    discovery_server_url: Optional[str] = None,
) -> bool:
    """Register Inventory Agent with the A2A Discovery Server."""
    target_url = discovery_server_url or os.getenv(
        "A2A_SERVER_URL", "http://127.0.0.1:8080"
    )
    card = AgentCard(
        name="inventory_agent",
        description=(
            "Specialized agent for stock level checks, organization list,"
            " inventory items catalog, and approved item suppliers"
        ),
        endpoint_url=os.getenv("INVENTORY_AGENT_URL", "http://127.0.0.1:8001"),
        version="2.0.0",
        capabilities=[
            "inventory_check",
            "stock_threshold",
            "on_hand_balance",
            "analyze_inventory",
            "organizations_list",
            "items_catalog",
            "item_suppliers",
        ],
        endpoints={
            "analyze-inventory": "/analyze-inventory",
            "check-stock": "/check-stock",
            "organizations": "/organizations",
            "items": "/items",
            "item-suppliers": "/item-suppliers",
            "health": "/health",
        },
    )

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"{target_url}/register", json=card.model_dump()
            )
            if response.status_code in (200, 201):
                logger.info(
                    "Successfully registered inventory_agent with A2A server"
                )
                return True
    except (httpx.HTTPError, OSError) as exc:
        logger.warning(
            "Failed to auto-register inventory_agent with A2A server (%s)", exc
        )
    return False
