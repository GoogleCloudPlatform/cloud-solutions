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

// API service for connecting to BigQuery data endpoints

import {
  ChatResponse,
  Conversation,
  ConversationListResponse,
  ErrorRateData,
  RevenueResponseTimeData,
  SystemHealthData,
  WidgetAnalysisRequest,
  WidgetAnalysisResponse,
} from '../types/chat';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080';

export interface ApiResponse<T> {
  data: T;
  status: 'success' | 'error';
  message?: string;
}

export class ApiService {
  private static async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'cloud-solutions/contextual-ai-for-isv-1.0.0',
          ...options?.headers,
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        data,
        status: 'success',
      };
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      return {
        data: null as T,
        status: 'error',
        message: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  // Revenue and response time data from BigQuery
  static async getRevenueResponseTimeData(
    days: number = 7
  ): Promise<ApiResponse<RevenueResponseTimeData[]>> {
    return this.request<RevenueResponseTimeData[]>(
      `/data_access/revenue-response-time?days=${days}`
    );
  }

  // System health metrics from BigQuery
  static async getSystemHealthData(): Promise<ApiResponse<SystemHealthData[]>> {
    return this.request<SystemHealthData[]>('/data_access/system-health');
  }

  // Error rate trends from BigQuery
  static async getErrorRateData(
    hours: number = 24
  ): Promise<ApiResponse<ErrorRateData[]>> {
    return this.request<ErrorRateData[]>(
      `/data_access/error-rates?hours=${hours}`
    );
  }

  // General data access endpoint
  static async queryData(
    query: string,
    params?: Record<string, unknown>
  ): Promise<ApiResponse<unknown>> {
    return this.request<unknown>('/data_access/query', {
      method: 'POST',
      body: JSON.stringify({query, params}),
    });
  }

  // Chat API endpoints
  static async sendChatMessage(
    content: string,
    conversationId?: string
  ): Promise<ApiResponse<ChatResponse>> {
    return this.request<ChatResponse>('/api/chat/message', {
      method: 'POST',
      body: JSON.stringify({content, conversationId}),
    });
  }

  static async analyzeWidget(
    widgetAnalysisRequest: WidgetAnalysisRequest
  ): Promise<ApiResponse<WidgetAnalysisResponse>> {
    return this.request<WidgetAnalysisResponse>('/api/chat/analyze-widget', {
      method: 'POST',
      body: JSON.stringify(widgetAnalysisRequest),
    });
  }

  static async getConversations(
    limit: number = 50,
    offset: number = 0,
    hours?: number
  ): Promise<ApiResponse<ConversationListResponse>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    if (hours) {
      params.append('hours', hours.toString());
    }
    return this.request<ConversationListResponse>(
      `/api/chat/conversations?${params}`
    );
  }

  static async getConversation(
    conversationId: string
  ): Promise<ApiResponse<Conversation>> {
    return this.request<Conversation>(
      `/api/chat/conversations/${conversationId}`
    );
  }
}

export default ApiService;
