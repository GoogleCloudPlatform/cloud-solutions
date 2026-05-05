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


# pylint: disable=C0114, C0301
import inspect
import pathlib
import sys
import traceback


def load_prompt_file_from_calling_agent(
    variables_to_replace: dict[str, str] | None = None,
    filename: str | None = None,
) -> str:
    """Loads and optionally formats a 'prompt.md' file from the calling agent's directory.

    This utility function is designed to be called by an agent to dynamically
    load its associated prompt file. It inspects the call stack to determine
    the caller's file path, constructs the path to 'prompt.md' relative to
    that caller, and if provided, replaces placeholders in the format `{{key}}`
    with values from the `variables_to_replace` dictionary.

    Args:
        variables_to_replace: An optional dictionary where keys are placeholder
            names (without curly braces) and values are the strings to
            substitute.

    Returns:
        The content of the 'prompt.md' file, with placeholders replaced if a
        dictionary was provided.

    Raises:
        FileNotFoundError: If 'prompt.md' is not found in the caller's directory.
        ValueError: If the loaded prompt is empty.
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
                    raise ValueError(f"Prompt value replacement for key '{key}' is empty.")
                placeholder = "{{" + key + "}}"
                modified_prompt = modified_prompt.replace(placeholder, str(value))

        print(f"Prompt loaded correctly. Agent: {caller_filepath}.")
        return modified_prompt
    except FileNotFoundError as e:
        print(
            f"ERROR. Prompt file not found. Agent: {caller_filepath}. Error: {e}",
            file=sys.stderr,
        )
        traceback.print_exc()
        raise
    except ValueError as e:
        print(
            f"ERROR. An error occurred while loading prompt. Agent: {caller_filepath}. Error: {e}",
            file=sys.stderr,
        )
        traceback.print_exc()
        raise
    except Exception as e:
        print(
            f"ERROR. An error occurred while loading prompt. Agent: {caller_filepath}. Error: {e}",
            file=sys.stderr,
        )
        traceback.print_exc()
        raise
