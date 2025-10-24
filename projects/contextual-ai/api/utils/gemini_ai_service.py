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

"""This module provides a service for
interacting with the Google Gemini API."""


import json
import os
import re
from typing import Any, Dict

import google.generativeai as genai
from models.chat import WidgetAnalysisRequest, WidgetAnalysisResponse


class GeminiAIService:
    """Real AI service that makes calls to Google Gemini API."""

    def __init__(self):
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print(
                (
                    "WARNING: GEMINI_API_KEY "
                    "environment variable not set. Using fallback mode."
                )
            )
            self.api_key = None
            self.model = None
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-pro")
            self.api_key = api_key

    def generate_widget_analysis(
        self, request: WidgetAnalysisRequest
    ) -> WidgetAnalysisResponse:
        """Generate analysis using Gemini API based on widget interaction."""

        # Build the prompt
        prompt = self._build_analysis_prompt(request)

        # Check if API key is available
        if not self.api_key or not self.model:
            return self._generate_fallback_response(
                request, "API key not configured"
            )

        try:
            # Generate response using Gemini
            response = self.model.generate_content(prompt)

            # Parse the response
            analysis_result = self._parse_gemini_response(response.text)

            return WidgetAnalysisResponse(
                conversationId="",  # Will be set by caller
                response=analysis_result["response"],
                actionSuggestions=analysis_result.get("actionSuggestions", []),
                relatedMetrics=analysis_result.get("relatedMetrics", []),
                confidence=analysis_result.get("confidence", 0.8),
                analysisType=f"{request.widgetMeta.type}-analysis",
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Fallback to mock response on API failure
            return self._generate_fallback_response(request, str(e))

    def _build_analysis_prompt(self, request: WidgetAnalysisRequest) -> str:
        """Build a comprehensive prompt for Gemini based on widget context."""

        widget = request.widgetMeta
        interaction = request.interactionContext
        screen = request.screenContext
        user = request.userContext

        prompt = f"""
You are an expert DevOps engineer and data analyst.
Analyze the following widget interaction and provide actionable insights.

WIDGET CONTEXT:
- Type: {widget.type} ({widget.subtype})
- Title: {widget.title}
- Data Source: {widget.dataSource}
- Time Range: {widget.timeRange}

INTERACTION:
- User clicked: {interaction.clickType}
"""

        if interaction.clickedDataPoint:
            point = interaction.clickedDataPoint
            prompt += f"- Data Point: {json.dumps(point.__dict__, indent=2)}\n"

        visible_kpis = json.dumps(
            screen.visibleKPIs.__dict__ if screen.visibleKPIs else {}, indent=2
        )
        prompt += f"""
SCREEN CONTEXT:
- Page: {screen.pageUrl}
- Visible KPIs: {visible_kpis}

USER CONTEXT:
- Role: {user.role}
- Permissions: {", ".join(user.permissions)}

INSTRUCTIONS:
1. Analyze the data point in context of the widget type and user's role
2. Identify any concerning patterns, anomalies, or opportunities
3. Provide 3-5 specific, actionable recommendations
4. Suggest related metrics to monitor
5. Keep the response concise but insightful (2-3 sentences max)

Please respond in the following JSON format:
{{
  "response": "Your analysis here...",
  "actionSuggestions": ["Action 1", "Action 2", "Action 3"],
  "relatedMetrics": ["Metric 1", "Metric 2", "Metric 3"],
  "confidence": 0.85
}}
"""
        return prompt

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini response and extract structured data."""
        try:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback: treat entire response as analysis text
                return {
                    "response": response_text.strip(),
                    "actionSuggestions": [
                        "Review the analysis and take appropriate action"
                    ],
                    "relatedMetrics": ["System Performance", "User Experience"],
                    "confidence": 0.7,
                }
        except Exception:  # pylint: disable=broad-exception-caught
            return {
                "response": response_text.strip()[:500] + "...",
                "actionSuggestions": ["Review the full analysis"],
                "relatedMetrics": ["System Health"],
                "confidence": 0.6,
            }

    def generate_follow_up_response(
        self, message: str, conversation_id: str
    ) -> str:
        """Generate a follow-up response to user messages using Gemini."""

        prompt = f"""
You are an expert DevOps engineer and data analyst
helping a user understand their system performance data.

The user just asked: "{message}"

This is in the context of an IT operations dashboard conversation
(conversation ID: {conversation_id}).

Please provide a helpful, concise response (1-2 sentences) that:
1. Directly addresses their question
2. Provides actionable insights when relevant
3. Uses technical language appropriate for a DevOps engineer
4. Relates to system performance, monitoring,
    or troubleshooting when applicable

Keep your response conversational but professional.
"""

        # Check if API key is available
        if not self.api_key or not self.model:
            return (
                f"🤖 [MOCK AI]: I understand you're asking about: {message}."
                " Let me help you analyze this in the context of your system "
                "performance data. Could you provide more specific details "
                "about what you'd like to investigate?"
            )
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception:  # pylint: disable=broad-exception-caught
            # Fallback response
            return (
                f"🤖 [MOCK AI]: I understand you're asking about: {message}. "
                "Let me help you analyze this in the context of your system "
                "performance data. Could you provide more specific details "
                "about what you'd like to investigate?"
            )

    def _generate_fallback_response(
        self,
        request: WidgetAnalysisRequest,
        error: str,  # pylint: disable=unused-argument
    ) -> WidgetAnalysisResponse:
        """Generate fallback response when Gemini API fails."""

        widget_title = request.widgetMeta.title
        interaction = request.interactionContext

        # Generate a contextual fallback based on widget type
        if (
            "revenue" in widget_title.lower()
            and "response" in widget_title.lower()
        ):
            if (
                interaction.clickedDataPoint
                and interaction.clickedDataPoint.responseTime
            ):
                response_time = interaction.clickedDataPoint.responseTime
                if response_time > 500:
                    response = (
                        "🤖 [MOCK AI]: I notice elevated response times around "
                        "{response_time}ms in your revenue correlation data. "
                        "High response times typically correlate with "
                        "decreased conversion rates."
                    )
                    actions = [
                        "Check payment gateway performance",
                        "Review database connection pools",
                        "Scale payment processing instances",
                    ]
                else:
                    response = (
                        "🤖 [MOCK AI]: The data shows healthy performance "
                        f"with {response_time}ms response times. "
                        "This represents good correlation between "
                        "system performance and revenue."
                    )
                    actions = [
                        "Monitor for capacity trends",
                        "Document current configuration as baseline",
                    ]
            else:
                response = (
                    "🤖 [MOCK AI]: I analyzed the revenue vs response "
                    "time correlation. "
                    "This data helps identify when system performance "
                    "impacts business metrics."
                )
                actions = ["Click specific data points for detailed analysis"]
        else:
            response = (
                f"🤖 [MOCK AI]: I analyzed the '{widget_title}' widget data. "
                "The metrics show current system state and trends that can "
                "inform operational decisions."
            )
            actions = [
                "Review historical patterns",
                "Set up monitoring alerts if needed",
                "Cross-reference with related metrics",
            ]

        return WidgetAnalysisResponse(
            conversationId="",
            response=response,
            actionSuggestions=actions,
            relatedMetrics=["System Performance", "Operational Metrics"],
            confidence=0.7,
            analysisType="mock-ai-analysis",
        )


# Global instance (would be initialized once)
gemini_service = None


def get_gemini_service():
    global gemini_service
    if gemini_service is None:
        gemini_service = GeminiAIService()
    return gemini_service
