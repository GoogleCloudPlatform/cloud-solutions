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

import datetime
import uuid
from typing import Any


def create_service_ticket(
    service_request: str,
    settlement_status: str,
    sentiment_analysis: str,
    assigned_to: str,  # Moved to be before parameters with default values
    date_time: str | None = None,
    image_url: str | None = None,
    image_analysis: str | None = None,
) -> dict[str, Any]:
    """
    Creates a new service ticket with the provided details.

    Args:
        service_request (str): Detailed description of the service request.
        settlement_status (str): The current settlement status related to the request (e.g., "Pending", "Settled", "Failed").
        sentiment_analysis (str): The sentiment of the user's request (e.g., "positive", "neutral", "negative").
        date_time (str | None): Optional date and time the ticket is being created, in ISO format (YYYY-MM-DDTHH:MM:SS).
                                If not provided, the current date from context will be used.
        assigned_to (str): The name of the service team member assigned to the ticket.
        image_url (str | None): Optional URL of an image provided by the user.
        image_analysis (str | None): Optional analysis of the provided image.

    Returns:
        dict[str, Any]: A dictionary indicating the success or failure of ticket creation, along with the new ticket ID.
              Example: {"success": True, "ticket_id": "NEWTICKET001", "message": "Service ticket created successfully."}
              Example: {"success": False, "message": "Failed to create ticket due to system error."}
    """
    # MOCK: This is a mock implementation. In a real scenario, this would interact with a CRM or ticketing system API.
    customer_id = context.state.get(
        "customer_id", "UNKNOWN_CUSTOMER"
    )  # Retrieved from context
    contact_id = context.state.get(
        "contact_id", "UNKNOWN_CONTACT"
    )  # Retrieved from context

    if not customer_id or not contact_id or not service_request:
        return {
            "success": False,
            "message": "Missing essential information (customer_id, contact_id, or service_request) to create ticket.",
        }

    if date_time is None:
        # Retrieve current_date from context.state as a fallback
        # The framework specifies {current_date} in constraints, implying it's a YYYY-MM-DD string.
        # We combine it with the current time to match the YYYY-MM-DDTHH:MM:SS format.
        current_date_str = context.state.get(
            "current_date", datetime.date.today().isoformat()
        )
        current_time_str = datetime.datetime.now().strftime("%H:%M:%S")
        date_time = f"{current_date_str}T{current_time_str}"

    # Generate a unique ticket ID
    ticket_id = f"CSST-{uuid.uuid4().hex[:8].upper()}"

    # Simulate storing the ticket details
    mock_ticket_db = context.state.get("mock_ticket_db", {})
    mock_ticket_db[ticket_id] = {
        "customer_id": customer_id,
        "contact_id": contact_id,
        "service_request": service_request,
        "settlement_status": settlement_status,
        "sentiment_analysis": sentiment_analysis,
        "date_time": date_time,
        "assigned_to": assigned_to,
        "image_analysis": image_analysis,
        "status": "New",
    }
    context.state["mock_ticket_db"] = mock_ticket_db

    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": f"Service ticket {ticket_id} created successfully for Customer {customer_id}.",
    }
