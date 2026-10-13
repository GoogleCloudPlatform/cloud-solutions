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

"""Workflow Triage & Human Confirmation Gate Orchestration Service."""

import logging
import re
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from src.a2a.schemas import (
    ActionResultItem,
    ConfirmationProposal,
    NotificationItem,
    PolicyEvaluation,
    PolicyVerificationResponse,
    TriageSummaryResponse,
    WorkflowActionRequest,
    WorkflowExecutionResponse,
)
from src.workflow.client import EBSWorkflowClient
from src.workflow.policy import PolicyEngine


def clean_workflow_error(raw_err: str) -> str:
    """Extract clean explanation from Oracle or HTTP exceptions."""
    if not raw_err:
        return "Action could not be executed on this notification."
    if "is already " in raw_err and "no action is required" in raw_err:
        return raw_err
    if "3202" in raw_err or "not currently open" in raw_err:
        return (
            "Notification is an informational (FYI) notice or is no "
            "longer open; no approval or rejection is required."
        )
    if "PLS-00306" in raw_err:
        return "Oracle PL/SQL procedure argument mismatch."
    if "404" in raw_err or "not found" in raw_err.lower():
        return "Notification not found in Oracle EBS."
    clean = re.sub(r"^[a-zA-Z0-9_\.]*Error:\s*", "", raw_err).strip()
    return clean or raw_err


logger = logging.getLogger(__name__)

try:
    import oracledb

    ORA_DB_ERRORS: tuple[type[Exception], ...] = (oracledb.Error,)
except ImportError:
    ORA_DB_ERRORS = ()

WORKFLOW_ACTION_EXCEPTIONS = (
    HTTPException,
    ValueError,
    RuntimeError,
    OSError,
    httpx.HTTPError,
) + ORA_DB_ERRORS


class WorkflowTriageService:
    """Service layer coordinating policy triage and certified execution."""

    def __init__(self, client: EBSWorkflowClient | None = None) -> None:
        self.client = client or EBSWorkflowClient()
        self.policy_engine = PolicyEngine()

    def triage_pending_notifications(
        self,
        recipient: str | None = None,
        message_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TriageSummaryResponse:
        """Triage pending notifications, evaluate policies, and build table."""
        notifications = self.client.list_notifications(
            recipient=recipient,
            message_type=message_type,
            status_val="OPEN",
            limit=limit,
            offset=offset,
        )

        by_type: dict[str, int] = {}
        high_risk_nids: list[int] = []
        evaluations: list[tuple[NotificationItem, PolicyEvaluation]] = []
        risk_alerts: list[str] = []

        for item in notifications:
            by_type[item.message_type] = by_type.get(item.message_type, 0) + 1
            attrs = self.client.get_notification_attributes(
                item.notification_id, verify_exists=False
            )
            eval_res = self.policy_engine.evaluate(item, attrs)
            evaluations.append((item, eval_res))

            if eval_res.risk_level in ("HIGH", "CRITICAL"):
                high_risk_nids.append(item.notification_id)
                risk_alerts.append(
                    self.policy_engine.format_risk_alert(eval_res)
                )

        table_md = self._build_markdown_table(evaluations)
        next_steps = self._generate_proactive_next_steps(
            len(notifications), high_risk_nids, by_type
        )

        return TriageSummaryResponse(
            total_pending=len(notifications),
            by_type=by_type,
            high_risk_notifications=high_risk_nids,
            markdown_table=table_md,
            risk_alerts=risk_alerts,
            proactive_next_steps=next_steps,
            items=[
                {
                    **item.model_dump(),
                    "risk_level": eval_res.risk_level,
                    "recommended_action": eval_res.recommendation,
                }
                for item, eval_res in evaluations
            ],
        )

    def verify_policies_for_notifications(
        self, notification_ids: list[int]
    ) -> PolicyVerificationResponse:
        """Evaluate policy compliance across notification IDs."""
        evaluations: list[PolicyEvaluation] = []
        high_risk_cnt = 0

        for nid in notification_ids:
            item = self.client.get_notification(nid)
            attrs = self.client.get_notification_attributes(
                nid, verify_exists=False
            )
            eval_res = self.policy_engine.evaluate(item, attrs)
            evaluations.append(eval_res)
            if eval_res.risk_level in ("HIGH", "CRITICAL"):
                high_risk_cnt += 1

        return PolicyVerificationResponse(
            status="SUCCESS",
            evaluations=evaluations,
            total_evaluated=len(evaluations),
            high_risk_count=high_risk_cnt,
        )

    def process_action(
        self, request: WorkflowActionRequest
    ) -> ConfirmationProposal | WorkflowExecutionResponse:
        """Process action with explicit human confirmation gate."""
        if not request.confirmed:
            return self._create_confirmation_proposal(request)

        return self._execute_confirmed_action(request)

    def _build_closed_result(
        self, nid: int, status_val: str, request: WorkflowActionRequest
    ) -> ActionResultItem:
        """Build an ActionResultItem for a non-open notification."""
        act = request.action.upper()
        act_verb = "approved" if act == "APPROVE" else "rejected"
        msg = (
            f"Notification #{nid} is already {status_val.upper()} "
            f"and cannot be {act_verb}; no action is required."
        )
        return ActionResultItem(
            notification_id=nid,
            status="FAILED",
            action=act,
            execution_path=(
                request.execution_path
                or self.client.settings.workflow.default_path
            ),
            message=msg,
            error=msg,
        )

    def _create_confirmation_proposal(
        self, request: WorkflowActionRequest
    ) -> ConfirmationProposal | WorkflowExecutionResponse:
        """Construct proposal requiring human verification before mutation."""
        high_risk_alerts: list[str] = []
        total_impact = 0.0
        open_nids: list[int] = []
        closed_results: list[ActionResultItem] = []

        for nid in request.notification_ids:
            item = self.client.get_notification(nid)
            if item.status.upper() != "OPEN":
                closed_results.append(
                    self._build_closed_result(nid, item.status, request)
                )
                continue

            open_nids.append(nid)
            attrs = self.client.get_notification_attributes(
                nid, verify_exists=False
            )
            eval_res = self.policy_engine.evaluate(item, attrs)
            total_impact += (
                self.policy_engine.resolve_amount(item, attrs) or 0.0
            )
            if eval_res.risk_level in ("HIGH", "CRITICAL"):
                high_risk_alerts.append(
                    self.policy_engine.format_risk_alert(eval_res)
                )

        act = request.action.upper()
        if not open_nids:
            return WorkflowExecutionResponse(
                status="COMPLETED",
                action=act,
                results=closed_results,
                executed_at=datetime.now(timezone.utc).isoformat(),
            )

        summary = (
            f"Action proposed: {act} {len(open_nids)} notification(s) with "
            f"total financial impact of ${total_impact:,.2f}. "
            f"High-risk items flagged: {len(high_risk_alerts)}."
        )
        if closed_results:
            skipped = [r.notification_id for r in closed_results]
            act_verb = "approved" if act == "APPROVE" else "rejected"
            summary += (
                f" (Skipped {len(skipped)} already-closed "
                f"notification(s) {skipped} which cannot be {act_verb}; "
                "no action is required for them.)"
            )
        prompt = (
            f"CONFIRMATION REQUIRED: Please review and confirm {act} for "
            f"{len(open_nids)} workflow notification(s) [NIDs: "
            f"{open_nids}]. "
            "To execute, reply CONFIRM or set confirmed=True."
        )

        return ConfirmationProposal(
            action=act,
            notification_ids=open_nids,
            total_count=len(open_nids),
            total_financial_impact=round(total_impact, 2),
            risk_summary=summary,
            high_risk_alerts=high_risk_alerts,
            confirmation_prompt=prompt,
            required_confirmation_flag=True,
            comments=request.comments or request.comment,
        )

    def _execute_confirmed_action(
        self, request: WorkflowActionRequest
    ) -> WorkflowExecutionResponse:
        """Execute certified action across all confirmed notification IDs."""
        results: list[ActionResultItem] = []
        act = request.action.upper()

        for nid in request.notification_ids:
            try:
                res = self.client.respond(
                    nid=nid,
                    action=act,
                    comment=request.comments
                    or request.comment
                    or "Processed via Agent",
                    responder=request.responder,
                    path=request.execution_path or "REST",
                )
                results.append(
                    ActionResultItem(
                        notification_id=nid,
                        status="SUCCESS",
                        action=act,
                        execution_path=str(
                            res.get("execution_path")
                            or request.execution_path
                            or "REST"
                        ),
                        message=res.get("message", "Response recorded"),
                    )
                )
            except WORKFLOW_ACTION_EXCEPTIONS as exc:
                err_msg = clean_workflow_error(str(exc))
                logger.error(
                    "Error executing action on notification %s: %s",
                    nid,
                    err_msg,
                )
                results.append(
                    ActionResultItem(
                        notification_id=nid,
                        status="FAILED",
                        action=act,
                        execution_path=(
                            request.execution_path
                            or self.client.settings.workflow.default_path
                        ),
                        message=err_msg,
                        error=err_msg,
                    )
                )

        now_str = datetime.now(timezone.utc).isoformat()
        return WorkflowExecutionResponse(
            status="COMPLETED",
            action=act,
            results=results,
            executed_at=now_str,
        )

    @staticmethod
    def _build_markdown_table(
        evaluations: list[tuple[NotificationItem, PolicyEvaluation]],
    ) -> str:
        """Format markdown table for notifications and policy evaluation."""
        if not evaluations:
            return "_No pending workflow notifications found._"

        headers = [
            "NID",
            "Type",
            "Subject",
            "Requester",
            "Amount",
            "Policy Status",
            "Risk",
            "Rec",
        ]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]

        for item, ev in evaluations:
            amt_str = f"${item.amount:,.2f}" if item.amount is not None else "-"
            raw_subj = item.subject or "No Subject"
            subj = (raw_subj[:40] + "...") if len(raw_subj) > 43 else raw_subj
            subj = subj.replace("|", "/")
            req = (item.requester or "-").replace("|", "/")
            lines.append(
                f"| {item.notification_id} | {item.message_type} | {subj} | "
                f"{req} | {amt_str} | {ev.compliance_status} | "
                f"{ev.risk_level} | {ev.recommendation} |"
            )

        return "\n".join(lines)

    @staticmethod
    def _generate_proactive_next_steps(
        total: int, high_risk_nids: list[int], by_type: dict[str, int]
    ) -> list[str]:
        """Synthesize manager recommendations based on pending triage."""
        steps: list[str] = []
        if by_type.get("APEXP", 0) > 0:
            count_exp = by_type.get("APEXP", 0)
            steps.append(
                f"Verify receipt attachments for {count_exp} "
                "pending Expense Report(s)."
            )
        if high_risk_nids:
            sample_nids = high_risk_nids[:5]
            steps.append(
                f"Inspect and audit {len(high_risk_nids)} high-risk "
                f"notification(s) [NIDs: {sample_nids}] before approval."
            )
        count_po = by_type.get("POAPPR", 0) + by_type.get("POAPPRV", 0)
        if count_po > 0:
            steps.append(
                f"Confirm approved supplier for {count_po} "
                "Purchase Order(s)."
            )
        count_req = by_type.get("REQAPPR", 0) + by_type.get("REQAPPRV", 0)
        if count_req > 0:
            steps.append(
                f"Check quarterly budget caps for {count_req} "
                "Requisition(s)."
            )
        if total > 0 and not high_risk_nids:
            steps.append(
                "All workflows are low risk. Proceed with bulk approval."
            )
        return steps

    # Method aliases for backward and phase-2 compatibility
    triage = triage_pending_notifications
    triage_worklist = triage_pending_notifications
    verify_policies = verify_policies_for_notifications
    verify_policy_batch = verify_policies_for_notifications
    execute_action = process_action
