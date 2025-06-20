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

import {Conversation, ConversationEntry} from '@/types/chat';
import ChatService from './chatService';

export class FollowUpAnalysisService {
  // Generate AI response to follow-up questions based on conversation context
  static async generateFollowUpResponse(
    userMessage: string,
    conversationId: string
  ): Promise<string> {
    const conversation = ChatService.getConversation(conversationId);
    if (!conversation) {
      return this.getGenericResponse(userMessage);
    }

    // Get the most recent widget analysis from the conversation
    const widgetAnalysis = this.getLatestWidgetAnalysis(conversation);
    if (!widgetAnalysis) {
      return this.getGenericResponse(userMessage);
    }

    // Generate contextual response based on the original widget analysis
    return this.generateContextualResponse(userMessage, widgetAnalysis);
  }

  private static getLatestWidgetAnalysis(
    conversation: Conversation
  ): ConversationEntry | null {
    // Find the most recent assistant message with widget metadata
    for (let i = conversation.entries.length - 1; i >= 0; i--) {
      const entry = conversation.entries[i];
      if (entry.type === 'assistant' && entry.metadata?.widgetId) {
        return entry;
      }
    }
    return null;
  }

  private static generateContextualResponse(
    userMessage: string,
    originalAnalysis: ConversationEntry
    // conversation: Conversation // This parameter was unused
  ): string {
    const widgetId = originalAnalysis.metadata?.widgetId;

    // Normalize user message for keyword matching
    const message = userMessage.toLowerCase();

    // Revenue/Response Time follow-ups
    if (widgetId?.includes('revenue') || widgetId?.includes('response-time')) {
      return this.generateRevenueFollowUp(
        message, // userMessage normalized
        originalAnalysis.metadata
      );
    }

    // System Health follow-ups
    if (widgetId?.includes('system-health') || widgetId?.includes('service')) {
      return this.generateSystemHealthFollowUp(
        message, // userMessage normalized
        originalAnalysis.metadata
      );
    }

    // Error Rate follow-ups
    if (widgetId?.includes('error-rate') || widgetId?.includes('error')) {
      return this.generateErrorRateFollowUp(
        message, // userMessage normalized
        originalAnalysis.metadata
      );
    }

    // General follow-up
    return this.generateGeneralFollowUp(message, originalAnalysis);
  }

  private static generateRevenueFollowUp(
    message: string,
    metrics: ConversationEntry['metadata']
  ): string {
    if (
      message.includes('historical') ||
      message.includes('trend') ||
      message.includes('history')
    ) {
      return `📊 **Historical Response Time Analysis**

Based on the last 7 days of data, here are the key trends:

**Response Time Patterns:**
• Average: 180ms (within optimal range)
• Peak hours (2-4 PM): 280ms average
• Off-peak hours: 120ms average
• 95th percentile: ${metrics?.responseTime || 250}ms

**Revenue Correlation:**
• Strong negative correlation (-0.78) between response time and conversion
• Every 100ms increase = ~3.2% revenue decrease
• Optimal performance window: <200ms response time

**Recommendations:**
• Implement auto-scaling during peak hours
• Consider CDN optimization for static assets
• Monitor database query performance during high traffic`;
    }

    if (message.includes('payment') || message.includes('gateway')) {
      return `💳 **Payment Gateway Analysis**

Current payment processing performance:

**Gateway Metrics:**
• Payment success rate: 98.7%
• Average processing time: 1.8s
• Failed payments: 1.3% (mostly timeout-related)
• Peak processing time: ${metrics?.responseTime || 250}ms additional latency

**Impact Assessment:**
• Payment timeouts correlate with high response times
• Revenue impact: ~$${Math.round((metrics?.responseTime || 250) * 0.5)}/hour during spikes

**Immediate Actions:**
• Check payment gateway connection pool
• Implement payment retry logic
• Monitor third-party payment API status
• Consider backup payment processor`;
    }

    if (
      message.includes('alert') ||
      message.includes('monitor') ||
      message.includes('notification')
    ) {
      return `🔔 **Alert Configuration Recommendations**

I recommend setting up these monitoring alerts:

**Response Time Alerts:**
• Warning: >250ms for 2 consecutive minutes
• Critical: >400ms for 1 minute
• Recovery: <200ms for 5 minutes

**Revenue Impact Alerts:**
• Revenue drop >$100/hour compared to baseline
• Conversion rate decrease >5%
• Payment failure rate >2%

**Suggested Alert Channels:**
• Slack #ops-alerts for warnings
• PagerDuty for critical issues
• Email dashboard for daily summaries

Would you like me to help configure any specific alert thresholds?`;
    }

    return `Based on the revenue vs response time analysis, I can provide more details about:
• Historical performance trends over the last 30 days
• Payment gateway-specific metrics and optimizations
• Alert configuration for proactive monitoring
• Database query optimization recommendations

What specific aspect would you like me to elaborate on?`;
  }

  private static generateSystemHealthFollowUp(
    message: string,
    metrics: ConversationEntry['metadata']
  ): string {
    const serviceName = metrics?.serviceName || 'the service';

    if (
      message.includes('dependency') ||
      message.includes('dependencies') ||
      message.includes('map')
    ) {
      return `🔗 **Service Dependency Map for ${serviceName}**

**Upstream Dependencies:**
• Database (PostgreSQL): ${(metrics?.healthScore || 0) > 80 ? 'Healthy' : 'Degraded'}
• Redis Cache: Healthy
• Payment Gateway API: Healthy
• Authentication Service: Healthy

**Downstream Services:**
• Frontend Application: 3 instances
• Mobile API Gateway: 2 instances
• Analytics Pipeline: 1 instance

**Critical Path Impact:**
• ${serviceName} failure affects 4 downstream services
• Estimated impact: ${(metrics?.healthScore || 0) < 50 ? 'High' : (metrics?.healthScore || 0) < 80 ? 'Medium' : 'Low'} user impact
• Recovery time: 2-5 minutes with auto-scaling

**Recommended Actions:**
• Implement circuit breaker patterns
• Add health check endpoints
• Configure graceful degradation`;
    }

    if (
      message.includes('scale') ||
      message.includes('scaling') ||
      message.includes('resource')
    ) {
      return `📈 **Scaling Recommendations for ${serviceName}**

**Current Resource Utilization:**
• CPU: ${metrics?.cpu || 0}%
• Memory: ${metrics?.memory || 0}%
• Response Time: ${metrics?.responseTime || 0}ms

**Scaling Analysis:**
${
  (metrics?.cpu || 0) > 80
    ? '• **Immediate scaling needed**: CPU usage critical'
    : (metrics?.cpu || 0) > 60
      ? '• **Proactive scaling**: CPU approaching limits'
      : '• **Resources adequate**: No immediate scaling needed'
}

**Recommendations:**
• Horizontal scaling: Add 1-2 instances during peak hours
• Vertical scaling: Consider upgrading to next tier if sustained high usage
• Auto-scaling triggers: CPU >70% or Response Time >300ms

**Cost Impact:**
• Additional instance cost: ~$50/month
• Potential revenue protection: $500-2000/month`;
    }

    if (
      message.includes('log') ||
      message.includes('debug') ||
      message.includes('troubleshoot')
    ) {
      return `🔍 **Troubleshooting Guide for ${serviceName}**

**Log Analysis Steps:**
1. Check application logs: \`kubectl logs -f ${serviceName}-pod\`
2. Review error patterns in the last hour
3. Monitor resource metrics in real-time
4. Check database connection status

**Common Issues & Solutions:**
• **Memory leaks**: Look for gradual memory increase over time
• **Database timeouts**: Check connection pool settings
• **API rate limits**: Review third-party service quotas
• **Network issues**: Verify service mesh connectivity

**Debug Commands:**
• Health check: \`curl ${serviceName}/health\`
• Metrics endpoint: \`curl ${serviceName}/metrics\`
• Memory profile: Available in admin dashboard

Would you like me to walk through any specific troubleshooting steps?`;
    }

    return `For ${serviceName} health analysis, I can provide more information about:
• Service dependency mapping and impact analysis
• Resource scaling recommendations and cost analysis
• Detailed troubleshooting steps and log analysis
• Historical performance comparisons

What specific aspect would you like me to explore further?`;
  }

  private static generateErrorRateFollowUp(
    message: string,
    metrics: ConversationEntry['metadata']
  ): string {
    if (
      message.includes('type') ||
      message.includes('breakdown') ||
      message.includes('category')
    ) {
      return `📊 **Error Breakdown Analysis**

**Error Distribution (Last 24 Hours):**
• 4xx Client Errors: 45% of total errors
  - 404 Not Found: 32%
  - 400 Bad Request: 8%
  - 401 Unauthorized: 5%

• 5xx Server Errors: 55% of total errors
  - 500 Internal Server Error: 28%
  - 503 Service Unavailable: 15%
  - 502 Bad Gateway: 12%

**Error Rate Context:**
• Current rate: ${metrics?.errorRate || 0}%
• Baseline: 0.5%
• Peak today: ${Math.max(5, (metrics?.errorRate || 0) * 1.5)}%

**Top Error Sources:**
• Payment processing endpoint: 35%
• User authentication: 25%
• Database queries: 20%
• External API calls: 20%`;
    }

    if (
      message.includes('pattern') ||
      message.includes('time') ||
      message.includes('when')
    ) {
      return `⏰ **Error Pattern Analysis**

**Temporal Patterns:**
• Peak error times: 2-4 PM, 8-10 PM (traffic spikes)
• Lowest errors: 3-6 AM
• Weekend vs Weekday: 23% higher errors on weekends

**Error Frequency Patterns:**
• Batch processing errors: Every 15 minutes
• Authentication errors: Correlate with login attempts
• Payment errors: Higher during sale events

**Correlation Analysis:**
• Traffic vs Errors: Strong correlation (r=0.72)
• Response Time vs Errors: Moderate correlation (r=0.45)
• Memory Usage vs Errors: Weak correlation (r=0.23)

**Predicted Error Windows:**
• Next 2 hours: ${(metrics?.errorRate || 0) > 3 ? 'High risk' : 'Normal risk'}
• Peak traffic (2-4 PM): Elevated risk
• Maintenance window (2 AM): Very low risk`;
    }

    if (
      message.includes('custom') ||
      message.includes('alert') ||
      message.includes('threshold')
    ) {
      return `🚨 **Custom Alert Configuration**

**Recommended Alert Thresholds:**
• **Warning**: Error rate >2% for 5 minutes
• **Critical**: Error rate >5% for 2 minutes
• **Severe**: Error rate >10% for 1 minute

**Smart Alert Rules:**
• Suppress alerts during known maintenance windows
• Escalate if error rate increases 300% from baseline
• Auto-resolve when error rate <1% for 10 minutes

**Alert Channels by Severity:**
• Warning: Slack #engineering-alerts
• Critical: PagerDuty + Slack #incident-response
• Severe: PagerDuty + SMS + Phone call

**Custom Filters:**
• Exclude 404 errors from static assets
• Include only business-critical endpoint errors
• Group related errors to reduce alert fatigue

Would you like me to configure any of these alert rules?`;
    }

    return `Based on the error rate analysis, I can provide more details about:
• Error type breakdown and categorization
• Temporal patterns and correlation analysis
• Custom alert thresholds and notification setup
• Root cause analysis for specific error types

What specific aspect would you like me to investigate further?`;
  }

  private static generateGeneralFollowUp(
    message: string,
    originalAnalysis: ConversationEntry
  ): string {
    if (
      message.includes('what') &&
      (message.includes('do') || message.includes('next'))
    ) {
      return `Based on our analysis, here are the recommended next steps:

${
  originalAnalysis.metadata?.actionSuggestions
    ?.map((action: string, i: number) => `${i + 1}. ${action}`)
    .join('\n') ||
  '• Review the metrics and trends\n• Set up monitoring for similar issues'
}

**Priority Actions:**
• Immediate: Address any critical issues identified
• Short-term: Implement monitoring and alerts
• Long-term: Optimize performance based on trends

Would you like me to elaborate on any specific action item?`;
    }

    if (
      message.includes('explain') ||
      message.includes('why') ||
      message.includes('how')
    ) {
      return `Let me explain the technical details behind this analysis:

The analysis is based on correlating multiple data points including response times, error rates, resource utilization, and business metrics. Here's how the system works:

• **Data Collection**: Real-time metrics from multiple sources
• **Pattern Recognition**: Statistical analysis to identify anomalies
• **Impact Assessment**: Business logic to calculate potential impact
• **Recommendations**: Best practices matched to your specific scenario

The insights are generated using machine learning models trained on historical patterns and industry benchmarks.

Is there a specific technical aspect you'd like me to dive deeper into?`;
    }

    return `I can provide more specific guidance based on our previous analysis. Could you clarify what aspect you'd like me to elaborate on? For example:

• Technical implementation details
• Specific troubleshooting steps
• Historical data comparisons
• Business impact calculations

Feel free to ask about any part of the analysis!`;
  }

  private static getGenericResponse(message: string): string {
    const responses = [
      "I'd be happy to help! Could you provide more context about what you're looking for?",
      "Let me assist you with that. Can you clarify which aspect of the dashboard you're interested in?",
      "I'm here to help analyze your data. What specific insights are you looking for?",
      "Could you be more specific about what you'd like me to analyze or explain?",
      'I can provide detailed analysis on any of the dashboard widgets. What would you like to explore?',
    ];
    // Reserve `message` for future releases.
    console.log(`getGenericResponse(message):${message}`);
    return responses[Math.floor(Math.random() * responses.length)];
  }
}

export default FollowUpAnalysisService;
