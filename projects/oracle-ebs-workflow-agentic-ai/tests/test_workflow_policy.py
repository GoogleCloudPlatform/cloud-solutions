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

"""Unit tests for the Corporate Policy Verification Engine."""

from src.a2a.schemas import NotificationItem
from src.workflow.policy import PolicyEngine


def test_apex_compliant_expense() -> None:
    """Test standard compliant expense report under $1,000 with receipts."""
    item = NotificationItem(
        notification_id=101,
        message_type="APEXP",
        message_name="EXP_MSG",
        recipient_role="MGR",
        amount=450.0,
    )
    attrs = {
        "EXP_REPORT_TOTAL": 450.0,
        "HAS_RECEIPTS": "Y",
        "WEEKEND_SPEND": "N",
    }
    res = PolicyEngine.evaluate(item, attrs)
    assert res.compliance_status == "COMPLIANT"
    assert res.risk_level == "LOW"
    assert res.recommendation == "APPROVE"
    assert len(res.violations) == 0


def test_apex_missing_receipt_high_risk() -> None:
    """Test high-risk flag for expense over $75 with missing receipt."""
    item = NotificationItem(
        notification_id=102,
        message_type="APEXP",
        message_name="EXP_MSG",
        recipient_role="MGR",
        amount=150.0,
    )
    attrs = {"EXP_REPORT_TOTAL": 150.0, "HAS_RECEIPTS": "N"}
    res = PolicyEngine.evaluate(item, attrs)
    assert res.risk_level == "HIGH"
    assert res.compliance_status == "FLAGGED_FOR_REVIEW"
    assert any(v.code == "POLICY_MISSING_RECEIPT" for v in res.violations)
    assert res.recommendation == "ESCALATE"


def test_apex_executive_tier_and_weekend() -> None:
    """Test executive threshold ($5,000+) and weekend transaction flag."""
    item = NotificationItem(
        notification_id=103,
        message_type="APEXP",
        message_name="EXP_MSG",
        recipient_role="MGR",
        amount=6200.0,
    )
    attrs = {
        "EXP_REPORT_TOTAL": 6200.0,
        "HAS_RECEIPTS": "Y",
        "WEEKEND_SPEND": "Y",
    }
    res = PolicyEngine.evaluate(item, attrs)
    assert res.risk_level == "HIGH"
    assert any(v.code == "EXPENSE_TIER_2_EXCEEDED" for v in res.violations)
    assert any(v.code == "POLICY_WEEKEND_SPEND_FLAG" for v in res.violations)


def test_poappr_unapproved_vendor_critical() -> None:
    """Test critical rejection recommendation for unapproved vendor."""
    item = NotificationItem(
        notification_id=201,
        message_type="POAPPR",
        message_name="PO_MSG",
        recipient_role="DIR",
        amount=15000.0,
    )
    attrs = {"PO_AMOUNT": 15000.0, "VENDOR_STATUS": "PROBATIONARY"}
    res = PolicyEngine.evaluate(item, attrs)
    assert res.risk_level == "CRITICAL"
    assert res.compliance_status == "NON_COMPLIANT"
    assert res.recommendation == "REJECT"
    assert any(v.code == "POLICY_UNAPPROVED_SUPPLIER" for v in res.violations)


def test_poappr_limits_and_after_the_fact() -> None:
    """Test buyer limit exceedance and after-the-fact spend violation."""
    item = NotificationItem(
        notification_id=202,
        message_type="POAPPR",
        message_name="PO_MSG",
        recipient_role="DIR",
        amount=35000.0,
    )
    attrs = {
        "PO_AMOUNT": 35000.0,
        "VENDOR_STATUS": "APPROVED",
        "AFTER_THE_FACT": "Y",
    }
    res = PolicyEngine.evaluate(item, attrs)
    assert res.risk_level == "HIGH"
    assert any(v.code == "PO_EXCEEDS_BUYER_LIMIT" for v in res.violations)
    assert any(v.code == "POLICY_AFTER_THE_FACT_PO" for v in res.violations)


def test_reqappr_suspected_split_requisition() -> None:
    """Test suspected split order threshold near $10,000."""
    item = NotificationItem(
        notification_id=301,
        message_type="REQAPPR",
        message_name="REQ_MSG",
        recipient_role="MGR",
        amount=9850.0,
        subject="Hardware purchases",
    )
    attrs = {"REQ_AMOUNT": 9850.0, "JUSTIFICATION": "Valid department project"}
    res = PolicyEngine.evaluate(item, attrs)
    assert res.risk_level == "HIGH"
    assert any(
        v.code == "POLICY_SUSPECTED_SPLIT_REQUISITION" for v in res.violations
    )


def test_format_risk_alert_badges() -> None:
    """Test formatting of markdown risk alert badges across risk tiers."""
    item_low = NotificationItem(
        notification_id=1,
        message_type="APEXP",
        message_name="M",
        recipient_role="R",
    )
    res_low = PolicyEngine.evaluate(item_low, {})
    alert_low = PolicyEngine.format_risk_alert(res_low)
    assert "Policy Compliant" in alert_low

    item_crit = NotificationItem(
        notification_id=2,
        message_type="POAPPR",
        message_name="M",
        recipient_role="R",
    )
    res_crit = PolicyEngine.evaluate(item_crit, {"VENDOR_STATUS": "UNAPPROVED"})
    alert_crit = PolicyEngine.format_risk_alert(res_crit)
    assert "CRITICAL POLICY VIOLATION" in alert_crit


def test_apex_under_75_without_receipt_is_compliant() -> None:
    """Verify expenses <= $75.00 do not require itemized receipts."""
    item = NotificationItem(
        notification_id=104,
        message_type="APEXP",
        message_name="EXP_MSG",
        recipient_role="MGR",
        amount=65.0,
    )
    attrs = {"EXP_REPORT_TOTAL": 65.0, "HAS_RECEIPTS": "N"}
    res = PolicyEngine.evaluate(item, attrs)
    assert res.compliance_status == "COMPLIANT"
    assert res.risk_level == "LOW"
    assert len(res.violations) == 0
