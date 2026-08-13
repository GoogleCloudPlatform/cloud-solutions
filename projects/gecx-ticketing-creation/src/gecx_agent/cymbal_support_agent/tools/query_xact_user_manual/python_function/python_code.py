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

# pylint: skip-file
"""Module for querying Xact User Manual mock."""

from typing import Any


def query_xact_user_manual(query: str) -> dict[str, Any]:
    """
    Queries the Xact Web Portal User Manual for information based on the user's question.

    Args:
        query (str): The user's question about the Xact Web Portal.

    Returns:
        dict[str, Any]: A dictionary containing the answer found in the manual or a message if not found.
              Example: {"answer": "The Xact Web Portal provides a single window to all services offered by Cymbal..."}
              Example: {"answer": "I couldn't find specific information for that query in the Xact Web Portal User Manual."}
    """
    # MOCK: This is a mock implementation. In a real scenario, this would involve a RAG system
    # querying the actual PDF document.
    query_lower = query.lower()

    if (
        "purpose of xact web portal" in query_lower
        or "what is xact web portal" in query_lower
    ):
        return {
            "answer": "The Xact Web Portal brings a new dimension to Cymbal's connectivity framework, providing a single window to all services offered by Cymbal's international central securities depository (ICSD), German CSD, and LuxCSD, including Settlement, Cash & Liquidity, Asset Servicing, and Tax services."
        }
    elif (
        "security features" in query_lower
        or "how to login" in query_lower
        or "authentication" in query_lower
    ):
        return {
            "answer": "Access to the Xact Web Portal is restricted to authorized users only and is controlled by multi-factor authentication (2FA/3FA). Detailed information about 3FA can be found in the 'ForgeRock Mobile Authenticator App activation' section of the manual."
        }
    elif "access xact web portal" in query_lower or "url" in query_lower:
        return {
            "answer": "The Xact Web Portal is reachable via the internet URL: xact.cymbal.com."
        }
    elif "create a ticket" in query_lower or "support hub" in query_lower:
        return {
            "answer": "To create a ticket, navigate to 'Help & Resources', 'Help & News', then 'Support Hub' in the main menu of Xact Web Portal. Click on the 'Create' tab and populate the mandatory fields."
        }
    elif "dashboard" in query_lower:
        return {
            "answer": "After logging in to the Xact Web Portal, you are taken directly to the Dashboard, which provides an overview of your activities and tools for day-to-day tasks."
        }
    elif "application form" in query_lower or "initial access" in query_lower:
        return {
            "answer": "To start working with the Xact Web Portal, you must first fill in the application form. Please contact your Cymbal Relationship Officer for this form."
        }
    else:
        return {
            "answer": "I couldn't find specific information for that query in the Xact Web Portal User Manual."
        }
