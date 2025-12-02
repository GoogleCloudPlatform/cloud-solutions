# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Agent definition for customer support."""

from google.adk.agents import LlmAgent

from .tools import get_ticket_description, get_ticket_details

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="customer_support_agent",
    instruction="""You are a customer support assistant.
Your goal is to help users with their support tickets.

You have two tools at your disposal:
- `get_ticket_details(ticket_id: str)`: Use this tool to get the full details of a ticket.
- `get_ticket_description(ticket_id: str)`: Use this tool to get the description of a ticket.

To summarize a ticket, first use the `get_ticket_description` tool to get the content, and then summarize the content you receive.
""",
    tools=[get_ticket_details, get_ticket_description],
)
