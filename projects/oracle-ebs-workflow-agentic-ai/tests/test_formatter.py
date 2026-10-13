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

"""Unit tests for Markdown synthesis and table formatting utilities."""

import pytest
from src.a2a import formatter
from src.a2a.formatter import (
    clean_html_markup,
    render_evaluations_table,
    render_full_items_table,
    render_results_table,
    render_single_notification_detail,
    synthesize_response,
)


def test_clean_html_markup() -> None:
    """Verify HTML tags, line breaks, and entities are sanitized."""
    assert clean_html_markup("") == ""
    raw = "<p>Approve &amp; review<br/>Item <b>#1001</b></p>"
    cleaned = clean_html_markup(raw)
    assert "Approve & review" in cleaned
    assert "#1001" in cleaned
    assert "<p>" not in cleaned


def test_render_full_items_table() -> None:
    """Verify Markdown table rendering across LOW, HIGH, and CRITICAL risks."""
    items = [
        {
            "notification_id": 1001,
            "message_type": "APEXP",
            "subject": "Expense | Report",
            "requester": "JDOE",
            "amount": 325.0,
            "risk_level": "LOW",
            "recommended_action": "APPROVE",
        },
        {
            "notification_id": 2002,
            "message_type": "POAPPR",
            "subject": "PO-9910",
            "requester": "RROE",
            "amount": 120000.0,
            "risk_level": "CRITICAL",
            "recommended_action": "REJECT",
        },
    ]
    md = render_full_items_table(items)
    assert "Showing 2 notification(s):" in md
    assert "| 1001 | APEXP | Expense / Report | JDOE | $325.00 |" in md
    assert "🟢 LOW" in md
    assert "🚨 CRITICAL" in md


def test_render_evaluations_table() -> None:
    """Verify policy evaluations table sorting and violation rendering."""
    evals = [
        {
            "notification_id": 1001,
            "message_type": "APEXP",
            "amount": 325.0,
            "compliance_status": "COMPLIANT",
            "risk_level": "LOW",
            "recommendation": "APPROVE",
            "violations": [],
        },
        {
            "notification_id": 2002,
            "message_type": "POAPPR",
            "amount": 120000.0,
            "compliance_status": "NON_COMPLIANT",
            "risk_level": "CRITICAL",
            "recommendation": "REJECT",
            "violations": [
                {"code": "UNAPPROVED_VENDOR", "message": "Probationary vendor"}
            ],
        },
    ]
    md = render_evaluations_table(evals)
    assert "Corporate Policy & Compliance Evaluation (2 item(s))" in md
    assert md.index("2002") < md.index("1001")
    assert "UNAPPROVED_VENDOR: Probationary vendor" in md


def test_render_results_table() -> None:
    """Verify execution results table renders processed and failed items."""
    empty_md = render_results_table({"action": "APPROVE"})
    assert "No items were processed." in empty_md

    raw = {
        "action": "APPROVE",
        "processed_items": [
            {
                "notification_id": 1001,
                "status": "SUCCESS",
                "execution_path": "REST",
                "message": "Approved cleanly",
            }
        ],
        "failed_items": [
            {
                "notification_id": 9999,
                "status": "FAILED",
                "execution_path": "REST",
                "error": "Notification not found",
            }
        ],
    }
    md = render_results_table(raw)
    assert "✅ SUCCESS" in md
    assert "❌ FAILED" in md
    assert "Notification not found" in md


def test_render_single_notification_detail() -> None:
    """Verify single notification detail rendering and attribute filtering."""
    hdr = {
        "notification_id": 1001,
        "message_type": "APEXP",
        "status": "OPEN",
        "recipient_role": "JDOE",
        "subject": "Expense Report EXP-501",
        "amount": 325.0,
        "begin_date": "2026-09-10",
        "due_date": "2026-09-17",
    }
    raw = {
        "attributes": {
            "JUSTIFICATION": "Client workshop travel",
            "#INTERNAL": "skip",
            "HTML_BODY": "<p>Detailed travel breakdown</p>",
        }
    }
    md = render_single_notification_detail(hdr, raw)
    assert "### 📋 Notification #1001 Details" in md
    assert "**JUSTIFICATION**: Client workshop travel" in md
    assert "#INTERNAL" not in md
    assert "Detailed travel breakdown" in md


def test_synthesize_response_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify synthesize_response handles status, gates, and worklists."""
    monkeypatch.setattr(formatter, "get_ai_client", lambda: None)

    direct = synthesize_response({"text": "Hello user"}, "Hi")
    assert direct == "Hello user"

    err = synthesize_response(
        {"status": "ERROR", "detail": "Invalid ID"}, "Check 999"
    )
    assert "Oracle EBS Workflow Notice" in err
    assert "Invalid ID" in err

    gate = synthesize_response(
        {
            "status": "CONFIRMATION_REQUIRED",
            "proposal": {
                "action": "APPROVE",
                "notification_ids": [1001],
                "total_financial_impact": 325.0,
                "risk_summary": "Low risk",
                "confirmation_prompt": "Confirm approval?",
            },
        },
        "Approve 1001",
    )
    assert "Human Confirmation Gate Required" in gate
    assert "$325.00" in gate

    empty_recip = synthesize_response(
        {"items": [], "recipient": "JDOE"}, "List"
    )
    assert "No pending notifications found for recipient `JDOE`" in empty_recip

    triage = synthesize_response(
        {
            "items": [
                {
                    "notification_id": 1001,
                    "message_type": "APEXP",
                    "subject": "Expense",
                    "amount": 325.0,
                }
            ],
            "total_pending": 1,
            "high_risk_notifications": [],
            "risk_alerts": ["1001 compliant"],
            "proactive_next_steps": ["Approve 1001"],
        },
        "Triage worklist",
    )
    assert "Workflow Triage Summary" in triage
    assert "Recommended Next Steps" in triage


def test_render_full_items_table_evaluates_missing_risk_level() -> None:
    """Verify raw APEXP, POAPPR, and REQAPPR items compute policy risk."""
    raw_items = [
        {
            "notification_id": 1005,
            "message_type": "APEXP",
            "subject": "Executive Travel Expense Report",
            "recipient_role": "JDOE",
            "amount": 6500.0,
        },
        {
            "notification_id": 2002,
            "message_type": "POAPPRV",
            "subject": "Vision Operations - Standard Purchase Order 6502, 0",
            "recipient_role": "RROE",
            "amount": 440000.0,
        },
        {
            "notification_id": 3003,
            "message_type": "REQAPPR",
            "subject": "CapEx Server Cluster Requisition",
            "recipient_role": "KLEE",
            "amount": 65000.0,
        },
    ]
    table_md = render_full_items_table(raw_items)
    assert "| 1005 | APEXP |" in table_md
    assert "| 2002 | POAPPRV |" in table_md
    assert "| 3003 | REQAPPR |" in table_md
    assert table_md.count("⚠️ HIGH") == 3
    assert table_md.count("| ESCALATE |") == 3

    for raw_item in raw_items:
        detail_md = render_single_notification_detail(
            raw_item, {"attributes": {}}
        )
        assert "- **Risk Status**: ⚠️ HIGH" in detail_md
        assert "- **Recommended Action**: `ESCALATE`" in detail_md
