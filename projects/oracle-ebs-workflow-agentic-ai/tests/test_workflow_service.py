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

"""Unit tests for Workflow Triage and Human Confirmation Gate Service."""

from typing import Literal
from unittest.mock import patch

from src.a2a.schemas import (
    ConfirmationProposal,
    NotificationItem,
    WorkflowActionRequest,
    WorkflowExecutionResponse,
)
from src.workflow.service import WorkflowTriageService


def test_triage_pending_notifications(
    mock_workflow_service: WorkflowTriageService,
) -> None:
    """Test full workflow triage, policy evaluation, and table rendering."""
    triage = mock_workflow_service.triage_pending_notifications()
    assert triage.total_pending >= 4
    assert "APEXP" in triage.by_type
    assert "POAPPR" in triage.by_type
    assert len(triage.high_risk_notifications) > 0
    assert "| NID | Type |" in triage.markdown_table
    assert len(triage.proactive_next_steps) > 0


def test_verify_policies_service(
    mock_workflow_service: WorkflowTriageService,
) -> None:
    """Test batch policy evaluation service method."""
    res = mock_workflow_service.verify_policies_for_notifications([1001, 1002])
    assert res.total_evaluated == 2
    assert res.high_risk_count == 1
    eval_map = {ev.notification_id: ev for ev in res.evaluations}
    assert eval_map[1001].risk_level == "HIGH"
    assert eval_map[1002].risk_level == "LOW"


def test_human_confirmation_gate_unconfirmed(
    mock_workflow_service: WorkflowTriageService,
) -> None:
    """Test gate stops mutative action and returns ConfirmationProposal."""
    req = WorkflowActionRequest(
        action="APPROVE",
        notification_ids=[1001, 2001],
        comment="Manager approval",
        confirmed=False,
    )
    result = mock_workflow_service.process_action(req)
    assert isinstance(result, ConfirmationProposal)
    assert result.status == "CONFIRMATION_REQUIRED"
    assert result.action == "APPROVE"
    assert result.total_count == 2
    assert result.total_financial_impact == 46500.0
    assert result.required_confirmation_flag is True
    assert "CONFIRMATION REQUIRED" in result.confirmation_prompt


def test_human_confirmation_gate_confirmed(
    mock_workflow_service: WorkflowTriageService,
) -> None:
    """Test gate executes mutation when confirmed is True."""
    req = WorkflowActionRequest(
        action="APPROVE",
        notification_ids=[1001, 2001],
        comment="Explicitly confirmed",
        confirmed=True,
    )
    result = mock_workflow_service.process_action(req)
    assert isinstance(result, WorkflowExecutionResponse)
    assert result.status == "COMPLETED"
    assert result.action == "APPROVE"
    assert len(result.results) == 2
    assert all(r.status == "SUCCESS" for r in result.results)


def test_closed_notification_skips_confirmation_gate(
    mock_workflow_service: WorkflowTriageService,
) -> None:
    """Verify already-CLOSED notification skips confirmation gate."""
    closed_item = NotificationItem(
        notification_id=7900386,
        message_type="POAPPRV",
        message_name="EMAIL_PO_PDF",
        recipient_role="OPERATIONS",
        status="CLOSED",
        subject="Standard Purchase Order 6565",
        amount=470000.0,
    )
    with patch.object(
        mock_workflow_service.client,
        "get_notification",
        return_value=closed_item,
    ):
        req = WorkflowActionRequest(
            action="REJECT",
            notification_ids=[7900386],
            comment="Duplicate rejection attempt",
            confirmed=False,
        )
        result = mock_workflow_service.process_action(req)
        assert isinstance(result, WorkflowExecutionResponse)
        assert result.status == "COMPLETED"
        assert len(result.results) == 1
        assert result.results[0].status == "FAILED"
        assert "already CLOSED" in (result.results[0].message or "")
        assert "cannot be rejected" in (result.results[0].message or "")


def test_mixed_open_and_closed_batch_proposal(
    mock_workflow_service: WorkflowTriageService,
) -> None:
    """Verify mixed batch excludes CLOSED item from ConfirmationProposal."""
    orig_get = mock_workflow_service.client.get_notification

    def side_effect(nid: int) -> NotificationItem:
        if nid == 7900386:
            return NotificationItem(
                notification_id=7900386,
                message_type="POAPPRV",
                message_name="EMAIL_PO_PDF",
                recipient_role="OPERATIONS",
                status="CLOSED",
                subject="Standard Purchase Order 6565",
                amount=470000.0,
            )
        return orig_get(nid)

    with patch.object(
        mock_workflow_service.client,
        "get_notification",
        side_effect=side_effect,
    ):
        req = WorkflowActionRequest(
            action="APPROVE",
            notification_ids=[7900386, 1001],
            comment="Batch approval",
            confirmed=False,
        )
        result = mock_workflow_service.process_action(req)
        assert isinstance(result, ConfirmationProposal)
        assert result.status == "CONFIRMATION_REQUIRED"
        assert result.notification_ids == [1001]
        assert result.total_count == 1
        assert result.comments == "Batch approval"
        assert "Skipped 1 already-closed" in result.risk_summary


def test_bulk_closed_notifications_skip_confirmation_gate(
    mock_workflow_service: WorkflowTriageService,
) -> None:
    """Verify bulk approve/reject skip gate when all items are CLOSED."""

    def closed_side_effect(nid: int) -> NotificationItem:
        return NotificationItem(
            notification_id=nid,
            message_type="POAPPRV",
            message_name="EMAIL_PO_PDF",
            recipient_role="ADHOC245476943274117150PO",
            status="CLOSED",
            subject=f"Purchase Order {nid}",
            amount=1200.0,
        )

    with patch.object(
        mock_workflow_service.client,
        "get_notification",
        side_effect=closed_side_effect,
    ):
        cases: tuple[tuple[Literal["APPROVE", "REJECT"], str], ...] = (
            ("APPROVE", "approved"),
            ("REJECT", "rejected"),
        )
        for act, verb in cases:
            req = WorkflowActionRequest(
                action=act,
                notification_ids=[7119699, 7119698, 7119697],
                comment=f"Bulk {act.lower()} attempt on closed items",
                confirmed=False,
            )
            result = mock_workflow_service.process_action(req)
            assert isinstance(result, WorkflowExecutionResponse)
            assert result.status == "COMPLETED"
            assert len(result.results) == 3
            for r, expected_nid in zip(
                result.results, [7119699, 7119698, 7119697], strict=True
            ):
                assert r.notification_id == expected_nid
                assert r.status == "FAILED"
                assert "already CLOSED" in (r.message or "")
                assert f"cannot be {verb}" in (r.message or "")
