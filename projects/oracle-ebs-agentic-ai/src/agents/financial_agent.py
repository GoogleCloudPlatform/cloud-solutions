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

"""Financial Agent Worker for Oracle EBS using Gemini Function Calling."""

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
    """Lifespan handler to register Financial Agent with A2A Server."""
    register_with_a2a()
    yield


app = FastAPI(
    title="Financial Agent (Agentic)",
    description=(
        "LLM-native worker for Oracle EBS Financials and DSO Analytics"
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

        logger.info("LLM generating SQL execution: %s", query)
        params = args[0] if args else kwargs.get("params")
        try:
            return db_client.execute_query(query, params)
        except SAFE_EXCEPTIONS as exc:
            setattr(execute_oracle_sql, "db_error", exc)
            raise

    setattr(execute_oracle_sql, "db_error", None)
    return execute_oracle_sql


class FinancialQueryRequest(BaseModel):
    """Natural language financial request for agentic reasoning."""

    query: str = Field(
        ...,
        description=(
            "Natural language question or request from user/orchestrator"
            " (e.g. 'Check invoice status for ERS-9163-109073 and compute DSO"
            " over 90 days')"
        ),
    )


class FinancialInvoiceRecord(BaseModel):
    """Invoice record schema mapped to Oracle AP tables and LLM risk."""

    invoice_id: int = Field(default=0, description="Oracle AP Invoice ID")
    invoice_num: str
    vendor_id: int = Field(
        default=0, description="Vendor / Supplier PO Vendor ID"
    )
    invoice_amount: float
    payment_status_flag: str = Field(
        default="N", description="Payment status flag ('Y'/'N')"
    )
    payment_status: Optional[str] = Field(
        default=None, description="Payment status text alias"
    )
    approval_status: str
    due_date: Optional[str] = None
    risk_assessment: str = Field(
        default="NORMAL",
        description="LLM evaluation of payment timeliness and vendor risk",
    )
    INVOICE_ID: Optional[int] = None
    INVOICE_NUM: Optional[str] = None
    VENDOR_ID: Optional[int] = None
    INVOICE_AMOUNT: Optional[float] = None
    PAYMENT_STATUS_FLAG: Optional[str] = None
    APPROVAL_STATUS: Optional[str] = None
    DUE_DATE: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_casing_variants(cls, data: Any) -> Any:
        if isinstance(data, dict):
            iid = data.get("invoice_id") or data.get("INVOICE_ID") or 0
            inum = data.get("invoice_num") or data.get("INVOICE_NUM") or ""
            vid = data.get("vendor_id") or data.get("VENDOR_ID") or 0
            iamt = (
                data.get("invoice_amount") or data.get("INVOICE_AMOUNT") or 0.0
            )
            pflag = (
                data.get("payment_status_flag")
                or data.get("PAYMENT_STATUS_FLAG")
                or "N"
            )
            appr = (
                data.get("approval_status")
                or data.get("APPROVAL_STATUS")
                or "APPROVED"
            )
            ddate = data.get("due_date") or data.get("DUE_DATE")
            data["invoice_id"] = iid
            data["INVOICE_ID"] = iid
            data["invoice_num"] = inum
            data["INVOICE_NUM"] = inum
            data["vendor_id"] = vid
            data["VENDOR_ID"] = vid
            data["invoice_amount"] = iamt
            data["INVOICE_AMOUNT"] = iamt
            data["payment_status_flag"] = pflag
            data["PAYMENT_STATUS_FLAG"] = pflag
            data["approval_status"] = appr
            data["APPROVAL_STATUS"] = appr
            data["due_date"] = ddate
            data["DUE_DATE"] = ddate
        return data


# Unified alias for schema consolidation
InvoiceRecord = FinancialInvoiceRecord


class FinancialAnalysisResponse(BaseModel):
    """Structured output for LLM-native financial reasoning."""

    summary: str = Field(description="Executive summary of findings")
    invoices: List[FinancialInvoiceRecord] = Field(default_factory=list)
    days_sales_outstanding: Optional[float] = Field(
        default=None, description="Calculated DSO metric if applicable"
    )
    cash_flow_health: str = Field(
        default="OPTIMAL",
        description=(
            "OPTIMAL, MODERATE, or HIGH_RISK based on financial context"
        ),
    )

    recommended_actions: List[str] = Field(default_factory=list)


class InvoiceStatusRequest(BaseModel):
    """Payload for invoice status inspection."""

    invoice_number: Optional[str] = Field(
        default=None, description="Invoice identifier number"
    )
    invoice_num: Optional[str] = Field(
        default=None, description="Invoice number alias"
    )
    vendor_id: Optional[int] = Field(
        default=None, description="Vendor / Supplier PO Vendor ID"
    )
    invoice_id: Optional[int] = Field(
        default=None, description="Oracle AP Invoice ID"
    )


class InvoiceStatusResponse(BaseModel):
    """Response containing queried invoice status information."""

    query_params: Dict[str, Any] = Field(default_factory=dict)
    total_found: int = 0
    invoices: List[InvoiceRecord] = Field(default_factory=list)
    status: str = "SUCCESS"


class DSORequest(BaseModel):
    """Payload for calculating Days Sales Outstanding (DSO)."""

    period_days: int = Field(
        default=90, description="Analysis period in days (e.g. 30, 90, 365)"
    )
    total_accounts_receivable: Optional[float] = Field(
        default=None, description="Total outstanding AR balance"
    )
    total_receivables: Optional[float] = Field(
        default=None, description="Alias for total outstanding AR balance"
    )
    total_credit_sales: Optional[float] = Field(
        default=None, description="Total credit sales for the period"
    )


class DSOResponse(BaseModel):
    """Response containing calculated Days Sales Outstanding (DSO)."""

    period_days: int
    total_accounts_receivable: float
    total_credit_sales: float
    dso_days: float
    evaluation: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InvoiceListRequest(BaseModel):
    """Payload for listing recent AP invoices."""

    limit: int = Field(
        default=50, description="Max records to return (capped at 100)"
    )
    offset: int = Field(default=0, ge=0, description="Offset for pagination")
    vendor_id: Optional[int] = Field(
        default=None, description="Optional vendor ID filter"
    )


RecentInvoicesRequest = InvoiceListRequest


class RecentInvoiceItem(BaseModel):
    """Structured recent invoice item."""

    invoice_id: int = Field(default=0, description="Oracle AP Invoice ID")
    invoice_num: str = Field(..., description="Invoice Number")
    vendor_id: int = Field(default=0, description="Vendor ID")
    invoice_amount: float = Field(default=0.0, description="Invoice Amount")
    payment_status_flag: str = Field(
        default="N", description="Payment status flag ('Y'/'N')"
    )
    approval_status: str = Field(
        default="APPROVED", description="Workflow approval status"
    )
    due_date: Optional[str] = Field(default=None, description="Due date")
    INVOICE_ID: Optional[int] = None
    INVOICE_NUM: Optional[str] = None
    VENDOR_ID: Optional[int] = None
    INVOICE_AMOUNT: Optional[float] = None
    PAYMENT_STATUS_FLAG: Optional[str] = None
    APPROVAL_STATUS: Optional[str] = None
    DUE_DATE: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_casing_variants(cls, data: Any) -> Any:
        if isinstance(data, dict):
            iid = data.get("invoice_id") or data.get("INVOICE_ID") or 0
            inum = data.get("invoice_num") or data.get("INVOICE_NUM") or ""
            vid = data.get("vendor_id") or data.get("VENDOR_ID") or 0
            iamt = (
                data.get("invoice_amount") or data.get("INVOICE_AMOUNT") or 0.0
            )
            pflag = (
                data.get("payment_status_flag")
                or data.get("PAYMENT_STATUS_FLAG")
                or "N"
            )
            appr = (
                data.get("approval_status")
                or data.get("APPROVAL_STATUS")
                or "APPROVED"
            )
            ddate = data.get("due_date") or data.get("DUE_DATE")
            data["invoice_id"] = iid
            data["INVOICE_ID"] = iid
            data["invoice_num"] = inum
            data["INVOICE_NUM"] = inum
            data["vendor_id"] = vid
            data["VENDOR_ID"] = vid
            data["invoice_amount"] = iamt
            data["INVOICE_AMOUNT"] = iamt
            data["payment_status_flag"] = pflag
            data["PAYMENT_STATUS_FLAG"] = pflag
            data["approval_status"] = appr
            data["APPROVAL_STATUS"] = appr
            data["due_date"] = ddate
            data["DUE_DATE"] = ddate
        return data


class RecentInvoicesResponse(BaseModel):
    """Response model for recent AP invoices listing."""

    status: str = Field(default="SUCCESS", description="Operation status")
    total_found: int = Field(default=0, description="Count of invoices found")
    invoices: List[RecentInvoiceItem] = Field(
        default_factory=list, description="List of invoice records"
    )
    summary: Optional[str] = Field(
        default=None, description="Executive summary or markdown table"
    )


class ReceivablesRequest(BaseModel):
    """Payload for AR payment schedules and DSO calculation."""

    period_days: int = Field(
        default=90, ge=1, le=365, description="Period days for evaluation"
    )


class ReceivablesResponse(BaseModel):
    """Response model for AR payment schedules and DSO calculation."""

    status: str = Field(default="SUCCESS", description="Operation status")
    period_days: int = Field(default=90, description="Period days evaluated")
    total_receivables: float = Field(
        default=0.0, description="Total outstanding AR balance"
    )
    total_credit_sales: float = Field(
        default=0.0, description="Total credit sales"
    )
    dso_days: float = Field(default=0.0, description="Days Sales Outstanding")
    health: str = Field(default="HEALTHY", description="HEALTHY or WARNING")


SYSTEM_INSTRUCTION = """
You are an expert Oracle EBS Financials & AP/AR Accounting Architect.
You have access to the `execute_oracle_sql` tool to inspect accounts payable and accounts receivable tables:
- `apps.AP_INVOICES_ALL`: invoice_id, invoice_num, vendor_id, invoice_amount, payment_status_flag ('Y'/'N'), wfapproval_status (aliased as approval_status), invoice_date
- `apps.AP_SUPPLIERS`: vendor_id, vendor_name
- `apps.AP_PAYMENT_SCHEDULES_ALL`: invoice_id, due_date, gross_amount, amount_remaining
- `apps.AR_PAYMENT_SCHEDULES_ALL`: amount_due_remaining (Accounts Receivable balance), amount_due_original (Total credit sales), trx_date
- `apps.RA_CUSTOMER_TRX_LINES_ALL`: extended_amount (Line-level sales amount where line_type = 'LINE')

Available List & Lookup Tools:
- List Recent Invoices: Query `apps.AP_INVOICES_ALL` ordered by invoice_id DESC with `FETCH FIRST :limit_val ROWS ONLY`.
- Receivables & DSO: Query `apps.AR_PAYMENT_SCHEDULES_ALL` over period_days.

ENTITY VALIDATION RULES:
If the user specifies an invoice number or vendor that does not exist in `apps.AP_INVOICES_ALL` or `apps.AP_SUPPLIERS`:
1. Query the respective table (`apps.AP_INVOICES_ALL` or `apps.AP_SUPPLIERS`).
2. If no matching record is found, state clearly that the invoice or vendor was not found in Accounts Payable.

TABLE RENDERING MANDATE:
When the raw data contains an array of records (such as organizations, items, suppliers, or invoices) or when the user asks for a table or list, you MUST render the FULL Markdown table displaying EVERY record with its individual columns (e.g. Invoice ID, Invoice Number, Vendor ID, Amount, Status, Due Date). NEVER replace, omit, or collapse the records into a high-level count summary table (e.g., do NOT just show 'Total Invoices: 50'). Display the actual row-by-row data. State clearly how many records are being shown (e.g. 'Showing X records...'). If the user requested more records than the system query limit (e.g. asking for 300 records when the maximum limit is 100), explicitly inform the user that only 100 records are being shown due to the query limit.

DSO EVALUATION RULES:
Formula: DSO Days = round((Total Accounts Receivable / Total Credit Sales) * Period Days, 2).
Tiers:
- OPTIMAL: DSO <= 45 days
- MODERATE: DSO > 45 and <= 60 days
- HIGH_RISK: DSO > 60 days

RECOMMENDED ACTIONS GUIDELINE:
When suggesting recommended_actions in the output schema, suggest ONLY supported application queries and actions that this system can actually perform (e.g. 'Inspect status for invoice [invoice_num]', 'Calculate DSO metrics for accounts receivable', 'Show recent AP invoices'). Do NOT suggest offline manual tasks or administrative procedures like manually approving invoices or issuing physical checks.

STRICT QUERY LIMIT:
Execute at most 1 SQL query per request to apps.AP_INVOICES_ALL or apps.AR_PAYMENT_SCHEDULES_ALL. Do NOT retry or probe other tables if no records match. Immediately output the JSON response.
"""


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "agent": "financial_agent"}


@app.post("/analyze-financials", response_model=FinancialAnalysisResponse)
def analyze_financials(
    request: FinancialQueryRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> FinancialAnalysisResponse:
    """Endpoint where Gemini handles reasoning, SQL generation, & decoding."""
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query cannot be empty",
        )

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI financial reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        f"Analyze financial metrics and invoices for query: '{request.query}'."
        " If the query asks to list invoices or schedules in a table, "
        "query the relevant database tables and provide the full Markdown "
        "table of all retrieved records in the `summary`. Indicate the "
        "number of records shown and clarify if the 100-record limit "
        "capped a larger request."
    )

    try:
        response = generate_content_with_models(
            ai_client=ai_client,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[execute_oracle_sql],
                response_mime_type="application/json",
                response_schema=FinancialAnalysisResponse,
                temperature=0.1,
            ),
        )
        if response and response.text:
            return FinancialAnalysisResponse.model_validate_json(response.text)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Gemini financial reasoning error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI financial reasoning unavailable or failed",
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI financial reasoning unavailable or failed",
    )


@app.post("/invoice-status", response_model=InvoiceStatusResponse)
def get_invoice_status(
    request: InvoiceStatusRequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Retrieve invoice and payment status using Gemini Flash."""
    raw_invoice = request.invoice_number or request.invoice_num
    target_invoice = raw_invoice.strip() if raw_invoice else None
    if (
        not target_invoice
        and request.invoice_id is None
        and request.vendor_id is None
    ):
        err = (
            "At least one query parameter (invoice_num, invoice_id, "
            "vendor_id) must be specified"
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err,
        )

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI financial reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    target_invoice = request.invoice_num or request.invoice_number
    filter_desc = []
    if target_invoice:
        filter_desc.append(f'invoice_num="{target_invoice}"')
    if request.invoice_id is not None:
        filter_desc.append(f"invoice_id={request.invoice_id}")
    if request.vendor_id is not None:
        filter_desc.append(f"vendor_id={request.vendor_id}")

    filter_str = ", ".join(filter_desc)
    prompt = (
        "Inspect invoice status in apps.AP_INVOICES_ALL for filters: "
        f"{filter_str}. "
        "Query apps.AP_INVOICES_ALL i (optionally LEFT JOIN "
        "apps.AP_PAYMENT_SCHEDULES_ALL ps ON i.invoice_id = ps.invoice_id to "
        "retrieve due_date, or select NULL as due_date) to retrieve "
        "invoice_id, invoice_num, vendor_id, invoice_amount, "
        "payment_status_flag, wfapproval_status (as approval_status), and "
        "due_date. Use case-insensitive matching UPPER(i.invoice_num) = "
        f"UPPER('{target_invoice}') when filtering by invoice_num. "
        "If no matching invoice is found, set total_found to 0, "
        'invoices to [], and status to "NOT_FOUND". In the summary or notes, '
        "include the full Markdown table of retrieved invoices."
    )

    try:
        response = generate_content_with_models(
            ai_client=ai_client,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[execute_oracle_sql],
                response_mime_type="application/json",
                response_schema=InvoiceStatusResponse,
                temperature=0.1,
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Gemini invoice-status query error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found in Accounts Payable",
        ) from exc
    if response and response.text:
        res_obj = InvoiceStatusResponse.model_validate_json(response.text)
        if (
            res_obj.total_found == 0
            or not res_obj.invoices
            or res_obj.status == "NOT_FOUND"
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found in Accounts Payable",
            )
        out = res_obj.model_dump()
        out["query_params"] = request.model_dump()
        out["status"] = "SUCCESS"
        out["total_found"] = len(res_obj.invoices)
        for inv in out.get("invoices", []):
            if "invoice_num" in inv and "INVOICE_NUM" not in inv:
                inv["INVOICE_NUM"] = inv["invoice_num"]
            if "vendor_id" in inv and "VENDOR_ID" not in inv:
                inv["VENDOR_ID"] = inv["vendor_id"]
            if "invoice_amount" in inv and "INVOICE_AMOUNT" not in inv:
                inv["INVOICE_AMOUNT"] = inv["invoice_amount"]
            if "invoice_id" in inv and "INVOICE_ID" not in inv:
                inv["INVOICE_ID"] = inv["invoice_id"]
            if (
                "payment_status_flag" in inv
                and "PAYMENT_STATUS_FLAG" not in inv
            ):
                inv["PAYMENT_STATUS_FLAG"] = inv["payment_status_flag"]
            if "approval_status" in inv and "APPROVAL_STATUS" not in inv:
                inv["APPROVAL_STATUS"] = inv["approval_status"]
            if "due_date" in inv and "DUE_DATE" not in inv:
                inv["DUE_DATE"] = inv["due_date"]
        return out

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI financial reasoning unavailable or failed",
    )


@app.post("/calculate-dso", response_model=DSOResponse)
def calculate_dso(
    request: DSORequest,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> DSOResponse:
    """Calculate Days Sales Outstanding (DSO) metrics using Gemini Flash."""
    if request.period_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_days must be greater than zero for DSO calculation",
        )

    if (
        request.total_credit_sales is not None
        and request.total_credit_sales <= 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total credit sales must be > 0 for DSO calculation",
        )

    ar_balance = (
        request.total_accounts_receivable
        if request.total_accounts_receivable is not None
        else request.total_receivables
    )
    if ar_balance is not None and ar_balance < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Total accounts receivable cannot be negative for DSO"
                " calculation"
            ),
        )

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI financial reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)

    provided_metrics = []
    if ar_balance is not None:
        provided_metrics.append(f"total_accounts_receivable={ar_balance}")
    if request.total_credit_sales is not None:
        provided_metrics.append(
            f"total_credit_sales={request.total_credit_sales}"
        )

    metrics_str = ", ".join(provided_metrics) if provided_metrics else "None"
    prompt = (
        f"Calculate Days Sales Outstanding (DSO) for period_days="
        f"{request.period_days}. Provided metrics: {metrics_str}. "
        "If metrics are not provided, query apps.AR_PAYMENT_SCHEDULES_ALL "
        "using execute_oracle_sql to evaluate total receivables "
        "(SUM of amount_due_remaining) and total credit sales "
        "(SUM of amount_due_original). If total credit sales is 0 or "
        "metrics cannot be retrieved, set evaluation to 'MISSING_METRICS'. "
        "Otherwise, calculate DSO as round((total_accounts_receivable / "
        "total_credit_sales) * period_days, 2) and evaluate tier: OPTIMAL "
        "(<= 45 days), MODERATE (<= 60 days), or HIGH_RISK (> 60 days)."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=DSOResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        dso_obj = DSOResponse.model_validate_json(response.text)
        if (
            dso_obj.evaluation == "MISSING_METRICS"
            or dso_obj.total_credit_sales <= 0
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing required financial metrics to calculate DSO",
            )
        return dso_obj

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI financial reasoning unavailable or failed",
    )


@app.post("/recent-invoices", response_model=RecentInvoicesResponse)
@app.get("/recent-invoices", response_model=RecentInvoicesResponse)
def get_recent_invoices(
    request: Optional[InvoiceListRequest] = None,
    limit: int = 50,
    offset: int = 0,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Retrieve recent AP invoices using Gemini Flash."""
    raw_limit = request.limit if request else limit
    raw_offset = request.offset if request else offset
    if raw_limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be greater than 0",
        )
    rec_limit = min(raw_limit, 100)
    rec_offset = max(0, raw_offset)

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI financial reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    vendor_filter = (
        f"for vendor_id={request.vendor_id}"
        if request and request.vendor_id is not None
        else ""
    )

    prompt = (
        f"Query apps.AP_INVOICES_ALL to retrieve recent invoices "
        f"{vendor_filter} (limit: {rec_limit}, offset: {rec_offset}) "
        "ordered by invoice_id DESC. Populate the `invoices` list with every "
        "retrieved invoice record including invoice_id, invoice_num, "
        "vendor_id, invoice_amount, payment_status_flag, approval_status, "
        "and due_date. Render the full Markdown table displaying every "
        "record with its individual columns. State how many records are "
        "being shown, noting if the 100-record query limit capped a larger "
        "request."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=RecentInvoicesResponse,
            temperature=0.1,
        ),
    )
    if getattr(execute_oracle_sql, "db_error", None):
        raise getattr(execute_oracle_sql, "db_error")
    if response and response.text:
        res_obj = RecentInvoicesResponse.model_validate_json(response.text)
        out = res_obj.model_dump()
        out["status"] = "SUCCESS"
        for inv in out.get("invoices", []):
            if "invoice_num" in inv and "INVOICE_NUM" not in inv:
                inv["INVOICE_NUM"] = inv["invoice_num"]
            if "vendor_id" in inv and "VENDOR_ID" not in inv:
                inv["VENDOR_ID"] = inv["vendor_id"]
            if "invoice_amount" in inv and "INVOICE_AMOUNT" not in inv:
                inv["INVOICE_AMOUNT"] = inv["invoice_amount"]
            if "invoice_id" in inv and "INVOICE_ID" not in inv:
                inv["INVOICE_ID"] = inv["invoice_id"]
            if (
                "payment_status_flag" in inv
                and "PAYMENT_STATUS_FLAG" not in inv
            ):
                inv["PAYMENT_STATUS_FLAG"] = inv["payment_status_flag"]
            if "approval_status" in inv and "APPROVAL_STATUS" not in inv:
                inv["APPROVAL_STATUS"] = inv["approval_status"]
            if "due_date" in inv and "DUE_DATE" not in inv:
                inv["DUE_DATE"] = inv["due_date"]
        return out

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI financial reasoning unavailable or failed",
    )


@app.post("/receivables", response_model=ReceivablesResponse)
@app.get("/receivables", response_model=ReceivablesResponse)
def get_receivables_and_dso(
    request: Optional[ReceivablesRequest] = None,
    period_days: int = 90,
    db_client: EBSDatabaseClient = Depends(get_db_client),
) -> Dict[str, Any]:
    """Calculate AR Accounts Receivable & DSO metrics using Gemini Flash."""
    p_days = request.period_days if request else period_days
    if p_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_days must be greater than 0",
        )

    ai_client = get_ai_client()
    if not ai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI financial reasoning unavailable or failed",
        )

    execute_oracle_sql = make_execute_oracle_sql(db_client)
    prompt = (
        f"Query apps.AR_PAYMENT_SCHEDULES_ALL over period_days={p_days} to "
        "evaluate total receivables (SUM of amount_due_remaining) and total "
        "credit sales (SUM of amount_due_original). Calculate dso_days as "
        "round((total_receivables / total_credit_sales) * period_days, 1). "
        "Set health to 'HEALTHY' if dso_days <= 45.0 else 'WARNING'."
    )

    response = generate_content_with_models(
        ai_client=ai_client,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[execute_oracle_sql],
            response_mime_type="application/json",
            response_schema=ReceivablesResponse,
            temperature=0.1,
        ),
    )
    if response and response.text:
        res_obj = ReceivablesResponse.model_validate_json(response.text)
        out = res_obj.model_dump()
        out["TOTAL_RECEIVABLES"] = out["total_receivables"]
        out["TOTAL_CREDIT_SALES"] = out["total_credit_sales"]
        out["DSO_DAYS"] = out["dso_days"]
        return out

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI financial reasoning unavailable or failed",
    )


def register_with_a2a(
    discovery_server_url: Optional[str] = None,
) -> bool:
    """Register Financial Agent with the A2A Discovery Server."""
    target_url = discovery_server_url or os.getenv(
        "A2A_SERVER_URL", "http://127.0.0.1:8080"
    )
    card = AgentCard(
        name="financial_agent",
        description=(
            "Specialized agent for AP invoices list, Accounts Payable "
            "status, Days Sales Outstanding (DSO), & Financial Analysis"
        ),
        endpoint_url=os.getenv("FINANCIAL_AGENT_URL", "http://127.0.0.1:8002"),
        version="2.0.0",
        capabilities=[
            "invoice_status",
            "ap_invoices",
            "dso_metrics",
            "financial_analytics",
            "analyze_financials",
            "recent_invoices",
            "receivables",
        ],
        endpoints={
            "analyze-financials": "/analyze-financials",
            "invoice-status": "/invoice-status",
            "calculate-dso": "/calculate-dso",
            "recent-invoices": "/recent-invoices",
            "receivables": "/receivables",
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
                    "Successfully registered financial_agent with A2A server"
                )
                return True
    except (httpx.HTTPError, OSError) as exc:
        logger.warning(
            "Failed to auto-register financial_agent with A2A server (%s)", exc
        )
    return False
