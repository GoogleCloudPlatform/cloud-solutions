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


# pylint: disable=line-too-long, broad-exception-caught
"""Module containing GECX tickets logic."""

import json
import logging
import os
import re
import sys

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from src.backend.routes.loopback.chat import (
    ACTIVE_CONVERSATIONS,
    CHAT_ROOMS,
    agent_assist_service,
)
from src.backend.services.agent_assist import AgentAssistService
from src.backend.services.bigquery_service import BigQueryService

logger = logging.getLogger(__name__)

router = APIRouter()
bq_service = BigQueryService()


class TicketCreateRequest(BaseModel):
    """Request schema to create a support ticket."""

    account: str = Field(..., description="User's bank account number")
    isin: str = Field(..., description="Financial instrument ISIN code")
    reference_id: str = Field(
        ..., description="External transaction reference ID"
    )
    description: str = Field(..., description="User issue detail description")
    temp_session_id: str = Field(
        None,
        description="Optional temporary session ID to migrate chat history from",
    )
    gecx_conversation_id: str = Field(
        None, description="Optional GECX conversation ID to complete"
    )

    @field_validator("account")
    @classmethod
    def validate_account(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Account number cannot be empty")
        return v

    @field_validator("isin")
    @classmethod
    def validate_isin(cls, v: str) -> str:
        v = v.strip().upper()
        # ISIN must be exactly 12 characters and match standard alphanumeric pattern
        if not re.match(r"^[A-Z]{2}[A-Z0-9]{9}\d$", v):
            raise ValueError(
                "Invalid ISIN format. Must be a standard 12-character alphanumeric code."
            )
        return v

    @field_validator("reference_id")
    @classmethod
    def validate_reference_id(cls, v: str) -> str:
        v = v.strip()
        # Reference ID must start with REF- and contain alphanumeric characters/hyphens
        if not re.match(r"^REF-[A-Z0-9\-]+$", v):
            raise ValueError(
                "Invalid Reference ID format. Must start with 'REF-' followed by transaction identifier."
            )
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v


@router.post("/tickets", status_code=status.HTTP_200_OK)
def create_ticket(payload: TicketCreateRequest):
    print(
        f"[Tickets API] Received ticket creation request for account: {payload.account}, GECX Conversation ID: {payload.gecx_conversation_id}"
    )
    try:
        result = bq_service.insert_ticket(
            account=payload.account,
            isin=payload.isin,
            reference_id=payload.reference_id,
            description=payload.description,
        )
        ticket_id = result.get("ticket_id")
        if ticket_id:
            temp_session_id = (
                payload.temp_session_id
                if payload.temp_session_id
                else f"{payload.account}-session"
            )
            if temp_session_id in CHAT_ROOMS:
                print(
                    f"[Tickets API] Migrating chat history from temporary session {temp_session_id} to ticket {ticket_id}"
                )
                temp_room = CHAT_ROOMS.pop(temp_session_id)
                CHAT_ROOMS[ticket_id] = temp_room

            # Complete the GECX virtual agent conversation if session ID is provided
            if payload.gecx_conversation_id:
                project_id = os.environ.get("GCP_PROJECT_ID")
                if project_id:
                    gecx_conv_name = f"projects/{project_id}/locations/global/conversations/{payload.gecx_conversation_id}"
                    try:
                        logger.info(
                            "Completing GECX Chat Conversation: %s",
                            gecx_conv_name,
                        )
                        AgentAssistService().complete_conversation(
                            gecx_conv_name
                        )
                    except Exception as ce_ex:
                        logger.error(
                            "Failed to complete GECX conversation %s: %s",
                            gecx_conv_name,
                            ce_ex,
                        )
                else:
                    logger.warning(
                        "GCP_PROJECT_ID environment variable is missing. "
                        "Cannot complete GECX conversation."
                    )
        return result
    except Exception as e:
        logger.error("Database insertion failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Failed to create ticket.",
        ) from e


class TicketResolveRequest(BaseModel):
    """Request schema to resolve a support ticket."""

    resolution_summary: str = Field(..., description="Summary of resolution")
    email_recipient: str = Field(..., description="Recipient email address")
    email_subject: str = Field(..., description="Email subject")
    email_body: str = Field(..., description="Email body")

    @field_validator(
        "resolution_summary", "email_recipient", "email_subject", "email_body"
    )
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v


@router.post("/tickets/{ticket_id}/resolve", status_code=status.HTTP_200_OK)
def resolve_ticket(ticket_id: str, payload: TicketResolveRequest):
    try:
        # 1. Update status and resolution summary in BigQuery
        bq_service.resolve_ticket(ticket_id, payload.resolution_summary)

        # 2. Print JSON notification email send payload synchronously to stdout
        email_log = {
            "type": "notification_sent",
            "channel": "email",
            "ticket_id": ticket_id,
            "status": "success",
            "recipient": payload.email_recipient,
            "subject": payload.email_subject,
        }
        print(json.dumps(email_log))
        sys.stdout.flush()

        return {"ticket_id": ticket_id, "status": "resolved"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resolution commit failed: {str(e)}",
        ) from e


@router.get("/tickets/{ticket_id}/transcript")
def get_ticket_transcript(ticket_id: str):
    metadata = ACTIVE_CONVERSATIONS.get(ticket_id)
    if not metadata or "conversation_name" not in metadata:
        # Fall back to empty array if no active GCP Dialogflow Conversation exists
        return []

    try:
        messages = agent_assist_service.list_conversation_messages(
            metadata["conversation_name"]
        )
        return messages
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation transcript: {str(e)}",
        ) from e
