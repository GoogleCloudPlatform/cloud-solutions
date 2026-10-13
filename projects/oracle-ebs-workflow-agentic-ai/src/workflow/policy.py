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

"""Corporate Policy Verification Engine for Oracle EBS Workflows."""

from typing import Any, Literal

from src.a2a.schemas import (
    NotificationItem,
    PolicyEvaluation,
    PolicyViolation,
    extract_amount_from_attributes,
)


class PolicyEngine:
    """Enterprise policy validation rules for APEXP, POAPPR, and REQAPPR."""

    @staticmethod
    def resolve_amount(
        item: NotificationItem, attrs: dict[str, Any]
    ) -> float | None:
        """Resolve monetary amount from header, attributes, or subject."""
        if item.amount is not None:
            return item.amount
        resolved = extract_amount_from_attributes(attrs, item.subject)
        if resolved is not None:
            item.amount = resolved
        return resolved

    @classmethod
    def _evaluate_expense_report(
        cls, item: NotificationItem, attrs: dict[str, Any]
    ) -> tuple[list[PolicyViolation], str]:
        """Evaluate Expense Report (APEXP) against travel & expense policy."""
        violations: list[PolicyViolation] = []
        amount = cls.resolve_amount(item, attrs) or 0.0

        if amount > 5000.0:
            violations.append(
                PolicyViolation(
                    code="EXPENSE_TIER_2_EXCEEDED",
                    message=(
                        f"Expense total (${amount:,.2f}) exceeds executive "
                        "threshold ($5,000.00)."
                    ),
                    severity="HIGH",
                )
            )
        elif amount > 1000.0:
            violations.append(
                PolicyViolation(
                    code="EXPENSE_TIER_1_EXCEEDED",
                    message=(
                        f"Expense total (${amount:,.2f}) exceeds standard "
                        "manager tier ($1,000.00)."
                    ),
                    severity="MEDIUM",
                )
            )

        receipt_flag = str(
            attrs.get("HAS_RECEIPTS", attrs.get("RECEIPTS_ATTACHED", "Y"))
        ).upper()
        if amount > 75.0 and receipt_flag in ("N", "NO", "FALSE"):
            violations.append(
                PolicyViolation(
                    code="POLICY_MISSING_RECEIPT",
                    message=(
                        "Mandatory itemized receipt missing for expense "
                        "item exceeding $75.00."
                    ),
                    severity="HIGH",
                )
            )

        weekend_spend = str(
            attrs.get("WEEKEND_SPEND", attrs.get("WEEKEND_TRANSACTION", "N"))
        ).upper()
        if weekend_spend in ("Y", "YES", "TRUE"):
            violations.append(
                PolicyViolation(
                    code="POLICY_WEEKEND_SPEND_FLAG",
                    message=(
                        "Expense incurred on weekend/non-business day "
                        "without prior authorization."
                    ),
                    severity="MEDIUM",
                )
            )

        explanation = (
            f"Evaluated APEXP expense report total of ${amount:,.2f}. "
            f"Found {len(violations)} policy flags."
        )
        return violations, explanation

    @classmethod
    def _evaluate_purchase_order(
        cls, item: NotificationItem, attrs: dict[str, Any]
    ) -> tuple[list[PolicyViolation], str]:
        """Evaluate Purchase Order (POAPPR/POAPPRV) against policy."""
        violations: list[PolicyViolation] = []
        amount = cls.resolve_amount(item, attrs) or 0.0

        if amount > 100000.0:
            violations.append(
                PolicyViolation(
                    code="PO_EXCEEDS_MANAGER_LIMIT",
                    message=(
                        f"PO total (${amount:,.2f}) exceeds director/VP "
                        "limit ($100,000.00)."
                    ),
                    severity="HIGH",
                )
            )
        elif amount > 25000.0:
            violations.append(
                PolicyViolation(
                    code="PO_EXCEEDS_BUYER_LIMIT",
                    message=(
                        f"PO total (${amount:,.2f}) exceeds standard buyer "
                        "threshold ($25,000.00)."
                    ),
                    severity="MEDIUM",
                )
            )

        supplier_status = str(
            attrs.get("VENDOR_STATUS", attrs.get("SUPPLIER_STATUS", "APPROVED"))
        ).upper()
        if supplier_status in ("PROBATIONARY", "UNAPPROVED", "SUSPENDED"):
            violations.append(
                PolicyViolation(
                    code="POLICY_UNAPPROVED_SUPPLIER",
                    message=(
                        f"Vendor status is '{supplier_status}'; unapproved "
                        "suppliers require risk review."
                    ),
                    severity="CRITICAL",
                )
            )

        after_the_fact = str(attrs.get("AFTER_THE_FACT", "N")).upper()
        if after_the_fact in ("Y", "YES", "TRUE"):
            violations.append(
                PolicyViolation(
                    code="POLICY_AFTER_THE_FACT_PO",
                    message=(
                        "PO initiated after goods receipt or invoice arrival "
                        "(after-the-fact spend)."
                    ),
                    severity="HIGH",
                )
            )

        explanation = (
            f"Evaluated POAPPR purchase order total of ${amount:,.2f}. "
            f"Found {len(violations)} policy flags."
        )
        return violations, explanation

    @classmethod
    def _evaluate_requisition(
        cls, item: NotificationItem, attrs: dict[str, Any]
    ) -> tuple[list[PolicyViolation], str]:
        """Evaluate Purchase Requisition (REQAPPR/REQAPPRV) against policy."""
        violations: list[PolicyViolation] = []
        amount = cls.resolve_amount(item, attrs) or 0.0

        if amount > 50000.0:
            violations.append(
                PolicyViolation(
                    code="REQ_CAPEX_THRESHOLD",
                    message=(
                        f"Requisition total (${amount:,.2f}) exceeds CapEx "
                        "threshold ($50,000.00)."
                    ),
                    severity="HIGH",
                )
            )
        elif amount > 10000.0:
            violations.append(
                PolicyViolation(
                    code="REQ_HIGH_VALUE",
                    message=(
                        f"Requisition total (${amount:,.2f}) exceeds "
                        "department budget tier ($10,000.00)."
                    ),
                    severity="MEDIUM",
                )
            )

        split_suspect = str(attrs.get("SPLIT_REQUISITION", "N")).upper()
        if split_suspect in ("Y", "YES", "TRUE") or (
            9500.0 <= amount < 10000.0
        ):
            violations.append(
                PolicyViolation(
                    code="POLICY_SUSPECTED_SPLIT_REQUISITION",
                    message=(
                        "Transaction amount is just below $10,000 threshold "
                        "(potential split order)."
                    ),
                    severity="HIGH",
                )
            )

        justification = str(
            attrs.get("JUSTIFICATION", item.subject or "")
        ).strip()
        if len(justification) < 5:
            violations.append(
                PolicyViolation(
                    code="POLICY_INSUFFICIENT_JUSTIFICATION",
                    message=(
                        "Requisition lacks required business justification."
                    ),
                    severity="MEDIUM",
                )
            )

        explanation = (
            f"Evaluated REQAPPR requisition total of ${amount:,.2f}. "
            f"Found {len(violations)} policy flags."
        )
        return violations, explanation

    @classmethod
    def evaluate(
        cls, item: NotificationItem, attributes: dict[str, Any] | None = None
    ) -> PolicyEvaluation:
        """Run policy validation on a workflow notification."""
        attrs = attributes or {}
        msg_type = item.message_type.upper()

        resolved_amt = cls.resolve_amount(item, attrs)
        if msg_type == "APEXP":
            violations, explanation = cls._evaluate_expense_report(item, attrs)
        elif msg_type in ("POAPPR", "POAPPRV", "CREATEPO"):
            violations, explanation = cls._evaluate_purchase_order(item, attrs)
        elif msg_type in ("REQAPPR", "REQAPPRV"):
            violations, explanation = cls._evaluate_requisition(item, attrs)
        else:
            amt_val = resolved_amt or 0.0
            violations, explanation = (
                [],
                (
                    f"Evaluated {msg_type} workflow total of ${amt_val:,.2f}. "
                    f"No specific policy constraints for type '{msg_type}'."
                ),
            )

        severities = [v.severity for v in violations]
        risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
        compliance_status: Literal[
            "COMPLIANT", "FLAGGED_FOR_REVIEW", "NON_COMPLIANT"
        ] = "COMPLIANT"
        recommendation: Literal["APPROVE", "REJECT", "ESCALATE"] = "APPROVE"

        if "CRITICAL" in severities:
            risk_level = "CRITICAL"
            compliance_status = "NON_COMPLIANT"
            recommendation = "REJECT"
        elif "HIGH" in severities:
            risk_level = "HIGH"
            compliance_status = "FLAGGED_FOR_REVIEW"
            recommendation = "ESCALATE"
        elif "MEDIUM" in severities:
            risk_level = "MEDIUM"
            compliance_status = "FLAGGED_FOR_REVIEW"
            recommendation = "APPROVE"

        item.risk_level = risk_level
        item.recommended_action = recommendation
        return PolicyEvaluation(
            notification_id=item.notification_id,
            message_type=msg_type,
            amount=item.amount,
            compliance_status=compliance_status,
            risk_level=risk_level,
            violations=violations,
            recommendation=recommendation,
            explanation=explanation,
        )

    @staticmethod
    def format_risk_alert(evaluation: PolicyEvaluation) -> str:
        """Format markdown risk alert badge and violation details."""
        if evaluation.risk_level == "LOW":
            return (
                f"✅ **NID {evaluation.notification_id}**: "
                "Policy Compliant (Low Risk)"
            )

        icon_map = {
            "MEDIUM": "⚠️ **MODERATE RISK**",
            "HIGH": "🚨 **HIGH RISK ALERT**",
            "CRITICAL": "🛑 **CRITICAL POLICY VIOLATION**",
        }
        badge = icon_map.get(evaluation.risk_level, "⚠️ **ALERT**")
        details = "; ".join(
            f"{v.code}: {v.message}" for v in evaluation.violations
        )
        return (
            f"{badge} on NID {evaluation.notification_id} "
            f"({evaluation.message_type}): {details} — "
            f"*Recommendation: {evaluation.recommendation}*"
        )
