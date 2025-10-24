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

"""In-memory conversation storage for demo purposes."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from models.chat import Conversation, ConversationEntry, WidgetAnalysisResponse


class ConversationStore:
    """In-memory conversation storage for demo purposes."""

    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}
        self._conversation_counter = 1

        # Initialize with demo data
        self._initialize_demo_conversations()

    def create_widget_analysis_conversation(
        self,
        widget_title: str,
        analysis_result: WidgetAnalysisResponse,
        interaction_summary: str,
    ) -> str:
        """Create a new conversation from widget analysis."""
        ts_number = int(datetime.now().timestamp())
        conversation_id = f"conv-{ts_number}-{self._conversation_counter}"
        self._conversation_counter += 1
        timestamp = datetime.now().isoformat()

        # Create user entry showing what was analyzed
        user_entry = ConversationEntry(
            id=f"{conversation_id}-user",
            timestamp=timestamp,
            type="user",
            content=f"🔍 Analyzed {widget_title} - {interaction_summary}",
            metadata={
                "widgetId": widget_title.lower().replace(" ", "-"),
                "interactionType": "widget-analysis",
            },
        )

        # Create assistant entry with analysis result
        assistant_timestamp = (
            datetime.now() + timedelta(seconds=1)
        ).isoformat()
        assistant_metadata = {
            "widgetId": widget_title.lower().replace(" ", "-"),
            "actionSuggestions": analysis_result.actionSuggestions,
            "relatedMetrics": analysis_result.relatedMetrics,
            "confidence": analysis_result.confidence,
            "analysisType": analysis_result.analysisType,
        }

        # Add AI provider metadata
        assistant_metadata["aiProvider"] = "vertex-ai"

        assistant_entry = ConversationEntry(
            id=f"{conversation_id}-assistant",
            timestamp=assistant_timestamp,
            type="assistant",
            content=analysis_result.response,
            metadata=assistant_metadata,
        )

        conversation = Conversation(
            id=conversation_id,
            title=f"{widget_title} Analysis",
            createdAt=timestamp,
            updatedAt=assistant_timestamp,
            entries=[user_entry, assistant_entry],
            status="active",
            tags=["widget-analysis", analysis_result.analysisType or "general"],
        )

        self._conversations[conversation_id] = conversation

        # Update the analysis result with the conversation ID
        analysis_result.conversationId = conversation_id

        return conversation_id

    def add_chat_message(
        self, message: str, user_id: Optional[str] = None
    ) -> str:
        """
        Add a regular chat message to the most
        recent conversation or create new one.
        """

        timestamp = datetime.now().isoformat()

        # Check if there's an active conversation from the last 10 minutes
        recent_conversation = self._get_recent_active_conversation(minutes=10)

        if recent_conversation:
            # Add to existing conversation
            ts_number = int(datetime.now().timestamp())
            user_entry = ConversationEntry(
                id=f"{recent_conversation.id}-user-{ts_number}",
                timestamp=timestamp,
                type="user",
                content=message,
                metadata={"userId": user_id} if user_id else None,
            )

            recent_conversation.entries.append(user_entry)
            recent_conversation.updatedAt = timestamp

            return recent_conversation.id
        else:
            # Create new conversation
            ts_number = int(datetime.now().timestamp())
            conversation_id = f"conv-{ts_number}-{self._conversation_counter}"
            self._conversation_counter += 1

            user_entry = ConversationEntry(
                id=f"{conversation_id}-user",
                timestamp=timestamp,
                type="user",
                content=message,
                metadata={"userId": user_id} if user_id else None,
            )

            conversation = Conversation(
                id=conversation_id,
                title=message[:50] + ("..." if len(message) > 50 else ""),
                createdAt=timestamp,
                updatedAt=timestamp,
                entries=[user_entry],
                status="active",
                tags=["chat"],
            )

            self._conversations[conversation_id] = conversation
            return conversation_id

    def add_ai_response(
        self,
        conversation_id: str,
        response: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Add an AI response to an existing conversation."""

        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return False

        timestamp = datetime.now().isoformat()

        # Add AI provider metadata
        if metadata is None:
            metadata = {}

        metadata["aiProvider"] = "vertex-ai"

        assistant_entry = ConversationEntry(
            id=f"{conversation_id}-assistant-{int(datetime.now().timestamp())}",
            timestamp=timestamp,
            type="assistant",
            content=response,
            metadata=metadata,
        )

        conversation.entries.append(assistant_entry)
        conversation.updatedAt = timestamp

        return True

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)

    def get_all_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Conversation]:
        """Get all conversations, sorted by most recent first."""
        conversations = list(self._conversations.values())
        conversations.sort(key=lambda c: c.updatedAt, reverse=True)
        return conversations[offset : offset + limit]

    def get_recent_conversations(self, hours: int = 24) -> List[Conversation]:
        """Get conversations from the last N hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cutoff_iso = cutoff_time.isoformat()

        recent_conversations = [
            conv
            for conv in self._conversations.values()
            if conv.updatedAt >= cutoff_iso
        ]

        recent_conversations.sort(key=lambda c: c.updatedAt, reverse=True)
        return recent_conversations

    def resolve_conversation(self, conversation_id: str) -> bool:
        """Mark a conversation as resolved."""
        conversation = self._conversations.get(conversation_id)
        if conversation:
            conversation.status = "resolved"
            conversation.updatedAt = datetime.now().isoformat()
            return True
        return False

    def clear_all(self):
        """Clear all conversations (for testing)."""
        self._conversations.clear()
        self._conversation_counter = 1

    def _get_recent_active_conversation(
        self, minutes: int = 10
    ) -> Optional[Conversation]:
        """Get the most recent active conversation within N minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        cutoff_iso = cutoff_time.isoformat()

        active_conversations = [
            conv
            for conv in self._conversations.values()
            if conv.status == "active" and conv.updatedAt >= cutoff_iso
        ]

        if active_conversations:
            active_conversations.sort(key=lambda c: c.updatedAt, reverse=True)
            return active_conversations[0]

        return None

    def _initialize_demo_conversations(self):
        """Initialize with some demo conversations for testing."""

        # Demo conversation 1: System performance query
        demo_timestamp = (datetime.now() - timedelta(minutes=15)).isoformat()
        demo_conv = Conversation(
            id="demo-system-perf",
            title="System Performance Query",
            createdAt=demo_timestamp,
            updatedAt=(datetime.now() - timedelta(minutes=10)).isoformat(),
            entries=[
                ConversationEntry(
                    id="demo-system-perf-user",
                    timestamp=demo_timestamp,
                    type="user",
                    content="What is the current system performance status?",
                ),
                ConversationEntry(
                    id="demo-system-perf-assistant",
                    timestamp=(
                        datetime.now() - timedelta(minutes=14)
                    ).isoformat(),
                    type="assistant",
                    content=(
                        "Current system performance is "
                        "stable with all services operational. "
                        "Response times are within normal ranges, "
                        "averaging 245ms. CPU utilization across "
                        "the cluster is at 58%, providing good headroom "
                        "for traffic spikes."
                    ),
                ),
            ],
            status="resolved",
            tags=["system-health", "performance"],
        )

        self._conversations["demo-system-perf"] = demo_conv


# Global instance for demo purposes
conversation_store = ConversationStore()
