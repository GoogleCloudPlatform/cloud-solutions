"""Sentiment analyst agent."""

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

import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from . import prompt

api_base_url = os.getenv("SENTIMENT_MODEL_API_BASE_URL")
print(f"The SENTIMENT_MODEL_API_BASE_URL is {api_base_url}")

model_name_at_endpoint = os.getenv(
    "SENTIMENT_MODEL_NAME", "huggingface/google/gemma-3-1b-it"
)
print(f"The SENTIMENT_MODEL_NAME is {model_name_at_endpoint}")

sentiment_agent = LlmAgent(
    model=LiteLlm(
        model=model_name_at_endpoint,
        api_base=api_base_url,
    ),
    name="sentiment_agent",
    instruction=prompt.SENTIMENT_ANALYST_PROMPT,
    output_key="sentiment_analysis_output",
)
