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

"""Oracle EBS Skills and NL2SQL LLM Engine."""

import logging
from typing import Any, Callable, Dict, List, Optional

from src.gemini_cli_extensions.oracle import ExecutionEngine

logger = logging.getLogger(__name__)

ORACLE_EBS_SCHEMA_PROMPT = (
    "You are an expert Oracle EBS Database SQL Translator.\n"
    "Target Schema Tables:\n"
    "1. AP_INVOICES_ALL (INVOICE_ID, INVOICE_NUM, VENDOR_ID, INVOICE_AMOUNT, "
    "PAYMENT_STATUS_FLAG, WFAPPROVAL_STATUS, DUE_DATE)\n"
    "2. MTL_ONHAND_QUANTITIES_DETAIL (INVENTORY_ITEM_ID, ORGANIZATION_ID, "
    "TRANSACTION_QUANTITY, PRIMARY_TRANSACTION_QUANTITY, DESCRIPTION, "
    "ITEM_CODE)\n"
    "3. AR_PAYMENT_SCHEDULES_ALL (PAYMENT_SCHEDULE_ID, CUSTOMER_ID, "
    "AMOUNT_DUE_REMAINING, AMOUNT_DUE_ORIGINAL, DUE_DATE)\n"
    "4. PO_HEADERS_ALL (PO_HEADER_ID, VENDOR_ID, SEGMENT1, TYPE_LOOKUP_CODE)\n"
    "5. PO_LINES_ALL (PO_LINE_ID, PO_HEADER_ID, ITEM_ID, UNIT_PRICE, "
    "QUANTITY)\n\n"
    "Convert the natural language request into a valid Oracle SQL query with "
    "appropriate WHERE clauses."
)


class NLToSQLEngine:
    """Oracle Skills NL-to-SQL Translation Engine.

    Translates domain-specific natural language prompts into optimized SQL
    queries targeting Oracle E-Business Suite (EBS) schema tables using
    LLM prompt synthesis as primary with fallback table mapping.
    """

    def __init__(
        self,
        execution_engine: ExecutionEngine,
        llm_generator: Optional[
            Callable[[str, Optional[Dict[str, Any]]], str]
        ] = None,
    ) -> None:
        self.execution_engine = execution_engine
        self.llm_generator = llm_generator

    def generate_sql_via_llm(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Translate natural language prompt into SQL via LLM generator."""
        if not self.llm_generator:
            return None
        try:
            full_prompt = (
                f"{ORACLE_EBS_SCHEMA_PROMPT}\nContext:"
                f" {context}\nRequest: {prompt}"
            )
            generated_sql = self.llm_generator(full_prompt, context)
            if generated_sql and generated_sql.strip().upper().startswith(
                "SELECT"
            ):
                logger.info(
                    "LLM NL2SQL generated query: %s", generated_sql.strip()
                )
                return generated_sql.strip()
        except (ValueError, RuntimeError, OSError, TypeError) as exc:
            logger.warning(
                "LLM NL2SQL generation failed (%s); falling back",
                exc,
            )
        return None

    def _build_ap_invoices_sql(self, ctx: Dict[str, Any]) -> str:
        sql = (
            "SELECT INVOICE_ID, INVOICE_NUM, VENDOR_ID, INVOICE_AMOUNT, "
            "PAYMENT_STATUS_FLAG, WFAPPROVAL_STATUS, NULL AS DUE_DATE "
            "FROM AP_INVOICES_ALL"
        )
        where_clauses: List[str] = []
        if ctx.get("invoice_num"):
            inv_num = str(ctx["invoice_num"]).strip()
            where_clauses.append(
                f"(UPPER(INVOICE_NUM) = UPPER('{inv_num}') OR "
                f"UPPER(INVOICE_NUM) LIKE UPPER('%{inv_num}%'))"
            )
        if ctx.get("invoice_id") is not None:
            where_clauses.append(f'INVOICE_ID = {ctx["invoice_id"]}')
        if ctx.get("vendor_id") is not None:
            where_clauses.append(f'VENDOR_ID = {ctx["vendor_id"]}')

        if where_clauses:
            return sql + " WHERE " + " AND ".join(where_clauses)
        return sql + " WHERE ROWNUM <= 20"

    def _build_onhand_sql(self, ctx: Dict[str, Any]) -> str:
        sql = (
            "SELECT INVENTORY_ITEM_ID, ORGANIZATION_ID, "
            "TRANSACTION_QUANTITY, PRIMARY_TRANSACTION_QUANTITY, "
            "DESCRIPTION FROM MTL_ONHAND_QUANTITIES_DETAIL"
        )
        where_clauses: List[str] = []
        if ctx.get("item_id"):
            item_id = str(ctx["item_id"]).strip()
            if item_id.isdigit():
                where_clauses.append(f"INVENTORY_ITEM_ID = {item_id}")
            else:
                where_clauses.append(
                    "(UPPER(TO_CHAR(INVENTORY_ITEM_ID)) ="
                    f" UPPER('{item_id}') OR UPPER(SUBINVENTORY_CODE) ="
                    f" UPPER('{item_id}'))"
                )
        if ctx.get("organization_id") is not None:
            where_clauses.append(f'ORGANIZATION_ID = {ctx["organization_id"]}')

        if where_clauses:
            return sql + " WHERE " + " AND ".join(where_clauses)
        return sql + " WHERE ROWNUM <= 20"

    def _build_fallback_sql(self, prompt: str, tables: List[str]) -> str:
        if "AP_INVOICES_ALL" in tables:
            return "SELECT * FROM AP_INVOICES_ALL WHERE ROWNUM <= 20"
        if "MTL_ONHAND_QUANTITIES_DETAIL" in tables:
            return (
                "SELECT * FROM MTL_ONHAND_QUANTITIES_DETAIL WHERE ROWNUM <= 20"
            )
        if "AR_PAYMENT_SCHEDULES_ALL" in tables:
            return (
                "SELECT SUM(AMOUNT_DUE_REMAINING) AS TOTAL_AR, "
                "SUM(AMOUNT_DUE_ORIGINAL) AS TOTAL_SALES "
                "FROM AR_PAYMENT_SCHEDULES_ALL"
            )

        prompt_lower = prompt.lower()
        if "invoice" in prompt_lower:
            return "SELECT * FROM AP_INVOICES_ALL WHERE ROWNUM <= 20"
        if "stock" in prompt_lower or "inventory" in prompt_lower:
            return (
                "SELECT * FROM MTL_ONHAND_QUANTITIES_DETAIL WHERE ROWNUM <= 20"
            )
        if "dso" in prompt_lower or "receivable" in prompt_lower:
            return (
                "SELECT SUM(AMOUNT_DUE_REMAINING) AS TOTAL_AR, "
                "SUM(AMOUNT_DUE_ORIGINAL) AS TOTAL_SALES "
                "FROM AR_PAYMENT_SCHEDULES_ALL"
            )

        return "SELECT * FROM DUAL"

    def translate_prompt(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Translate natural language prompt into Oracle SQL query."""
        ctx = context or {}

        # 1. Primary: Use LLM for NL-to-SQL conversion
        llm_sql = self.generate_sql_via_llm(prompt, ctx)
        if llm_sql:
            return llm_sql

        # 2. Offline fallback: Basic table/prompt query selector
        tables = ctx.get("tables", [])
        if "AP_INVOICES_ALL" in tables:
            return self._build_ap_invoices_sql(ctx)
        if "MTL_ONHAND_QUANTITIES_DETAIL" in tables:
            return self._build_onhand_sql(ctx)

        return self._build_fallback_sql(prompt, tables)

    def translate_and_execute(
        self,
        natural_language_prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Translate natural language prompt and execute via engine."""
        sql_query = self.translate_prompt(natural_language_prompt, context)
        logger.info(
            "Oracle Skills translation: prompt='%s' -> sql='%s'",
            natural_language_prompt,
            sql_query,
        )
        return self.execution_engine.execute(sql_query, None)
