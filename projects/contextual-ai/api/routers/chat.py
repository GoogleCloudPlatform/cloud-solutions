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
import json

from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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

    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Error analyzing widget: %s", str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze widget: {str(e)}"
        ) from e


@router.post("/analyze-widget/stream", tags=["chat"])
async def analyze_widget_stream(request: WidgetAnalysisRequest):
    """
    Analyze widget interaction with streaming response.
    """
    try:
        logger.info(
            "Processing streaming widget analysis: %s", request.widgetMeta.title
        )

        # Create conversation entry immediately
        conversation_id = conversation_store.add_widget_analysis(
            f"Analyzing {request.widgetMeta.title}", request.dict()
        )

        # Get Vertex AI service
        vertex_service = get_vertex_service()

        def generate_stream():
            try:
                # Send initial data with conversation ID
                text_yield = json.dumps(
                    {
                        "type": "conversation_id",
                        "conversation_id": conversation_id
                    }
                )
                yield f"data: {text_yield}\n\n"

                # Send the analyzed data first
                data_summary = "📊 **Data Point Analysis**\n"
                if (
                    hasattr(request.interactionContext, "clickedDataPoint")
                    and request.interactionContext.clickedDataPoint
                ):
                    point = request.interactionContext.clickedDataPoint
                    if hasattr(point, "timestamp") and point.timestamp:
                        data_summary += f"• Time: {point.timestamp}\n"
                    if hasattr(point, "revenue") and point.revenue is not None:
                        data_summary += f"• Revenue: ${point.revenue:,.0f}\n"
                    if (
                        hasattr(point, "responseTime")
                        and point.responseTime is not None
                    ):
                        data_summary += (
                            f"• Response Time: {point.responseTime}ms\n"
                        )
                    if hasattr(point, "data") and point.data:
                        for key, value in point.data.items():
                            if key not in [
                                "timestamp",
                                "revenue",
                                "responseTime",
                            ]:
                                data_summary += f"• {key.replace("_", " ").title()}: {value}\n" # pylint: disable=line-too-long

                yield f"data: {json.dumps({"type": "data_summary", "content": data_summary})}\n\n" # pylint: disable=line-too-long

                # Now generate AI analysis using streaming
                analysis_chunks = []
                for chunk in vertex_service.generate_widget_analysis_stream(
                    request
                ):
                    if (
                        chunk.candidates
                        and chunk.candidates[0].content
                        and chunk.candidates[0].content.parts
                    ):
                        chunk_text = chunk.candidates[0].content.parts[0].text
                        analysis_chunks.append(chunk_text)
                        yield f"data: {json.dumps({"type": "analysis_chunk", "content": chunk_text})}\n\n" # pylint: disable=line-too-long

                # Save complete analysis to conversation
                full_analysis = "".join(analysis_chunks)
                if full_analysis.strip():
                    conversation_store.add_ai_response(
                        conversation_id, full_analysis
                    )

                # Send completion signal
                yield f"data: {json.dumps({"type": "complete"})}\n\n"

            except Exception as e: # pylint: disable=broad-exception-caught
                logger.error("Error in streaming widget analysis: %s", {str(e)})
                yield f"data: {json.dumps({"type": "error", "message": str(e)})}\n\n" # pylint: disable=line-too-long

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )

    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Error processing streaming widget analysis: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process streaming message: {str(e)}"
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

    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Error processing chat message: %s", str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to process message: {str(e)}"
        ) from e


@router.post("/message/stream", tags=["chat"])
async def send_chat_message_stream(message: ChatMessage):
    """
    Send a chat message and get a streaming AI response.
    """
    try:
        logger.info(
            "Processing streaming chat message: %s...", message.content[:100]
        )

        # Add user message to conversation
        conversation_id = (
            message.conversationId
            or conversation_store.add_chat_message(message.content)
        )

        # Generate streaming AI response using Vertex AI
        vertex_service = get_vertex_service()

        def generate_stream():
            try:
                # Send initial data with conversation ID
                yield f"data: {json.dumps({"type": "conversation_id", "conversation_id": conversation_id})}\n\n" # pylint: disable=line-too-long

                response_chunks = []
                for chunk in vertex_service.generate_follow_up_response_stream(
                    message.content, conversation_id
                ):
                    if (
                        chunk.candidates
                        and chunk.candidates[0].content
                        and chunk.candidates[0].content.parts
                    ):
                        chunk_text = chunk.candidates[0].content.parts[0].text
                        response_chunks.append(chunk_text)
                        # Send chunk to client
                        yield f"data: {json.dumps({"type": "chunk", "content": chunk_text})}\n\n" # pylint: disable=line-too-long

                # Combine all chunks and save to conversation
                full_response = "".join(response_chunks)
                if full_response.strip():
                    conversation_store.add_ai_response(
                        conversation_id, full_response
                    )

                # Send completion signal
                yield f"data: {json.dumps({"type": "complete"})}\n\n"

            except Exception as e: # pylint: disable=broad-exception-caught
                logger.error("Error in streaming response: %s", str(e))
                yield f"data: {json.dumps({"type": "error", "message": str(e)})}\n\n" # pylint: disable=line-too-long

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )

    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Error processing streaming chat message: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process streaming message: {str(e)}"
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
    except Exception as e: # pylint: disable=broad-exception-caught
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

    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Error retrieving conversations: %s", str(e))
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
    except Exception as e: # pylint: disable=broad-exception-caught
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

    except Exception as e: # pylint: disable=broad-exception-caught
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
