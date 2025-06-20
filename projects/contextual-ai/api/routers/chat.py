# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This module provides API endpoints for the chat service,
including widget analysis and general chat interactions.
It uses Vertex AI for generating responses and an in-memory
store for managing conversations.
"""


import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from models.chat import (
    WidgetAnalysisRequest,
    WidgetAnalysisResponse,
    ChatMessage,
    ChatResponse,
    Conversation,
    ConversationListResponse,
)
from utils.vertex_ai_service import get_vertex_service
from utils.conversation_store import conversation_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze-widget", response_model=WidgetAnalysisResponse, tags=["chat"]
)
async def analyze_widget(
    request: WidgetAnalysisRequest,
) -> WidgetAnalysisResponse:
    """
    Analyze widget interaction and create conversation entry.

    This is the main endpoint for widget analysis that:
    1. Receives widget interaction data
    2. Generates AI analysis
    3. Creates conversation entry
    4. Returns analysis response with conversation ID
    """
    try:
        logger.info("Analyzing widget: %s", request.widgetMeta.title)

        # Generate AI analysis based on widget context using Vertex AI
        vertex_service = get_vertex_service()
        analysis_response = vertex_service.generate_widget_analysis(request)

        # Create interaction summary for conversation
        interaction_type = request.interactionContext.clickType.replace(
            "-", " "
        )
        interaction_summary = f"{interaction_type}"

        if request.interactionContext.clickedDataPoint:
            dp = request.interactionContext.clickedDataPoint
            if dp.timestamp:
                interaction_summary += f" at {dp.timestamp}"
            if dp.revenue is not None:
                interaction_summary += f" (Revenue: ${dp.revenue:,.0f})"
            if dp.responseTime is not None:
                interaction_summary += f" (Response: {dp.responseTime}ms)"

        # Create conversation entry
        conversation_id = (
            conversation_store.create_widget_analysis_conversation(
                widget_title=request.widgetMeta.title,
                analysis_result=analysis_response,
                interaction_summary=interaction_summary,
            )
        )

        # Update response with conversation ID
        analysis_response.conversationId = conversation_id

        logger.info(
            "Created conversation %s for widget analysis", conversation_id
        )
        return analysis_response

    except Exception as e:
        logger.error("Error analyzing widget: %s", str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze widget: {str(e)}"
        ) from e


@router.post("/message", response_model=ChatResponse, tags=["chat"])
async def send_chat_message(message: ChatMessage) -> ChatResponse:
    """
    Send a chat message and get AI response.

    This endpoint handles regular chat messages (not widget-triggered).
    It can add to an existing conversation or create a new one.
    """
    try:
        logger.info("Processing chat message: %s...", message.content[:50])

        # Add user message to conversation
        conversation_id = (
            message.conversationId
            or conversation_store.add_chat_message(message.content)
        )

        # Generate AI response using Vertex AI
        vertex_service = get_vertex_service()
        ai_response = vertex_service.generate_follow_up_response(
            message.content, conversation_id
        )

        # Add AI response to conversation
        conversation_store.add_ai_response(conversation_id, ai_response)

        response = ChatResponse(
            conversationId=conversation_id,
            response=ai_response,
            timestamp=conversation_store.get_conversation(
                conversation_id
            ).updatedAt,
        )

        logger.info("Generated response for conversation %s", conversation_id)
        return response

    except Exception as e:
        logger.error("Error processing chat message: %s", str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to process message: {str(e)}"
        ) from e


@router.get(
    "/conversations/{conversation_id}",
    response_model=Conversation,
    tags=["chat"],
)
async def get_conversation(conversation_id: str) -> Conversation:
    """
    Get a specific conversation by ID.
    """
    try:
        conversation = conversation_store.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=404, detail="Conversation not found"
            )

        return conversation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error retrieving conversation {conversation_id}: %s", str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve conversation: {str(e)}"
        ) from e


@router.get(
    "/conversations", response_model=ConversationListResponse, tags=["chat"]
)
async def get_conversations(
    limit: int = 50, offset: int = 0, hours: Optional[int] = None
) -> ConversationListResponse:
    """
    Get list of conversations.

    Parameters:
    - limit: Maximum number of conversations to return
    - offset: Number of conversations to skip
    - hours: If specified, only return conversations from the last N hours
    """
    try:
        if hours is not None:
            conversations = conversation_store.get_recent_conversations(
                hours=hours
            )
            conversations = conversations[offset : offset + limit]
        else:
            conversations = conversation_store.get_all_conversations(
                limit=limit, offset=offset
            )

        total = len(conversation_store.get_all_conversations())

        return ConversationListResponse(
            conversations=conversations,
            total=total,
            page=offset // limit + 1,
            pageSize=limit,
        )

    except Exception as e:
        logger.error("Error retrieving conversations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversations: {str(e)}",
        ) from e


@router.post("/conversations/{conversation_id}/resolve", tags=["chat"])
async def resolve_conversation(conversation_id: str):
    """
    Mark a conversation as resolved.
    """
    try:
        success = conversation_store.resolve_conversation(conversation_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Conversation not found"
            )

        return {
            "message": "Conversation resolved",
            "conversationId": conversation_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error resolving conversation %s: %s", conversation_id, str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to resolve conversation: {str(e)}"
        ) from e


@router.delete("/conversations", tags=["chat"])
async def clear_all_conversations():
    """
    Clear all conversations (for testing/demo purposes).
    """
    try:
        conversation_store.clear_all()
        return {"message": "All conversations cleared"}

    except Exception as e:
        logger.error("Error clearing conversations: %s", str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to clear conversations: {str(e)}"
        ) from e


@router.get("/health", tags=["chat"])
async def health_check():
    """
    Health check endpoint for the chat service.
    """
    return {
        "status": "healthy",
        "service": "chat-api",
        "conversations": len(conversation_store.get_all_conversations()),
    }
