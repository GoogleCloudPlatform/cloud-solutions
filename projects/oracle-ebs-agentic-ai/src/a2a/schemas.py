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

"""Pydantic schemas for Oracle EBS A2A Agentic AI services."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

SAFE_EXCEPTIONS = (Exception,)


class StockCheckRequest(BaseModel):
    """Payload for inventory stock level verification."""

    item_code: Optional[str] = Field(
        default=None,
        description="The unique item code segment in MTL_SYSTEM_ITEMS_B",
    )
    item_id: Optional[str] = Field(
        default=None,
        description="Oracle EBS Inventory Item ID or Segment Code",
    )
    organization_id: Optional[int] = Field(
        default=None, description="Oracle Inventory Organization ID (e.g. 204)"
    )
    organization_code: Optional[str] = Field(
        default=None,
        description="Oracle Inventory Organization Code (e.g. V1, AD1)",
    )
    min_threshold: float = Field(
        default=10.0,
        description="Minimum acceptable on-hand quantity threshold",
    )


class StockCheckResponse(BaseModel):
    """Response model for stock check analysis."""

    item_id: str
    organization_id: int
    on_hand_quantity: float
    min_threshold: float
    below_threshold: bool
    stock_status: str
    recommended_actions: List[str]
    details: Dict[str, Any]


class InvoiceStatusRequest(BaseModel):
    """Payload for invoice status inspection."""

    invoice_num: Optional[str] = Field(
        default=None, description="The invoice number in AP_INVOICES_ALL"
    )
    invoice_number: Optional[str] = Field(
        default=None, description="Invoice identifier number"
    )
    vendor_id: Optional[int] = Field(
        default=None, description="Vendor / Supplier PO Vendor ID"
    )
    invoice_id: Optional[int] = Field(
        default=None, description="Oracle AP Invoice ID"
    )


class InvoiceStatusResponse(BaseModel):
    """Response model for invoice status inspection."""

    summary: str
    total_found: int
    status: str
    invoices: List[Dict[str, Any]]
    recommended_actions: List[str]
    details: Dict[str, Any]


class DSOCalculationRequest(BaseModel):
    """Request payload for Days Sales Outstanding (DSO) metrics."""

    customer_id: Optional[str] = Field(
        default=None, description="Oracle AR Customer Account Number or ID"
    )
    period_days: int = Field(
        default=90,
        gt=0,
        description="Historical period in days for DSO calculation",
    )
    total_accounts_receivable: Optional[float] = Field(
        default=None, description="Total outstanding AR balance"
    )
    total_credit_sales: Optional[float] = Field(
        default=None, description="Total credit sales for the period"
    )


class DSOCalculationResponse(BaseModel):
    """Response model for Days Sales Outstanding (DSO) calculation."""

    dso_days: float
    period_days: int
    total_receivables: float
    credit_sales: float
    performance_status: str
    recommendations: List[str]
    details: Dict[str, Any]


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
        default=None, description="Target quantity float"
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
    """Response model for PO restock negotiation."""

    supplier_id: Optional[int] = Field(
        default=None, description="Oracle PO Supplier / Vendor ID"
    )
    supplier_name: str = Field(description="Vendor or Supplier name")
    item_id: Optional[str] = Field(
        default=None, description="Inventory item ID or SKU"
    )
    target_unit_price: float = Field(description="Target unit price")
    counter_unit_price: float = Field(description="Counter-offer unit price")
    accepted: bool = Field(description="Whether negotiation terms are accepted")
    negotiated_terms: Optional[str] = Field(
        default=None, description="Negotiated payment terms"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Negotiation notes or counter-offer rationale",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Legacy fields
    po_number: Optional[str] = Field(
        default=None, description="Oracle EBS Purchase Order Number"
    )
    quantity: Optional[int] = Field(default=None, description="Order quantity")
    savings_pct: Optional[float] = Field(
        default=None, description="Savings percentage"
    )
    summary: Optional[str] = Field(
        default=None, description="Summary statement"
    )
    negotiation_notes: List[str] = Field(
        default_factory=list, description="List of notes"
    )


class OrganizationListRequest(BaseModel):
    """Request model for listing organizations."""

    limit: int = Field(
        default=50, gt=0, le=100, description="Maximum organizations to return"
    )


class ItemListRequest(BaseModel):
    """Request model for listing inventory items."""

    organization_id: Optional[int] = Field(
        default=None, description="Filter by Organization ID"
    )
    organization_code: Optional[str] = Field(
        default=None, description="Filter by Organization Code (e.g. V1, PR4)"
    )
    limit: int = Field(
        default=50, gt=0, le=100, description="Maximum records to return"
    )


class ItemListResponse(BaseModel):
    """Response model for inventory items catalog listing."""

    status: str
    total_found: int
    organization_id: int
    organization_code: str
    items: List[Dict[str, Any]]


class SupplierListRequest(BaseModel):
    """Request model for listing approved suppliers."""

    limit: int = Field(
        default=50, gt=0, description="Maximum suppliers to return"
    )


class SupplierListResponse(BaseModel):
    """Response model for listing approved suppliers."""

    status: str
    total_suppliers: int
    suppliers: List[Dict[str, Any]]


class ItemSuppliersRequest(BaseModel):
    """Request payload for finding suppliers for a specific item."""

    item_code: str = Field(..., description="Unique item segment code")
    organization_id: Optional[int] = Field(
        default=None,
        description="Optional Oracle Inventory Organization ID filter",
    )


class ItemSuppliersResponse(BaseModel):
    """Response payload for item approved suppliers."""

    item_code: str
    organization_id: Optional[int] = None
    total_suppliers: int
    primary_supplier_id: Optional[int]
    primary_supplier_name: Optional[str]
    suppliers: List[Dict[str, Any]]


class InvoiceListRequest(BaseModel):
    """Request model for listing recent AP invoices."""

    limit: int = Field(
        default=50, gt=0, le=100, description="Maximum invoices to return"
    )
    vendor_id: Optional[int] = Field(
        default=None, description="Optional vendor ID filter"
    )


class SupplierItemEntry(BaseModel):
    """Individual item record supplied by an Oracle EBS vendor."""

    inventory_item_id: Optional[int] = Field(
        default=None, description="Oracle Inventory Item ID"
    )
    item_code: str = Field(..., description="Oracle Item Segment Code")
    description: Optional[str] = Field(
        default=None, description="Item Description"
    )
    unit_price: Optional[float] = Field(
        default=None, description="Purchase Order Unit Price"
    )
    organization_id: Optional[int] = Field(
        default=None, description="Inventory Organization ID"
    )
    po_number: Optional[str] = Field(
        default=None, description="Associated PO Number"
    )


class SupplierItemsRequest(BaseModel):
    """Request payload for querying items supplied by a specific vendor."""

    supplier_id: Optional[int] = Field(
        default=None, description="Oracle EBS Supplier / Vendor ID (e.g. 515)"
    )
    supplier_name: Optional[str] = Field(
        default=None, description="Oracle EBS Supplier / Vendor Name"
    )
    limit: int = Field(
        default=50, gt=0, le=100, description="Max items to retrieve (1-100)"
    )


class SupplierItemsResponse(BaseModel):
    """Response payload for items supplied by an Oracle EBS vendor."""

    supplier_id: Optional[int] = Field(
        default=None, description="Queried Supplier ID"
    )
    supplier_name: Optional[str] = Field(
        default=None, description="Queried Supplier Name"
    )
    total_items: int = Field(default=0, description="Total items supplied")
    items: List[SupplierItemEntry] = Field(
        default_factory=list, description="Items supplied by this vendor"
    )
    status: str = Field(default="SUCCESS", description="Operation status")
    notes: Optional[str] = Field(
        default=None, description="Detailed markdown table of items"
    )
