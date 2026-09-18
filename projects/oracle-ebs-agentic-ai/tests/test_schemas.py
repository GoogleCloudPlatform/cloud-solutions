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

"""Unit tests for centralized A2A Pydantic data schemas."""

from src.a2a.schemas import (
    DSOCalculationRequest,
    InvoiceStatusRequest,
    ItemListRequest,
    NegotiationRequest,
    StockCheckRequest,
)


def test_consolidated_a2a_schemas_import() -> None:
    """Verify shared Pydantic schemas import cleanly."""
    stock_req = StockCheckRequest(item_code="AS54888", organization_id=204)
    assert stock_req.item_code == "AS54888"
    assert stock_req.organization_id == 204

    inv_req = InvoiceStatusRequest(invoice_num="INV-2024-001")
    assert inv_req.invoice_num == "INV-2024-001"

    dso_req = DSOCalculationRequest(period_days=90)
    assert dso_req.period_days == 90

    neg_req = NegotiationRequest(item_code="AS54888", quantity=500)
    assert neg_req.quantity == 500

    item_req = ItemListRequest(organization_code="PR4", limit=25)
    assert item_req.organization_code == "PR4"
    assert item_req.limit == 25
