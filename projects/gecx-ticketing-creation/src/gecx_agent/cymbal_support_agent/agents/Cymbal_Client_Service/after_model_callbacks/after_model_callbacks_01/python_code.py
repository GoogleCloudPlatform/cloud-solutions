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

"""After model callback to inject disclaimer."""

# pylint: skip-file

DISCLAIMER = "THIS CONVERSATION MAY BE RECORDED FOR LEGAL PURPOSES."


def after_model_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    if callback_context.variables.get("first_turn"):
        callback_context.variables["first_turn"] = False

        # Check if the agent's response already contains the disclaimer.
        # The agent might have produced it based on instructions.
        for part in callback_context.get_last_agent_output():
            if part.text and DISCLAIMER in part.text:
                return None

        # If the agent failed to produce the disclaimer, force it.
        return LlmResponse.from_parts(
            parts=[Part.from_text(DISCLAIMER), *llm_response.content.parts]
        )

    return None
