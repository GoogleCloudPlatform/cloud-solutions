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
  Conversation,
  WidgetMeta,
  InteractionContext,
  ScreenContext,
  UserContext,
} from '@/types/chat';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080';

export class WidgetAnalysisService {
  // Main widget analysis API call
  static async analyzeWidget(
    request: WidgetAnalysisRequest
  ): Promise<WidgetAnalysisResponse | null> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/analyze-widget`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        console.error('Widget analysis failed:', response.status);
        return null;
      }

      return await response.json();
    } catch (error) {
      console.error('Widget analysis error:', error);
      return null;
    }
  }

  // Generate realistic mock responses based on widget type and context
  private static generateMockResponse(
    request: WidgetAnalysisRequest
  ): WidgetAnalysisResponse {
    const {widgetMeta, interactionContext} = request;
    const conversationId = `mock-${Date.now()}`;

    // Generate different responses based on widget type
    switch (widgetMeta.subtype) {
      case 'line-chart':
        return this.generateRevenueResponseTimeMockResponse(
          conversationId,
          interactionContext
        );
      case 'service-health':
        return this.generateSystemHealthMockResponse(
          conversationId,
          interactionContext
        );
      case 'area-chart':
        return this.generateErrorRateMockResponse(
          conversationId,
          interactionContext
        );
      default:
        return {
          conversationId,
          response:
            "I've analyzed this widget." +
            'This is a general analysis response for demonstration purposes.',
          actionSuggestions: [
            'Review the data trends',
            'Check related metrics',
          ],
          followUpQuestions: [
            'Would you like more details?',
            'Should we investigate further?',
          ],
        };
    }
  }

  private static generateRevenueResponseTimeMockResponse(
    conversationId: string,
    context: InteractionContext
  ): WidgetAnalysisResponse {
    const dataPoint = context.clickedDataPoint;
    const revenue = dataPoint?.revenue || 0;
    const responseTime = dataPoint?.responseTime || 0;
    const timestamp = dataPoint?.timestamp
      ? new Date(dataPoint.timestamp)
      : new Date();

    let analysis = '';
    let suggestions: string[] = [];

    if (responseTime > 400) {
      // Simulated loss calculation
      const revenueLoss = Math.round((responseTime - 200) * 2);
      analysis =
        '🚨 **Performance Impact Detected**\n\n' +
        'I noticed a significant revenue dip of ' +
        `$${revenueLoss} at ${timestamp.toLocaleTimeString()} when ` +
        `response time spiked to ${responseTime}ms.` +
        'This suggests payment processing delays during peak traffic.' +
        '\n\n**Analysis:**\n• Response time exceeded acceptable threshold ' +
        `(>400ms)\n• Estimated revenue impact: -$${revenueLoss}\n` +
        '• Likely cause: Database connection pool saturation\n\n' +
        '**Root Cause:** High response times typically correlate with ' +
        'reduced conversion rates due to user abandonment.';

      suggestions = [
        'Scale payment-api instances immediately',
        'Check database connection pool status',
        'Investigate CDN cache hit rates',
        'Monitor payment gateway response times',
        'Set up alerts for response times >300ms',
      ];
    } else if (responseTime > 250) {
      analysis =
        '⚠️ **Moderate Performance Issue**\n\n' +
        `Response time of ${responseTime}ms at ${timestamp.toLocaleTimeString()} ` +
        'is approaching concerning levels. ' +
        `Revenue of $${revenue} is within normal range but could be at risk.\n\n` +
        '**Preventive Analysis:**\n• ' +
        'Response time is elevated but not critical\n' +
        '• Revenue impact: Minimal ' +
        '(<$50 estimated)\n• Early warning for potential issues';

      suggestions = [
        'Monitor trends over next hour',
        'Check application server CPU usage',
        'Review recent deployments',
        'Verify load balancer health',
      ];
    } else {
      analysis =
        '✅ **Healthy Performance**\n\n' +
        `Response time of ${responseTime}ms at ${timestamp.toLocaleTimeString()} ` +
        `is within optimal range. Revenue of $${revenue} shows strong ` +
        'performance.\n\n**Positive Indicators:**\n' +
        '• Response time well below 250ms threshold\n' +
        '• Revenue tracking normally\n• System operating efficiently';

      suggestions = [
        'Continue monitoring',
        'Document current optimal configuration',
        'Use as baseline for future comparisons',
      ];
    }

    return {
      conversationId,
      response: analysis,
      actionSuggestions: suggestions,
      relatedMetrics: [
        'Response Time Trends',
        'Payment Gateway Performance',
        'Revenue Conversion Rate',
        'Database Connection Pool',
      ],
      followUpQuestions: [
        'Would you like to see historical response time trends?',
        'Should I analyze payment gateway performance?',
        'Do you want alerts set up for similar incidents?',
      ],
    };
  }

  private static generateSystemHealthMockResponse(
    conversationId: string,
    context: InteractionContext
  ): WidgetAnalysisResponse {
    const service = context.clickedDataPoint;
    const serviceName = service?.serviceName || 'unknown-service';
    const status = service?.status || 'unknown';
    const cpu = service?.cpu || 0;
    const memory = service?.memory || 0;
    const responseTime = service?.responseTime || 0;

    let analysis = '';
    let suggestions: string[] = [];

    if (status === 'critical') {
      analysis =
        `🔴 **Critical Service Alert: ${serviceName}**\n\n` +
        `The ${serviceName} service is in critical condition requiring immediate attention.\n\n` +
        `**Current Metrics:**\n• CPU Usage: ${cpu}%\n` +
        `• Memory Usage: ${memory}%\n• Response Time: ${responseTime}ms\n` +
        `• Status: ${status.toUpperCase()}\n\n**Impact Assessment:**\n` +
        '• High risk of service disruption\n• User experience severely degraded\n' +
        '• Potential cascade failures to dependent services';

      suggestions = [
        'Restart service instances immediately',
        'Scale horizontally to reduce load',
        'Check for memory leaks',
        'Review recent code deployments',
        'Activate incident response procedure',
      ];
    } else if (status === 'warning') {
      analysis =
        `⚠️ **Service Warning: ${serviceName}**\n\n` +
        `The ${serviceName} service is showing warning signs that ` +
        `need attention.\n\n**Current Metrics:**\n• CPU Usage: ${cpu}%\n` +
        `• Memory Usage: ${memory}%\n• Response Time: ${responseTime}ms\n` +
        `• Status: ${status.toUpperCase()}\n\n**Preventive Action Needed:**\n` +
        '• Resource usage approaching limits\n' +
        '• Performance degradation detected\n' +
        '• Intervention recommended before critical threshold';

      suggestions = [
        'Monitor resource usage closely',
        'Consider scaling up resources',
        'Review application logs',
        'Check for unusual traffic patterns',
        'Optimize resource-intensive operations',
      ];
    } else {
      analysis =
        `✅ **Service Health: ${serviceName}**\n\n` +
        `The ${serviceName} service is operating within normal parameters.\n\n` +
        `**Current Metrics:**\n• CPU Usage: ${cpu}%\n` +
        `• Memory Usage: ${memory}%\n• Response Time: ${responseTime}ms\n` +
        `• Status: ${status.toUpperCase()}\n\n**Health Summary:**\n` +
        '• All metrics within acceptable ranges\n• Service performing optimally\n' +
        '• No immediate action required';

      suggestions = [
        'Continue routine monitoring',
        'Document current performance baseline',
        'Schedule regular health checks',
      ];
    }

    return {
      conversationId,
      response: analysis,
      actionSuggestions: suggestions,
      relatedMetrics: [
        'CPU Utilization',
        'Memory Usage',
        'Service Response Time',
        'Health Score',
        'Container Status',
      ],
      followUpQuestions: [
        'Would you like to see service dependency map?',
        'Should I check related infrastructure components?',
        'Do you want historical performance comparison?',
      ],
    };
  }

  private static generateErrorRateMockResponse(
    conversationId: string,
    context: InteractionContext
  ): WidgetAnalysisResponse {
    const dataPoint = context.clickedDataPoint;
    const errorRate = dataPoint?.errorRate || 0;
    const totalRequests = dataPoint?.totalRequests || 0;
    const errors = dataPoint?.errors || 0;
    const isAnomaly = dataPoint?.isAnomaly || false;
    const incident = dataPoint?.incident;
    const timestamp = dataPoint?.timestamp
      ? new Date(dataPoint.timestamp)
      : new Date();

    let analysis = '';
    let suggestions: string[] = [];

    if (isAnomaly || errorRate > 5) {
      analysis =
        '🚨 **Error Rate Anomaly Detected**\n\n' +
        `Critical error rate spike of ${errorRate}% detected at ` +
        `${timestamp.toLocaleTimeString()}.\n\n**Incident Details:**\n` +
        `• Error Rate: ${errorRate}%\n• Total Requests:` +
        ` ${totalRequests.toLocaleString()}\n• Failed Requests: ` +
        `${errors.toLocaleString()}\n` +
        `• Impact: ${incident || 'High user impact detected'}\n\n` +
        '**Severity Assessment:**\n' +
        '• Error rate significantly above baseline (>5%)\n' +
        '• User experience severely impacted\n• Immediate investigation required';

      suggestions = [
        'Investigate root cause immediately',
        'Check application and infrastructure logs',
        'Verify database connectivity',
        'Review recent deployments',
        'Consider rollback if deployment-related',
        'Scale resources if capacity issue',
      ];
    } else if (errorRate > 2) {
      analysis =
        `⚠️ **Elevated Error Rate**\n\nError rate of ${errorRate}%` +
        ` at ${timestamp.toLocaleTimeString()} is above normal threshold.\n\n` +
        `**Current Status:**\n• Error Rate: ${errorRate}%\n` +
        `• Total Requests: ${totalRequests.toLocaleString()}\n` +
        `• Failed Requests: ${errors.toLocaleString()}\n` +
        '• Trend: Monitoring required\n\n**Assessment:**\n' +
        '• Error rate elevated but not critical\n' +
        '• Early warning indicator\n• Proactive monitoring recommended';

      suggestions = [
        'Monitor error trends closely',
        'Check for patterns in error types',
        'Review application health metrics',
        'Investigate if errors are user-specific',
        'Set up enhanced alerting',
      ];
    } else {
      analysis =
        '✅ **Normal Error Rate**\n\n' +
        `Error rate of ${errorRate}% at ${timestamp.toLocaleTimeString()}` +
        ' is within acceptable parameters.\n\n**Current Status:**\n' +
        `• Error Rate: ${errorRate}%\n` +
        `• Total Requests: ${totalRequests.toLocaleString()}\n` +
        `• Failed Requests: ${errors.toLocaleString()}\n` +
        '• System Health: Good\n\n**Health Indicators:**\n' +
        '• Error rate well below 2% threshold\n• System operating normally\n' +
        '• No immediate concerns';

      suggestions = [
        'Continue standard monitoring',
        'Maintain current error handling',
        'Document baseline performance',
      ];
    }

    return {
      conversationId,
      response: analysis,
      actionSuggestions: suggestions,
      relatedMetrics: [
        'Error Rate Trends',
        'Request Success Rate',
        'Error Severity Level',
        'API Response Times',
        'Service Dependencies',
      ],
      followUpQuestions: [
        'Would you like to see error breakdown by type?',
        'Should I analyze error patterns over time?',
        'Do you want to set up custom alerts?',
      ],
    };
  }

  // Get conversation by ID
  static async getConversation(
    conversationId: string
  ): Promise<Conversation | null> {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/chat/conversations/${conversationId}`
      );

      if (!response.ok) {
        console.error('Failed to fetch conversation:', response.status);
        return null;
      }

      return await response.json();
    } catch (error) {
      console.error('Conversation fetch error:', error);
      return null;
    }
  }

  // Get all conversations
  static async getAllConversations(): Promise<Conversation[]> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/conversations`);

      if (!response.ok) {
        console.error('Failed to fetch conversations:', response.status);
        return [];
      }

      return await response.json();
    } catch (error) {
      console.error('Conversations fetch error:', error);
      return [];
    }
  }

  // Helper method to build widget analysis request
  static buildAnalysisRequest(
    widgetMeta: WidgetMeta,
    interactionContext: InteractionContext,
    additionalContext?: Partial<ScreenContext & UserContext>
  ): WidgetAnalysisRequest {
    // Get current screen context
    const defaultScreenContext: ScreenContext = {
      pageUrl: window.location.pathname,
      visibleKPIs: {
        totalRevenue: '$45,231',
        activeUsers: '2,345',
        pageViews: '54,321',
        responseTime: '1.2s',
      },
      recentActivity: [
        {
          id: 1,
          action: 'User registration completed',
          time: '2 minutes ago',
          status: 'success',
        },
        {
          id: 2,
          action: 'Payment processed',
          time: '5 minutes ago',
          status: 'success',
        },
        {
          id: 3,
          action: 'API rate limit exceeded',
          time: '10 minutes ago',
          status: 'warning',
        },
      ],
      otherVisibleCharts: ['system-health-heatmap', 'error-rate-trend'],
    };

    // Default user context - in real app this would come from auth
    const defaultUserContext: UserContext = {
      role: 'devops-engineer',
      permissions: [
        'view-infrastructure',
        'create-incidents',
        'view-analytics',
      ],
      userId: 'user-123',
    };

    return {
      widgetMeta,
      interactionContext,
      screenContext: {...defaultScreenContext, ...additionalContext},
      userContext: {...defaultUserContext, ...additionalContext},
    };
  }

  // Helper method for revenue/response time correlation analysis
  static async analyzeRevenueResponseTime(dataPoint: {
    timestamp: string;
    revenue: number;
    responseTime: number;
  }): Promise<WidgetAnalysisResponse | null> {
    const widgetMeta: WidgetMeta = {
      type: 'chart',
      subtype: 'line-chart',
      title: 'Revenue vs Response Time Correlation',
      dataSource: 'bigquery.ecommerce.revenue_metrics',
      timeRange: 'last_7_days',
    };

    const interactionContext: InteractionContext = {
      clickedDataPoint: dataPoint,
      clickType: 'data-point',
    };

    const request = this.buildAnalysisRequest(widgetMeta, interactionContext);
    return this.analyzeWidget(request);
  }

  // Helper method for system health analysis
  static async analyzeSystemHealth(service: {
    name: string;
    displayName: string;
    status: string;
    cpu: number;
    memory: number;
    responseTime: number;
  }): Promise<WidgetAnalysisResponse | null> {
    const widgetMeta: WidgetMeta = {
      type: 'heatmap',
      subtype: 'service-health',
      title: 'System Health Status',
      dataSource: 'bigquery.infrastructure.health_metrics',
      timeRange: 'real_time',
    };

    const interactionContext: InteractionContext = {
      clickedDataPoint: {
        timestamp: new Date().toISOString(),
        serviceName: service.name,
        status: service.status,
        cpu: service.cpu,
        memory: service.memory,
        responseTime: service.responseTime,
      },
      clickType: 'service-tile',
    };

    const request = this.buildAnalysisRequest(widgetMeta, interactionContext);
    return this.analyzeWidget(request);
  }

  // Helper method for error rate analysis
  static async analyzeErrorRate(dataPoint: {
    timestamp: string;
    errorRate: number;
    totalRequests: number;
    errors: number;
    isAnomaly?: boolean;
    incident?: string;
  }): Promise<WidgetAnalysisResponse | null> {
    const widgetMeta: WidgetMeta = {
      type: 'chart',
      subtype: 'area-chart',
      title: 'Error Rate Trend',
      dataSource: 'bigquery.logging.error_metrics',
      timeRange: 'last_24_hours',
    };

    const interactionContext: InteractionContext = {
      clickedDataPoint: dataPoint,
      clickType: dataPoint.isAnomaly ? 'anomaly' : 'data-point',
    };

    const request = this.buildAnalysisRequest(widgetMeta, interactionContext);
    return this.analyzeWidget(request);
  }
}

export default WidgetAnalysisService;
