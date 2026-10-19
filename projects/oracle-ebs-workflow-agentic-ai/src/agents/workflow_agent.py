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

"""Workflow Agent Microservice for Oracle EBS Workflow & Approval Triage."""

import logging
from typing import Annotated, Any

import httpx
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Path,
    Query,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from google.genai import types
from src.a2a.ai_client import generate_content_with_models, get_ai_client
from src.a2a.schemas import (
    ALLOWED_WORKFLOW_TYPES,
    DirectRespondRequest,
    NotificationDetail,
    NotificationListRequest,
    NotificationListResponse,
    NotificationRecord,
    PendingWorklistRequest,
    PolicyVerificationRequest,
    PolicyVerificationResponse,
    TriageSummaryResponse,
    WorkflowActionRequest,
    WorkflowActionResponse,
    WorklistResponse,
)
from src.config import Settings, get_settings
from src.gemini_cli_extensions.oracle import ExecutionEngine
from src.mcp.ebs_db_client import EBSDatabaseClient
from src.workflow.client import EBSWorkflowClient
from src.workflow.policy import PolicyEngine
from src.workflow.service import WorkflowTriageService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Workflow Operations"])


def get_db_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EBSDatabaseClient:
    """Dependency provider for EBSDatabaseClient."""
    # When Pylint runs across the monorepo, it may resolve
    # src.mcp.ebs_db_client to oracle-ebs-agentic-ai's definition.
    # pylint: disable-next=unexpected-keyword-arg
    return EBSDatabaseClient(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=(
            f"{settings.oracle_host}:{settings.oracle_port}/"
            f"{settings.oracle_service_name}"
        ),
    )


def get_workflow_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EBSWorkflowClient:
    """Dependency provider for EBSWorkflowClient."""
    engine = ExecutionEngine(
        dsn=(
            f"{settings.oracle_host}:{settings.oracle_port}/"
            f"{settings.oracle_service_name}"
        ),
        user=settings.oracle_user,
        password=settings.oracle_password,
    )
    return EBSWorkflowClient(engine=engine, settings=settings)


def get_triage_service(
    client: Annotated[EBSWorkflowClient, Depends(get_workflow_client)],
) -> WorkflowTriageService:
    """Dependency provider for WorkflowTriageService."""
    return WorkflowTriageService(client=client)


# Compatibility alias
get_workflow_service = get_triage_service


@router.get("/health", summary="Health Check")
def health_check() -> dict[str, str]:
    """Microservice health check."""
    return {"status": "healthy", "service": "oracle-ebs-workflow-agent"}


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="List notifications",
)
def list_notifications(
    query_params: Annotated[NotificationListRequest, Query()],
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> NotificationListResponse:
    """List pending workflow notifications using parameterized query."""
    items = service.client.list_notifications(
        recipient=query_params.recipient,
        message_type=query_params.message_type,
        limit=query_params.limit,
        offset=query_params.offset,
    )
    return NotificationListResponse(
        status="SUCCESS",
        count=len(items),
        notifications=items,
        items=items,
    )


@router.get(
    "/notifications/{notification_id}",
    response_model=NotificationDetail,
    summary="Inspect notification",
)
def get_notification(
    notification_id: Annotated[int, Path(ge=1)],
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> NotificationDetail:
    """Inspect full notification details and attributes."""
    return service.client.get_notification_detail(notification_id)


@router.post(
    "/verify-policy",
    response_model=PolicyVerificationResponse,
    summary="Verify policy compliance",
)
def verify_policy(
    request: PolicyVerificationRequest,
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> PolicyVerificationResponse:
    """Verify policy compliance for notifications."""
    return service.verify_policy_batch(
        notification_ids=request.notification_ids
    )


@router.get(
    "/triage",
    response_model=TriageSummaryResponse,
    summary="Triage pending notifications",
)
def triage_notifications(
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
    recipient: str | None = Query(None),
    message_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> TriageSummaryResponse:
    """Triage pending notifications with Markdown summary table."""
    return service.triage_worklist(
        recipient=recipient, message_type=message_type, limit=limit
    )


@router.post("/execute", summary="Execute certified action")
def execute_workflow_action(
    request: WorkflowActionRequest,
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> Any:
    """Execute certified workflow action with explicit confirmation gate."""
    return service.execute_action(request)


@router.post("/approve", summary="Approve notifications with confirmation gate")
def approve_notifications(
    request: WorkflowActionRequest,
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> Any:
    """Convenience endpoint to approve notifications."""
    req_dict = request.model_dump()
    req_dict["action"] = "APPROVE"
    return service.execute_action(
        WorkflowActionRequest.model_validate(req_dict)
    )


@router.post("/reject", summary="Reject notifications with confirmation gate")
def reject_notifications(
    request: WorkflowActionRequest,
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> Any:
    """Convenience endpoint to reject notifications."""
    req_dict = request.model_dump()
    req_dict["action"] = "REJECT"
    return service.execute_action(
        WorkflowActionRequest.model_validate(req_dict)
    )


@router.post("/respond", summary="Direct response execution")
def respond_endpoint(
    body: dict[str, Any],
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> dict[str, Any]:
    """Execute direct response for single notification."""
    raw_nid = body.get("nid", body.get("notification_id"))
    try:
        nid = int(raw_nid) if raw_nid is not None else 0
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Notification ID must be a positive integer.",
        ) from exc
    if nid <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Notification ID must be a positive integer.",
        )
    action = str(body.get("action", "APPROVE"))
    comment = str(body.get("comment", body.get("comments", "Direct response")))
    responder = str(body.get("responder", "AGENT"))
    path = str(body.get("path", service.client.settings.workflow.default_path))
    return service.client.respond(
        nid=nid,
        action=action,
        comment=comment,
        responder=responder,
        path=path,
    )


@router.post(
    "/notifications/{notification_id}/respond", summary="Direct single respond"
)
def direct_respond(
    notification_id: Annotated[int, Path(ge=1)],
    request: DirectRespondRequest,
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> dict[str, Any]:
    """Execute direct response for a single notification."""
    comment_val = request.comments or request.comment or "Processed via Agent"
    responder_val = request.responder or "AGENT"
    return service.client.respond(
        nid=notification_id,
        action=request.action,
        comment=comment_val,
        responder=responder_val,
    )


# --- Phase 2 Routes ---


@router.post(
    "/analyze-workflow", summary="LLM-powered Triage and Policy Analysis"
)
def analyze_workflow(
    request: PendingWorklistRequest,
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> dict[str, Any]:
    """Perform LLM-powered workflow analysis using Gemini 3.8 Flash."""
    triage_res = service.triage_worklist(
        recipient=request.recipient,
        message_type=request.notification_type,
        limit=request.limit,
    )

    llm_analysis = "Policy verification complete."
    ai_client = get_ai_client()
    if ai_client:
        try:
            prompt = (
                f"Analyze pending worklist for manager {request.recipient}:\n"
                f"Total items: {triage_res.total_pending}\n"
                f"Table:\n{triage_res.markdown_table}\n"
            )
            response = generate_content_with_models(
                ai_client,
                prompt,
                types.GenerateContentConfig(temperature=0.2),
                fast_tier=False,
            )
            if response and getattr(response, "text", None):
                llm_analysis = response.text
        except (
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
            OSError,
        ) as exc:
            logger.debug("Gemini dynamic analysis skipped: %s", exc)

    return {
        "recipient": request.recipient,
        "total_pending": triage_res.total_pending,
        "risk_summary": triage_res.risk_summary,
        "analysis": llm_analysis,
        "triage_table_markdown": triage_res.markdown_table,
        "items": triage_res.items,
    }


@router.get(
    "/worklist/pending",
    response_model=WorklistResponse,
    summary="Retrieve Pending Worklist",
)
def get_pending_worklist(
    db_client: Annotated[EBSDatabaseClient, Depends(get_db_client)],
    recipient: str = Query(..., description="Recipient username or role"),
    notification_type: str | None = Query(
        None, description="APEXP, POAPPR, REQAPPR"
    ),
    max_amount: float | None = Query(None, description="Max amount filter"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
) -> WorklistResponse:
    """Retrieve pending notifications for a recipient.

    Supports bind-variable filtering.
    """
    if (
        notification_type
        and notification_type.upper() not in ALLOWED_WORKFLOW_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid notification_type: {notification_type}",
        )

    items_raw = db_client.get_pending_notifications(
        recipient=recipient,
        notification_type=notification_type,
        max_amount=max_amount,
        limit=limit,
    )
    records = [NotificationRecord.model_validate(item) for item in items_raw]
    for record in records:
        PolicyEngine.evaluate(record, record.attributes)
    return WorklistResponse(
        total_count=len(records),
        recipient=recipient,
        items=records,
    )


@router.post(
    "/worklist/evaluate",
    response_model=PolicyVerificationResponse,
    summary="Evaluate Worklist Policy",
)
def evaluate_worklist_policy(
    request: PolicyVerificationRequest,
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> PolicyVerificationResponse:
    """Evaluate policy compliance for specified notifications."""
    return service.verify_policy_batch(
        notification_ids=request.notification_ids
    )


@router.post(
    "/worklist/respond",
    response_model=WorkflowActionResponse,
    summary="Execute Worklist Response",
)
def respond_worklist(
    request: WorkflowActionRequest,
    service: Annotated[WorkflowTriageService, Depends(get_triage_service)],
) -> WorkflowActionResponse:
    """Execute APPROVE / REJECT on worklist notifications.

    Enforces human confirmation gate before state changes.
    """
    if request.action not in ("APPROVE", "REJECT"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Unsupported action [{request.action}]. "
                "Only APPROVE or REJECT are permitted."
            ),
        )

    execution_res = service.execute_action(request)

    if (
        hasattr(execution_res, "status")
        and execution_res.status == "CONFIRMATION_REQUIRED"
    ):
        proposal_dict = execution_res.model_dump()
        return WorkflowActionResponse(
            status="CONFIRMATION_REQUIRED",
            action=request.action,
            requires_confirmation=True,
            proposal=proposal_dict,
        )

    processed = [
        {
            "notification_id": r.notification_id,
            "status": r.status,
            "execution_path": r.execution_path,
            "message": r.message,
        }
        for r in getattr(execution_res, "results", [])
        if r.status == "SUCCESS"
    ]
    failed = [
        {
            "notification_id": r.notification_id,
            "status": r.status,
            "error": r.error or r.message,
            "message": r.message or r.error,
            "execution_path": r.execution_path,
        }
        for r in getattr(execution_res, "results", [])
        if r.status == "FAILED"
    ]

    return WorkflowActionResponse(
        status=getattr(execution_res, "status", "COMPLETED"),
        action=request.action,
        requires_confirmation=False,
        processed_items=processed,
        failed_items=failed,
    )


def register_with_a2a(gateway_url: str | None = None) -> bool:
    """Register this worker agent with the A2A Gateway registry."""
    target_url = gateway_url or "http://127.0.0.1:8080"
    try:
        with httpx.Client(timeout=1.0) as client:
            resp = client.post(
                f"{target_url.rstrip("/")}/a2a/agents/register",
                json={},
            )
            return resp.status_code == 200
    except (httpx.HTTPError, OSError, ValueError):
        return False


def create_app() -> FastAPI:
    """Create and configure FastAPI application for Workflow Agent Worker."""
    agent_app = FastAPI(
        title="Oracle EBS Workflow Agent Worker",
        description=(
            "Worker microservice for Oracle EBS Workflow inspection "
            "and response"
        ),
        version="1.0.0",
    )
    agent_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    agent_app.include_router(router)
    return agent_app


app = create_app()
