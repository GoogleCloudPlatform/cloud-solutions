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

"""Before model callback to handle session start."""

# pylint: skip-file


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    for part in callback_context.get_last_user_input():
        if part.text == "<event>session start</event>":
            response = LlmResponse.from_parts(
                [
                    Part.from_text(
                        "Hello, I'm the CX Assistant, your personal AI assistant."
                    )
                ]
            )
            response.partial = True
            return response
    return None
