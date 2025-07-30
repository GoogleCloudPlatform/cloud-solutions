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

"""This module provides a service for interacting with AI models,
including a mock service for testing."""

import random
from datetime import datetime
from models.chat import WidgetAnalysisRequest, WidgetAnalysisResponse


class MockAIService:
    """Mock AI service that generates realistic analysis
    responses based on widget context."""

    @staticmethod
    def generate_widget_analysis(
        request: WidgetAnalysisRequest,
    ) -> WidgetAnalysisResponse:
        """Generate a contextual analysis response
        based on widget interaction."""

        widget_title = request.widgetMeta.title

        # Generate response based on widget type and context
        if (
            "revenue" in widget_title.lower()
            and "response" in widget_title.lower()
        ):
            return MockAIService._analyze_revenue_response_correlation(request)
        elif "error" in widget_title.lower() or "rate" in widget_title.lower():
            return MockAIService._analyze_error_rates(request)
        elif (
            "health" in widget_title.lower() or "system" in widget_title.lower()
        ):
            return MockAIService._analyze_system_health(request)
        else:
            return MockAIService._generate_generic_analysis(request)

    @staticmethod
    def _analyze_revenue_response_correlation(
        request: WidgetAnalysisRequest,
    ) -> WidgetAnalysisResponse:
        """Generate analysis for revenue vs response time correlation."""
        interaction = request.interactionContext
        clicked_point = interaction.clickedDataPoint

        if (
            clicked_point
            and clicked_point.revenue
            and clicked_point.responseTime
        ):
            revenue = clicked_point.revenue
            response_time = clicked_point.responseTime
            timestamp = clicked_point.timestamp

            # Parse timestamp for contextual information
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%I:%M %p")

            # Generate contextual response based on data
            if response_time > 500:  # High response time
                response = f"""
I notice a concerning pattern at {time_str}: revenue dropped to ${revenue:,.0f}
when response time spiked to {response_time}ms.
This indicates payment processing delays during what appears to be peak traffic
When response times exceed 500ms, users typically abandon transactions,
directly impacting revenue."""

                actions = [
                    "Check payment gateway status and connection pools",
                    "Scale payment-api instances horizontally",
                    "Investigate database connection bottlenecks",
                    "Enable payment retry mechanisms for failed transactions",
                    "Set up alerting for response times >400ms",
                ]

                related_metrics = [
                    "Payment Success Rate",
                    "Database Connection Pool Usage",
                    "API Gateway Throughput",
                    "CDN Cache Hit Rate",
                ]
            else:
                response = (
                    f"At {time_str}, we see healthy performance with "
                    f"${revenue:,.0f} revenue and "
                    f"{response_time}ms response time."
                    "This data point represents optimal system performance "
                    "where fast response times correlate with "
                    "successful transactions."
                )
                actions = [
                    "Document current configuration as baseline",
                    "Monitor for capacity planning trends",
                    "Consider this timeframe for load testing scenarios",
                ]

                related_metrics = [
                    "Concurrent User Count",
                    "CPU Utilization",
                    "Memory Usage",
                ]
        else:
            response = (
                "I analyzed the revenue vs response time correlation chart."
                "This visualization helps identify "
                "when system performance impacts business metrics."
                "Look for inverse correlations where higher "
                "response times coincide with revenue dips."
            )
            actions = ["Click on specific data points for detailed analysis"]
            related_metrics = [
                "Payment Processing Time",
                "User Session Duration",
            ]

        return WidgetAnalysisResponse(
            conversationId="",  # Will be set by caller
            response=response,
            actionSuggestions=actions,
            relatedMetrics=related_metrics,
            confidence=0.85,
            analysisType="performance-revenue-correlation",
        )

    @staticmethod
    def _analyze_error_rates(
        request: WidgetAnalysisRequest,  # pylint: disable=unused-argument
    ) -> WidgetAnalysisResponse:
        """Generate analysis for error rate trends."""

        responses = [
            (
                "Error rates are showing an upward trend in the last 2 hours."
                "The spike coincides with increased traffic,"
                "suggesting capacity constraints in"
                "our error handling systems."
            ),
            (
                "Current error rate of 2.3%"
                " is above our SLA threshold of 1%."
                "Most errors are originating from the authentication "
                "service during peak login periods."
            ),
            (
                "I notice intermittent error spikes every 15 minutes,"
                "which suggests a scheduled job or batch"
                "process might be interfering with normal operations."
            ),
        ]

        action_sets = [
            [
                "Scale authentication service pods",
                "Implement circuit breaker patterns",
                "Review error handling timeouts",
                "Enable graceful degradation for non-critical features",
            ],
            [
                "Investigate batch job scheduling",
                "Implement resource isolation for background tasks",
                "Add rate limiting to prevent cascading failures",
            ],
        ]

        return WidgetAnalysisResponse(
            conversationId="",
            response=random.choice(responses),
            actionSuggestions=random.choice(action_sets),
            relatedMetrics=[
                "Service Availability",
                "Response Time P95",
                "Circuit Breaker Status",
            ],
            confidence=0.78,
            analysisType="error-rate-analysis",
        )

    @staticmethod
    def _analyze_system_health(
        request: WidgetAnalysisRequest,  # pylint: disable=unused-argument
    ) -> WidgetAnalysisResponse:
        """Generate analysis for system health metrics."""

        responses = [
            (
                "System health is generally stable with all services"
                "operating within normal parameters."
                "CPU utilization is at 65%"
                "across the cluster, leaving good headroom for traffic spikes."
            ),
            (
                "I'm detecting some memory pressure on the database nodes"
                " (85% utilization)."
                "This could lead to performance "
                "degradation if traffic increases during peak hours.",
            ),
            (
                "The system health heatmap shows excellent distribution"
                " of load across availability zones."
                "No single point of failure detected in the "
                "current configuration."
            ),
        ]

        actions = [
            "Monitor memory usage trends on database cluster",
            "Consider implementing memory-based auto-scaling",
            "Review database query optimization opportunities",
            "Schedule maintenance window for memory upgrades",
        ]

        return WidgetAnalysisResponse(
            conversationId="",
            response=random.choice(responses),
            actionSuggestions=actions,
            relatedMetrics=[
                "Memory Utilization",
                "Disk I/O",
                "Network Throughput",
            ],
            confidence=0.82,
            analysisType="system-health-overview",
        )

    @staticmethod
    def _generate_generic_analysis(
        request: WidgetAnalysisRequest,
    ) -> WidgetAnalysisResponse:
        """Generate a generic analysis for unknown widget types."""

        widget_title = request.widgetMeta.title
        click_type = request.interactionContext.clickType

        response = (
            f"I analyzed the '{widget_title}' widget."
            f"""You {click_type.replace("-", " ")} which provides"""
            " insights into this metric's current state and trends."
            " This data can help inform operational"
            " decisions and identify potential areas for optimization."
        )
        actions = [
            "Review historical trends for patterns",
            "Set up alerting thresholds if not already configured",
            "Cross-reference with related business metrics",
        ]

        return WidgetAnalysisResponse(
            conversationId="",
            response=response,
            actionSuggestions=actions,
            relatedMetrics=["Related System Metrics"],
            confidence=0.70,
            analysisType="general-widget-analysis",
        )

    @staticmethod
    def generate_follow_up_response(
        message: str, conversation_id: str # pylint: disable=unused-argument
    ) -> str:
        """Generate a follow-up response to user messages."""

        message_lower = message.lower()

        # Context-aware responses based on message content
        if any(word in message_lower for word in ["fix", "solve", "resolve"]):
            responses = [
                (
                    "To resolve this issue,"
                    " I recommend starting with the highest impact action "
                    "from my previous suggestions. Would you like me to "
                    "walk you through the implementation steps?"
                ),
                (
                    "Based on the analysis, "
                    "the quickest fix would be to address the immediate "
                    "performance bottleneck. Let me break down the "
                    "step-by-step approach."
                ),
                (
                    "I can help you prioritize these fixes by business impact."
                    " The payment gateway optimization "
                    "should be your first priority."
                ),
            ]
        elif any(word in message_lower for word in ["why", "explain", "how"]):
            responses = [
                (
                    "This correlation occurs because user experience "
                    "directly impacts conversion rates. When pages "
                    "load slowly, users abandon their transactions "
                    "before completion."
                ),
                (
                    "The underlying cause is typically resource contention. "
                    "During peak traffic, limited database connections "
                    "create queuing delays that cascade through the "
                    "payment flow."
                ),
                (
                    "This pattern is common in e-commerce systems "
                    "where payment processing has strict timeout "
                    "requirements but depends on shared "
                    "infrastructure resources.",
                ),
            ]
        elif any(
            word in message_lower for word in ["when", "timeline", "schedule"]
        ):
            responses = [
                (
                    "I recommend implementing these changes "
                    "during your next maintenance window. "
                    "The critical fixes can be deployed "
                    "within 2-4 hours."
                ),
                (
                    "Based on historical patterns, "
                    "you'll likely see this issue "
                    "recur during peak traffic hours (2-4 PM) "
                    "unless addressed proactively."
                ),
                (
                    "The monitoring improvements can be implemented "
                    " immediately, while the scaling changes "
                    "should be scheduled during low-traffic periods."
                ),
            ]
        else:
            responses = [
                (
                    "I understand you're looking for more details about "
                    "this analysis. Could you specify which aspect you'd "
                    "like me to elaborate on?"
                ),
                (
                    "That's a great follow-up question. "
                    "Let me provide additional context based on "
                    "the current system state and recent trends."
                ),
                (
                    "I can help you dive deeper into any of the metrics "
                    "or recommendations from the analysis. What specific "
                    "area interests you most?"
                ),
            ]

        return random.choice(responses)
