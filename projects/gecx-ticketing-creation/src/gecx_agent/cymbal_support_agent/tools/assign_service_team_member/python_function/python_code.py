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
"""Module to assign service team member."""

# pylint: skip-file

from typing import Any


def assign_service_team_member(
    service_request: str, sentiment: str
) -> dict[str, Any]:
    """
    Assigns a service team member based on the service request and sentiment.

    Args:
        service_request (str): The detailed description of the service request.
        sentiment (str): The sentiment analysis result (e.g., "positive", "neutral", "negative").

    Returns:
        dict[str, Any]: A dictionary with the assigned team member and their team.
              Example: {"assigned_to": "Jane Smith", "team": "Settlement Support"}
    """
    # MOCK: This is a mock implementation. In a real scenario, this would use a rule-based system
    # or an AI model to intelligently assign tickets.


    assigned_to = "General Support"
    team = "Client Services"

    if "settlement" in service_request.lower():
        assigned_to = "Jane Smith"
        team = "Settlement Operations"
    elif (
        "xact portal" in service_request.lower()
        or "login" in service_request.lower()
    ):
        assigned_to = "IT Helpdesk"
        team = "Technical Support"
    elif "collateral" in service_request.lower():
        assigned_to = "David Lee"
        team = "Collateral Management"

    if sentiment == "negative":
        assigned_to = (
            "Senior " + assigned_to
        )  # Escalate if sentiment is negative

    return {"assigned_to": assigned_to, "team": team}
