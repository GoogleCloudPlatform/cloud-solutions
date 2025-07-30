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
interacting with the Google Vertex AI API."""

import os
import json
import re
from typing import Dict, Any
from models.chat import WidgetAnalysisRequest, WidgetAnalysisResponse

from google import genai
from google.genai import types


class VertexAIService:
    """
    Vertex AI service that uses default credentials
    and the project's Vertex AI instance.
    """

    def __init__(self, project_id: str = None):
        # Configure Vertex AI with default credentials
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("VERTEX_AI_LOCATION") or "global"

        # Initialize Google GenAI client with Vertex AI
        self.client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location,
        )

        # Set the model name from your working example
        self.model_name = "gemini-2.0-flash"
        print(f"Vertex AI client initialized with model: {self.model_name}")

        print(
            "Vertex AI initialized - Project:"
            f"{self.project_id}, Location: {self.location}"
        )

    def generate_widget_analysis(
        self, request: WidgetAnalysisRequest
    ) -> WidgetAnalysisResponse:
        """Generate analysis using Vertex AI based on widget interaction."""

        # Build the prompt
        prompt = self._build_analysis_prompt(request)

        # Create content for the new API
        contents = [
            types.Content(
                role="user", parts=[types.Part.from_text(text=prompt)]
            )
        ]

        # Configure generation settings
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.9,
            max_output_tokens=1024,  # Reduced for faster responses
            response_mime_type="application/json",
        )

        # Generate response using Vertex AI
        response = self.client.models.generate_content(
            model=self.model_name, contents=contents, config=config
        )

        # Parse the response
        if (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            response_text = response.candidates[0].content.parts[0].text
        else:
            response_text = (
                response.text
                if response.text
                else "No valid response generated"
            )

        analysis_result = self._parse_vertex_response(response_text)

        return WidgetAnalysisResponse(
            conversationId="",  # Will be set by caller
            response=analysis_result["response"],
            actionSuggestions=analysis_result.get("actionSuggestions", []),
            relatedMetrics=analysis_result.get("relatedMetrics", []),
            confidence=analysis_result.get("confidence", 0.8),
            analysisType=f"vertex-{request.widgetMeta.type}-analysis",
        )

    def _build_analysis_prompt(self, request: WidgetAnalysisRequest) -> str:
        """
        Build a comprehensive prompt for Vertex AI
        based on widget context.
        """

        widget = request.widgetMeta
        interaction = request.interactionContext
        screen = request.screenContext
        user = request.userContext

        prompt = f"""
You are an expert DevOps engineer and data analyst working
with IT operations data.
Analyze the following widget interaction and provide actionable insights.

WIDGET CONTEXT:
- Type: {widget.type} ({widget.subtype})
- Title: {widget.title}
- Data Source: {widget.dataSource}
- Time Range: {widget.timeRange}

INTERACTION:
- User action: {interaction.clickType.replace("-", " ")}
"""

        if interaction.clickedDataPoint:
            point = interaction.clickedDataPoint
            prompt += "- Data Point Details:\n"
            if hasattr(point, "timestamp") and point.timestamp:
                prompt += f"  - Timestamp: {point.timestamp}\n"
            if hasattr(point, "revenue") and point.revenue is not None:
                prompt += f"  - Revenue: ${point.revenue:,.0f}\n"
            if (
                hasattr(point, "responseTime")
                and point.responseTime is not None
            ):
                prompt += f"  - Response Time: {point.responseTime}ms\n"
            if hasattr(point, "data") and point.data:
                data_text = json.dumps(point.data, indent=2)
                prompt += f"  - Additional Data: {data_text}\n"

        prompt += f"""
DASHBOARD CONTEXT:
- Page: {screen.pageUrl}
- User Role: {user.role}
- Permissions: {", ".join(user.permissions)}
"""

        if screen.visibleKPIs:
            prompt += "- Current KPIs visible to user:\n"
            if hasattr(screen.visibleKPIs, "totalRevenue"):
                prompt += (
                    f"  - Total Revenue: {screen.visibleKPIs.totalRevenue}\n"
                )
            if hasattr(screen.visibleKPIs, "activeUsers"):
                prompt += (
                    f"  - Active Users: {screen.visibleKPIs.activeUsers}\n"
                )
            if hasattr(screen.visibleKPIs, "responseTime"):
                prompt += (
                    "  - Avg Response Time: "
                    f"{screen.visibleKPIs.responseTime}\n"
                )

        prompt += """
ANALYSIS REQUIREMENTS:
1. MUST reference specific numbers from the dashboard data
(revenue, users, response times, etc.)
2. Calculate business impact using actual metrics provided
3. Give 3-5 concrete recommendations based on the real data,
not generic advice
4. Connect technical issues to business metrics shown on this dashboard
5. Keep analysis concise but data-driven (2-3 sentences max)
6. Example: "With your current revenue of $X and Y active users,
this Z% error rate likely impacts..."

RESPONSE FORMAT:
Please respond with a JSON object in this exact format:
{{
  "response": "Your technical analysis here focusing on operational insights",
  "actionSuggestions": [
      "Specific action 1",
      "Specific action 2",
      "Specific action 3"
    ],
  "relatedMetrics": [
      "Related metric 1",
      "Related metric 2",
      "Related metric 3"
  ],
  "confidence": 0.85
}}

Ensure the JSON is valid and properly formatted.
"""
        return prompt

    def _build_simple_analysis_prompt(
        self, request: WidgetAnalysisRequest
    ) -> str:
        """Build a simple prompt for streaming widget analysis."""

        widget = request.widgetMeta
        interaction = request.interactionContext
        user = request.userContext

        prompt = f"""
You are an expert DevOps engineer analyzing IT operations data.

Widget: {widget.title}
User clicked on data point from {widget.dataSource}
User role: {user.role}

IMPORTANT: Base your analysis on the SPECIFIC data from this dashboard,
not generic advice.

Provide a concise technical analysis (2-3 sentences) that:
1. References the specific metrics and context from this dashboard
2. Gives immediate actionable recommendations based on actual data
3. Explains business impact using the real numbers provided

Be specific and data-driven for a {user.role}."""

        if interaction.clickedDataPoint:
            point = interaction.clickedDataPoint
            prompt += "\n\nData Point Details:"
            if hasattr(point, "timestamp") and point.timestamp:
                prompt += f"\n- Timestamp: {point.timestamp}"
            if hasattr(point, "revenue") and point.revenue is not None:
                prompt += f"\n- Revenue: ${point.revenue:,.0f}"
            if (
                hasattr(point, "responseTime")
                and point.responseTime is not None
            ):
                prompt += f"\n- Response Time: {point.responseTime}ms"
            if hasattr(point, "data") and point.data:
                for key, value in point.data.items():
                    if key not in ["timestamp", "revenue", "responseTime"]:
                        prompt += (
                            f"\n- {key.replace("_", " ").title()}: {value}"
                        )

        return prompt

    def generate_follow_up_response_stream(
        self, message: str, conversation_id: str # pylint: disable=unused-argument
    ):
        """Generate a follow-up response to user messages using Vertex AI."""

        prompt = f"""
You are a DevOps expert helping with IT operations dashboard analysis.

User question: "{message}"

Provide a helpful, concise technical response (1-2 sentences)
with actionable DevOps guidance."""

        # Create content for the new API
        contents = [
            types.Content(
                role="user", parts=[types.Part.from_text(text=prompt)]
            )
        ]

        # Configure generation settings
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.9,
            max_output_tokens=1024,  # Reduced for faster responses
        )

        # Generate streaming response using Vertex AI
        return self.client.models.generate_content_stream(
            model=self.model_name, contents=contents, config=config
        )

    def generate_follow_up_response(
        self, message: str, conversation_id: str # pylint: disable=unused-argument
    ) -> str:
        """Generate a follow-up response to user messages using Vertex AI."""

        prompt = f"""
You are a DevOps expert helping with IT operations dashboard analysis.

User question: "{message}"

Provide a helpful, concise technical response (1-2 sentences)
with actionable DevOps guidance."""

        # Create content for the new API
        contents = [
            types.Content(
                role="user", parts=[types.Part.from_text(text=prompt)]
            )
        ]

        # Configure generation settings
        # (no JSON format for follow-up responses)
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.9,
            max_output_tokens=2048,  # match widget analysis
        )

        # Generate response using Vertex AI
        response = self.client.models.generate_content(
            model=self.model_name, contents=contents, config=config
        )

        # Parse the response - handle both successful and truncated responses
        if response.candidates and response.candidates[0].content:
            if (
                response.candidates[0].content.parts
                and response.candidates[0].content.parts[0].text
            ):
                response_text = response.candidates[0].content.parts[0].text
            elif (
                getattr(response.candidates[0], "finish_reason", None)
                == "MAX_TOKENS"
            ):
                # For MAX_TOKENS, try to get text from response.text
                # or provide helpful message
                response_text = (
                    response.text
                    if response.text
                    else (
                        "I was providing an analysis but my response was"
                        "cut off due to length limits."
                        "Could you ask a more specific question?"
                    )
                )
            else:
                response_text = (
                    response.text
                    if response.text
                    else "Unable to generate response"
                )
        else:
            response_text = (
                response.text
                if response.text
                else "Unable to generate response"
            )

        return response_text.strip()

    def _parse_vertex_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Vertex AI response and extract structured data."""
        try:
            # Try to extract JSON from the response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())

                # Validate required fields
                if "response" in parsed:
                    return {
                        "response": parsed.get("response", ""),
                        "actionSuggestions": parsed.get(
                            "actionSuggestions", []
                        ),
                        "relatedMetrics": parsed.get("relatedMetrics", []),
                        "confidence": parsed.get("confidence", 0.8),
                    }

            # Fallback: treat entire response as analysis text
            return {
                "response": response_text.strip()[:500]
                + ("..." if len(response_text) > 500 else ""),
                "actionSuggestions": [
                    "Review the analysis and take appropriate action"
                ],
                "relatedMetrics": ["System Performance", "User Experience"],
                "confidence": 0.7,
            }
        except Exception as e:
            raise Exception(  # pylint: disable=broad-exception-raised
                (
                    f"Error parsing Vertex AI response: {str(e)}."
                    "Raw response: {response_text}"
                )
            ) from e


# Global instance (will be initialized once)
vertex_service = None


def get_vertex_service():
    global vertex_service
    if vertex_service is None:
        vertex_service = VertexAIService()
    return vertex_service
