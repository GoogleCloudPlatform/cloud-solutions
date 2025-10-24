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
Pydantic models for representing data related to the chat interface and
contextual analysis.

This module defines the data structures used for handling chat messages,
conversation history, and the context provided for analyzing user interactions
with dashboard widgets.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WidgetMeta(BaseModel):
    type: str  # "chart", "kpi", "table", etc.
    subtype: str  # "line-chart", "bar-chart", "gauge", etc.
    title: str
    dataSource: str
    timeRange: str


class ClickedDataPoint(BaseModel):
    timestamp: str
    revenue: Optional[float] = None
    responseTime: Optional[float] = None
    # Allow additional fields for different chart types
    data: Optional[Dict[str, Any]] = None


class InteractionContext(BaseModel):
    clickedDataPoint: Optional[ClickedDataPoint] = None
    clickType: str  # "data-point", "legend", "axis", "area", etc.
    coordinates: Optional[Dict[str, float]] = (
        None  # x, y coordinates if relevant
    )


class VisibleKPIs(BaseModel):
    totalRevenue: Optional[float] = None
    activeUsers: Optional[int] = None
    pageViews: Optional[int] = None
    responseTime: Optional[str] = None
    # Allow additional KPIs
    additionalKPIs: Optional[Dict[str, Any]] = None


class ScreenContext(BaseModel):
    pageUrl: str
    visibleKPIs: Optional[VisibleKPIs] = None
    recentActivity: Optional[List[str]] = None
    otherVisibleCharts: Optional[List[str]] = None


class UserContext(BaseModel):
    role: str
    permissions: List[str]
    userId: Optional[str] = None


class WidgetAnalysisRequest(BaseModel):
    widgetMeta: WidgetMeta
    interactionContext: InteractionContext
    screenContext: ScreenContext
    userContext: UserContext


class ConversationEntry(BaseModel):
    id: str
    timestamp: str
    type: str  # "user" or "assistant"
    content: str
    metadata: Optional[Dict[str, Any]] = None


class Conversation(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    entries: List[ConversationEntry]
    status: str  # "active", "resolved"
    tags: Optional[List[str]] = None


class WidgetAnalysisResponse(BaseModel):
    conversationId: str
    response: str
    actionSuggestions: Optional[List[str]] = None
    relatedMetrics: Optional[List[str]] = None
    confidence: Optional[float] = None
    analysisType: Optional[str] = None


class ChatMessage(BaseModel):
    content: str
    conversationId: Optional[str] = None


class ChatResponse(BaseModel):
    conversationId: str
    response: str
    timestamp: str


class ConversationListResponse(BaseModel):
    conversations: List[Conversation]
    total: int
    page: int
    pageSize: int
