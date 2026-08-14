#  Copyright 2026 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Client interface for kubectl and gcloud cli tools."""

import json
import os
import select
import subprocess
import sys
from typing import Any, Dict, List, Optional

import config
from config import MigrationError

# Set the gcloud cli non-interactive mode
SANDBOX_ENV = os.environ.copy()
SANDBOX_ENV["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"


def run_command(
    cmd: List[str],
    input_data: Optional[str] = None,
    timeout: Optional[float] = 30.0,
) -> str:
    """Executes a CLI command in non-interactive mode and captures stdout.

    Args:
        cmd: A list of command arguments (e.g., ['kubectl', 'get', 'ingress']).
        input_data: Optional string data to pass to the command's stdin.
        timeout: Optional maximum duration in seconds before timing out.

    Returns:
        The stripped standard output of the executed command.

    Raises:
        MigrationError: If the command execution fails with a non-zero exit
            code or times out.
    """
    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            text=True,
            capture_output=True,
            env=SANDBOX_ENV,
            check=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired as e:
        raise MigrationError(
            f"Command {cmd} timed out after {timeout} seconds."
        ) from e
    except subprocess.CalledProcessError as e:
        raise MigrationError(f"Command failed: {e.stderr.strip()}") from e


def emit_ui_payload(
    step_name: str, prompt_type: str, data: Dict[str, Any]
) -> None:
    """Emits a structured JSON payload to stdout to trigger Agent UI widgets.

    Wraps the payload in special sentinel markers so that the agent frontend
    can intercept and render interactive UI elements during migration steps.

    Args:
        step_name: The identifier of the current migration step.
        prompt_type: The type of interactive UI widget or prompt to render.
        data: A dictionary containing the payload data for the UI widget.
    """
    payload = {
        "AGENT_UI_WIDGET_TRIGGER": True,
        "step": step_name,
        "promptType": prompt_type,
        "payload": data,
    }
    print(
        f"\n__AGENT_UI_DATA_START__\n"
        f"{json.dumps(payload, indent=2)}\n"
        f"__AGENT_UI_DATA_END__\n",
        flush=True,
    )


def get_ui_response(timeout: Optional[float] = None) -> Dict[str, Any]:
    """Reads and parses a single line of JSON input from stdin with timeout.

    Waits up to the specified timeout duration for input to become available.

    Args:
        timeout: Maximum duration in seconds to wait for input. If None,
            uses config.STDIN_TIMEOUT.

    Returns:
        A dictionary representing the parsed JSON response.

    Raises:
        MigrationError: If no input is received within the timeout period or
            decoding fails.
    """
    if timeout is None:
        timeout = config.STDIN_TIMEOUT
    if timeout is not None:
        ready, _, _ = select.select([0], [], [], timeout)
        if not ready:
            raise MigrationError(
                f"Timed out waiting for operator response on stdin after "
                f"{timeout} seconds."
            )

    raw_line = sys.stdin.readline().strip()
    if not raw_line:
        raise MigrationError("Received empty input from stdin.")

    try:
        return json.loads(raw_line)
    except json.JSONDecodeError as e:
        raise MigrationError(
            f"Failed to parse stdin payload as JSON: {e}. "
            f"Raw data: {raw_line}"
        ) from e
