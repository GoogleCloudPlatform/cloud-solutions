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

"""Unit tests for Pydantic schemas and validation rules."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from src.a2a.agent_card import AgentCard, AgentSkill, create_workflow_agent_card
from src.a2a.schemas import (
    ConfirmationProposal,
    DirectRespondRequest,
    NotificationDetail,
    NotificationItem,
    NotificationListRequest,
    NotificationListResponse,
    PolicyEvaluation,
    PolicyVerificationRequest,
    PolicyViolation,
    WorkflowActionRequest,
    extract_amount_from_attributes,
    extract_amount_from_text,
    parse_amount_value,
)


def test_notification_item_validation() -> None:
    """Verify valid instantiation and attribute parsing of NotificationItem."""
    item = NotificationItem(
        notification_id=101,
        message_type="APEXP",
        message_name="EXP_APPR_MSG",
        recipient_role="JDOE",
        status="OPEN",
        subject="Expense report",
        priority=50,
        amount=1250.50,
    )
    assert item.notification_id == 101
    assert item.message_type == "APEXP"
    assert item.amount == 1250.50


def test_notification_list_request_valid() -> None:
    """Test valid NotificationListRequest filtering and normalization."""
    req = NotificationListRequest(
        recipient="jdoe", message_type="apexP", limit=25, offset=10
    )
    assert req.recipient == "jdoe"
    assert req.message_type == "APEXP"
    assert req.limit == 25
    assert req.offset == 10


def test_notification_list_request_invalid_type() -> None:
    """Test rejection of unsupported message_type."""
    with pytest.raises(ValidationError):
        NotificationListRequest(message_type="INVALID_TYPE")


def test_notification_list_request_invalid_limit() -> None:
    """Test rejection of non-positive limit."""
    with pytest.raises(ValidationError):
        NotificationListRequest(limit=0)


def test_workflow_action_request_validation() -> None:
    """Test valid and invalid WorkflowActionRequest payloads."""
    valid_req = WorkflowActionRequest(
        action="APPROVE",
        notification_ids=[1001, 1002],
        comment="Approved per audit",
        confirmed=False,
    )
    assert valid_req.action == "APPROVE"
    assert valid_req.confirmed is False

    with pytest.raises(ValidationError):
        WorkflowActionRequest.model_validate(
            {"action": "INVALID_ACTION", "notification_ids": [1001]}
        )

    with pytest.raises(ValidationError):
        WorkflowActionRequest(action="APPROVE", notification_ids=[])


def test_direct_respond_request() -> None:
    """Test DirectRespondRequest schema validation."""
    req = DirectRespondRequest(
        nid=2001, action="REJECT", comment="Over limit", path="REST"
    )
    assert req.nid == 2001
    assert req.action == "REJECT"
    assert req.path == "REST"


def test_policy_evaluation_schema() -> None:
    """Verify PolicyEvaluation nested violation structure."""
    violation = PolicyViolation(
        code="TEST_VIOLATION", message="Policy breached", severity="HIGH"
    )
    eval_res = PolicyEvaluation(
        notification_id=101,
        message_type="APEXP",
        compliance_status="FLAGGED_FOR_REVIEW",
        risk_level="HIGH",
        violations=[violation],
        recommendation="ESCALATE",
        explanation="Testing high risk evaluation",
    )
    assert eval_res.compliance_status == "FLAGGED_FOR_REVIEW"
    assert len(eval_res.violations) == 1
    assert eval_res.violations[0].code == "TEST_VIOLATION"


def test_agent_card_serialization() -> None:
    """Verify AgentCard compliant protocol serialization and strict schema."""
    card = AgentCard(
        name="Oracle EBS Assistant",
        description="Workflow Assistant",
        url="https://test.run.app",
        skills=[
            AgentSkill(
                id="triage",
                name="Triage",
                description="Triage skill",
                tags=["wf"],
                examples=["triage"],
            )
        ],
    )
    dumped = card.model_dump(by_alias=True)
    assert dumped["protocolVersion"] == "0.3.0"
    assert "triage" in dumped["skills"][0]["id"]
    assert "authentication" not in dumped

    wf_card = create_workflow_agent_card("https://a2a-workflow-server.run.app")
    wf_dumped = wf_card.model_dump(by_alias=True)
    assert wf_dumped["url"] == "https://a2a-workflow-server.run.app"
    assert "authentication" not in wf_dumped

    with pytest.raises(ValidationError):
        AgentCard.model_validate(
            {
                **wf_dumped,
                "authentication": {
                    "type": "OIDC",
                    "serviceAccountEmail": (
                        "test@example.iam.gserviceaccount.com"
                    ),
                },
            }
        )

    project_root = Path(__file__).resolve().parent.parent
    main_tf_text = (project_root / "terraform" / "main.tf").read_text(
        encoding="utf-8"
    )
    assert "serviceAccountEmail" not in main_tf_text
    spec_data = json.loads(
        (project_root / "src" / "a2a" / "agent_card_spec.json").read_text(
            encoding="utf-8"
        )
    )
    rendered_card = {
        **spec_data,
        "url": "https://a2a-workflow-server-dev.run.app",
    }
    validated = AgentCard.model_validate(rendered_card)
    assert validated.url == "https://a2a-workflow-server-dev.run.app"


def test_notification_detail_and_proposal() -> None:
    """Verify NotificationDetail and ConfirmationProposal schemas."""
    item = NotificationItem(
        notification_id=1,
        message_type="APEXP",
        message_name="MSG",
        recipient_role="MGR",
    )
    detail = NotificationDetail(header=item, attributes={"AMOUNT": 500.0})
    assert detail.header.notification_id == 1
    assert detail.attributes["AMOUNT"] == 500.0

    proposal = ConfirmationProposal(
        action="APPROVE",
        notification_ids=[1],
        total_count=1,
        total_financial_impact=500.0,
        risk_summary="Low risk",
        confirmation_prompt="Please confirm",
    )
    assert proposal.status == "CONFIRMATION_REQUIRED"
    assert proposal.required_confirmation_flag is True


def test_policy_verification_request_empty() -> None:
    """Test rejection of empty notification_ids in verification request."""
    with pytest.raises(ValidationError):
        PolicyVerificationRequest(notification_ids=[])


def test_notification_list_response() -> None:
    """Test NotificationListResponse model."""
    resp = NotificationListResponse(count=0, notifications=[])
    assert resp.status == "SUCCESS"
    assert resp.count == 0


def test_parse_amount_value_formats() -> None:
    """Verify US and European formatted currency strings parse accurately."""
    assert parse_amount_value(1250.5) == 1250.5
    assert parse_amount_value("509,950.00") == 509950.0
    assert parse_amount_value("2.320,00 EUR") == 2320.0
    assert parse_amount_value("294,00 EUR") == 294.0
    assert parse_amount_value("$7,148.34") == 7148.34
    assert parse_amount_value("") is None
    assert parse_amount_value(None) is None


def test_extract_amount_from_text_and_attributes() -> None:
    """Verify subject and attribute extraction for EBS notifications."""
    assert (
        extract_amount_from_text(
            "Internet Expense Report S15 for 2.320,00 EUR requires approval"
        )
        == 2320.0
    )
    assert (
        extract_amount_from_text(
            "Standard Purchase Order 6291 ($509,950.00) has been approved"
        )
        == 509950.0
    )
    assert (
        extract_amount_from_attributes(
            {"COST_CENTER": "740", "TOTAL_AMOUNT_DSP": "509,950.00"}
        )
        == 509950.0
    )
    assert (
        extract_amount_from_attributes(
            {"#HDR_DISPLAY_TOTAL": "175.00 USD", "EXPENSE_REPORT_ID": 30222}
        )
        == 175.0
    )

    item = NotificationItem(
        notification_id=7941939,
        message_type="APEXP",
        message_name="OIE_REQ_EXPENSE_REPORT_APPRVL",
        recipient_role="OPERATIONS",
        subject="Internet Expense Report IE11 for 95.00 USD requires approval",
    )
    assert item.amount == 95.0
