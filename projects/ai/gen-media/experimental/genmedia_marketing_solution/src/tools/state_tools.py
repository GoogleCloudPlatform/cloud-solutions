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

"""
Tools for managing and updating the agent's internal state.
"""


def update_state(key: str, value: str, state: dict) -> dict:
    """
    Updates or adds a key-value pair to the agent's internal state.

    Args:
        key: The unique identifier for the piece of information to be stored.
             If the key already exists in the state, its value will be
             overwritten. If not, a new entry will be created.
        value: The data to be associated with the key. It can be a string,
               number, list, or even a nested dictionary.
        state: The mutable dictionary representing the agent's current
               conversation state. This is typically provided by the agent
               framework.

    Returns:
        A dictionary confirming the successful update, including the key that
        was updated and the new value that was set.
    """
    state[key] = value
    return {"status": "success", "updated_key": key, "new_value": value}
