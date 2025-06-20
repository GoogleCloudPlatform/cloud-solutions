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

import {
  WidgetAnalysisRequest,
  WidgetAnalysisResponse,
  VisibleKPIs,
} from '../types/chat';

interface DataPoint {
  timestamp: string;
  revenue: number;
  responseTime: number;
}

class WidgetAnalysisService {
  private static readonly API_BASE_URL =
    process.env.REACT_APP_API_URL || 'http://localhost:8080';

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

  static async analyzeErrorRateChart(
    dataPoint: {timestamp: string; [key: string]: unknown},
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
        recentActivity: [],
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

  static async analyzeSystemHealthHeatmap(
    dataPoint: Record<string, unknown>,
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
        recentActivity: [],
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
    widgetType: WidgetAnalysisRequest['widgetMeta']['type'],
    widgetSubtype: string,
    dataPoint: {timestamp?: string; [key: string]: unknown},
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
        recentActivity: [],
        otherVisibleCharts: [],
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
