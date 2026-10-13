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

"""Strict Pydantic v2 schemas and data contracts for Oracle EBS Workflow AI."""

import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

ALLOWED_WORKFLOW_TYPES = (
    "APEXP",
    "POAPPR",
    "POAPPRV",
    "REQAPPR",
    "REQAPPRV",
    "OKCAUKAP",
    "GMSWF",
    "AMSGAPP",
    "CREATEPO",
)

PRIORITY_AMOUNT_ATTRS = (
    "TOTAL_AMOUNT_DSP",
    "PO_AMOUNT_DSP",
    "PO_AMOUNT",
    "#HDR_DISPLAY_TOTAL",
    "EXP_REPORT_TOTAL",
    "REQ_AMOUNT_DSP",
    "REQ_AMOUNT",
    "TOTAL_AMOUNT",
    "DOCUMENT_TOTAL",
    "TOTAL",
    "AMOUNT",
    "CONTRACT_AMOUNT",
    "ESTIMATED_AMOUNT",
    "INSTALL_TOTAL_AMOUNT",
    "INSTALL_DIRECT_COST",
)


def parse_amount_value(val: Any) -> float | None:
    """Parse numeric or formatted US/European currency value into float."""
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None
    match = re.search(
        r"([0-9]+(?:[.,][0-9]{3})*(?:[.,][0-9]{1,2})?|[0-9]+(?:\.[0-9]+)?)",
        val.strip(),
    )
    if not match:
        return None
    token = match.group(1)
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        parts = token.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            token = token.replace(",", ".")
        else:
            token = token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def extract_amount_from_text(text: str | None) -> float | None:
    """Extract currency amount from notification subject or descriptive text."""
    if not text or not isinstance(text, str):
        return None
    patterns = (
        (
            r"(?:\$|€|£|\b(?:USD|EUR|CAD|GBP|AUD|CHF|INR|JPY)\b|\bdollars?\b)"
            r"\s*([0-9]+(?:[.,][0-9]{3})*(?:[.,][0-9]{1,2})?"
            r"|[0-9]+(?:\.[0-9]+)?)"
        ),
        (
            r"([0-9]+(?:[.,][0-9]{3})*(?:[.,][0-9]{1,2})?|[0-9]+(?:\.[0-9]+)?)"
            r"\s*(?:USD|EUR|CAD|GBP|AUD|CHF|INR|JPY)\b"
        ),
        r"\(\s*([0-9]+(?:[.,][0-9]{3})*[.,][0-9]{2})\s*\)",
    )
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            parsed = parse_amount_value(match.group(1))
            if parsed is not None:
                return parsed
    return None


def extract_amount_from_attributes(
    attrs: dict[str, Any] | None, subject: str | None = None
) -> float | None:
    """Extract amount from workflow notification attributes or subject."""
    if isinstance(attrs, dict) and attrs:
        upper_map = {str(k).upper().strip(): v for k, v in attrs.items()}
        for key in PRIORITY_AMOUNT_ATTRS:
            if key in upper_map and upper_map[key] is not None:
                parsed = parse_amount_value(upper_map[key])
                if parsed is not None:
                    return parsed
        for attr_k, attr_v in upper_map.items():
            if "COST_CENTER" in attr_k or "HOURS" in attr_k:
                continue
            if "AMOUNT" in attr_k or "TOTAL" in attr_k:
                parsed = parse_amount_value(attr_v)
                if parsed is not None:
                    return parsed
    return extract_amount_from_text(subject)


class NotificationRecord(BaseModel):
    """Notification record representation with field parsing."""

    model_config = ConfigDict(populate_by_name=True)

    notification_id: int = Field(
        ..., description="Unique Workflow Notification ID"
    )
    message_type: str = Field(
        ..., description="Item type: APEXP, POAPPR, REQAPPR"
    )
    message_name: str | None = Field(
        default=None, description="Workflow message name"
    )
    recipient_role: str = Field(..., description="Recipient user or role")
    status: str = Field(default="OPEN", description="Notification status")
    subject: str | None = Field(default=None, description="Subject line")
    begin_date: str | None = Field(default=None, description="Start date")
    due_date: str | None = Field(default=None, description="Due date")
    amount: float | None = Field(
        default=None, description="Extracted currency amount"
    )
    currency: str | None = Field(default="USD", description="Currency code")
    requester: str | None = Field(
        default=None, description="Requester user name"
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Notification attributes"
    )
    priority: int | None = Field(default=50, description="Workflow priority")
    risk_level: str | None = Field(
        default=None, description="Evaluated policy risk level"
    )
    recommended_action: str | None = Field(
        default=None, description="Recommended workflow action"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        """Handle case-insensitive fields from Oracle database."""
        if not isinstance(data, dict):
            return data
        normalized: dict[str, Any] = {}
        for key, value in data.items():
            k = key.lower()
            normalized[k] = value

        if "notification_id" not in normalized and "nid" in normalized:
            normalized["notification_id"] = normalized["nid"]

        parsed_amt = parse_amount_value(normalized.get("amount"))
        if parsed_amt is not None:
            normalized["amount"] = parsed_amt
        else:
            normalized["amount"] = extract_amount_from_attributes(
                normalized.get("attributes"),
                normalized.get("subject"),
            )

        return normalized


class PendingWorklistRequest(BaseModel):
    """Request schema for retrieving pending worklist notifications."""

    recipient: str = Field(
        ..., description="Username or role of the notification recipient"
    )
    notification_type: str | None = Field(
        default=None, description="Filter: APEXP, POAPPR, REQAPPR"
    )
    max_amount: float | None = Field(
        default=None, description="Maximum amount filter"
    )
    limit: int = Field(
        default=50, ge=1, le=100, description="Max notifications to return"
    )
    offset: int = Field(default=0, ge=0, description="Offset for pagination")

    @model_validator(mode="before")
    @classmethod
    def validate_types(cls, data: Any) -> Any:
        """Validate notification type filter."""
        if isinstance(data, dict):
            ntype = data.get("notification_type")
            if ntype:
                upper_t = ntype.upper().strip()
                if upper_t not in ALLOWED_WORKFLOW_TYPES:
                    raise ValueError(
                        f"Invalid notification_type: {ntype}. "
                        "Must be APEXP, POAPPR, or REQAPPR."
                    )
                data["notification_type"] = upper_t
        return data


class WorklistResponse(BaseModel):
    """Response containing retrieved notifications and metadata."""

    total_count: int
    recipient: str
    items: list[NotificationRecord]


class WorkflowActionRequest(BaseModel):
    """Request to execute a workflow response (APPROVE/REJECT)."""

    notification_ids: list[int] = Field(
        ..., min_length=1, description="List of notification IDs"
    )
    action: Literal["APPROVE", "REJECT"] = Field(
        ..., description="Certified action to perform"
    )
    comment: str | None = Field(
        default=None, description="Approval/Rejection comment"
    )
    comments: str | None = Field(
        default="Processed via Agentic AI",
        description="Approval/Rejection comment",
    )
    responder: str = Field(
        default="AGENT_SYSTEM", description="Acting user name"
    )
    confirmed: bool = Field(
        default=False, description="Explicit human confirmation flag"
    )
    execution_path: str | None = Field(
        default="REST", description="Execution path: REST or PLSQL"
    )

    @model_validator(mode="before")
    @classmethod
    def sync_comments(cls, data: Any) -> Any:
        """Sync comment and comments fields."""
        if isinstance(data, dict):
            if "comment" in data and "comments" not in data:
                data["comments"] = data["comment"]
            elif "comments" in data and "comment" not in data:
                data["comment"] = data["comments"]
        return data


class WorkflowActionResponse(BaseModel):
    """Response schema for workflow action execution or proposal."""

    status: str
    action: str
    requires_confirmation: bool = False
    proposal: dict[str, Any] | None = None
    processed_items: list[dict[str, Any]] = Field(default_factory=list)
    failed_items: list[dict[str, Any]] = Field(default_factory=list)


NotificationItem = NotificationRecord


class NotificationDetail(BaseModel):
    """Detailed notification item with header and attributes."""

    header: NotificationRecord
    attributes: dict[str, Any] = Field(default_factory=dict)
    attribute_types: dict[str, str] = Field(default_factory=dict)


class NotificationListRequest(BaseModel):
    """Backward-compatible list request."""

    recipient: str | None = None
    message_type: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def validate_type(cls, data: Any) -> Any:
        """Validate optional message type."""
        if isinstance(data, dict):
            mtype = data.get("message_type")
            if mtype:
                upper_t = mtype.upper().strip()
                if upper_t not in ALLOWED_WORKFLOW_TYPES:
                    raise ValueError(f"Invalid message_type: {mtype}")
                data["message_type"] = upper_t
        return data


class NotificationListResponse(BaseModel):
    """Backward-compatible list response."""

    status: str = "SUCCESS"
    count: int = 0
    total: int | None = None
    notifications: list[NotificationRecord] = Field(default_factory=list)
    items: list[NotificationRecord] | None = None

    @model_validator(mode="before")
    @classmethod
    def sync_items(cls, data: Any) -> Any:
        """Synchronize notifications and items list."""
        if isinstance(data, dict):
            if "notifications" in data and "items" not in data:
                data["items"] = data["notifications"]
                data["count"] = len(data["notifications"])
                data["total"] = len(data["notifications"])
            elif "items" in data and "notifications" not in data:
                data["notifications"] = data["items"]
                data["count"] = len(data["items"])
                data["total"] = len(data["items"])
        return data


class PolicyViolation(BaseModel):
    """Policy violation detail."""

    code: str | None = None
    rule_name: str = ""
    severity: str = "INFO"
    message: str

    @model_validator(mode="before")
    @classmethod
    def sync_code(cls, data: Any) -> Any:
        """Sync rule_name and code."""
        if isinstance(data, dict):
            if "code" in data and not data.get("rule_name"):
                data["rule_name"] = data["code"]
            elif "rule_name" in data and not data.get("code"):
                data["code"] = data["rule_name"]
        return data


class PolicyEvaluation(BaseModel):
    """Policy evaluation result."""

    notification_id: int
    message_type: str
    amount: float | None = None
    risk_level: str
    compliance_status: str = "COMPLIANT"
    recommended_action: str | None = None
    recommendation: str | None = None
    explanation: str | None = None
    violations: list[PolicyViolation] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def sync_recommendations(cls, data: Any) -> Any:
        """Sync recommendation and recommended_action."""
        if isinstance(data, dict):
            rec = (
                data.get("recommended_action")
                or data.get("recommendation")
                or "APPROVE"
            )
            data["recommended_action"] = rec
            data["recommendation"] = rec
        return data


class PolicyVerificationRequest(BaseModel):
    """Request for policy verification."""

    notification_ids: list[int] = Field(..., min_length=1)
    recipient: str | None = None


class PolicyVerificationResponse(BaseModel):
    """Response containing policy evaluations."""

    status: str = "SUCCESS"
    total_evaluated: int = 0
    evaluations: list[PolicyEvaluation] = Field(default_factory=list)
    high_risk_count: int = 0


class ConfirmationProposal(BaseModel):
    """Structured proposal returned when action lacks confirmation."""

    status: str = "CONFIRMATION_REQUIRED"
    action: str = "APPROVE"
    notification_ids: list[int]
    total_count: int = 1
    total_financial_impact: float = 0.0
    total_amount: float | None = None
    risk_summary: str = "Low risk"
    high_risk_count: int = 0
    high_risk_alerts: list[str] = Field(default_factory=list)
    summary_markdown: str | None = None
    confirmation_prompt: str
    required_confirmation_flag: bool = True
    comments: str | None = None

    @model_validator(mode="before")
    @classmethod
    def sync_amounts(cls, data: Any) -> Any:
        """Sync amounts and counts."""
        if isinstance(data, dict):
            if "total_financial_impact" in data and "total_amount" not in data:
                data["total_amount"] = data["total_financial_impact"]
            elif (
                "total_amount" in data and "total_financial_impact" not in data
            ):
                data["total_financial_impact"] = data["total_amount"]
        return data


class ActionResultItem(BaseModel):
    """Individual action result item."""

    notification_id: int
    status: Literal["SUCCESS", "FAILED"]
    action: str | None = None
    execution_path: str | None = None
    message: str | None = None
    error: str | None = None


class WorkflowExecutionResponse(BaseModel):
    """Response from executing workflow actions."""

    status: str
    action: str
    proposal: ConfirmationProposal | None = None
    results: list[ActionResultItem] = Field(default_factory=list)
    executed_at: str | None = None


class TriageSummaryResponse(BaseModel):
    """Response from multi-item triage."""

    total_pending: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    high_risk_notifications: list[int] = Field(default_factory=list)
    risk_summary: dict[str, int] = Field(default_factory=dict)
    markdown_table: str = ""
    triage_table_markdown: str | None = None
    risk_alerts: list[str] = Field(default_factory=list)
    proactive_next_steps: list[str] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sync_tables(cls, data: Any) -> Any:
        """Sync table markdown attributes."""
        if isinstance(data, dict):
            if "markdown_table" in data and "triage_table_markdown" not in data:
                data["triage_table_markdown"] = data["markdown_table"]
            elif (
                "triage_table_markdown" in data and "markdown_table" not in data
            ):
                data["markdown_table"] = data["triage_table_markdown"]
        return data


class DirectRespondRequest(BaseModel):
    """Direct single notification response request."""

    nid: int | None = None
    notification_id: int | None = None
    action: Literal["APPROVE", "REJECT"]
    comments: str | None = None
    comment: str | None = None
    responder: str | None = None
    path: str | None = "REST"

    @model_validator(mode="before")
    @classmethod
    def sync_nid_and_comment(cls, data: Any) -> Any:
        """Sync nid/notification_id and comment/comments."""
        if isinstance(data, dict):
            if "nid" in data and "notification_id" not in data:
                data["notification_id"] = data["nid"]
            elif "notification_id" in data and "nid" not in data:
                data["nid"] = data["notification_id"]

            if "comment" in data and "comments" not in data:
                data["comments"] = data["comment"]
            elif "comments" in data and "comment" not in data:
                data["comment"] = data["comments"]
        return data


class ActionPlan(BaseModel):
    """Cognitive action plan generated by Gemini Dispatcher."""

    action: str = Field(
        description=(
            "notifications | inspect | verify_policy | triage | "
            "approve | reject | help"
        )
    )
    recipient: str | None = Field(
        default=None,
        description="Oracle EBS recipient username or role",
    )
    notification_type: str | None = Field(
        default=None, description="APEXP | POAPPR | REQAPPR"
    )
    notification_id: int | None = Field(
        default=None, description="Specific notification ID"
    )
    notification_ids: list[int] | None = Field(
        default=None, description="List of notification IDs for bulk actions"
    )
    comments: str | None = Field(
        default="Actioned via AI Assistant",
        description="Comments or justification",
    )
    confirmed: bool | None = Field(
        default=False,
        description="True if user explicitly confirmed execution",
    )
    max_amount: float | None = Field(
        default=None, description="Max amount filter"
    )
    limit: int | None = Field(
        default=50, description="Max records to return (1-100)"
    )

    @field_validator("action", mode="before")
    @classmethod
    def sanitize_action(cls, v: Any) -> str:
        """Normalize action and default unrecognized values to help."""
        if not isinstance(v, str):
            return "help"
        clean = v.strip().lower()
        allowed = {
            "notifications",
            "pending",
            "list",
            "inspect",
            "verify_policy",
            "policy",
            "verify",
            "triage",
            "approve",
            "reject",
            "help",
            "greeting",
        }
        return clean if clean in allowed else "help"

    @field_validator("recipient", mode="before")
    @classmethod
    def sanitize_recipient(cls, v: Any) -> str | None:
        """Validate recipient role/username and strip unsafe tokens."""
        if v is None or not isinstance(v, str):
            return None
        clean = v.strip()
        if not clean or not re.match(r"^[A-Za-z0-9_@.\\-]{2,64}$", clean):
            return None
        blocked = {
            "SELECT",
            "DELETE",
            "DROP",
            "TRUNCATE",
            "INSERT",
            "UPDATE",
            "ALTER",
            "UNION",
            "GRANT",
            "REVOKE",
            "EXEC",
            "EXECUTE",
            "NONE",
            "NULL",
            "UNKNOWN",
        }
        if clean.upper() in blocked:
            return None
        if re.search(r"[bcdfghjklmnpqrstvwxz]{6,}", clean.lower()):
            return None
        return clean.upper()

    @field_validator("comments", mode="before")
    @classmethod
    def sanitize_comments(cls, v: Any) -> str:
        """Sanitize comments by stripping control characters and HTML tags."""
        if v is None or not isinstance(v, str):
            return "Actioned via AI Assistant"
        no_ctrl = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        no_html = re.sub(r"<[^>]*>", "", no_ctrl)
        clean = " ".join(no_html.split())[:500]
        return clean or "Actioned via AI Assistant"

    @field_validator("limit", mode="before")
    @classmethod
    def clamp_limit(cls, v: Any) -> int:
        """Clamp pagination limit to valid bounds (1-100)."""
        if v is None:
            return 50
        try:
            return max(1, min(int(v), 100))
        except (ValueError, TypeError):
            return 50

    @model_validator(mode="after")
    def consolidate_notification_ids(self) -> "ActionPlan":
        """Merge notification_id and notification_ids without duplicates."""
        merged: list[int] = []
        if self.notification_id is not None and self.notification_id > 0:
            merged.append(int(self.notification_id))
        if self.notification_ids:
            for raw_nid in self.notification_ids:
                if (
                    isinstance(raw_nid, int)
                    and raw_nid > 0
                    and raw_nid not in merged
                ):
                    merged.append(raw_nid)
        if merged:
            self.notification_ids = merged
            if self.notification_id is None:
                self.notification_id = merged[0]
        return self
