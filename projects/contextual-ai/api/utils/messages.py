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

"""Utility functions for formatting messages."""


def format_tool_code(code: str) -> str:
    """Formats code for display in a tool message."""
    return f"```python\n{code}\n```"


def format_tool_response(response: str) -> str:
    """Formats a tool response message."""
    return f"```json\n{response}\n```"


def format_tool_error(error: str) -> str:
    """Formats a tool error message."""
    return f"```error\n{error}\n```"


def format_tool_message(tool_name: str, tool_code: str) -> list[dict]:
    """Formats a message containing a tool call."""
    return [
        {
            "content": {
                "parts": [
                    {
                        "functionCall": {
                            "name": tool_name,
                            "args": {"code": tool_code},
                        }
                    }
                ]
            }
        }
    ]


def format_tool_result_message(tool_name: str, tool_result: str) -> list[dict]:
    """Formats a message containing the result of a tool call."""
    return [
        {
            "content": {
                "parts": [
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": {"result": tool_result},
                        }
                    }
                ]
            }
        }
    ]


def format_response_message(
    api_id: str,
    data_storage_id: str,
    data: list[dict],
    questions: list[str] = None,
) -> list[dict]:
    if questions is None:
        questions = []

    resp = [
        {
            "content": {
                "parts": [
                    {
                        "functionResponse": {
                            "id": "adk-0",
                            "name": "generate_final_response",
                            "data_storage_id": data_storage_id,
                            "response": {
                                "questions": questions,
                                "dataset": {
                                    "api_id": api_id,
                                    "dataset": data,
                                },
                            },
                        }
                    }
                ]
            }
        }
    ]
    return resp
