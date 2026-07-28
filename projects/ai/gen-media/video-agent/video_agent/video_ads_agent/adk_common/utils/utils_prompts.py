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

"""Utility functions for prompt handling."""

import inspect
import pathlib
import sys
import traceback


def load_prompt_file_from_calling_agent(
    variables_to_replace: dict[str, str] | None = None,
    filename: str | None = None,
) -> str:
    """Loads and formats a prompt file from caller's directory.

    Args:
        variables_to_replace: Placeholder replacement dictionary.
        filename: Optional prompt filename.

    Returns:
        Content of prompt file with placeholders replaced.

    Raises:
        FileNotFoundError: If prompt file not found in caller dir.
        ValueError: If loaded prompt is empty.
    """
    caller_frame = inspect.stack()[1]
    caller_filepath = pathlib.Path(caller_frame.filename)
    caller_dir = caller_filepath.parent
    filename = filename or "prompt.md"
    prompt = ""

    try:

        local_prompts_path = (caller_dir / filename).resolve()
        with open(local_prompts_path, "r", encoding="utf-8") as file:
            prompt = file.read()

        if not prompt:
            raise ValueError("Prompt is empty or could not be loaded.")

        modified_prompt = prompt
        if variables_to_replace:
            for key, value in variables_to_replace.items():
                if value is None:
                    raise ValueError(
                        f"Prompt value replacement for key '{key}' is empty."
                    )
                placeholder = "{{" + key + "}}"
                modified_prompt = modified_prompt.replace(
                    placeholder, str(value)
                )

        print(f"Prompt loaded correctly. Agent: {caller_filepath}.")
        return modified_prompt
    except FileNotFoundError as e:
        print(
            f"ERROR. Prompt file not found: {e}",
            file=sys.stderr,
        )
        traceback.print_exc()
        raise
    except ValueError as e:
        print(
            f"ERROR. ValueError loading prompt: {e}",
            file=sys.stderr,
        )
        traceback.print_exc()
        raise
    except Exception as e:
        print(
            f"ERROR. Loading prompt error: {e}",
            file=sys.stderr,
        )
        traceback.print_exc()
        raise
