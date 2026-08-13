# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module containing GECX python code logic."""

# pylint: skip-file

import json
from typing import Any, Dict


def analyze_sentiment() -> Dict[str, Any]:
    """
    Analyzes customer sentiment by reading live session text directly from the
    global context and evaluating it via an outbound Vertex AI REST call.

    Returns:
        Dict[str, Any]: Conformed dictionary mapping containing the detected sentiment string.
    """
    # 1. Platform-Compliant Text Extraction (No Parameters)
    user_content = getattr(context, "user_content", {})
    text_to_analyze = user_content.get("text", "")

    # Handle edge-case empty strings or quiet voice turns safely
    if not text_to_analyze or not text_to_analyze.strip():
        return {"sentiment": "neutral"}

    # 2. Configure Endpoint Infrastructure & Session State Properties
    # Retrieves your authorization credential from the global persistence state
    API_KEY = context.state.get("VERTEX_API_KEY", "YOUR_FALLBACK_API_KEY")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

    # 3. Structure the Zero-Shot Classification Prompt
    prompt = f"""
    Analyze the sentiment of the following customer text.
    Return EXACTLY one of these three values: "positive", "neutral", or "negative".
    Do not include markdown formatting, markdown code blocks, or extra words.

    Text to analyze: "{text_to_analyze}"
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,  # Guarantees deterministic classification
            "maxOutputTokens": 5,  # Caps output to prevent explanations
        },
    }

    # 4. Outbound Egress Execution (Strictly adhering to ces_requests signature)
    try:
        response = ces_requests.post(
            url=url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
        )

        # 5. Upstream Validation and Error Isolation
        if response.status_code != 200:
            return {
                "sentiment": "neutral",
                "status": "UPSTREAM_REST_ERROR",
                "details": response.text,
            }

        raw_res = response.json()
        model_output = raw_res["candidates"][0]["content"]["parts"][0]["text"]
        cleaned_sentiment = model_output.strip().lower()

        # 6. Schema Normalization
        if "positive" in cleaned_sentiment:
            return {"sentiment": "positive"}
        elif "negative" in cleaned_sentiment:
            return {"sentiment": "negative"}
        else:
            return {"sentiment": "neutral"}

    except Exception as e:
        # Model Risk Management (MRM) fallback pattern
        return {
            "sentiment": "neutral",
            "status": "SANDBOX_RUNTIME_EXCEPTION",
            "error": str(e),
        }
