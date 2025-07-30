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

/* eslint-disable no-constant-condition */
/* eslint-disable @typescript-eslint/no-explicit-any */

interface DataPoint {
  timestamp: string;
  revenue: number;
  responseTime: number;
}

interface WidgetMeta {
  type: string;
  subtype: string;
  title: string;
  dataSource: string;
  timeRange: string;
}

interface ClickedDataPoint {
  timestamp: string;
  revenue?: number;
  responseTime?: number;
  data?: Record<string, any>;
}

interface InteractionContext {
  clickedDataPoint?: ClickedDataPoint;
  clickType: string;
  coordinates?: {x: number; y: number};
}

interface VisibleKPIs {
  totalRevenue?: number;
  activeUsers?: number;
  pageViews?: number;
  responseTime?: string;
  additionalKPIs?: Record<string, any>;
}

interface ScreenContext {
  pageUrl: string;
  visibleKPIs?: VisibleKPIs;
  recentActivity?: string[];
  otherVisibleCharts?: string[];
}

interface UserContext {
  role: string;
  permissions: string[];
  userId?: string;
}

interface WidgetAnalysisRequest {
  widgetMeta: WidgetMeta;
  interactionContext: InteractionContext;
  screenContext: ScreenContext;
  userContext: UserContext;
}

interface WidgetAnalysisResponse {
  conversationId: string;
  response: string;
  actionSuggestions?: string[];
  relatedMetrics?: string[];
  confidence?: number;
  analysisType?: string;
}

class WidgetAnalysisService {
  private static readonly API_BASE_URL =
    process.env.REACT_APP_API_URL || 'http://localhost:8080';

  static async analyzeWidgetStream(
    request: WidgetAnalysisRequest,
    onDataSummary: (summary: string) => void,
    onAnalysisChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: string) => void
  ): Promise<string> {
    try {
      const response = await fetch(
        `${this.API_BASE_URL}/api/chat/analyze-widget/stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
        }
      );

      if (!response.ok) {
        throw new Error(
          `API request failed: ${response.status} ${response.statusText}`
        );
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body reader available');
      }

      const decoder = new TextDecoder();
      let conversationId = '';

      try {
        while (true) {
          const {done, value} = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

                if (data.type === 'conversation_id') {
                  conversationId = data.conversation_id;
                } else if (data.type === 'data_summary') {
                  onDataSummary(data.content);
                } else if (data.type === 'analysis_chunk') {
                  onAnalysisChunk(data.content);
                } else if (data.type === 'complete') {
                  onComplete();
                } else if (data.type === 'error') {
                  onError(data.message);
                }
              } catch (e) {
                // Ignore JSON parse errors for malformed chunks
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

      return conversationId;
    } catch (error) {
      console.error('Widget analysis streaming failed:', error);
      onError(error instanceof Error ? error.message : 'Unknown error');
      throw error;
    }
  }

  static async analyzeWidget(
    request: WidgetAnalysisRequest
  ): Promise<WidgetAnalysisResponse> {
    try {
      const response = await fetch(
        `${this.API_BASE_URL}/api/chat/analyze-widget`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
        }
      );

      if (!response.ok) {
        throw new Error(
          `API request failed: ${response.status} ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('Widget analysis API call failed:', error);
      throw error;
    }
  }

  static async analyzeRevenueResponseChart(
    dataPoint: DataPoint,
    visibleKPIs?: VisibleKPIs
  ): Promise<WidgetAnalysisResponse> {
    const request: WidgetAnalysisRequest = {
      widgetMeta: {
        type: 'chart',
        subtype: 'line-chart',
        title: 'Revenue vs Response Time Correlation',
        dataSource: 'bigquery.ecommerce.revenue_metrics',
        timeRange: 'last_7_days',
      },
      interactionContext: {
        clickedDataPoint: {
          timestamp: dataPoint.timestamp,
          revenue: dataPoint.revenue,
          responseTime: dataPoint.responseTime,
        },
        clickType: 'data-point',
      },
      screenContext: {
        pageUrl: window.location.pathname,
        visibleKPIs: visibleKPIs || {
          totalRevenue: 45231,
          activeUsers: 2345,
          pageViews: 54321,
          responseTime: '1.2s',
        },
        recentActivity: [],
        otherVisibleCharts: ['Error Rate Trend Chart', 'System Health Heatmap'],
      },
      userContext: {
        role: 'devops-engineer',
        permissions: ['view-infrastructure', 'create-incidents'],
        userId: 'current-user',
      },
    };

    return this.analyzeWidget(request);
  }

  static async analyzeRevenueResponseChartStream(
    dataPoint: DataPoint,
    onDataSummary: (summary: string) => void,
    onAnalysisChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: string) => void,
    visibleKPIs?: VisibleKPIs
  ): Promise<string> {
    const request: WidgetAnalysisRequest = {
      widgetMeta: {
        type: 'chart',
        subtype: 'line-chart',
        title: 'Revenue vs Response Time Correlation',
        dataSource: 'bigquery.ecommerce.revenue_metrics',
        timeRange: 'last_7_days',
      },
      interactionContext: {
        clickedDataPoint: {
          timestamp: dataPoint.timestamp,
          revenue: dataPoint.revenue,
          responseTime: dataPoint.responseTime,
        },
        clickType: 'data-point',
      },
      screenContext: {
        pageUrl: window.location.pathname,
        visibleKPIs: visibleKPIs || {
          totalRevenue: 45231,
          activeUsers: 2345,
          pageViews: 54321,
          responseTime: '1.2s',
        },
        recentActivity: [],
        otherVisibleCharts: ['Error Rate Trend Chart', 'System Health Heatmap'],
      },
      userContext: {
        role: 'devops-engineer',
        permissions: ['view-infrastructure', 'create-incidents'],
        userId: 'current-user',
      },
    };

    return this.analyzeWidgetStream(
      request,
      onDataSummary,
      onAnalysisChunk,
      onComplete,
      onError
    );
  }

  static async analyzeErrorRateChart(
    dataPoint: any,
    visibleKPIs?: VisibleKPIs
  ): Promise<WidgetAnalysisResponse> {
    const request: WidgetAnalysisRequest = {
      widgetMeta: {
        type: 'chart',
        subtype: 'line-chart',
        title: 'Error Rate Trend',
        dataSource: 'bigquery.monitoring.error_logs',
        timeRange: 'last_24_hours',
      },
      interactionContext: {
        clickedDataPoint: {
          timestamp: dataPoint.timestamp,
          data: dataPoint,
        },
        clickType: 'data-point',
      },
      screenContext: {
        pageUrl: window.location.pathname,
        visibleKPIs,
        otherVisibleCharts: [
          'Revenue vs Response Time Correlation',
          'System Health Heatmap',
        ],
      },
      userContext: {
        role: 'devops-engineer',
        permissions: ['view-infrastructure', 'create-incidents'],
      },
    };

    return this.analyzeWidget(request);
  }

  static async analyzeErrorRateChartStream(
    dataPoint: any,
    onDataSummary: (summary: string) => void,
    onAnalysisChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: string) => void,
    visibleKPIs?: VisibleKPIs
  ): Promise<string> {
    const request: WidgetAnalysisRequest = {
      widgetMeta: {
        type: 'chart',
        subtype: 'line-chart',
        title: 'Error Rate Trend',
        dataSource: 'bigquery.monitoring.error_logs',
        timeRange: 'last_24_hours',
      },
      interactionContext: {
        clickedDataPoint: {
          timestamp: dataPoint.timestamp,
          data: dataPoint,
        },
        clickType: 'data-point',
      },
      screenContext: {
        pageUrl: window.location.pathname,
        visibleKPIs,
        otherVisibleCharts: [
          'Revenue vs Response Time Correlation',
          'System Health Heatmap',
        ],
      },
      userContext: {
        role: 'devops-engineer',
        permissions: ['view-infrastructure', 'create-incidents'],
      },
    };

    return this.analyzeWidgetStream(
      request,
      onDataSummary,
      onAnalysisChunk,
      onComplete,
      onError
    );
  }

  static async analyzeSystemHealthHeatmap(
    dataPoint: any,
    visibleKPIs?: VisibleKPIs
  ): Promise<WidgetAnalysisResponse> {
    const request: WidgetAnalysisRequest = {
      widgetMeta: {
        type: 'chart',
        subtype: 'heatmap',
        title: 'System Health Heatmap',
        dataSource: 'bigquery.monitoring.system_metrics',
        timeRange: 'last_6_hours',
      },
      interactionContext: {
        clickedDataPoint: {
          timestamp: new Date().toISOString(),
          data: dataPoint,
        },
        clickType: 'heatmap-cell',
      },
      screenContext: {
        pageUrl: window.location.pathname,
        visibleKPIs,
        otherVisibleCharts: [
          'Revenue vs Response Time Correlation',
          'Error Rate Trend Chart',
        ],
      },
      userContext: {
        role: 'devops-engineer',
        permissions: ['view-infrastructure', 'create-incidents'],
      },
    };

    return this.analyzeWidget(request);
  }

  static async analyzeGenericWidget(
    widgetTitle: string,
    widgetType: string,
    widgetSubtype: string,
    dataPoint: any,
    visibleKPIs?: VisibleKPIs
  ): Promise<WidgetAnalysisResponse> {
    const request: WidgetAnalysisRequest = {
      widgetMeta: {
        type: widgetType,
        subtype: widgetSubtype,
        title: widgetTitle,
        dataSource: 'bigquery.analytics.generic_metrics',
        timeRange: 'last_24_hours',
      },
      interactionContext: {
        clickedDataPoint: {
          timestamp: dataPoint.timestamp || new Date().toISOString(),
          data: dataPoint,
        },
        clickType: 'data-point',
      },
      screenContext: {
        pageUrl: window.location.pathname,
        visibleKPIs,
      },
      userContext: {
        role: 'devops-engineer',
        permissions: ['view-infrastructure', 'create-incidents'],
      },
    };

    return this.analyzeWidget(request);
  }

  // Helper method to get current visible KPIs from dashboard state
  static getCurrentKPIs(): VisibleKPIs {
    // In a real implementation, this would extract KPIs from the dashboard state
    // For now, return mock data
    return {
      totalRevenue: 45231,
      activeUsers: 2345,
      pageViews: 54321,
      responseTime: '1.2s',
    };
  }
}

export default WidgetAnalysisService;
export type {
  WidgetAnalysisRequest,
  WidgetAnalysisResponse,
  DataPoint,
  VisibleKPIs,
};
/* eslint-enable no-constant-condition */
/* eslint-enable @typescript-eslint/no-explicit-any */
