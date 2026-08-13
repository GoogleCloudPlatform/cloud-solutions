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
"""Module to authenticate user."""

# pylint: skip-file

from typing import Any


def authenticate_user(username: str, password: str) -> dict[str, Any]:
    """
    Authenticates a user with the provided username and password.

    Args:
        username (str): The user's login username.
        password (str): The user's login password.

    Returns:
        dict[str, Any]: A dictionary indicating authentication status, and if successful,
                        the customer_id and contact_id.
              Example: {"authenticated": True, "customer_id": "CUST123", "contact_id": "CONT456"}
              Example: {"authenticated": False, "reason": "Invalid credentials"}
    """
    # MOCK: This is a mock implementation. In a real scenario, this would call an external
    # authentication service.
    # Hardcoded credentials for demonstration purposes.
    if username == "test" and password == "123":
        # Store customer_id and contact_id in context for subsequent calls
        context.state["customer_id"] = "CUST123"
        context.state["contact_id"] = "CONT456"
        return {
            "authenticated": True,
            "customer_id": "CUST123",
            "contact_id": "CONT456",
        }
    elif username == "lockeduser":
        return {
            "authenticated": False,
            "reason": "Account is locked. Please contact support.",
        }
    else:
        return {
            "authenticated": False,
            "reason": "Invalid username or password.",
        }
