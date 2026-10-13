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

"""Model Context Protocol (MCP) Server for Oracle EBS Workflows."""

import json
import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from src.a2a.schemas import WorkflowActionRequest
from src.workflow.service import WorkflowTriageService

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Oracle EBS Workflow MCP Server",
    description="MCP Tool Interface for Gemini CLI and Enterprise Agents.",
    version="1.0.0",
)


@lru_cache
def get_service() -> WorkflowTriageService:
    """Dependency provider for WorkflowTriageService."""
    return WorkflowTriageService()


ServiceDep = Annotated[WorkflowTriageService, Depends(get_service)]


class ToolCallRequest(BaseModel):
    """Payload for invoking an MCP tool."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Tool name identifier")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool invocation arguments"
    )


class MCPTool(BaseModel):
    """MCP Tool metadata descriptor."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    input_schema: dict[str, Any] = Field(..., alias="inputSchema")


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return catalog of exposed Oracle EBS Workflow MCP tools."""
    return [
        {
            "name": "ebs_list_pending_notifications",
            "description": (
                "List pending Oracle EBS workflow notifications for "
                "APEXP (Expenses), POAPPR (POs), or REQAPPR (Requisitions)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "message_type": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
        {
            "name": "ebs_inspect_notification",
            "description": (
                "Inspect detailed attributes for a specific notification ID."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "notification_id": {"type": "integer"},
                },
                "required": ["notification_id"],
            },
        },
        {
            "name": "ebs_verify_policy",
            "description": (
                "Evaluate corporate policy compliance and risk flags for "
                "one or more notification IDs."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "notification_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["notification_ids"],
            },
        },
        {
            "name": "ebs_triage_workflow",
            "description": (
                "Triage open notifications, evaluate policy risks, and "
                "synthesize a comprehensive summary table with next steps."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "message_type": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
        {
            "name": "ebs_respond_notification",
            "description": (
                "Execute approval or rejection under the explicit human "
                "confirmation gate using certified PL/SQL or REST APIs."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["APPROVE", "REJECT"],
                    },
                    "notification_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "comment": {"type": "string"},
                    "confirmed": {"type": "boolean", "default": False},
                    "execution_path": {
                        "type": "string",
                        "enum": ["REST", "PLSQL"],
                        "default": "REST",
                    },
                },
                "required": ["action", "notification_ids"],
            },
        },
    ]


@app.api_route(
    "/health",
    methods=["GET", "POST", "OPTIONS"],
    status_code=status.HTTP_200_OK,
)
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "oracle_ebs_workflow_mcp_server"}


@app.post("/tools/list")
def list_tools() -> dict[str, Any]:
    """Return all available MCP tool definitions."""
    return {"tools": get_tool_definitions()}


@app.post("/tools/call")
def call_tool(
    request: ToolCallRequest,
    service: ServiceDep,
) -> dict[str, Any]:
    """Execute a specified MCP tool with argument validation."""
    name = request.name
    args = request.arguments

    if name == "ebs_list_pending_notifications":
        notifications = service.client.list_notifications(
            recipient=args.get("recipient"),
            message_type=args.get("message_type"),
            limit=int(args.get("limit", 50)),
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        [n.model_dump() for n in notifications], indent=2
                    ),
                }
            ]
        }

    if name == "ebs_inspect_notification":
        nid = int(args.get("notification_id", 0))
        detail = service.client.get_notification_detail(nid)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(detail.model_dump(), indent=2),
                }
            ]
        }

    if name == "ebs_verify_policy":
        nids = [int(x) for x in args.get("notification_ids", [])]
        verification = service.verify_policies_for_notifications(nids)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(verification.model_dump(), indent=2),
                }
            ]
        }

    if name == "ebs_triage_workflow":
        triage_res = service.triage_pending_notifications(
            recipient=args.get("recipient"),
            message_type=args.get("message_type"),
            limit=int(args.get("limit", 50)),
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(triage_res.model_dump(), indent=2),
                }
            ]
        }

    if name == "ebs_respond_notification":
        act_req = WorkflowActionRequest(
            action=args.get("action", "APPROVE"),
            notification_ids=[int(x) for x in args.get("notification_ids", [])],
            comment=args.get("comment", ""),
            confirmed=bool(args.get("confirmed", False)),
            execution_path=args.get("execution_path", "REST"),
        )
        action_res = service.process_action(act_req)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(action_res.model_dump(), indent=2),
                }
            ]
        }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown MCP tool '{name}'",
    )
