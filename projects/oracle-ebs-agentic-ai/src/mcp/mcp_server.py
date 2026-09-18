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

"""Oracle EBS MCP Tool Server for Gemini Enterprise & Vertex AI Agents."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from oracledb import DatabaseError
from pydantic import BaseModel, Field
from src.a2a.schemas import (
    SAFE_EXCEPTIONS,
    SupplierItemEntry,
    SupplierItemsRequest,
    SupplierItemsResponse,
)
from src.agents.inventory_agent import worker_get_item_suppliers
from src.mcp.ebs_db_client import EBSDatabaseClient

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Oracle EBS MCP Tool Server",
    description=(
        "Production-grade Model Context Protocol (MCP) Tool Server providing"
        " deterministic Oracle EBS business operations for Gemini Enterprise."
    ),
    version="2.0.0",
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


# Request & Response Schemas


class StockCheckRequest(BaseModel):
    """Payload for inventory stock level verification."""

    item_code: str = Field(
        ...,
        description="Oracle EBS Item Code or Segment Code (e.g. AS54888)",
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
    """Response containing on-hand balance and threshold evaluation."""

    item_code: str
    organization_id: int
    on_hand_quantity: float
    min_threshold: float
    below_threshold: bool
    status: str
    primary_supplier_name: Optional[str] = Field(
        default=None,
        description="Primary approved supplier name",
    )
    approved_suppliers: List[Dict[str, Any]] = Field(
        default_factory=list, description="Approved suppliers for this item"
    )


class ItemSuppliersRequest(BaseModel):
    """Payload for retrieving approved suppliers for an inventory item."""

    item_code: str = Field(
        ..., description="Oracle EBS Item Code (e.g. AS54888)"
    )


class ItemSuppliersResponse(BaseModel):
    """Response containing approved suppliers for an inventory item."""

    item_code: str
    total_suppliers: int
    primary_supplier_id: Optional[int] = None
    primary_supplier_name: Optional[str] = None
    suppliers: List[Dict[str, Any]] = Field(default_factory=list)


_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _resolve_item_suppliers(item_code: str) -> List[Dict[str, Any]]:
    """Helper to resolve approved suppliers for item code from database."""
    try:
        data = worker_get_item_suppliers(item_code)
        return data.get("suppliers") or []
    except (*SAFE_EXCEPTIONS, httpx.HTTPError) as exc:
        logger.warning(
            "DB resolution of suppliers failed in mcp_server: %s", exc
        )
        return []


class InvoiceStatusRequest(BaseModel):
    """Payload for Accounts Payable invoice status query."""

    invoice_num: Optional[str] = Field(
        default=None,
        description="Oracle AP Invoice Number (e.g. INV-2024-001)",
    )
    vendor_id: Optional[int] = Field(
        default=None, description="Oracle PO Supplier / Vendor ID"
    )
    invoice_id: Optional[int] = Field(
        default=None, description="Oracle AP Invoice Primary Key ID"
    )


class InvoiceRecord(BaseModel):
    """Schema for individual Oracle AP invoice record."""

    invoice_id: Optional[int] = None
    invoice_num: str
    vendor_id: int
    invoice_amount: float
    payment_status: str
    approval_status: str
    due_date: Optional[str] = None


class InvoiceStatusResponse(BaseModel):
    """Response container for AP invoice query results."""

    query_params: Dict[str, Any]
    total_found: int
    invoices: List[InvoiceRecord]
    status: str


class DSORequest(BaseModel):
    """Payload for Days Sales Outstanding (DSO) calculation."""

    period_days: int = Field(
        default=90, description="DSO analysis window in days (default 90)"
    )
    total_accounts_receivable: Optional[float] = Field(
        default=None, description="Explicit Accounts Receivable total override"
    )
    total_credit_sales: Optional[float] = Field(
        default=None, description="Explicit Total Credit Sales override"
    )


class DSOResponse(BaseModel):
    """Response containing calculated DSO analytics and financial health."""

    period_days: int
    total_accounts_receivable: float
    total_credit_sales: float
    dso_days: float
    evaluation: str
    is_synthetic: bool = False


class NegotiateRequest(BaseModel):
    """Payload for restocking vendor negotiation."""

    item_code: str = Field(..., description="Inventory item code or SKU")
    quantity: int = Field(..., description="Restock order quantity")


class NegotiateResponse(BaseModel):
    """Response returned from restock supplier negotiation."""

    vendor: str
    item_code: str
    quantity: int
    unit_price: float
    total_estimated_cost: float
    delivery_timeline: str
    status: str


class QueryRequest(BaseModel):
    """Payload for natural language query execution."""

    prompt: str = Field(..., description="Natural language query prompt")


# MCP Tool Endpoints


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Health check endpoint conforming to MCP standard."""
    return {"status": "healthy", "service": "oracle_ebs_mcp_server"}


@lru_cache(maxsize=128)
def _resolve_organization_info_cached(clean_token: str) -> Tuple[int, str, str]:
    """Cached organization resolver using default database client."""
    client = get_db_client()
    try:
        sql = (
            "SELECT organization_id, organization_code, organization_name "
            "FROM apps.org_organization_definitions "
            "WHERE UPPER(organization_code) = :tok "
            "   OR UPPER(organization_name) LIKE :pat "
            "   OR TO_CHAR(organization_id) = :tok"
        )
        rows = client.execute_query(
            sql, {"tok": clean_token, "pat": f"%{clean_token}%"}
        )
        if rows and isinstance(rows, list) and len(rows) > 0:
            r = rows[0]
            oid = int(r.get("ORGANIZATION_ID") or r.get("organization_id") or 0)
            code = str(
                r.get("ORGANIZATION_CODE")
                or r.get("organization_code")
                or clean_token
            )
            name = str(
                r.get("ORGANIZATION_NAME")
                or r.get("organization_name")
                or f"Organization {code}"
            )
            return oid, code, name
    except (DatabaseError, *SAFE_EXCEPTIONS) as exc:
        logger.debug(
            "Database org lookup failed in _resolve_organization_info: %s", exc
        )
    return 0, "", ""


def _resolve_organization_info(
    token: str, db_client: Optional[EBSDatabaseClient] = None
) -> Tuple[int, str, str]:
    """Resolve org token (numeric ID or Org Code) into (id, code, name)."""
    if not token:
        return 0, "", ""

    clean_token = str(token).strip().upper()
    if not clean_token:
        return 0, "", ""

    if db_client is None:
        return _resolve_organization_info_cached(clean_token)

    try:
        sql = (
            "SELECT organization_id, organization_code, organization_name "
            "FROM apps.org_organization_definitions "
            "WHERE UPPER(organization_code) = :tok "
            "   OR UPPER(organization_name) LIKE :pat "
            "   OR TO_CHAR(organization_id) = :tok"
        )
        rows = db_client.execute_query(
            sql, {"tok": clean_token, "pat": f"%{clean_token}%"}
        )
        if rows and isinstance(rows, list) and len(rows) > 0:
            r = rows[0]
            oid = int(r.get("ORGANIZATION_ID") or r.get("organization_id") or 0)
            code = str(
                r.get("ORGANIZATION_CODE")
                or r.get("organization_code")
                or clean_token
            )
            name = str(
                r.get("ORGANIZATION_NAME")
                or r.get("organization_name")
                or f"Organization {code}"
            )
            return oid, code, name
    except (DatabaseError, *SAFE_EXCEPTIONS) as exc:
        logger.debug(
            "Database org lookup failed in _resolve_organization_info: %s", exc
        )

    return 0, "", ""


@app.post("/check-stock", response_model=StockCheckResponse)
def check_stock(
    req: StockCheckRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> StockCheckResponse:
    """MCP Tool: Check stock balance by joining inventory tables."""
    org_id = req.organization_id
    if org_id is None and req.organization_code:
        oid, _, _ = _resolve_organization_info(req.organization_code, db_client)
        if oid > 0:
            org_id = oid

    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="organization_id or organization_code must be specified",
        )

    sql = (
        "SELECT "
        "msi.segment1 AS item_code, "
        "msi.organization_id, "
        "NVL(SUM(moq.transaction_quantity), 0) AS total_on_hand "
        "FROM apps.mtl_system_items_b msi "
        "LEFT JOIN apps.mtl_onhand_quantities_detail moq "
        "ON msi.inventory_item_id = moq.inventory_item_id "
        "AND msi.organization_id = moq.organization_id "
        "WHERE (UPPER(msi.segment1) = UPPER(:item_code) "
        "OR TO_CHAR(msi.inventory_item_id) = :item_code) "
        "AND msi.organization_id = :org_id "
        "GROUP BY msi.segment1, msi.organization_id"
    )
    params = {"item_code": str(req.item_code), "org_id": org_id}
    res = db_client.execute_query(sql, params)

    on_hand = 0.0
    found = False
    if res and isinstance(res, list) and len(res) > 0:
        found = True
        first_row = res[0]
        on_hand = float(
            first_row.get("TOTAL_ON_HAND")
            or first_row.get("TRANSACTION_QUANTITY")
            or first_row.get("PRIMARY_TRANSACTION_QUANTITY")
            or 0.0
        )

    below_thresh = on_hand < req.min_threshold
    status_str = (
        "CRITICAL_LOW_STOCK"
        if (found and below_thresh)
        else ("SUFFICIENT_STOCK" if found else "ITEM_NOT_FOUND")
    )

    suppliers = _resolve_item_suppliers(req.item_code)
    p_name = suppliers[0]["supplier_name"] if suppliers else None

    return StockCheckResponse(
        item_code=req.item_code,
        organization_id=org_id,
        on_hand_quantity=on_hand,
        min_threshold=req.min_threshold,
        below_threshold=below_thresh if found else True,
        status=status_str,
        primary_supplier_name=p_name,
        approved_suppliers=suppliers,
    )


@app.post("/get-item-suppliers", response_model=ItemSuppliersResponse)
def get_item_suppliers(
    req: ItemSuppliersRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> ItemSuppliersResponse:
    """MCP Tool: Retrieve approved suppliers for item."""
    if not req.item_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required parameter: item_code",
        )

    sql = (
        "SELECT DISTINCT "
        "aps.vendor_id AS supplier_id, "
        "aps.vendor_name AS supplier_name, "
        "pla.unit_price "
        "FROM apps.po_lines_all pla "
        "JOIN apps.po_headers_all pha ON pla.po_header_id = pha.po_header_id "
        "JOIN apps.ap_suppliers aps ON pha.vendor_id = aps.vendor_id "
        "LEFT JOIN apps.mtl_system_items_b msi "
        "ON pla.item_id = msi.inventory_item_id "
        "WHERE UPPER(msi.segment1) = UPPER(:item_code) "
        "AND ROWNUM <= 20"
    )
    try:
        rows = db_client.execute_query(sql, {"item_code": req.item_code})
    except (*SAFE_EXCEPTIONS, httpx.HTTPError) as exc:
        logger.warning("DB query for item suppliers failed: %s", exc)
        rows = None

    suppliers: List[Dict[str, Any]] = []
    if rows and isinstance(rows, list):
        for r in rows:
            sid = r.get("SUPPLIER_ID") or r.get("VENDOR_ID")
            sname = r.get("SUPPLIER_NAME") or r.get("VENDOR_NAME")
            if sid and sname:
                suppliers.append(
                    {
                        "supplier_id": int(sid),
                        "supplier_name": str(sname),
                        "unit_price": float(r.get("UNIT_PRICE", 0.0)),
                    }
                )

    if not suppliers:
        suppliers = _resolve_item_suppliers(req.item_code)

    p_id = suppliers[0]["supplier_id"] if suppliers else None
    p_name = suppliers[0]["supplier_name"] if suppliers else None

    return ItemSuppliersResponse(
        item_code=req.item_code,
        total_suppliers=len(suppliers),
        primary_supplier_id=p_id,
        primary_supplier_name=p_name,
        suppliers=suppliers,
    )


def _parse_supplier_item_rows(
    rows: Any, req: SupplierItemsRequest
) -> Tuple[List[SupplierItemEntry], Optional[int], Optional[str]]:
    """Parse supplier item rows into structured models and supplier metadata."""
    items: List[SupplierItemEntry] = []
    s_id = req.supplier_id
    s_name = req.supplier_name
    if rows and isinstance(rows, list):
        for r in rows:
            if not s_id and r.get("SUPPLIER_ID"):
                s_id = int(r["SUPPLIER_ID"])
            if not s_name and r.get("SUPPLIER_NAME"):
                s_name = str(r["SUPPLIER_NAME"])
            item_c = str(r.get("ITEM_CODE") or r.get("item_code") or "")
            if item_c:
                items.append(
                    SupplierItemEntry(
                        inventory_item_id=r.get("INVENTORY_ITEM_ID"),
                        item_code=item_c,
                        description=r.get("DESCRIPTION"),
                        unit_price=float(r.get("UNIT_PRICE", 0.0)),
                        organization_id=r.get("ORGANIZATION_ID"),
                        po_number=r.get("PO_NUMBER"),
                    )
                )
    return items, s_id, s_name


def _parse_invoice_records(
    rows: Any, req: InvoiceStatusRequest
) -> List[InvoiceRecord]:
    """Parse database rows into AP InvoiceRecord instances."""
    records: List[InvoiceRecord] = []
    if not (rows and isinstance(rows, list)):
        return records
    for r in rows:
        inv_num = str(r.get("INVOICE_NUM", "UNKNOWN"))
        v_id = int(r.get("VENDOR_ID", 0))
        if req.invoice_num and inv_num.upper() != req.invoice_num.upper():
            continue
        if req.vendor_id is not None and v_id != req.vendor_id:
            continue
        amt = float(r.get("INVOICE_AMOUNT", 0.0))
        pmt = str(r.get("PAYMENT_STATUS_FLAG", r.get("PAYMENT_STATUS", "N")))
        appr = str(
            r.get("WFAPPROVAL_STATUS", r.get("APPROVAL_STATUS", "PENDING"))
        )
        due = r.get("DUE_DATE")
        records.append(
            InvoiceRecord(
                invoice_id=r.get("INVOICE_ID"),
                invoice_num=inv_num,
                vendor_id=v_id,
                invoice_amount=amt,
                payment_status=pmt,
                approval_status=appr,
                due_date=str(due) if due else None,
            )
        )
    return records


def _extract_metric_from_rows(
    rows: Any, primary_keys: tuple[str, ...]
) -> Optional[float]:
    """Extract numeric metric from the first database row."""
    if not (rows and isinstance(rows, list) and len(rows) > 0):
        return None
    first = rows[0]
    for k in primary_keys:
        if first.get(k) is not None:
            return float(first[k])
    for v in first.values():
        if isinstance(v, (int, float)):
            return float(v)
    return None


@app.post("/supplier-items", response_model=SupplierItemsResponse)
def get_supplier_items(
    req: SupplierItemsRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> SupplierItemsResponse:
    """MCP Tool: Retrieve items supplied by a specific vendor."""
    if req.supplier_id is None and not req.supplier_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required parameter: supplier_id or supplier_name",
        )

    where_clauses = []
    params: Dict[str, Any] = {}
    if req.supplier_id is not None:
        where_clauses.append("aps.vendor_id = :supplier_id")
        params["supplier_id"] = req.supplier_id
    if req.supplier_name:
        where_clauses.append(
            "UPPER(aps.vendor_name) LIKE UPPER(:supplier_name)"
        )
        params["supplier_name"] = f"%{req.supplier_name}%"

    where_sql = " AND ".join(where_clauses)
    rec_limit = min(req.limit or 50, 100)
    sql = (
        "SELECT DISTINCT "
        "msi.inventory_item_id, "
        "msi.segment1 AS item_code, "
        "msi.description, "
        "pla.unit_price, "
        "msi.organization_id, "
        "pha.segment1 AS po_number, "
        "aps.vendor_id AS supplier_id, "
        "aps.vendor_name AS supplier_name "
        "FROM apps.po_lines_all pla "
        "JOIN apps.po_headers_all pha ON pla.po_header_id = pha.po_header_id "
        "JOIN apps.ap_suppliers aps ON pha.vendor_id = aps.vendor_id "
        "JOIN apps.mtl_system_items_b msi "
        "ON pla.item_id = msi.inventory_item_id "
        f"WHERE {where_sql} "
        f"AND ROWNUM <= {rec_limit}"
    )
    try:
        rows = db_client.execute_query(sql, params)
    except (*SAFE_EXCEPTIONS, httpx.HTTPError) as exc:
        logger.warning("DB query for supplier items failed: %s", exc)
        rows = None

    items, s_id, s_name = _parse_supplier_item_rows(rows, req)
    status_str = "SUCCESS" if items else "NOT_FOUND"
    notes_str = (
        f"Found {len(items)} items for supplier {s_id or s_name}."
        if items
        else f"No items found for supplier {s_id or s_name}."
    )
    return SupplierItemsResponse(
        supplier_id=s_id,
        supplier_name=s_name,
        total_items=len(items),
        items=items,
        status=status_str,
        notes=notes_str,
    )


@app.post("/invoice-status", response_model=InvoiceStatusResponse)
def invoice_status(
    req: InvoiceStatusRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> InvoiceStatusResponse:
    """MCP Tool: Query AP_INVOICES_ALL using bind variables."""
    query_conditions = []
    params: Dict[str, Any] = {}

    if req.invoice_num:
        query_conditions.append("UPPER(INVOICE_NUM) = UPPER(:inv_num)")
        params["inv_num"] = req.invoice_num
    if req.vendor_id is not None:
        query_conditions.append("VENDOR_ID = :vendor_id")
        params["vendor_id"] = req.vendor_id
    if req.invoice_id is not None:
        query_conditions.append("INVOICE_ID = :inv_id")
        params["inv_id"] = req.invoice_id

    where_clause = (
        " WHERE " + " AND ".join(query_conditions) if query_conditions else ""
    )
    sql = f"SELECT * FROM AP_INVOICES_ALL{where_clause}"
    if not where_clause:
        sql += " WHERE ROWNUM <= 50"
    else:
        sql += " AND ROWNUM <= 50"

    rows = db_client.execute_query(sql, params)
    records = _parse_invoice_records(rows, req)

    qp = {
        "invoice_num": req.invoice_num,
        "vendor_id": req.vendor_id,
        "invoice_id": req.invoice_id,
    }

    return InvoiceStatusResponse(
        query_params=qp,
        total_found=len(records),
        invoices=records,
        status="SUCCESS" if len(records) > 0 else "NOT_FOUND",
    )


@app.post("/calculate-dso", response_model=DSOResponse)
def calculate_dso(
    req: DSORequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> DSOResponse:
    """MCP Tool: Calculate Days Sales Outstanding (DSO) over period window."""
    if req.period_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_days must be greater than zero",
        )

    ar_total = req.total_accounts_receivable
    sales_total = req.total_credit_sales

    if ar_total is None or sales_total is None:
        metrics_sql = (
            "SELECT NVL(SUM(AMOUNT_DUE_REMAINING), 0) AS TOTAL_AR, "
            "       NVL(SUM(AMOUNT_DUE_ORIGINAL), 0) AS TOTAL_SALES "
            "FROM AR_PAYMENT_SCHEDULES_ALL"
        )
        metrics_res = db_client.execute_query(metrics_sql)
        if ar_total is None:
            ar_total = _extract_metric_from_rows(
                metrics_res, ("TOTAL_AR", "TOTAL_ACCOUNTS_RECEIVABLE")
            )
        if sales_total is None:
            sales_total = _extract_metric_from_rows(
                metrics_res, ("TOTAL_SALES", "TOTAL_CREDIT_SALES")
            )

        if sales_total is None or sales_total <= 0:
            lines_sql = (
                "SELECT NVL(SUM(EXTENDED_AMOUNT), 0) AS TOTAL_SALES "
                "FROM RA_CUSTOMER_TRX_LINES_ALL "
                "WHERE LINE_TYPE = 'LINE'"
            )
            lines_res = db_client.execute_query(lines_sql)
            sales_total = _extract_metric_from_rows(
                lines_res, ("TOTAL_SALES", "TOTAL_CREDIT_SALES")
            )

    if ar_total is None or sales_total is None or sales_total <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Total credit sales must be > 0 for DSO calculation",
        )

    dso_days = round((ar_total / sales_total) * req.period_days, 2)
    evaluation = (
        "OPTIMAL"
        if dso_days <= 45.0
        else (
            "EVALUATE_CREDIT_TERMS" if dso_days <= 60.0 else "CRITICAL_DSO_HIGH"
        )
    )

    return DSOResponse(
        period_days=req.period_days,
        total_accounts_receivable=ar_total,
        total_credit_sales=sales_total,
        dso_days=dso_days,
        evaluation=evaluation,
        is_synthetic=False,
    )


@app.post("/negotiate", response_model=NegotiateResponse)
def negotiate(
    req: NegotiateRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> NegotiateResponse:
    """MCP Tool: Negotiate restocking quote against vendor catalog."""
    if req.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quantity must be greater than zero",
        )

    sql = (
        "SELECT DISTINCT "
        "aps.vendor_id AS supplier_id, "
        "aps.vendor_name AS supplier_name, "
        "pla.unit_price "
        "FROM apps.po_lines_all pla "
        "JOIN apps.po_headers_all pha ON pla.po_header_id = pha.po_header_id "
        "JOIN apps.ap_suppliers aps ON pha.vendor_id = aps.vendor_id "
        "LEFT JOIN apps.mtl_system_items_b msi "
        "ON pla.item_id = msi.inventory_item_id "
        "WHERE UPPER(msi.segment1) = UPPER(:item_code) "
        "AND ROWNUM <= 1"
    )
    rows = db_client.execute_query(sql, {"item_code": req.item_code})

    if rows and isinstance(rows, list) and len(rows) > 0:
        v_name = rows[0].get("SUPPLIER_NAME") or rows[0].get("VENDOR_NAME")
        vendor_name = str(v_name or f"Supplier for {req.item_code}")
        unit_price = float(rows[0].get("UNIT_PRICE", 12.50))
        lead_time = 5
        status_str = "QUOTE_ACCEPTED"
    else:
        vendor_name = f"Supplier for {req.item_code}"
        unit_price = 0.0
        lead_time = 0
        status_str = "ITEM_NOT_FOUND"

    total_cost = round(unit_price * req.quantity, 2)
    delivery_str = f"{lead_time} business days" if lead_time > 0 else "N/A"

    return NegotiateResponse(
        vendor=vendor_name,
        item_code=req.item_code,
        quantity=req.quantity,
        unit_price=unit_price,
        total_estimated_cost=total_cost,
        delivery_timeline=delivery_str,
        status=status_str,
    )


@app.post("/execute")
def execute(
    req: QueryRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Execute natural language query endpoint for backward compatibility."""
    results = db_client.execute_nl_query(req.prompt)
    return {"status": "success", "results": results}
