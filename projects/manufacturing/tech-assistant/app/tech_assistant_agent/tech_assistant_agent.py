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

"""Module defining the Tech Assistant Agent."""

import os

from google.adk.agents import Agent

agent = Agent(
    name="tech_assistant",
    model=os.getenv("DEMO_AGENT_MODEL", "gemini-live-2.5-flash-native-audio"),
    tools=[],
    instruction=(
        "You are a helpful technician assistant. You receive real-time "
        "images forming a video stream; use these visual inputs to "
        "understand the context and answer any questions about what is "
        "being shown to you. You will also be provided with context "
        "documents (manuals, procedures, etc.) in your instruction to "
        "answer questions about them."
    ),
)
