// Copyright 2024 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Type definitions for chat and widget analysis system

export interface WidgetMeta {
  type: 'chart' | 'table' | 'metric' | 'heatmap';
  subtype: string;
  title: string;
  dataSource: string;
  timeRange: string;
}

export interface InteractionContext {
  clickedDataPoint?: {
    timestamp: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    [key: string]: any;
  };
  clickType: 'data-point' | 'service-tile' | 'anomaly' | 'trend-line';
  selectedRange?: {
    start: string;
    end: string;
  };
}

export interface ScreenContext {
  pageUrl: string;
  visibleKPIs: {
    [key: string]: string | number;
  };
  recentActivity: Array<{
    id: number;
    action: string;
    time: string;
    status: string;
  }>;
  otherVisibleCharts: string[];
}

export interface UserContext {
  role: string;
  permissions: string[];
  userId?: string;
  preferences?: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    [key: string]: any;
  };
}

export interface WidgetAnalysisRequest {
  widgetMeta: WidgetMeta;
  interactionContext: InteractionContext;
  screenContext: ScreenContext;
  userContext: UserContext;
}

export interface ConversationEntry {
  id: string;
  timestamp: string;
  type: 'user' | 'assistant';
  content: string;
  metadata?: {
    widgetId?: string;
    actionSuggestions?: string[];
    relatedMetrics?: string[];
    confidence?: number;
    analysisType?: string;
    isMockAI?: boolean;
    aiProvider?: 'mock' | 'gemini';
    interactionType?: string;
    responseTime?: number;
    serviceName?: string;
    healthScore?: number;
    cpu?: number;
    memory?: number;
    errorRate?: number;
  };
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  entries: ConversationEntry[];
  status: 'active' | 'resolved' | 'archived';
}

export interface WidgetAnalysisResponse {
  conversationId: string;
  response: string;
  actionSuggestions?: string[];
  relatedMetrics?: string[];
  confidence?: number;
  analysisType?: string;
  followUpQuestions?: string[];
}

export interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: string;
  metadata?: {
    widgetId?: string;
    actionSuggestions?: string[];
    relatedMetrics?: string[];
    confidence?: number;
    analysisType?: string;
    isMockAI?: boolean;
    aiProvider?: 'mock' | 'gemini';
    interactionType?: string;
  };
}

/**
 * Represents the response from the chat API after sending a message.
 */
export interface ChatResponse {
  conversationId: string;
  response: string;
  timestamp: string;
}

export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ErrorRateData {
  timestamp: string;
  errorRate: number;
  // Add other properties like errorType, count, etc., if known
}

/** Represents a data point for revenue and response time. */
export interface RevenueResponseTimeData {
  timestamp: string;
  revenue: number;
  responseTime: number;
  // Add other properties if known from the BigQuery schema
}

/** Represents a data point for system health metrics. */
export interface SystemHealthData {
  serviceName: string;
  healthScore: number;
  cpu: number;
  memory: number;
  responseTime: number;
  // Add other properties if known from the BigQuery schema
}
