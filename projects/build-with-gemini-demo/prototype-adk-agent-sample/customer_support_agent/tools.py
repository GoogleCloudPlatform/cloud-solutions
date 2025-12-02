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

"""Tools for the customer support agent."""

from .tickets import TICKETS


def get_ticket_details(ticket_id: str) -> str:
    """
    Retrieves the full details of a ticket given its ID.

    Args:
        ticket_id: The ID of the ticket to retrieve.

    Returns:
        A string containing the ticket details, or an error message if not
        found.
    """
    for ticket in TICKETS:
        if ticket["id"] == ticket_id:
            return (
                f'Ticket ID: {ticket["id"]}\n'
                f'Title: {ticket["title"]}\n'
                f'Description: {ticket["description"]}'
            )
    return f"Ticket with ID '{ticket_id}' not found."


def get_ticket_description(ticket_id: str) -> str:
    """
    Retrieves the description of a ticket given its ID.

    Args:
        ticket_id: The ID of the ticket to retrieve the description for.

    Returns:
        A string containing the ticket's description, or an error message if
        not found.
    """
    for ticket in TICKETS:
        if ticket["id"] == ticket_id:
            return ticket["description"]
    return f"Ticket with ID '{ticket_id}' not found."
