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

"""Supplier Agent Worker for Oracle EBS using Gemini Function Calling."""

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
from src.a2a.schemas import (
    SupplierItemsRequest,
    SupplierItemsResponse,
)
from src.mcp.ebs_db_client import EBSDatabaseClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """Lifespan handler to register Supplier Agent with A2A Server."""
    register_with_a2a()
    yield


app = FastAPI(
    title="Supplier Agent (Agentic)",
    description=(
        "LLM-native worker for automated supplier negotiations, terms"
        " evaluation, and mock catalog REST API"
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

        if not db_client.is_context_initialized():
            try:
                db_client.initialize_apps_context()
            except (
                RuntimeError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                OSError,
            ) as exc:
                logger.warning("Apps context initialization warning: %s", exc)

        logger.info("LLM generating SQL execution: %s", query)
        params = args[0] if args else kwargs.get("params")
        return db_client.execute_query(query, params)

    return execute_oracle_sql


class SupplierQueryRequest(BaseModel):
    """Natural language supplier negotiation request for agentic reasoning."""

    query: str = Field(
        ...,
        description=(
            "Natural language request regarding supplier negotiations or quote"
            " evaluations (e.g. 'Negotiate price for item AS54888 with supplier"
            " 301 at target price 12.50 USD')"
        ),
    )


class SupplierAnalysisResponse(BaseModel):
    """Structured output for LLM-native supplier negotiation reasoning."""

    summary: str = Field(description="Executive summary of negotiation")
    supplier_id: Optional[int] = Field(
        default=None, description="Oracle PO Supplier ID"
    )
    supplier_name: Optional[str] = Field(
        default=None, description="Supplier / Vendor name"
    )
    negotiation_accepted: bool = Field(
        default=False, description="Whether target price was accepted"
    )
    proposed_unit_price: float = Field(
        default=0.0, description="Proposed target unit price"
    )
    counter_unit_price: float = Field(
        default=0.0, description="Final counter-offer unit price"
    )
    recommended_actions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VendorItemQuote(BaseModel):
    """Schema for vendor catalog item quote."""

    supplier_id: int
    supplier_name: str
    item_id: str
    unit_price: float
    lead_time_days: int
    min_order_qty: float
    available_stock: float


class CatalogQueryRequest(BaseModel):
    """Payload for querying external vendor catalog REST API."""

    item_id: str = Field(..., description="Inventory item ID or SKU code")
    required_quantity: float = Field(
        default=10.0, description="Required restocking volume"
    )


class CatalogQueryResponse(BaseModel):
    """Response from mock vendor catalog REST API."""

    item_id: str
    required_quantity: float
    total_vendors_found: int
    best_quote: Optional[VendorItemQuote] = None
    all_quotes: List[VendorItemQuote] = Field(default_factory=list)


class NegotiationRequest(BaseModel):
    """Payload for initiating a supplier terms or price negotiation."""

    supplier_id: Optional[int] = Field(
        default=None, description="Oracle PO Supplier / Vendor ID"
    )
    item_id: Optional[str] = Field(
        default=None, description="Inventory item ID or SKU to negotiate"
    )
    item_code: Optional[str] = Field(
        default=None, description="Inventory item code"
    )
    po_number: Optional[str] = Field(
        default=None, description="Oracle EBS Purchase Order Number"
    )
    target_quantity: Optional[float] = Field(
        default=None, description="Requested order volume"
    )
    quantity: Optional[int] = Field(
        default=None, description="Order quantity alias"
    )
    target_unit_price: Optional[float] = Field(
        default=None, description="Target unit price in USD"
    )
    proposed_payment_terms: str = Field(
        default="Net 30", description="Proposed payment terms"
    )


class NegotiationResponse(BaseModel):
    """Response returned from supplier negotiation engine."""

    supplier_id: int
    supplier_name: str
    item_id: str
    target_unit_price: float
    counter_unit_price: float
    accepted: bool
    negotiated_terms: str
    notes: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SupplierListRequest(BaseModel):
    """Payload for listing approved suppliers."""

    limit: int = Field(
        default=50, ge=1, description="Max records to return (1-100)"
    )


class SupplierItem(BaseModel):
    """Approved supplier representation."""

    vendor_id: int
    vendor_number: Optional[str] = None
    vendor_name: str
    enabled_flag: Optional[str] = "Y"
    VENDOR_ID: Optional[int] = None
    VENDOR_NUMBER: Optional[str] = None
    VENDOR_NAME: Optional[str] = None
    ENABLED_FLAG: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_casing_variants(cls, data: Any) -> Any:
        if isinstance(data, dict):
            vid = data.get("vendor_id") or data.get("VENDOR_ID")
            vname = data.get("vendor_name") or data.get("VENDOR_NAME")
            vnum = data.get("vendor_number") or data.get("VENDOR_NUMBER")
            eflag = data.get("enabled_flag") or data.get("ENABLED_FLAG") or "Y"
            data["vendor_id"] = vid
            data["VENDOR_ID"] = vid
            data["vendor_name"] = vname
            data["VENDOR_NAME"] = vname
            data["vendor_number"] = vnum
            data["VENDOR_NUMBER"] = vnum
            data["enabled_flag"] = eflag
            data["ENABLED_FLAG"] = eflag
        return data


class SuppliersResponse(BaseModel):
    """Structured response for listing approved suppliers."""

    status: str = Field(default="SUCCESS", description="Operation status")
    total_found: int = Field(default=0, description="Count of suppliers found")
    suppliers: List[SupplierItem] = Field(
        default_factory=list, description="List of approved suppliers"
    )


SYSTEM_INSTRUCTION = """
You are an expert Oracle EBS Purchasing & Procurement Architect.
You have access to the `execute_oracle_sql` tool to inspect PO pricing and supplier terms:
- `apps.PO_HEADERS_ALL`: po_header_id, segment1 (po_number), vendor_id, terms_id
- `apps.PO_LINES_ALL`: po_header_id, item_id, unit_price, quantity
- `apps.AP_SUPPLIERS`: vendor_id, vendor_name, segment1 (vendor_num), enabled_flag
- `apps.MTL_SYSTEM_ITEMS_B`: inventory_item_id, segment1 (item_code)

Available List & Lookup Tools:
- List Approved Suppliers: Query `apps.AP_SUPPLIERS` ordered by vendor_id with `FETCH FIRST :limit_val ROWS ONLY`.
- Vendor Quotes Catalog: Query `apps.PO_LINES_ALL` joined with `apps.PO_HEADERS_ALL` and `apps.AP_SUPPLIERS` for item quotes.

SUPPLIER VALIDATION RULES:
If the user specifies a supplier name or ID that does not exist in `apps.AP_SUPPLIERS` or the vendor registry:
1. Query `apps.AP_SUPPLIERS`.
2. If no matching supplier exists, state clearly that the supplier was not found, and list available approved suppliers (e.g., 301 - Acme Industrial Supplies, 302 - Global Electronics).

TABLE RENDERING MANDATE:
When the raw data contains an array of records (such as organizations, items, suppliers, or invoices) or when the user asks for a table or list, you MUST render the FULL Markdown table displaying EVERY record with its individual columns (e.g. Supplier ID, Vendor Number, Supplier Name, Enabled Flag). NEVER replace, omit, or collapse the records into a high-level count summary table (e.g., do NOT just show 'Total Suppliers: 50'). Display the actual row-by-row data. State clearly how many records are being shown (e.g. 'Showing X records...'). If the user requested more records than the system query limit (e.g. asking for 300 records when the maximum limit is 100), explicitly inform the user that only 100 records are being shown due to the query limit.

NEGOTIATION & PRICING RULES:
Assess historical pricing feasibility using database PO logs and catalog quotes:
- For high-volume purchases (quantity >= 100), assess volume discounts; accept target_unit_price if within reasonable threshold of historical unit price (TIER_1 volume tier), or propose a counter-offer around target_unit_price * 1.02.
- For low-volume purchases (quantity < 100), do NOT accept discounted target prices below historical base price without standard lot volume (STANDARD volume tier); reject and set accepted=false, and propose a standard-margin counter-offer at target_unit_price * 1.10 (e.g., if target_unit_price is 50.00, counter_unit_price is 55.00).
- If the item or supplier is unlisted or not found in the catalog or PO logs, clearly indicate that the item or supplier is unlisted, set notes to 'ITEM_NOT_FOUND' and accepted to false.

RECOMMENDED ACTIONS GUIDELINE:
When suggesting recommended_actions in the output schema, suggest ONLY supported application queries and actions that this system can actually perform (e.g. 'Check stock for item [item_code] in Organization [org_id]', 'Negotiate restock for [qty] units of item [item_code]', 'List suppliers for item [item_code]'). Do NOT suggest offline manual tasks or administrative procedures like creating POs manually in Oracle EBS or updating supplier master data.
"""


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "agent": "supplier_agent"}


@app.post("/vendor-catalog", response_model=CatalogQueryResponse)
def query_vendor_catalog(
    request: CatalogQueryRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> CatalogQueryResponse:
    """External vendor catalog service endpoint using Gemini Flash."""
    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supplier reasoning failed or AI client unavailable",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        f'Query our vendor quotes catalog for item "{request.item_id}" and '
        f'required quantity "{request.required_quantity}". Query '
        "apps.PO_LINES_ALL, apps.PO_HEADERS_ALL, apps.AP_SUPPLIERS, and "
        "apps.MTL_SYSTEM_ITEMS_B to find active vendor quotes. If no matching "
        "item or quotes exist, return total_vendors_found: 0, best_quote: "
        "null, all_quotes: []. When quotes are found, populate all_quotes and "
        "set best_quote to the quote with the lowest unit_price. Render the "
        "full Markdown table displaying every quote record in summary or "
        "notes."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=CatalogQueryResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        return CatalogQueryResponse.model_validate_json(response.text)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Supplier reasoning failed or AI client unavailable",
    )


@app.post("/analyze-suppliers", response_model=SupplierAnalysisResponse)
def analyze_suppliers(
    request: SupplierQueryRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> SupplierAnalysisResponse:
    """Endpoint where Gemini handles reasoning and supplier evaluation."""
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query cannot be empty",
        )

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supplier reasoning failed or AI client unavailable",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        f'Analyze suppliers for query "{request.query}". '
        "If the query asks to list suppliers or quotes in a table, "
        "query the relevant database tables and provide the full Markdown "
        "table of all retrieved records in the `summary`."
    )

    try:
        response = generate_content_with_models(
            ai_client=ai_client,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[execute_oracle_sql],
                response_mime_type="application/json",
                response_schema=SupplierAnalysisResponse,
                temperature=0.1,
            ),
        )
        if response and response.text:
            return SupplierAnalysisResponse.model_validate_json(response.text)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supplier reasoning failed or AI client unavailable",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Gemini supplier reasoning error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supplier reasoning failed or AI client unavailable",
        ) from exc


@app.post("/negotiate", response_model=NegotiationResponse)
def negotiate(
    request: NegotiationRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> NegotiationResponse:
    """Execute supplier negotiation using Gemini Flash."""
    target_item = (request.item_id or request.item_code or "").strip()
    if not target_item:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required parameter: item_id or item_code",
        )

    if request.target_quantity is not None and request.target_quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_quantity must be greater than zero for negotiation",
        )
    if request.quantity is not None and request.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quantity must be greater than zero for negotiation",
        )

    if request.target_quantity is not None:
        target_qty = float(request.target_quantity)
    elif request.quantity is not None:
        target_qty = float(request.quantity)
    else:
        target_qty = 100.0

    if target_qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_quantity must be greater than zero for negotiation",
        )

    if request.target_unit_price is not None and request.target_unit_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "target_unit_price must be greater than zero for negotiation"
            ),
        )

    target_price = request.target_unit_price or 0.0

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supplier reasoning failed or AI client unavailable",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    sup_filter = (
        f", supplier_id: {request.supplier_id}"
        if request.supplier_id is not None
        else ""
    )

    prompt = (
        f'Negotiate purchase terms for item "{target_item}", quantity '
        f'"{target_qty}", proposed payment terms '
        f'"{request.proposed_payment_terms}", and target price '
        f'"{target_price}"{sup_filter}. Use database PO logs to assess '
        "historical pricing feasibility. Query apps.PO_HEADERS_ALL, "
        "apps.PO_LINES_ALL, apps.AP_SUPPLIERS, and apps.MTL_SYSTEM_ITEMS_B. "
        "For low-volume orders (quantity < 100), do not accept discounts; "
        "set accepted=false and counter_unit_price = "
        "round(target_price * 1.10, 2) (e.g. 50.00 -> 55.00). For "
        "high-volume orders (quantity >= 100), assess volume discounts; "
        "accept if reasonable or counter at target_price * 1.02. If the item "
        "or supplier is unlisted or not found in catalog or database, set "
        'notes to "ITEM_NOT_FOUND" and accepted to false.'
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=NegotiationResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        neg_res = NegotiationResponse.model_validate_json(response.text)
        if "ITEM_NOT_FOUND" in neg_res.notes or "NOT_FOUND" in neg_res.notes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f'Item "{target_item}" is not listed in '
                    "catalog or database"
                ),
            )
        return neg_res

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Supplier reasoning failed or AI client unavailable",
    )


@app.post("/suppliers", response_model=SuppliersResponse)
@app.get("/suppliers", response_model=SuppliersResponse)
def get_suppliers(
    request: Optional[SupplierListRequest] = None,
    limit: int = 50,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Retrieve approved suppliers from apps.ap_suppliers using Gemini Flash."""
    raw_limit = request.limit if request else limit
    if raw_limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be greater than zero",
        )
    rec_limit = min(raw_limit, 100)

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supplier reasoning failed or AI client unavailable",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        "Retrieve a list of active general vendors and suppliers from AP "
        f"tables (apps.AP_SUPPLIERS) (limit: {rec_limit}). In the response, "
        "populate the `suppliers` list with every retrieved supplier record "
        "including vendor_id, vendor_number, vendor_name, and enabled_flag. "
        "Render the full Markdown table displaying every record with its "
        "individual columns. State how many records are being shown, "
        "noting if the 100-record query limit capped a larger request."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=SuppliersResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        sup_res = SuppliersResponse.model_validate_json(response.text)
        out = sup_res.model_dump()
        for sup in out.get("suppliers", []):
            if "vendor_id" in sup and "VENDOR_ID" not in sup:
                sup["VENDOR_ID"] = sup["vendor_id"]
            if "vendor_name" in sup and "VENDOR_NAME" not in sup:
                sup["VENDOR_NAME"] = sup["vendor_name"]
            if "vendor_number" in sup and "VENDOR_NUMBER" not in sup:
                sup["VENDOR_NUMBER"] = sup["vendor_number"]
            if "enabled_flag" in sup and "ENABLED_FLAG" not in sup:
                sup["ENABLED_FLAG"] = sup["enabled_flag"]
        return out

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Supplier reasoning failed or AI client unavailable",
    )


@app.post("/supplier-items", response_model=SupplierItemsResponse)
@app.get("/supplier-items", response_model=SupplierItemsResponse)
def get_supplier_items(
    request: Optional[SupplierItemsRequest] = None,
    supplier_id: Optional[int] = None,
    supplier_name: Optional[str] = None,
    limit: int = 50,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Retrieve items supplied by a vendor using Gemini Flash."""
    req_supplier_id = (
        request.supplier_id
        if request and request.supplier_id is not None
        else supplier_id
    )
    req_supplier_name = (
        request.supplier_name
        if request and request.supplier_name
        else supplier_name
    )
    raw_limit = request.limit if request else limit
    if raw_limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be greater than zero",
        )
    rec_limit = min(raw_limit, 100)

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supplier reasoning failed or AI client unavailable",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    filter_desc = []
    if req_supplier_id is not None:
        filter_desc.append(f"supplier/vendor_id={req_supplier_id}")
    if req_supplier_name:
        filter_desc.append(f"supplier/vendor_name='{req_supplier_name}'")
    filter_str = " and ".join(filter_desc) if filter_desc else "all suppliers"

    prompt = (
        f"Retrieve items supplied by vendor ({filter_str}) by querying "
        "apps.AP_SUPPLIERS (or PO_VENDORS) joined with apps.PO_HEADERS_ALL, "
        "apps.PO_LINES_ALL, and apps.MTL_SYSTEM_ITEMS_B (limit: "
        f"{rec_limit}). Retrieve inventory_item_id, item_code (segment1), "
        "description, unit_price, organization_id, and po_number. "
        "If no items are found for this supplier or if the supplier does not "
        'exist, set total_items to 0, items to [], status to "NOT_FOUND", '
        "and in notes state that no items were found for this supplier. "
        "If items are found, populate the `items` list with every record, "
        'set status to "SUCCESS", and in `notes`, render the complete '
        "Markdown table displaying every record with all columns (Item Code, "
        "Description, Unit Price, PO Number, Organization ID). Indicate the "
        "number of records shown, clarifying if the 100-record query limit "
        "capped a larger request."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=SupplierItemsResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        sup_items_res = SupplierItemsResponse.model_validate_json(response.text)
        return sup_items_res.model_dump()

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Supplier reasoning failed or AI client unavailable",
    )


def register_with_a2a(
    discovery_server_url: Optional[str] = None,
) -> bool:
    """Register Supplier Agent with the A2A Discovery Server."""
    target_url = discovery_server_url or os.getenv(
        "A2A_SERVER_URL", "http://127.0.0.1:8080"
    )
    card = AgentCard(
        name="supplier_agent",
        description=(
            "Specialized agent for supplier list lookups, negotiations, "
            "terms evaluation, and vendor catalog"
        ),
        endpoint_url=os.getenv("SUPPLIER_AGENT_URL", "http://127.0.0.1:8003"),
        version="2.0.0",
        capabilities=[
            "supplier_negotiation",
            "terms_evaluation",
            "po_pricing",
            "vendor_catalog",
            "analyze_suppliers",
            "suppliers_list",
            "supplier_items",
        ],
        endpoints={
            "analyze-suppliers": "/analyze-suppliers",
            "negotiate": "/negotiate",
            "suppliers": "/suppliers",
            "supplier-items": "/supplier-items",
            "vendor-catalog": "/vendor-catalog",
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
                    "Successfully registered supplier_agent with A2A server"
                )
                return True
    except (httpx.HTTPError, OSError) as exc:
        logger.warning(
            "Failed to auto-register supplier_agent with A2A server (%s)", exc
        )
    return False
